"""Run cursors remain scoped by owner, evaluation and collection."""

# ruff: noqa: F811
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_agent_run import save, slot
from test_durable import durable  # noqa: F401
from test_instrument_search import client_for

from services.core.models import Account, AuditEvent

pytestmark = pytest.mark.integration


def record(d, key, kind, index, owner=None, stamp=None):
    with Session(d.engine) as db, db.begin():
        row = AuditEvent(
            id=UUID(int=index),
            account_id=owner or d.account,
            kind=kind,
            timestamp=stamp or d.clock.now,
            details={
                "evaluation_id": str(key),
                "role": "analysis",
                "output": {
                    "outlook": "UNCERTAIN",
                    "rationale": str(index),
                    "evidence_ids": [],
                    "news_ids": [],
                    "concerns": [],
                },
                "stage": "analysis",
                "state": "PASSED",
                "reason": None,
            },
        )
        db.add(row)
        return str(row.id)


def test_tied_timestamps_page_independently_without_gaps_or_repeating_new_records(durable):
    d = durable
    key = slot(d)
    event = save(d, key, kind="AGENT_EVALUATION")
    outputs = [record(d, key, "AI_OUTPUT", index) for index in range(100, 145)]
    checks = [record(d, key, "AI_STAGE_CHECK", index) for index in range(200, 243)]
    with Session(d.engine) as db:
        count = db.scalar(select(func.count()).select_from(AuditEvent))
        revision = db.get(Account, d.account).revision
    with client_for(d.engine, d.account) as client:
        url = f"/api/paper/agent-activity/{event}/run"
        first = client.get(url).json()
        assert [row["id"] for row in first["rows"]] == list(reversed(outputs))[:20]
        assert [row["id"] for row in first["checks"]] == list(reversed(checks))[:20]
        new = record(d, key, "AI_OUTPUT", 999, stamp=d.clock.now + timedelta(seconds=1))
        for field, cursor, expected, param in (
            ("rows", "next_outputs_before", outputs, "outputs_before"),
            ("checks", "next_checks_before", checks, "checks_before"),
        ):
            result = first
            loaded = [row["id"] for row in result[field]]
            while result[cursor]:
                response = client.get(url, params={param: result[cursor]})
                assert response.status_code == 200, response.text
                result = response.json()
                loaded.extend(row["id"] for row in result[field])
            assert loaded == list(reversed(expected))
            assert len(loaded) == len(set(loaded))
        assert client.get(url).json()["rows"][0]["id"] == new
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == revision
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == count + 1


@pytest.mark.parametrize("case", ["kind", "run", "owner", "missing"])
def test_cursor_cannot_cross_collection_evaluation_or_owner(durable, case):
    d = durable
    key = slot(d)
    event = save(d, key, kind="AGENT_EVALUATION")
    owner = None
    cursor_key = key
    kind = "AI_OUTPUT"
    if case == "kind":
        kind = "AI_STAGE_CHECK"
    elif case == "run":
        # A distinct explicit evaluation identifier never matches the current run.
        cursor_key = uuid4()
    elif case == "owner":
        with Session(d.engine) as db, db.begin():
            other = Account(cash=0, config={})
            db.add(other)
            db.flush()
            owner = other.id
    cursor = record(d, cursor_key, kind, 500, owner) if case != "missing" else str(uuid4())
    with client_for(d.engine, d.account) as client:
        url = f"/api/paper/agent-activity/{event}/run"
        assert client.get(url, params={"outputs_before": cursor}).status_code == 400
        assert client.get(url, params={"checks_before": "invalid"}).status_code == 422
