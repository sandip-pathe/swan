from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.core.contracts import IST, ExchangeSession
from services.market.history_refresh import HistoryError
from services.worker import strategy_watch


@pytest.mark.integration
def test_shared_acquisition_persists_and_queues_eligible_setup_once(paper, db_engine, monkeypatch):
    from datetime import timedelta

    from services.core.models import AgentAssignment, IndexHistoryBatch
    from services.market import index_refresh
    from services.market.index_history import normalize_index_bars

    _, owner = paper
    now = datetime(2026, 11, 23, 9, 33, 20, tzinfo=IST)
    session = ExchangeSession(key=now.date(), opens_at=now.replace(hour=9, minute=15, second=0),
                              closes_at=now.replace(hour=15, minute=30, second=0),
                              verified=True, calendar_source="fixture")

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now

    async def fetch(query):
        rows = [[(session.opens_at + timedelta(minutes=i)).isoformat(),
                 100, 101.3 if i == 17 else 101, 99, 101.2 if i == 17 else 100, 0]
                for i in range(18)]
        return normalize_index_bars(rows, query, now, {"fromdate": "2026-11-23 09:15", "todate": "2026-11-23 09:33"})

    monkeypatch.setattr(index_refresh, "datetime", Clock)
    monkeypatch.setattr(index_refresh, "SessionCalendar", lambda *args, **kwargs: SimpleNamespace(get=lambda *args: session))
    result = index_refresh.refresh_index_history(now.date(), db_engine, owner, fetch)
    assert result["agent_assignment"]["state"] == "QUEUED"
    with pytest.raises(HistoryError, match="RATE_LIMIT"):
        index_refresh.refresh_index_history(now.date(), db_engine, owner, fetch)
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(IndexHistoryBatch)) == 1
        assert db.scalar(select(func.count()).select_from(AgentAssignment)) == 1


def test_code_watcher_only_fetches_in_strategy_window_and_preserves_errors(monkeypatch):
    now = datetime(2026, 11, 23, 9, 32, tzinfo=IST)
    session = ExchangeSession(key=now.date(), opens_at=now.replace(hour=9, minute=15),
                              closes_at=now.replace(hour=15, minute=30), verified=True,
                              calendar_source="fixture")
    calls = []

    def fetch(day, engine, account):
        calls.append(day)
        return {"watcher": {"emitted": False}}

    monkeypatch.setattr(strategy_watch, "refresh_index_history", fetch)
    calendar = SimpleNamespace(get=lambda *args: session)
    assert strategy_watch.watch_index(None, None, now, calendar)["status"] == "UPDATED"
    assert strategy_watch.watch_index(None, None, now.replace(hour=12), calendar)["status"] == "OUTSIDE_ORB_WINDOW"
    assert len(calls) == 1

    def busy(*args):
        raise HistoryError(429, "INDEX_HISTORY_REFRESH_RATE_LIMIT")

    monkeypatch.setattr(strategy_watch, "refresh_index_history", busy)
    assert strategy_watch.watch_index(None, None, now, calendar)["reason"] == "INDEX_HISTORY_REFRESH_RATE_LIMIT"
