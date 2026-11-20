"""Reservation allowance is separate from partial reported usage and billing."""

# ruff: noqa: F811
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_durable import durable  # noqa: F401
from test_instrument_search import client_for

from services.api import agent_usage as api
from services.core.contracts import IST
from services.core.models import Account, AuditEvent

pytestmark = pytest.mark.integration


def save(d, kind, details, stamp=None, owner=None):
    with Session(d.engine) as db, db.begin():
        row = AuditEvent(
            account_id=owner or d.account,
            kind=kind,
            details=details,
            timestamp=stamp or d.clock.now,
        )
        db.add(row)
        db.flush()
        return str(row.id)


def get(d):
    with client_for(d.engine, d.account) as client:
        response = client.get("/api/paper/agent-usage")
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
def usage(durable, monkeypatch):
    d = durable
    monkeypatch.setattr(api, "utc_now", lambda: d.clock.now)
    monkeypatch.setattr(
        api,
        "AgentSettings",
        lambda: SimpleNamespace(openai_model="configured-model", swan_ai_daily_token_budget=1000),
    )
    return d


def test_empty_and_owned_linked_usage_are_readonly(usage):
    d = usage
    empty = get(d)
    assert empty["reservation_count"] == empty["reported_tokens"] == 0
    assert empty["remaining_allowance"] == 1000
    assert empty["billing_cost"] is None
    first = save(d, "AI_RESERVATION", {"tokens": 600, "model": "older-model", "role": "analysis"})
    save(
        d,
        "AI_OUTPUT",
        {
            "reservation_id": first,
            "usage": {"total_tokens": 90},
            "response_id": "private-id",
            "output": {"secret": "not-for-report"},
        },
    )
    save(d, "AI_RESERVATION", {"tokens": 500, "model": "newer-model"})
    save(d, "AI_OUTPUT", {"reservation_id": str(uuid4()), "usage": {"total_tokens": 9999}})
    save(
        d, "AI_RESERVATION", {"tokens": 9999, "model": "yesterday"}, d.clock.now - timedelta(days=1)
    )
    with Session(d.engine) as db, db.begin():
        other = Account(cash=100, config={})
        db.add(other)
        db.flush()
        other_id = other.id
    save(d, "AI_RESERVATION", {"tokens": 8000, "model": "other-owner"}, owner=other_id)
    with Session(d.engine) as db:
        events = db.scalar(select(func.count()).select_from(AuditEvent))
        revision = db.get(Account, d.account).revision
    result = get(d)
    assert result["day"] == d.clock.now.astimezone(IST).date().isoformat()
    assert result["reserved_allowance"] == 1100 and result["remaining_allowance"] == 0
    assert result["reported_tokens"] == 90 and result["reported_calls"] == 1
    assert result["unknown_calls"] == 1 and result["reservation_count"] == 2
    assert len(result["models"]) == 2
    assert "private-id" not in str(result) and "not-for-report" not in str(result)
    with Session(d.engine) as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == events
        assert db.get(Account, d.account).revision == revision
    with client_for(d.engine, uuid4()) as client:
        assert client.get("/api/paper/agent-usage").status_code == 409


def test_duplicate_missing_invalid_usage_and_policy_are_unavailable(usage, monkeypatch):
    d = usage
    key = save(d, "AI_RESERVATION", {"tokens": 100, "model": "model"})
    for _ in range(2):
        save(d, "AI_OUTPUT", {"reservation_id": key, "usage": {"total_tokens": 20}})
    key = save(d, "AI_RESERVATION", {"tokens": True})
    save(d, "AI_OUTPUT", {"reservation_id": key, "usage": {"total_tokens": -1}})
    result = get(d)
    assert result["reserved_allowance"] is None and result["remaining_allowance"] is None
    assert result["reported_tokens"] == 0 and result["unknown_calls"] == 2

    def invalid():
        raise ValueError("private settings value")

    monkeypatch.setattr(api, "AgentSettings", invalid)
    result = get(d)
    assert result["policy"] is None
    assert "private settings value" not in str(result)


def test_day_boundary_uses_ist_not_utc(usage, monkeypatch):
    d = usage
    now = d.clock.now.astimezone(IST).replace(hour=0, minute=1)
    monkeypatch.setattr(api, "utc_now", lambda: now)
    save(d, "AI_RESERVATION", {"tokens": 200, "model": "today"}, now - timedelta(seconds=30))
    save(d, "AI_RESERVATION", {"tokens": 800, "model": "yesterday"}, now - timedelta(minutes=2))
    assert get(d)["reserved_allowance"] == 200
