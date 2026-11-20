"""Agent activity exposes recorded stages without fabricating correlation or approval."""

# ruff: noqa: F811
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_durable import admit, durable  # noqa: F401
from test_instrument_search import client_for

from services.core.models import Account, AuditEvent, DecisionRecord, PaperOrder

pytestmark = pytest.mark.integration


def save(d, kind, details):
    with Session(d.engine) as db, db.begin():
        event = AuditEvent(account_id=d.account, kind=kind, timestamp=d.clock.now, details=details)
        db.add(event)
        db.flush()
        return event.id


def get(d, **params):
    with client_for(d.engine, d.account) as client:
        response = client.get("/api/paper/agent-activity", params=params)
        assert response.status_code == 200, response.text
        return response.json()


def test_real_risk_approval_links_actual_owned_order_readonly(durable):
    d = durable
    order_id = admit(d)
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
    result = get(d, category="risk")
    row = result["rows"][0]
    assert row["stage"] == "risk" and row["state"] == "ready"
    assert row["order"]["id"] == str(order_id) and row["order"]["status"] == "OPEN"
    assert row["order"]["filled_quantity"] == 0
    assert row["risk"]["quantity"] > 0 and row["instrument"]["underlying"]
    assert "approval" not in row and "request_payload" not in str(result)
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == revision
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 1


def test_wait_review_failure_and_unspecified_outcomes_are_distinct(durable):
    d = durable
    save(
        d,
        "AI_OUTPUT",
        {
            "role": "proposal",
            "output": {
                "action": "WAIT",
                "instrument_id": None,
                "min_entry": None,
                "max_entry": None,
                "stop_loss": None,
                "target": None,
                "rationale": "Evidence was inconclusive.",
                "evidence_ids": ["observation"],
            },
            "private_config": "DO_NOT_EXPOSE",
            "response_id": "DO_NOT_EXPOSE",
        },
    )
    save(
        d,
        "AI_OUTPUT",
        {
            "role": "review",
            "output": {
                "approved": False,
                "rationale": "Depth did not support the proposal.",
                "evidence_ids": ["observation"],
            },
        },
    )
    save(d, "AGENT_EVALUATION", {"status": "AI_HTTP_429", "private_config": "DO_NOT_EXPOSE"})
    save(d, "AGENT_EVALUATION", {"status": "AGENT_WAIT_OR_REJECT"})
    data = get(d)
    assert {row["state"] for row in data["rows"]} == {"wait", "blocked", "failed", "unspecified"}
    assert "DO_NOT_EXPOSE" not in str(data)
    waiting = next(row for row in data["rows"] if row["state"] == "wait")
    assert (
        waiting["rationale"] == "Evidence was inconclusive."
        and waiting["risk"] is None
        and waiting["order"] is None
    )
    assert all(row["risk"] is None for row in data["rows"])


def test_keyset_categories_owner_isolation_and_invalid_cursors(durable):
    d = durable
    other = d.legacy.create_account(d.scenario.config, d.clock.now)
    expected = {
        str(save(d, "AGENT_EVALUATION", {"status": "AI_NOT_CONFIGURED"})) for _ in range(13)
    }
    excluded = save(d, "AI_CONTEXT", {"private": "PRIVATE_CONTEXT"})
    seen = []
    cursor = None
    while True:
        data = get(d, limit=4, **({"before": cursor} if cursor else {}))
        seen.extend(row["id"] for row in data["rows"])
        cursor = data["next_before"]
        if cursor is None:
            break
    assert set(seen) == expected and len(seen) == 13
    assert get(d, category="risk")["rows"] == []
    with client_for(d.engine, other) as client:
        assert client.get("/api/paper/agent-activity").json()["rows"] == []
        assert (
            client.get("/api/paper/agent-activity", params={"before": seen[0]}).status_code == 400
        )
    with client_for(d.engine, d.account) as client:
        assert (
            client.get("/api/paper/agent-activity", params={"before": str(excluded)}).status_code
            == 400
        )
        assert (
            client.get("/api/paper/agent-activity", params={"category": "raw"}).status_code == 422
        )
        assert client.get("/api/paper/agent-activity", params={"limit": 51}).status_code == 422


def test_malformed_outputs_and_foreign_decision_references_fail_closed(durable):
    d = durable
    other = d.legacy.create_account(d.scenario.config, d.clock.now)
    with Session(d.engine) as db, db.begin():
        decision = DecisionRecord(
            id=uuid4(), account_id=other, payload={"rationale": "FOREIGN_PRIVATE"}, result={}
        )
        db.add(decision)
        decision_id = decision.id
    save(d, "DURABLE_RISK_DECISION", {"decision_id": str(decision_id)})
    save(
        d,
        "AI_OUTPUT",
        {"role": "proposal", "output": {"action": "BUY_CALL", "rationale": "MALFORMED_PRIVATE"}},
    )
    save(d, "AGENT_EVALUATION", {"status": "PRIVATE_ERROR_INTERNALS"})
    data = get(d)
    assert (
        "FOREIGN_PRIVATE" not in str(data)
        and "MALFORMED_PRIVATE" not in str(data)
        and "PRIVATE_ERROR_INTERNALS" not in str(data)
    )
    assert all(row["risk"] is None and row["order"] is None for row in data["rows"])
    assert [row for row in data["rows"] if row["stage"] == "risk"][0]["state"] == "unavailable"


def test_rejected_risk_has_known_explanation_without_order(durable):
    d = durable
    decision = d.scenario.decision.model_copy(update={"id": uuid4()})
    with Session(d.engine) as db, db.begin():
        db.add(
            DecisionRecord(
                id=decision.id,
                account_id=d.account,
                payload=decision.model_dump(mode="json"),
                result={"status": "REJECTED", "reason": "DAILY_LOSS_LIMIT"},
            )
        )
    save(d, "DURABLE_RISK_DECISION", {"decision_id": str(decision.id)})
    row = get(d, category="risk")["rows"][0]
    assert row["state"] == "blocked" and "daily loss limit" in row["summary"]
    assert row["order"] is None and row["risk"] is None
