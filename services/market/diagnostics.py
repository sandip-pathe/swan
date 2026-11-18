"""Explicit bounded connection tests. Never invoked by workspace polling."""

import asyncio
import json
import re
import ssl
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from services.agents.news import NewsReader
from services.agents.provider import StructuredProvider
from services.agents.settings import AgentSettings
from services.core.contracts import IST
from services.core.models import Account, AuditEvent
from services.market.angelone import AngelOneClient
from services.market.catalog import EXCHANGE_TYPES, InstrumentCatalog
from services.market.readiness import connection_fingerprint
from services.market.settings import MarketSettings, ProviderError
from services.market.stream import STREAM_URL, decode_quote

NAMES = ("broker", "catalog", "stream", "ai", "ai_schema", "news")


class ConnectionProof(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


def evidence_context(db: Session, account_id: UUID) -> dict:
    events = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.account_id == account_id,
            AuditEvent.kind == "CONNECTION_CHECK",
        )
        .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
        .limit(100)
    )
    evidence: dict[str, dict] = {}
    for event in events:
        evidence.setdefault(event.details["name"], event.details)
    review = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.account_id == account_id, AuditEvent.kind == "RISK_POLICY_REVIEWED")
        .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    risk_review = review.details.get("policy_digest") if review else None
    return {"evidence": evidence, "risk_review": risk_review}


async def probe(name: str) -> dict:
    if name == "ai":
        settings = AgentSettings()
        if not settings.openai_api_key.get_secret_value():
            raise ProviderError("AI_KEY_NOT_CONFIGURED")
        async with httpx.AsyncClient(
            timeout=20, follow_redirects=False, trust_env=False
        ) as http_client:
            response = await http_client.get(
                "https://api.openai.com/v1/models",
                headers={
                    "Authorization": "Bearer " + settings.openai_api_key.get_secret_value(),
                },
            )
        if response.status_code != 200:
            raise ProviderError("AI_HTTP_" + str(response.status_code))
        if len(response.content) > 1000000:
            raise ProviderError("AI_RESPONSE_TOO_LARGE")
        body = response.json()
        models = sorted(
            {
                row["id"]
                for row in body["data"]
                if isinstance(row.get("id"), str)
                and re.fullmatch(r"[a-zA-Z0-9._:-]{1,150}", row["id"])
            }
        )
        if settings.openai_model and settings.openai_model not in models:
            raise ProviderError("AI_MODEL_NOT_ACCESSIBLE")
        return {
            "status": "passed",
            "detail": "OpenAI authentication verified"
            + (
                " and configured model is listed."
                if settings.openai_model
                else "; select a model and budget."
            )
            + " No generation requested. This model-list test does not verify structured output.",
            "models": models,
        }
    if name == "news":
        settings = AgentSettings()
        items = await NewsReader(settings.swan_news_config, settings.news_api_key).read()
        delayed = any(item.provider_delay_seconds for item in items)
        return {
            "status": "passed",
            "detail": f"Retrieved {len(items)} attributed headlines published within 24 hours. "
            + (
                "NewsData.io free plan has a 12-hour delay; this is background context, not live news. "
                if delayed
                else ""
            )
            + "This does not establish comprehensive market coverage.",
        }
    if name == "catalog":
        catalog = await InstrumentCatalog.fetch()
        day = datetime.now(UTC).astimezone(IST).date()
        counts = {
            venue: sum(
                item.exchange == venue and day <= item.expiry <= day + timedelta(days=7)
                for item in catalog.instruments.values()
            )
            for venue in ("NFO", "BFO")
        }
        if not all(counts.values()):
            raise ProviderError("ELIGIBLE_NFO_BFO_CONTRACTS_REQUIRED")
        return {
            "status": "passed",
            "detail": "Actual eligible contracts retrieved: "
            + ", ".join(f"{key} {value}" for key, value in counts.items())
            + ". Provider quantity semantics still require validation.",
        }
    client = AngelOneClient(MarketSettings())
    try:
        if name == "broker":
            await client.verify_session()
            return {
                "status": "passed",
                "detail": "Broker authentication and account match verified. "
                "No broker orders placed; quote freshness not checked.",
            }
        session = await client.session()
        catalog = await InstrumentCatalog.fetch()
        now = datetime.now(UTC)
        day = now.astimezone(IST).date()
        selected = []
        for venue in ("NFO", "BFO"):
            candidates = [
                item
                for item in catalog.instruments.values()
                if item.exchange == venue and day <= item.expiry <= day + timedelta(days=7)
            ]
            if not candidates:
                raise ProviderError("ELIGIBLE_NFO_BFO_CONTRACTS_REQUIRED")
            selected.append(min(candidates, key=lambda item: (item.expiry, item.id)))
        lookup = {(EXCHANGE_TYPES[item.exchange], item.provider_token): item for item in selected}
        headers = {
            "Authorization": session.jwt.get_secret_value(),
            "x-api-key": client.settings.api_key.get_secret_value(),
            "x-client-code": client.settings.client_code.get_secret_value(),
            "x-feed-token": session.feed.get_secret_value(),
        }
        async with connect(
            STREAM_URL,
            additional_headers=headers,
            ssl=ssl.create_default_context(),
            open_timeout=15,
            close_timeout=3,
            max_size=65536,
            ping_interval=None,
        ) as socket:
            await socket.send(
                json.dumps(
                    {
                        "correlationID": "swandiagnostic",
                        "action": 1,
                        "params": {
                            "mode": 3,
                            "tokenList": [
                                {"exchangeType": venue, "tokens": [token]}
                                for venue, token in lookup
                            ],
                        },
                    }
                )
            )
            await socket.send("ping")
            async with asyncio.timeout(12):
                while True:
                    packet = await socket.recv()
                    if packet in ("pong", b"pong"):
                        return {
                            "status": "passed",
                            "detail": "Stream transport authenticated and heartbeat received. "
                            "Subscription acceptance and fresh depth remain market-session checks.",
                        }
                    if not isinstance(packet, bytes):
                        raise ProviderError("STREAM_SUBSCRIPTION_REJECTED")
                    quote = decode_quote(packet, lookup, datetime.now(UTC))
                    if quote:
                        return {
                            "status": "passed",
                            "detail": "Stream authenticated and an actual quote decoded. "
                            "Both venues and admission-time depth freshness still need validation.",
                        }
    finally:
        await client.close()


def run_diagnostic(engine: Engine, account_id: UUID, name: str) -> dict:
    if name not in NAMES:
        raise ValueError("UNKNOWN_CONNECTION_CHECK")
    # A session advisory lock prevents overlapping checks, including across processes.
    key = int.from_bytes(uuid5(NAMESPACE_URL, f"swan-diagnostic:{account_id}").bytes[:8], "big") & (
        (1 << 63) - 1
    )
    with engine.connect() as lease:
        if not lease.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}):
            lease.rollback()
            raise ValueError("CONNECTION_CHECK_ALREADY_RUNNING")
        lease.commit()
        try:
            with Session(engine) as db:
                if db.get(Account, account_id) is None:
                    raise ValueError("PAPER_ACCOUNT_NOT_CONFIGURED")
                previous = evidence_context(db, account_id)["evidence"].get(name)
            now = datetime.now(UTC)
            try:
                fingerprint = connection_fingerprint(name)
            except (ValueError, OSError):
                fingerprint = "invalid-configuration"
            if (
                previous
                and previous.get("fingerprint") == fingerprint
                and (
                    timedelta(0)
                    <= now - datetime.fromisoformat(previous["checked_at"])
                    < timedelta(seconds=30)
                )
            ):
                return {k: v for k, v in previous.items() if k != "fingerprint"}

            async def bounded():
                async with asyncio.timeout(80):
                    if name == "ai_schema":
                        settings = AgentSettings()
                        if not settings.ready():
                            raise ProviderError("AI_NOT_CONFIGURED")
                        settings.swan_ai_max_output_tokens = min(
                            settings.swan_ai_max_output_tokens, 1024
                        )
                        result = await StructuredProvider(engine, account_id, settings).generate(
                            "connection",
                            {
                                "purpose": "API schema connection test only. No market analysis or strategy.",
                                "instruction": "Return ok true to acknowledge this connection test.",
                            },
                            ConnectionProof,
                        )
                        if not result.ok:
                            raise ProviderError("AI_SCHEMA_CHECK_FAILED")
                        return {
                            "status": "passed",
                            "detail": "Configured model returned a valid strict structured response. "
                            "This test used the account token budget and made no trading decision.",
                        }
                    return await probe(name)

            try:
                result = asyncio.run(bounded())
            except ProviderError as error:
                code = str(error).split(":", 1)[0]
                code = code if re.fullmatch(r"[A-Z0-9_]{1,100}", code) else "PROVIDER_CHECK_FAILED"
                result = {"status": "failed", "detail": code.replace("_", " ").capitalize() + "."}
            except (TimeoutError, httpx.HTTPError, OSError, WebSocketException):
                result = {
                    "status": "failed",
                    "detail": "Connection unavailable or timed out. Retry after checking login and network access.",
                }
            except (ValueError, KeyError, TypeError):
                result = {
                    "status": "failed",
                    "detail": "Configuration or provider response is invalid. Correct the settings and retry.",
                }
            # Authentication refresh may replace the saved session during a successful probe.
            try:
                fingerprint = connection_fingerprint(name)
            except (ValueError, OSError):
                pass
            result = {
                **result,
                "name": name,
                "checked_at": datetime.now(UTC).isoformat(),
                "fingerprint": fingerprint,
            }
            with Session(engine) as db, db.begin():
                db.add(
                    AuditEvent(
                        account_id=account_id,
                        kind="CONNECTION_CHECK",
                        timestamp=datetime.now(UTC),
                        details=result,
                    )
                )
            return {k: v for k, v in result.items() if k != "fingerprint"}
        finally:
            lease.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            lease.commit()
