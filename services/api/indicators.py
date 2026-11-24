"""Read-only indicator tools over reconciled broker/observed candles."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from services.api.auth import account_identity
from services.api.candles import candles
from services.core.contracts import IST
from services.market.calendar import SessionCalendar
from services.market.indicators import indicator_series
from services.market.settings import MarketSettings

router = APIRouter()


@router.get("/api/market/indicators")
def indicators(
    request: Request, instrument_id: str, minutes: int = Query(1, ge=1, le=15),
    identifier: UUID = Depends(account_identity),
):
    now = datetime.now(UTC)
    calendar = SessionCalendar(MarketSettings().calendar_file, strict=False)
    session = calendar.get("NFO" if instrument_id.startswith("NFO:") else "BFO", now.astimezone(IST).date())
    if session is None or now < session.opens_at + timedelta(minutes=1):
        return {"status": "UNAVAILABLE", "reason": "NO_CURRENT_SESSION", "as_of": now.isoformat()}
    data = candles(request, instrument_id, session.opens_at, min(now, session.closes_at).replace(second=0, microsecond=0), "ONE_MINUTE", identifier)
    if minutes not in (1, 5, 15):
        from fastapi import HTTPException
        raise HTTPException(422, "UNSUPPORTED_TIMEFRAME")
    return {"instrument_id": instrument_id, "source": "/api/market/candles", **indicator_series(data, minutes)}
