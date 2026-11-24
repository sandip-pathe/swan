"""Evaluation histories require explicit owned IDs, not nearby timestamps."""

# ruff: noqa: F811
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_durable import durable, observed  # noqa: F401
from test_instrument_search import client_for

from services.agents.contracts import Analysis, Proposal
from services.agents.pipeline import AgentPipeline
from services.core.models import Account, AuditEvent
from services.worker.models import EvaluationSlot

pytestmark = pytest.mark.integration


def slot(d, owner=None, status="AWAITING_AGENT"):
    with Session(d.engine) as db, db.begin():
        row = EvaluationSlot(
            account_id=owner or d.account,
            session_key=d.scenario.session.key,
            slot_at=d.clock.now,
            status=status,
            evidence_ids=[],
        )
        db.add(row)
        db.flush()
        return row.id


def save(d, key=None, role="analysis", payload=None, owner=None, kind="AI_OUTPUT"):
    with Session(d.engine) as db, db.begin():
        row = AuditEvent(
            account_id=owner or d.account,
            kind=kind,
            timestamp=d.clock.now,
            details={"evaluation_id": str(key) if key else None, "role": role, "output": payload},
        )
        db.add(row)
        db.flush()
        return row.id


def read(d, event):
    with client_for(d.engine, d.account) as client:
        return client.get(f"/api/paper/agent-activity/{event}/run")


def test_pipeline_carries_evaluation_id_through_all_saved_stages(durable):
    d = durable
    quote = observed(d)
    key = slot(d)
    pipeline = AgentPipeline.__new__(AgentPipeline)
    pipeline.settings = SimpleNamespace(ready=lambda: True)

    async def news():
        return []

    pipeline.news = SimpleNamespace(read=news)

    async def generate(role, context, model):
        assert context["evaluation_id"] == str(key)
        assert context["citation_rules"]["market_quote_ids"] == [str(quote.id)]
        assert context["citation_rules"]["news_ids"] == []
        assert context["execution_model"]["version"]
        assert "not executable" in context["planning_semantics"]["quotes"]
        if role == "analysis":
            value = Analysis(
                outlook="UNCERTAIN",
                rationale="Uncertain",
                evidence_ids=[str(quote.id)],
                news_ids=[],
                concerns=[],
            )
        else:
            value = Proposal(
                action="WAIT",
                instrument_id=None,
                min_entry=None,
                max_entry=None,
                stop_loss=None,
                target=None,
                rationale="Wait",
                evidence_ids=[str(quote.id)],
            )
        save(d, key, role, value.model_dump(mode="json"))
        return value

    pipeline.provider = SimpleNamespace(engine=d.engine, account_id=d.account, generate=generate)
    assert (
        asyncio.run(
            pipeline.evaluate(
                {d.instrument.id: d.instrument}, [quote], d.scenario.session, d.scenario.config, key
            )
        )
        is None
    )
    event = save(d, key, kind="AGENT_EVALUATION")
    with Session(d.engine) as db:
        context = db.scalar(select(AuditEvent).where(AuditEvent.kind == "AI_CONTEXT"))
        assert context.details["evaluation_id"] == str(key)
        revision = db.get(Account, d.account).revision
        count = db.scalar(select(func.count()).select_from(AuditEvent))
    result = read(d, event).json()
    assert result["available"] and result["title"] == "Analysis pending"
    assert {row["stage"] for row in result["rows"]} == {"analysis", "proposal"}
    assert any(row["summary"] == "Wait proposed" for row in result["rows"])
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == revision
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == count


def test_legacy_foreign_and_wrong_kind_do_not_join(durable):
    d = durable
    key = slot(d)
    linked = save(d, key, kind="AGENT_EVALUATION")
    save(d, role="analysis", payload={"secret": "legacy"})
    assert read(d, linked).json()["rows"] == []
    legacy = save(d)
    assert read(d, legacy).json() == {"available": False}
    assert read(d, uuid4()).status_code == 404
    assert read(d, save(d, key, kind="AI_CONTEXT")).status_code == 404
    with Session(d.engine) as db, db.begin():
        other = Account(cash=0, config={})
        db.add(other)
        db.flush()
        owner = other.id
    foreign = slot(d, owner)
    assert not read(d, save(d, foreign)).json()["available"]
    assert read(d, save(d, key, owner=owner)).status_code == 404


def test_bounded_history_keeps_invalid_stages_and_failure_status(durable):
    d = durable
    key = slot(d, status="AI_HTTP_429")
    event = save(d, key, kind="AGENT_EVALUATION")
    for _ in range(21):
        save(d, key, role="review", payload={"private": "bad-output"})
    response = read(d, event)
    data = response.json()
    assert data["state"] == "failed" and data["truncated"]
    assert len(data["rows"]) == 20
    assert all(row["summary"] == "Recorded output unavailable" for row in data["rows"])
    assert "bad-output" not in response.text
