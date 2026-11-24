"""Staging integration with real provenance and isolated authority boundaries."""

# ruff: noqa: F811
import asyncio
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_agentic_workflow import StubPipeline, _store_snapshot, workflow_db  # noqa: F401

from services.agents.assessment_workflow import AssessmentWorkflow
from services.core.contracts import DepthLevel
from services.core.models import (
    Account,
    AuditEvent,
    DecisionRecord,
    InstrumentRecord,
    SnapshotRecord,
    StrategyPaperPlanCandidateRecord,
)
from services.market.reference_contracts import IndexReference
from services.paper.qualification import EntryPermission
from services.strategies import orb_admission as module
from services.worker.models import RuntimeControl


@pytest.fixture
def staging(workflow_db, scenario):
    for model in (Account, RuntimeControl, AuditEvent, DecisionRecord, InstrumentRecord, SnapshotRecord):
        model.__table__.create(workflow_db)
    owner = uuid4()
    session, snapshot, now = _store_snapshot(workflow_db, bullish=True)
    service = AssessmentWorkflow(workflow_db, owner, StubPipeline())
    result = asyncio.run(service.request(request_key="staging", snapshot_id=snapshot,
                                         as_of=now, session=session))
    assert result.state == "COMPLETED"
    with Session(workflow_db) as db, db.begin():
        candidate_id = db.scalar(select(StrategyPaperPlanCandidateRecord.candidate_id))
        assert candidate_id is not None
        db.add(Account(id=owner, cash=100000, config=scenario.config.model_dump(mode="json"),
                       enabled=False, revision=0, daily_blocked=False,
                       session_key=session.key, session_opening_equity=100000))
        db.add(RuntimeControl(account_id=owner, mode="AUTONOMOUS", resume_requested=True,
                              heartbeat=now, status="PAUSED"))
    instrument = scenario.instrument.model_copy(update={
        "exchange": "NFO", "expiry": session.key + timedelta(days=2),
        "strike": Decimal("100"), "verified_at": now - timedelta(minutes=20),
    })
    quote = scenario.quote.model_copy(update={
        "timestamp": now, "received_at": now, "market_event_id": "isolated-staging",
        "timestamp_basis": "exchange_feed", "depth_kind": "best_five",
        "quantity_unit": "units", "quantity_unit_source": "isolated-test",
        "bid_depth": (DepthLevel(price=scenario.quote.bid, quantity=200),),
        "ask_depth": (DepthLevel(price=scenario.quote.ask, quantity=200),),
    })
    return dict(engine=workflow_db, account_id=owner, candidate_id=candidate_id,
                instruments=[instrument], quotes={instrument.id: quote},
                reference=IndexReference(underlying="NIFTY", exchange="NSE", provider_token="test",
                                         timestamp=now, received_at=now, last_price="100.1"),
                session=session, now=now)


def test_staging_requires_real_entry_authority(staging, monkeypatch):
    monkeypatch.setattr(module, "flat", lambda *args: True)

    def denied(*args, **kwargs):
        raise ValueError("EXPLICIT_PAPER_ARM_REQUIRED")

    monkeypatch.setattr(module, "entry_permission", denied)
    with pytest.raises(ValueError, match="EXPLICIT_PAPER_ARM_REQUIRED"):
        module.stage_orb_candidate(**staging)
    with Session(staging["engine"]) as db:
        assert db.get(RuntimeControl, staging["account_id"]).active_envelope is None
        assert db.get(Account, staging["account_id"]).enabled is False


def test_staging_preserves_draft_and_does_not_enable_or_place_orders(staging, monkeypatch):
    monkeypatch.setattr(module, "flat", lambda *args: True)
    monkeypatch.setattr(module, "entry_permission", lambda *args, **kwargs: EntryPermission(
        None, uuid4(), 25, staging["now"] + timedelta(minutes=1)
    ))
    monkeypatch.setattr(module, "configuration_status", lambda *args, **kwargs: {"engine_ready": True})
    prepared = module.stage_orb_candidate(**staging)
    assert prepared.envelope.target is None
    with Session(staging["engine"]) as db:
        assert db.get(Account, staging["account_id"]).enabled is False
        assert db.get(RuntimeControl, staging["account_id"]).active_envelope["target"] is None
        original = db.get(StrategyPaperPlanCandidateRecord, staging["candidate_id"])
        assert original.payload["execution_eligible"] is False
        assert db.scalar(select(DecisionRecord)) is None
        event = db.scalar(select(AuditEvent))
        assert event.kind == "ORB_CANDIDATE_STAGED"
    with pytest.raises(ValueError, match="EXISTING_STRATEGY"):
        module.stage_orb_candidate(**staging)


def test_staging_applies_reviewed_unit_mapping_before_preparation(staging, monkeypatch):
    monkeypatch.setattr(module, "flat", lambda *args: True)
    monkeypatch.setattr(module, "entry_permission", lambda *args, **kwargs: EntryPermission(
        None, uuid4(), 25, staging["now"] + timedelta(minutes=1)))
    monkeypatch.setattr(module, "configuration_status", lambda *args, **kwargs: {"engine_ready": True})
    instrument = staging["instruments"][0]
    raw = staging["quotes"][instrument.id].model_copy(update={"quantity_unit": "unknown", "quantity_unit_source": None})
    staging["quotes"] = {instrument.id: raw}
    prepared = module.stage_orb_candidate(**staging)
    assert prepared.envelope.evidence_ids != (raw.id,)
    with Session(staging["engine"]) as db:
        saved = db.get(SnapshotRecord, prepared.envelope.evidence_ids[0])
        assert saved.payload["quantity_unit"] == "units"
        assert saved.payload["market_event_id"] == raw.market_event_id
        assert saved.payload["ask_depth"] == raw.model_dump(mode="json")["ask_depth"]
