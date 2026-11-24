import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from services.agents import assessment_workflow as workflow_module
from services.agents.assessment_workflow import AssessmentWorkflow
from services.core.contracts import IST, ExchangeSession
from services.core.models import (
    AgentArtifact,
    AgentAssignment,
    IndexHistoryBatch,
    StrategyAssessmentRecord,
    StrategyPaperPlanCandidateRecord,
    StrategyPlanDraftRecord,
)
from services.market.settings import ProviderError


class StubPipeline:
    def __init__(self, responses=None):
        self.settings = type("Settings", (), {"ready": lambda self: True})()
        self.provider = StubProvider(responses or {})


class StubProvider:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def generate(self, role, context, output):
        self.calls.append(role)
        response = self.responses.get(role)
        if callable(response):
            response = response(context)
        if isinstance(response, Exception):
            raise response
        if response is None:
            response = _response(role, context)
        return output.model_validate(response)


@pytest.fixture
def workflow_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    for model in (
        IndexHistoryBatch,
        StrategyAssessmentRecord,
        StrategyPlanDraftRecord,
        AgentAssignment,
        AgentArtifact,
        StrategyPaperPlanCandidateRecord,
    ):
        model.__table__.create(engine)
    yield engine
    engine.dispose()


def test_supported_setup_saves_reviewed_draft(workflow_db):
    account_id = uuid4()
    pipeline = StubPipeline()
    service = AssessmentWorkflow(workflow_db, account_id, pipeline)
    session, snapshot_id, as_of = _store_snapshot(workflow_db, bullish=True)

    result = asyncio.run(service.request(
        request_key="supported-setup", snapshot_id=snapshot_id, as_of=as_of, session=session
    ))

    assert result.state == "COMPLETED", result.outcome
    assert result.outcome["result"] == "REVIEWED_DRAFT_SAVED"
    assert pipeline.provider.calls == ["strategy_analyst", "strategy_reviewer"]
    assert any(row["kind"] == "REVIEWED_DRAFT" for row in result.artifacts)
    assert not any(row["kind"] == "StrategyEnvelope" for row in result.artifacts)


def test_no_setup_creates_linked_inactive_research_assignment(workflow_db):
    account_id = uuid4()
    pipeline = StubPipeline()
    service = AssessmentWorkflow(workflow_db, account_id, pipeline)
    session, snapshot_id, as_of = _store_snapshot(workflow_db, bullish=False)

    result = asyncio.run(service.request(
        request_key="no-setup", snapshot_id=snapshot_id, as_of=as_of, session=session
    ))
    linked = asyncio.run(service.readback(result.assignment_id))

    assert linked is not None
    assert linked.state == "COMPLETED"
    assert linked.outcome["result"] == "RESEARCH_SAVED"
    assert pipeline.provider.calls == ["strategy_analyst", "strategy_research"]
    child = linked.linked_assignments[0]
    assert child["kind"] == "EXPLICIT_STRATEGY_RESEARCH"
    assert child["state"] == "COMPLETED"
    hypothesis = next(a for a in child["artifacts"] if a["kind"] == "RESEARCH_HYPOTHESIS")
    assert hypothesis["activation_state"] == "INACTIVE"
    assert hypothesis["assessment_id"] == result.outcome["assessment_id"]
    with Session(workflow_db) as db:
        assignment = db.get(AgentAssignment, UUID(child["assignment_id"]))
        assert assignment is not None
        assert assignment.kind == "EXPLICIT_STRATEGY_RESEARCH"
        assert assignment.input_refs["parent_assignment_id"] == str(result.assignment_id)


def test_missing_snapshot_is_unavailable_idempotent_and_does_not_call_provider(workflow_db):
    pipeline = StubPipeline()
    service = AssessmentWorkflow(workflow_db, uuid4(), pipeline)
    session, _, as_of = _store_snapshot(workflow_db, bullish=True)
    missing_id = "missing-snapshot"

    first = asyncio.run(service.request(
        request_key="missing", snapshot_id=missing_id, as_of=as_of, session=session
    ))
    second = asyncio.run(service.request(
        request_key="missing", snapshot_id=missing_id, as_of=as_of, session=session
    ))

    assert first.assignment_id == second.assignment_id
    assert first.state == "UNAVAILABLE"
    assert pipeline.provider.calls == []
    tool_results = next(a for a in first.artifacts if a["kind"] == "TOOL_RESULTS")
    assert tool_results["read_index_snapshot"]["reason"] == "SNAPSHOT_MISSING_OR_LATE"
    with pytest.raises(ValueError, match="AGENT_REQUEST_KEY_CONFLICT"):
        asyncio.run(service.request(
            request_key="missing", snapshot_id="different-snapshot", as_of=as_of, session=session
        ))


def test_gapped_snapshot_is_insufficient_data_and_does_not_start_research(workflow_db):
    pipeline = StubPipeline()
    service = AssessmentWorkflow(workflow_db, uuid4(), pipeline)
    session, snapshot_id, as_of = _store_snapshot(workflow_db, bullish=False)
    with Session(workflow_db) as db, db.begin():
        batch = db.get(IndexHistoryBatch, snapshot_id)
        batch.payload = {
            "bars": [bar for bar in batch.payload["bars"] if bar["evidence_id"] != "bar-14"]
        }

    result = asyncio.run(service.request(
        request_key="gap", snapshot_id=snapshot_id, as_of=as_of, session=session
    ))

    assert result.state == "UNAVAILABLE"
    assert result.outcome["classification"] == "INSUFFICIENT_DATA"
    assert result.outcome["reason"] == "OPENING_RANGE_GAP"
    assert pipeline.provider.calls == []


def test_deterministic_tool_failure_is_saved_as_failed_without_agent_opinion(
    workflow_db, monkeypatch
):
    pipeline = StubPipeline()
    service = AssessmentWorkflow(workflow_db, uuid4(), pipeline)
    session, snapshot_id, as_of = _store_snapshot(workflow_db, bullish=False)

    def fail_tool(*args, **kwargs):
        raise ProviderError("ORB_TOOL_FAILURE")

    monkeypatch.setattr(workflow_module, "evaluate_orb", fail_tool)
    result = asyncio.run(service.request(
        request_key="tool-failure", snapshot_id=snapshot_id, as_of=as_of, session=session
    ))

    assert result.state == "FAILED"
    assert result.outcome["reason"] == "ORB_TOOL_FAILURE"
    assert pipeline.provider.calls == []


def test_late_analyst_response_cannot_save_a_draft(workflow_db):
    account_id = uuid4()
    session, snapshot_id, as_of = _store_snapshot(workflow_db, bullish=True)

    class LateProvider(StubProvider):
        async def generate(self, role, context, output):
            self.calls.append(role)
            with Session(workflow_db) as db, db.begin():
                row = db.get(AgentAssignment, UUID(context["assignment_id"]))
                row.deadline = datetime.now(UTC) - timedelta(seconds=1)
            return output.model_validate(_response(role, context))

    pipeline = StubPipeline()
    pipeline.provider = LateProvider({})
    service = AssessmentWorkflow(workflow_db, account_id, pipeline)
    result = asyncio.run(service.request(
        request_key="late-response", snapshot_id=snapshot_id, as_of=as_of, session=session
    ))

    assert result.state == "EXPIRED"
    assert pipeline.provider.calls == ["strategy_analyst"]
    assert not any(a["kind"] == "ANALYST_DRAFT" for a in result.artifacts)


def _response(role, context):
    if role == "strategy_analyst":
        assessment = context["assessment"]
        if assessment["status"] == "NO_SETUP":
            return {
                "disposition": "RESEARCH",
                "assessment_id": assessment["assessment_id"],
                "strategy_id": None,
                "strategy_version": None,
                "rationale": "The predefined setup did not trigger.",
                "evidence_ids": list(assessment["evidence_ids"]),
                "draft": None,
            }
        return {
            "disposition": "SELECT",
            "assessment_id": assessment["assessment_id"],
            "strategy_id": assessment["strategy_id"],
            "strategy_version": assessment["version"],
            "rationale": "The deterministic setup is supported.",
            "evidence_ids": list(assessment["evidence_ids"]),
            "draft": "Inactive research/trading-plan draft.",
        }
    if role == "strategy_reviewer":
        return {
            "approved": True,
            "rationale": "The draft cites the assessment evidence.",
            "evidence_ids": context["analyst_draft"]["evidence_ids"],
        }
    if role == "strategy_research":
        assessment = context["assessment"]
        return {
            "scope": "Intraday NIFTY index setup selection",
            "hypothesis": "A bounded alternative feature may identify a useful setup.",
            "assumptions": ["Only stored one-minute index bars are available."],
            "required_evidence": ["Chronological index bars and declared transaction costs."],
            "evidence_ids": list(assessment["evidence_ids"]),
            "evaluation_method": "Compare chronologically against the frozen predefined setup.",
        }
    raise AssertionError(f"Unexpected provider role: {role}")


def _store_snapshot(engine, *, bullish: bool):
    session_day = date.today() + timedelta(days=2)
    start = datetime.combine(session_day, datetime.min.time(), IST).replace(hour=9, minute=15)
    as_of = start + timedelta(minutes=16)
    exchange_session = ExchangeSession(
        key=session_day,
        opens_at=start,
        closes_at=start.replace(hour=15, minute=30),
        calendar_source="isolated-test",
        verified=True,
    )
    bars = []
    for index in range(16):
        opened = start + timedelta(minutes=index)
        if index < 15:
            values = (Decimal("99.5"), Decimal("100"), Decimal("99"), Decimal("99.5"))
        elif bullish:
            values = (Decimal("100"), Decimal("100.2"), Decimal("99.9"), Decimal("100.1"))
        else:
            values = (Decimal("99.5"), Decimal("100"), Decimal("99"), Decimal("99.5"))
        bars.append({
            "evidence_id": f"bar-{index}",
            "underlying": "NIFTY",
            "exchange": "NSE",
            "source": "isolated-fixture",
            "opens_at": opened.isoformat(),
            "closes_at": (opened + timedelta(minutes=1)).isoformat(),
            "available_at": (opened + timedelta(minutes=1)).isoformat(),
            "final": True,
            "open": str(values[0]),
            "high": str(values[1]),
            "low": str(values[2]),
            "close": str(values[3]),
        })
    snapshot_id = "isolated-snapshot-" + ("bull" if bullish else "none")
    with Session(engine) as db, db.begin():
        db.add(IndexHistoryBatch(
            snapshot_id=snapshot_id,
            underlying="NIFTY",
            exchange="NSE",
            session_key=session_day,
            received_at=as_of.astimezone(UTC),
            source="isolated-fixture",
            response_sha256="a" * 64,
            provider_request={"fixture": True},
            payload={"bars": bars},
        ))
    return exchange_session, snapshot_id, as_of
