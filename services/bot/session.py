"""Bound index collection to the cash session within verified exchange coverage."""

from datetime import datetime, time

from services.core.contracts import IST
from services.market.calendar import SessionCalendar


def market_context(calendar: SessionCalendar, now: datetime, venue: str = "NFO") -> dict:
    result = calendar.describe(venue, now)
    session = calendar.get(venue, now.astimezone(IST).date())
    if session:
        close = min(session.closes_at, datetime.combine(session.key, time(15, 30), IST))
        result = {
            **result,
            "closes_at": close.isoformat(),
            "state": "open" if session.opens_at <= now < close else "closed",
        }
    return {**result, "scope": f"index_cash_session_within_verified_{venue}_calendar"}
