"""Historical usage follows reservation dates without borrowing current policy."""

# ruff: noqa: F811
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_agent_usage import save, usage  # noqa: F401
from test_durable import durable  # noqa: F401
from test_instrument_search import client_for

from services.api import agent_usage as api
from services.core.contracts import IST
from services.core.models import Account, AuditEvent

pytestmark = pytest.mark.integration


def get(d, day):
    with client_for(d.engine, d.account) as client:
        return client.get("/api/paper/agent-usage", params={"day": day})


def test_historical_allowance_is_recorded_and_late_response_follows_request_day(usage, monkeypatch):
    d = usage
    stamp = d.clock.now - timedelta(days=1)
    first = save(
        d, "AI_RESERVATION", {"tokens": 200, "model": "old-model", "daily_allowance": 1000}, stamp
    )
    save(d, "AI_RESERVATION", {"tokens": 100, "model": "old-model", "daily_allowance": 1000}, stamp)
    save(d, "AI_OUTPUT", {"reservation_id": first, "usage": {"total_tokens": 75}})
    save(d, "AI_RESPONSE_USAGE", {"reservation_id": first, "usage": {"total_tokens": 75}})
    save(d, "AI_RESERVATION", {"tokens": 800, "model": "today", "daily_allowance": 9000})

    def no_current_settings():
        raise AssertionError("Historical view read current settings")

    monkeypatch.setattr(api, "AgentSettings", no_current_settings)
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
        count = db.scalar(select(func.count()).select_from(AuditEvent))
    result = get(d, stamp.astimezone(IST).date().isoformat()).json()
    assert result["day_ended"] and result["policy_source"] == "recorded"
    assert result["policy"] == {"model": None, "daily_allowance": 1000}
    assert result["reserved_allowance"] == 300 and result["remaining_allowance"] == 700
    assert result["reservation_count"] == 2 and result["reported_tokens"] == 75
    assert result["reported_calls"] == 1 and result["unknown_calls"] == 1
    assert result["models"] == [{"model": "old-model", "reservations": 2}]
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == revision
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == count


@pytest.mark.parametrize(
    "limits,source",
    [
        ([], "unrecorded"),
        ([None], "unrecorded"),
        ([1000, None], "unrecorded"),
        ([1000, 2000], "changed"),
        ([True], "unrecorded"),
    ],
)
def test_empty_legacy_invalid_and_changed_allowances_are_unknown(usage, limits, source):
    d = usage
    stamp = d.clock.now - timedelta(days=1)
    for limit in limits:
        save(d, "AI_RESERVATION", {"tokens": 100, "daily_allowance": limit}, stamp)
    result = get(d, stamp.astimezone(IST).date().isoformat()).json()
    assert result["policy_source"] == source and result["policy"] is None
    assert result["remaining_allowance"] is None
    assert result["reserved_allowance"] == 100 * len(limits)


def test_future_and_invalid_dates_rejected_and_ist_boundaries_preserved(usage):
    d = usage
    today = d.clock.now.astimezone(IST).date()
    assert get(d, (today + timedelta(days=1)).isoformat()).status_code == 422
    assert get(d, "not-a-date").status_code == 422
    result = get(d, today.isoformat()).json()
    assert not result["day_ended"] and result["policy_source"] == "current"
    assert result["policy"]["daily_allowance"] == 1000
