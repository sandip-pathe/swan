"""Explicit NIFTY index-history acquisition and bounded as-of reads."""

import asyncio
from datetime import date, datetime, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.models import Account
from services.market.angelone import AngelOneClient
from services.market.index_history import IndexHistoryQuery
from services.market.index_history_store import read_index_history
from services.market.settings import MarketSettings

router = APIRouter()
INDEX_HISTORY_LOCK = 726230519846
REFRESH_COOLDOWN = timedelta(seconds=30)
ORB_CUTOFF = time(11, 0)


class IndexHistoryRefresh(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_key: date


async def fetch_index_history(query: IndexHistoryQuery):
    async with asyncio.timeout(80):
        client = AngelOneClient(MarketSettings())
        try:
            return await client.index_candles(query)
        finally:
            await client.close()


@router.post("/api/market/index-history/refresh")
def refresh_index_history(
    body: IndexHistoryRefresh,
    request: Request,
    identifier: UUID = Depends(account_identity),
):
    from services.market.history_refresh import HistoryError
    from services.market.index_refresh import refresh_index_history as refresh

    try:
        return refresh(body.session_key, request.app.state.engine, identifier, fetch_index_history)
    except HistoryError as error:
        raise HTTPException(error.status_code, error.detail) from None


@router.get("/api/market/index-history")
def cached_index_history(
    request: Request,
    session_key: date,
    start: datetime,
    end: datetime,
    as_of: datetime,
    limit: int = Query(default=400, ge=1, le=400),
    identifier: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        if db.get(Account, identifier) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        try:
            bars = read_index_history(
                db,
                session_key=session_key,
                start=start,
                end=end,
                as_of=as_of,
                limit=limit,
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        return {
            "session_key": session_key.isoformat(),
            "as_of": as_of.isoformat(),
            "bar_count": len(bars),
            "bars": [bar.model_dump(mode="json") for bar in bars],
            "provider_called": False,
        }
