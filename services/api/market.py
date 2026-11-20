"""Deliberate bounded quote refresh, including last available prices after hours."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.api.instruments import persist_listing
from services.core.contracts import Instrument, Quote
from services.core.models import Account, AuditEvent
from services.market.analysis import normalize_rest_quote
from services.market.angelone import AngelOneClient
from services.market.catalog import InstrumentCatalog
from services.market.references import IndexReference, normalize_reference, save_reference
from services.market.selection import display_contracts
from services.market.settings import AuthenticationRequired, MarketSettings, ProviderError
from services.paper.engine import PaperEngine
from services.worker.models import LatestMarketQuote

router = APIRouter()
QUOTE_REFRESH_LOCK = 726230519844


class QuoteRefresh(BaseModel):
    model_config = ConfigDict(extra="forbid")
    underlying: Literal["NIFTY", "SENSEX"]


class SelectedQuoteRefresh(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument_ids: list[str] = Field(min_length=1, max_length=50)


async def fetch_selected_quotes(instruments: list[Instrument]) -> list[Quote]:
    """Fetch only requested identities; never infer them from an index price."""
    async with asyncio.timeout(80):
        client = AngelOneClient(MarketSettings())
        try:
            tokens: dict[str, list[str]] = {}
            lookup = {(item.exchange, item.provider_token): item for item in instruments}
            if len(lookup) != len(instruments):
                raise ProviderError("INVALID_DISPLAY_CONTRACTS")
            for instrument in instruments:
                tokens.setdefault(instrument.exchange, []).append(instrument.provider_token)
            rows = await client.quotes(tokens)
            quotes = []
            seen = set()
            for row in rows:
                if not isinstance(row, dict):
                    raise ProviderError("INVALID_QUOTE_RESPONSE")
                key = (
                    str(row.get("exchange", "")),
                    str(row.get("symbolToken", row.get("symboltoken"))),
                )
                item = lookup.get(key)
                if item is None or key in seen:
                    raise ProviderError("UNEXPECTED_QUOTE_CONTRACT")
                seen.add(key)
                quote = normalize_rest_quote(row, item, datetime.now(UTC))
                if quote.timestamp > quote.received_at:
                    raise ProviderError("INVALID_QUOTE_TIMESTAMP")
                quotes.append(quote)
            return quotes
        finally:
            await client.close()


async def fetch_quotes(underlying: str) -> tuple[list[Instrument], list[Quote], IndexReference]:
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
            now = datetime.now(UTC)
            reference = normalize_reference(matches[0], underlying, token, now)
            spot = reference.last_price
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
            return instruments, quotes, reference
        finally:
            await client.close()


@router.post("/api/market/quotes/refresh")
def refresh_quotes(
    body: QuoteRefresh, request: Request, identifier: UUID = Depends(account_identity)
):
    return perform_refresh(body, request, identifier)


@router.post("/api/market/quotes/selected/refresh")
def refresh_selected_quotes(
    body: SelectedQuoteRefresh, request: Request, identifier: UUID = Depends(account_identity)
):
    if len(set(body.instrument_ids)) != len(body.instrument_ids):
        raise HTTPException(422, "DUPLICATE_INSTRUMENTS")
    return perform_refresh(body, request, identifier)


def perform_refresh(body: QuoteRefresh | SelectedQuoteRefresh, request: Request, identifier: UUID):
    now = datetime.now(UTC)
    scope = (
        {"underlying": body.underlying}
        if isinstance(body, QuoteRefresh)
        else {"instrument_ids": body.instrument_ids}
    )
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
        selected_items = (
            [persist_listing(db, item) for item in body.instrument_ids]
            if isinstance(body, SelectedQuoteRefresh)
            else None
        )
        try:
            if selected_items is not None:
                instruments = selected_items
                quotes = asyncio.run(fetch_selected_quotes(instruments))
                reference = None
            else:
                assert isinstance(body, QuoteRefresh)
                instruments, quotes, reference = asyncio.run(fetch_quotes(body.underlying))
            if reference is not None:
                save_reference(db, reference)
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
                **scope,
                "contracts": len(instruments),
                "quotes": len(quotes),
                "reference_at": reference.timestamp.isoformat() if reference else None,
                "missing_instrument_ids": sorted(
                    {item.id for item in instruments} - {q.instrument_id for q in quotes}
                ),
                "fresh_quotes": sum(
                    0 <= (datetime.now(UTC) - q.timestamp).total_seconds() <= 10 for q in quotes
                ),
                "newest_exchange_at": max((q.timestamp.isoformat() for q in quotes), default=None),
                "received_at": datetime.now(UTC).isoformat(),
                "source": "angelone-rest:full",
                "coverage": "selected_contracts"
                if selected_items is not None
                else "nearest_expiry_up_to_five_strikes",
                "price_status": "last_available_observations_not_proof_of_live_feed",
            }
        except AuthenticationRequired:
            failed = True
            failure_code = "BROKER_LOGIN_REQUIRED"
            result = {
                "status": "unavailable",
                **scope,
                "problem": failure_code,
            }
        except (ProviderError, ValueError, TypeError, KeyError, OSError, TimeoutError):
            failed = True
            result = {"status": "unavailable", **scope}
        db.add(
            AuditEvent(
                account_id=identifier, kind="MARKET_QUOTES_REFRESHED", timestamp=now, details=result
            )
        )
    if failed:
        raise HTTPException(409, failure_code)
    return result
