"""Owned model-request paging preserves unknown response metadata."""

# ruff: noqa: F811
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session
from test_agent_run import save, slot
from test_durable import durable  # noqa: F401
from test_instrument_search import client_for

from services.core.models import Account, AuditEvent

pytestmark = pytest.mark.integration


def test_models_page_tied_requests_independently_and_reject_unscoped_cursors(durable):
    d = durable
    key = slot(d)
    root = save(d, key, kind="AGENT_EVALUATION")
    with Session(d.engine) as db, db.begin():
        foreign = uuid4()
        db.add(Account(id=foreign, enabled=False, cash=0, config={}))
        db.flush()
        for i in range(45):
            db.add(
                AuditEvent(
                    id=UUID(int=100 + i),
                    account_id=d.account,
                    kind="AI_RESERVATION",
                    timestamp=d.clock.now,
                    details={
                        "role": "analysis",
                        "request": {"evaluation_id": str(key), "model": str(i)},
                    },
                )
            )
        for i, owner, kind, details in [
            (1, foreign, "AI_RESERVATION", {"request": {"evaluation_id": str(key)}}),
            (2, d.account, "AI_RESERVATION", {"request": {"evaluation_id": str(uuid4())}}),
            (3, d.account, "AI_OUTPUT", {"request": {"evaluation_id": str(key)}}),
            (4, d.account, "AI_RESERVATION", {"request": None}),
        ]:
            db.add(
                AuditEvent(
                    id=UUID(int=i),
                    account_id=owner,
                    kind=kind,
                    timestamp=d.clock.now,
                    details=details,
                )
            )
    with client_for(d.engine, d.account) as client:
        url = f"/api/paper/agent-activity/{root}/run"
        response = client.get(url).json()
        expected = [str(UUID(int=i)) for i in reversed(range(100, 145))]
        found = []
        while True:
            versions = response["versions"]
            found.extend(row["id"] for row in versions["rows"])
            assert all(row["reported_model"] is None for row in versions["rows"])
            if not versions["next_before"]:
                assert not versions["truncated"]
                break
            response = client.get(url, params={"versions_before": versions["next_before"]}).json()
            assert response["rows"] == []
            assert response["checks"] == []
        assert found == expected
        for cursor in [UUID(int=i) for i in [1, 2, 3, 4, 999]]:
            assert client.get(url, params={"versions_before": str(cursor)}).status_code == 400
        assert client.get(url, params={"versions_before": "invalid"}).status_code == 422


def test_output_overflow_does_not_masquerade_as_more_model_pages(durable):
    d = durable
    key = slot(d)
    root = save(d, key, kind="AGENT_EVALUATION")
    reservation = uuid4()
    with Session(d.engine) as db, db.begin():
        db.add(
            AuditEvent(
                id=reservation,
                account_id=d.account,
                kind="AI_RESERVATION",
                timestamp=d.clock.now,
                details={"request": {"evaluation_id": str(key)}},
            )
        )
        for _ in range(201):
            db.add(
                AuditEvent(
                    account_id=d.account,
                    kind="AI_OUTPUT",
                    timestamp=d.clock.now,
                    details={"evaluation_id": str(key), "reservation_id": str(reservation)},
                )
            )
    with client_for(d.engine, d.account) as client:
        versions = client.get(f"/api/paper/agent-activity/{root}/run").json()["versions"]
        assert versions["next_before"] is None
        assert not versions["truncated"]
        assert versions["outputs_incomplete"]
        assert versions["rows"][0]["reported_model"] is None
