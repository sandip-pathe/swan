"""Deterministic event producer. No model calls or order authority."""

from datetime import datetime, time

from services.core.contracts import IST
from services.market.history_refresh import HistoryError
from services.market.index_refresh import refresh_index_history


def watch_index(engine, account_id, now: datetime, calendar) -> dict:
    session = calendar.get("NFO", now.astimezone(IST).date())
    if session is None or not session.opens_at < now < session.closes_at:
        return {"status": "OUTSIDE_SESSION"}
    if now.astimezone(IST).time() >= time(11, 0):
        return {"status": "OUTSIDE_ORB_WINDOW"}
    try:
        return {"status": "UPDATED", **refresh_index_history(session.key, engine, account_id)}
    except HistoryError as error:
        return {"status": "UNAVAILABLE", "reason": error.detail}
