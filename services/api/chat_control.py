"""The single explicitly permitted chat mutation; never an order endpoint."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from services.api.auth import account_identity
from services.core.contracts import IST
from services.market.calendar import SessionCalendar
from services.market.settings import MarketSettings
from services.paper.session_stop import stop_session_entries

router = APIRouter()


class SessionStopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


@router.post("/api/chat/stop-trading-today")
def stop_trading_today(
    body: SessionStopRequest, request: Request, owner: UUID = Depends(account_identity),
):
    now = datetime.now(UTC)
    calendar = SessionCalendar(MarketSettings().calendar_file, strict=False)
    session = calendar.get("NFO", now.astimezone(IST).date())
    if session is None:
        raise HTTPException(409, "VERIFIED_OPEN_SESSION_REQUIRED")
    try:
        return stop_session_entries(request.app.state.engine, owner, body.request_id, session, now)
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
