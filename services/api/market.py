"""Deliberate bounded quote refresh, including last available prices after hours."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import Instrument, Quote
from services.core.models import Account, AuditEvent
from services.market.analysis import normalize_rest_quote, provider_price, provider_time
from services.market.angelone import AngelOneClient
from services.market.catalog import InstrumentCatalog
from services.market.selection import display_contracts
from services.market.settings import AuthenticationRequired, MarketSettings, ProviderError
from services.paper.engine import PaperEngine
from services.worker.models import LatestMarketQuote

router = APIRouter()
QUOTE_REFRESH_LOCK = 726230519844


class QuoteRefresh(BaseModel):
    model_config = ConfigDict(extra="forbid")
    underlying: Literal["NIFTY", "SENSEX"]


async def fetch_quotes(underlying: str) -> tuple[list[Instrument], list[Quote], datetime]:
    async with asyncio.timeout(80):
        settings = MarketSettings()
        catalog = await InstrumentCatalog.fetch()
        exchange, token = (
            ("NSE", settings.nifty_index_token)
            if underlying == "NIFTY"
            else ("BSE", settings.sensex_index_token)
        )
        if not token:
            raise ProviderError("INDEX_REFERENCE_NOT_CONFIGURED")
        client = AngelOneClient(settings)
        try:
            references = await client.quotes({exchange: [token]})
            if any(not isinstance(row, dict) for row in references):
                raise ProviderError("INDEX_REFERENCE_UNAVAILABLE")
            matches = [
                row
                for row in references
                if row.get("exchange") == exchange
                and str(row.get("symbolToken", row.get("symboltoken"))) == token
            ]
            if len(matches) != 1 or not matches[0].get("exchFeedTime"):
                raise ProviderError("INDEX_REFERENCE_UNAVAILABLE")
            spot = provider_price(matches[0].get("ltp"))
            reference_at = provider_time(matches[0]["exchFeedTime"])
            now = datetime.now(UTC)
            if spot is None or reference_at > now:
                raise ProviderError("INDEX_REFERENCE_UNAVAILABLE")
            instruments = display_contracts(catalog, underlying, spot, now)
            venue = instruments[0].exchange
            lookup = {item.provider_token: item for item in instruments}
            if len(lookup) != len(instruments) or len(instruments) > 10:
                raise ProviderError("INVALID_DISPLAY_CONTRACTS")
            rows = await client.quotes({venue: list(lookup)})
            quotes = []
            seen = set()
            for row in rows:
                if not isinstance(row, dict):
                    raise ProviderError("INVALID_QUOTE_RESPONSE")
                provider_token = str(row.get("symbolToken", row.get("symboltoken")))
                instrument = lookup.get(provider_token)
                if instrument is None or provider_token in seen:
                    raise ProviderError("UNEXPECTED_QUOTE_CONTRACT")
                seen.add(provider_token)
                quote = normalize_rest_quote(row, instrument, datetime.now(UTC))
                if quote.timestamp > quote.received_at:
                    raise ProviderError("INVALID_QUOTE_TIMESTAMP")
                quotes.append(quote)
            return instruments, quotes, reference_at
        finally:
            await client.close()


@router.post("/api/market/quotes/refresh")
def refresh_quotes(
    body: QuoteRefresh, request: Request, identifier: UUID = Depends(account_identity)
):
    now = datetime.now(UTC)
    failed = False
    failure_code = "MARKET_PRICES_UNAVAILABLE"
    with Session(request.app.state.engine) as db, db.begin():
        if db.get(Account, identifier) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        if not db.scalar(
            text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": QUOTE_REFRESH_LOCK}
        ):
            raise HTTPException(429, "QUOTE_REFRESH_BUSY")
        previous = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.kind == "MARKET_QUOTES_REFRESHED")
            .order_by(AuditEvent.timestamp.desc())
            .limit(1)
        )
        if previous and now - previous.timestamp < timedelta(seconds=30):
            raise HTTPException(429, "QUOTE_REFRESH_RATE_LIMIT")
        try:
            instruments, quotes, reference_at = asyncio.run(fetch_quotes(body.underlying))
            for instrument in instruments:
                PaperEngine._persist_instrument(db, instrument)
            if quotes:
                statement = insert(LatestMarketQuote).values(
                    [
                        {
                            "instrument_id": q.instrument_id,
                            "timestamp": q.timestamp,
                            "payload": q.model_dump(mode="json"),
                        }
                        for q in quotes
                    ]
                )
                db.execute(
                    statement.on_conflict_do_update(
                        index_elements=[LatestMarketQuote.instrument_id],
                        set_={
                            "timestamp": statement.excluded.timestamp,
                            "payload": statement.excluded.payload,
                        },
                        where=LatestMarketQuote.timestamp <= statement.excluded.timestamp,
                    )
                )
            result = {
                "status": "available" if quotes else "empty",
                "underlying": body.underlying,
                "contracts": len(instruments),
                "quotes": len(quotes),
                "reference_at": reference_at.isoformat(),
                "received_at": datetime.now(UTC).isoformat(),
                "source": "angelone-rest:full",
                "coverage": "nearest_expiry_up_to_five_strikes",
                "price_status": "last_available_observations_not_proof_of_live_feed",
            }
        except AuthenticationRequired:
            failed = True
            failure_code = "BROKER_LOGIN_REQUIRED"
            result = {
                "status": "unavailable",
                "underlying": body.underlying,
                "problem": failure_code,
            }
        except (ProviderError, ValueError, TypeError, KeyError, OSError, TimeoutError):
            failed = True
            result = {"status": "unavailable", "underlying": body.underlying}
        db.add(
            AuditEvent(
                account_id=identifier, kind="MARKET_QUOTES_REFRESHED", timestamp=now, details=result
            )
        )
    if failed:
        raise HTTPException(409, failure_code)
    return result
