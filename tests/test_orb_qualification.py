"""Original ORB review proof, in isolated fixtures. Never live qualification."""

# ruff: noqa: F811
from datetime import UTC, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_agentic_workflow import workflow_db  # noqa: F401
from test_orb_admission import staging  # noqa: F401

from services.core.models import (
    Account,
    AgentArtifact,
    AgentAssignment,
    AuditEvent,
    IndexHistoryBatch,
    StrategyPaperPlanCandidateRecord,
)
from services.market.index_history import INDEX_HISTORY_SOURCE
from services.paper.orb_qualification import verified_orb_review
from services.paper.qualification import EntryPermission
from services.strategies import orb_admission
from services.strategies.contracts import StrategyPaperPlanCandidate


@pytest.mark.parametrize("fault", [None, "review_missing", "analyst_missing", "foreign_review", "bad_citation", "late_review", "bad_source"])
def test_orb_proof_requires_owned_original_models_and_market_evidence(staging, monkeypatch, fault):
    monkeypatch.setattr(orb_admission, "flat", lambda *args: True)
    monkeypatch.setattr(orb_admission, "entry_permission", lambda *args, **kwargs: EntryPermission(
        None, uuid4(), 25, staging["now"] + timedelta(minutes=1)))
    monkeypatch.setattr(orb_admission, "configuration_status", lambda *args, **kwargs: {"engine_ready": True})
    prepared = orb_admission.stage_orb_candidate(**staging)
    now = staging["now"].astimezone(UTC)
    with Session(staging["engine"]) as db, db.begin():
        db.scalar(select(AuditEvent).where(AuditEvent.kind == "ORB_CANDIDATE_STAGED")).timestamp = now
        record = db.get(StrategyPaperPlanCandidateRecord, staging["candidate_id"])
        payload = dict(record.payload)
        payload["reviewed_at"] = now.isoformat()
        record.payload = StrategyPaperPlanCandidate.model_validate(payload).model_dump(mode="json")
        assignment = db.get(AgentAssignment, record.review_assignment_id)
        assignment.created_at = now - timedelta(seconds=1)
        artifact = db.get(AgentArtifact, record.review_artifact_id)
        artifact.created_at = now
        batch = db.get(IndexHistoryBatch, record.payload["source_plan"]["snapshot_id"])
        batch.source = INDEX_HISTORY_SOURCE if fault != "bad_source" else "isolated-unsupported"
        batch.payload = {"bars": [{**bar, "source": INDEX_HISTORY_SOURCE} for bar in batch.payload["bars"]]}
        analyst = {key: artifact.payload.get(key) for key in (
            "disposition", "assessment_id", "strategy_id", "strategy_version", "rationale", "evidence_ids", "draft",
        )}
        for role, output in (("strategy_analyst", analyst), ("strategy_reviewer", artifact.payload["review"])):
            if fault == "review_missing" and role == "strategy_reviewer" or fault == "analyst_missing" and role == "strategy_analyst":
                continue
            output = dict(output)
            if fault == "bad_citation" and role == "strategy_reviewer":
                output["evidence_ids"] = ["not-in-original-review"]
            db.add(AuditEvent(
                account_id=uuid4() if fault == "foreign_review" and role == "strategy_reviewer" else staging["account_id"],
                kind="AI_OUTPUT", timestamp=now + timedelta(seconds=1) if fault == "late_review" else now,
                details={"assignment_id": str(assignment.id), "role": role,
                         "reported_model": "isolated-fixture-model", "response_id": "isolated-response",
                         "output": output},
            ))
    with Session(staging["engine"]) as db:
        assert verified_orb_review(
            db, db.get(Account, staging["account_id"]),
            SimpleNamespace(started_at=now - timedelta(seconds=2)),
            prepared.envelope, SimpleNamespace(accepted_at=now + timedelta(seconds=2)),
        ) is (fault is None)
