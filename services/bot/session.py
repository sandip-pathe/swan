"""Bound index collection to the cash session within verified exchange coverage."""

from datetime import datetime, time

from services.core.contracts import IST
from services.market.calendar import SessionCalendar


def market_context(calendar: SessionCalendar, now: datetime) -> dict:
    result = calendar.describe("NFO", now)
    session = calendar.get("NFO", now.astimezone(IST).date())
    if session:
        close = min(session.closes_at, datetime.combine(session.key, time(15, 30), IST))
        result = {**result, "closes_at": close.isoformat(),
                  "state": "open" if session.opens_at <= now < close else "closed"}
    return {**result, "scope": "index_cash_session_within_verified_NFO_calendar"}
