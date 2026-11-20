"""Accepted strategy linkage follows owned durable identities and real fills."""

# ruff: noqa: F811
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_agent_run import read
from test_durable import cycle, durable, observed  # noqa: F401

from services.core.models import Account, AuditEvent, DecisionRecord, PaperOrder
from services.worker.store import RuntimeStore

pytestmark = pytest.mark.integration


def accepted(d, quote):
    store = RuntimeStore(d.engine, d.account)
    key = store.save_evaluation(
        d.scenario.session, d.clock.now, {d.instrument.id: d.instrument}, [quote], d.clock.now
    )
    assert key
    envelope = d.scenario.envelope.model_copy(update={"evidence_ids": (quote.id,)})
    store.finish_evaluation(key, "STRATEGY_APPROVED", 0, envelope, d.clock.now)
    with Session(d.engine) as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.kind == "AGENT_EVALUATION"))
        return key, envelope, event.id


def admit(d, quote, envelope):
    decision = d.scenario.decision.model_copy(
        update={"snapshot_ids": (quote.id,), "strategy_id": envelope.id}
    )
    return d.service.admit(
        decision, d.instrument, quote, envelope, d.scenario.session, {d.instrument.id: quote}
    )


def test_accepted_strategy_no_decision_then_owned_order_and_real_fill(durable):
    d = durable
    quote = observed(d)
    key, envelope, event = accepted(d, quote)
    empty = read(d, event).json()["execution"]
    assert empty["state"] == "accepted" and empty["decisions"] == []
    assert "NIFTY" in empty["strategy"]["instrument"]
    result = admit(d, quote, envelope)
    assert result["status"] == "OPEN"
    entry = read(d, event).json()["execution"]["decisions"][0]
    assert entry["status"] == "APPROVED"
    assert entry["orders"][0]["id"] == result["order_id"]
    assert entry["orders"][0]["filled_quantity"] == 0
    cycle(d, 300)
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
        orders = db.scalar(select(func.count()).select_from(PaperOrder))
    filled = read(d, event).json()["execution"]["decisions"][0]["orders"][0]
    assert filled["filled_quantity"] > 0
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == revision
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == orders


def test_rejected_risk_does_not_imply_order(durable):
    d = durable
    quote = observed(d, bid="90", ask="100")
    key, envelope, event = accepted(d, quote)
    result = admit(d, quote, envelope)
    assert result["status"] == "REJECTED"
    decision = read(d, event).json()["execution"]["decisions"][0]
    assert decision["status"] == "REJECTED" and not decision["orders"]
    assert "spread" in decision["summary"].lower()


def test_foreign_and_bounded_decisions_are_not_inferred(durable):
    d = durable
    quote = observed(d)
    key, envelope, event = accepted(d, quote)
    with Session(d.engine) as db, db.begin():
        other = Account(cash=0, config={})
        db.add(other)
        db.flush()
        decision = d.scenario.decision.model_copy(
            update={"id": uuid4(), "strategy_id": envelope.id}
        )
        db.add(
            DecisionRecord(
                id=decision.id,
                account_id=other.id,
                payload=decision.model_dump(mode="json"),
                result={"status": "REJECTED", "reason": "private-other-owner"},
            )
        )
    assert read(d, event).json()["execution"]["decisions"] == []
    with Session(d.engine) as db, db.begin():
        for _ in range(21):
            decision = d.scenario.decision.model_copy(
                update={"id": uuid4(), "strategy_id": envelope.id}
            )
            db.add(
                DecisionRecord(
                    id=decision.id,
                    account_id=d.account,
                    payload=decision.model_dump(mode="json"),
                    result={"status": "REJECTED", "reason": "EXCESSIVE_SPREAD"},
                )
            )
    result = read(d, event).json()["execution"]
    assert len(result["decisions"]) == 20 and result["truncated"]
    assert "private-other-owner" not in str(result)


@pytest.mark.parametrize("mode", ["duplicate", "invalid", "missing", "none"])
def test_ambiguous_invalid_or_absent_acceptance_is_explicit(durable, mode):
    d = durable
    quote = observed(d)
    key, envelope, event = accepted(d, quote)
    with Session(d.engine) as db, db.begin():
        record = db.get(AuditEvent, event)
        if mode == "duplicate":
            db.add(
                AuditEvent(
                    account_id=d.account,
                    kind="AGENT_EVALUATION",
                    timestamp=d.clock.now,
                    details=dict(record.details),
                )
            )
        else:
            record.details = {
                **record.details,
                "status": "AGENT_WAIT_OR_REJECT" if mode == "none" else "STRATEGY_APPROVED",
                "envelope": {"private": "invalid"} if mode == "invalid" else None,
            }
    result = read(d, event).json()["execution"]
    assert result["state"] == ("none" if mode == "none" else "unavailable")
    assert not result["decisions"] and "private" not in str(result)
