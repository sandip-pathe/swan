"""Explicit provider backfill and cached reads. Neither endpoint enables entries."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import IST, Instrument
from services.core.models import Account, InstrumentRecord, MarketHistoryBatch
from services.market.angelone import AngelOneClient
from services.market.history import SOURCE, HistoryQuery, Interval
from services.market.settings import MarketSettings, ProviderError

router = APIRouter()
HISTORY_LOCK = 726230519843


def owner(db: Session, identifier: UUID) -> None:
    if db.get(Account, identifier) is None:
        raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")


def view(batch: MarketHistoryBatch) -> dict:
    return {
        "id": str(batch.id),
        "request": batch.request,
        "requested_at": batch.requested_at.isoformat(),
        **batch.payload,
    }


@router.get("/api/market/history")
def cached_history(
    request: Request,
    instrument_id: str,
    interval: Interval,
    identifier: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        owner(db, identifier)
        batch = db.scalar(
            select(MarketHistoryBatch)
            .where(
                MarketHistoryBatch.account_id == identifier,
                MarketHistoryBatch.instrument_id == instrument_id,
                MarketHistoryBatch.request["interval"].as_string() == interval,
            )
            .order_by(MarketHistoryBatch.requested_at.desc())
            .limit(1)
        )
        return {"batch": view(batch) if batch else None, "provider_called": False}


async def fetch(query: HistoryQuery, instrument: Instrument, now: datetime) -> dict:
    client = AngelOneClient(MarketSettings())
    try:
        return await client.candles(query, instrument, now)
    finally:
        await client.close()


@router.post("/api/market/history/refresh")
def refresh_history(
    body: HistoryQuery,
    request: Request,
    identifier: UUID = Depends(account_identity),
):
    now = datetime.now(UTC)
    problem = None
    with Session(request.app.state.engine) as db, db.begin():
        owner(db, identifier)
        # One bounded backfill across all local API processes/accounts. Busy is immediate.
        if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": HISTORY_LOCK}):
            raise HTTPException(429, "HISTORY_REFRESH_BUSY")
        latest = db.scalar(
            select(MarketHistoryBatch).order_by(MarketHistoryBatch.requested_at.desc()).limit(1)
        )
        if latest and now - latest.requested_at < timedelta(seconds=5):
            raise HTTPException(429, "HISTORY_REFRESH_RATE_LIMIT")
        record = db.get(InstrumentRecord, body.instrument_id)
        if record is None:
            raise HTTPException(404, "HISTORY_INSTRUMENT_NOT_FOUND")
        try:
            instrument = Instrument.model_validate(record.payload)
            body.provider_body(instrument, now)
            if (
                instrument.verified_at.astimezone(IST).date() != now.astimezone(IST).date()
                or instrument.expiry < now.astimezone(IST).date()
            ):
                raise ProviderError("HISTORY_CURRENT_METADATA_REQUIRED")
        except (ValueError, ProviderError):
            raise HTTPException(422, "HISTORY_UNSUPPORTED_INSTRUMENT_OR_RANGE") from None
        batch = MarketHistoryBatch(
            account_id=identifier,
            instrument_id=instrument.id,
            requested_at=now,
            request=body.model_dump(mode="json"),
            payload={},
        )
        db.add(batch)
        try:
            payload = asyncio.run(fetch(body, instrument, now))
            batch.payload = {
                "status": "available" if payload["bars"] else "empty",
                "source": SOURCE,
                "instrument": instrument.model_dump(mode="json"),
                "timezone": "Asia/Kolkata",
                "alignment": "provider_opening_timestamp",
                "finality": "elapsed_interval_only_not_provider_confirmation",
                "coverage": "returned_bars_only_missing_intervals_are_gaps",
                **jsonable_encoder(payload, custom_encoder={Decimal: str}),
            }
        except ProviderError as error:
            # Persist failures for throttling and honest availability, never raw provider bodies.
            problem = str(error)
            batch.payload = {"status": "unavailable", "source": SOURCE, "problem": problem}
        db.flush()
        result = view(batch)
    if problem:
        raise HTTPException(409, {"code": problem, "batch_id": result["id"]})
    return {"batch": result, "provider_called": True}
