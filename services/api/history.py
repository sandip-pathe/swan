"""Explicit provider backfill and cached reads. Neither endpoint enables entries."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import Instrument
from services.core.models import Account, MarketHistoryBatch
from services.market.angelone import AngelOneClient
from services.market.history import HistoryQuery, Interval
from services.market.history_refresh import HistoryError
from services.market.history_refresh import refresh_history as refresh_data
from services.market.settings import MarketSettings

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
    try:
        return refresh_data(body, request.app.state.engine, identifier, fetch)
    except HistoryError as error:
        raise HTTPException(error.status_code, error.detail) from None
