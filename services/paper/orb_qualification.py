"""Verify ORB's original analyst/reviewer provenance for paper qualification."""

from datetime import UTC

from sqlalchemy import select

from services.core.models import (
    AgentArtifact,
    AgentAssignment,
    AuditEvent,
    IndexHistoryBatch,
    StrategyPaperPlanCandidateRecord,
)
from services.market.index_history import INDEX_HISTORY_SOURCE
from services.strategies.contracts import IndexBar, StrategyPaperPlanCandidate
from services.strategies.paper_admission import candidate_provenance_valid


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def verified_orb_review(db, account, lease, envelope, buy) -> bool:
    """No permission is granted. Missing original model or market records fail closed."""
    stages = db.scalars(select(AuditEvent).where(
        AuditEvent.account_id == account.id, AuditEvent.kind == "ORB_CANDIDATE_STAGED",
        AuditEvent.timestamp >= lease.started_at, AuditEvent.timestamp <= buy.accepted_at,
        AuditEvent.details["strategy_id"].as_string() == str(envelope.id),
    ))
    for stage in stages:
        record = db.get(StrategyPaperPlanCandidateRecord, stage.details.get("candidate_id"))
        if record is None:
            continue
        try:
            candidate = StrategyPaperPlanCandidate.model_validate(record.payload)
            if not candidate_provenance_valid(db, record, candidate, account_id=account.id):
                continue
            plan = candidate.source_plan
            artifact = db.get(AgentArtifact, candidate.review_artifact_id)
            assignment = db.get(AgentAssignment, candidate.review_assignment_id)
            batch = db.get(IndexHistoryBatch, plan.snapshot_id)
            if (
                artifact is None or assignment is None or batch is None
                or batch.source != INDEX_HISTORY_SOURCE
                or batch.underlying != "NIFTY" or batch.exchange != "NSE"
                or plan.valid_until is None
                or not utc(plan.as_of) <= utc(candidate.reviewed_at) <= utc(stage.timestamp) < utc(plan.valid_until)
                or utc(artifact.created_at) != utc(candidate.reviewed_at)
                or utc(batch.received_at) > utc(candidate.reviewed_at)
            ):
                continue
            bars = {b["evidence_id"]: IndexBar.model_validate(b) for b in batch.payload["bars"]}
            if not plan.evidence_ids or any(
                key not in bars or not bars[key].final
                or bars[key].source != INDEX_HISTORY_SOURCE
                or bars[key].underlying != "NIFTY" or bars[key].exchange != "NSE"
                or utc(bars[key].available_at) > utc(candidate.reviewed_at)
                for key in plan.evidence_ids
            ):
                continue
            outputs = list(db.scalars(select(AuditEvent).where(
                AuditEvent.account_id == account.id, AuditEvent.kind == "AI_OUTPUT",
                AuditEvent.details["assignment_id"].as_string() == str(assignment.id),
                AuditEvent.timestamp >= assignment.created_at,
                AuditEvent.timestamp <= artifact.created_at,
            )))
            expected = artifact.payload
            valid_roles = set()
            for output in outputs:
                details = output.details
                value = details.get("output", {})
                if not details.get("response_id") or not details.get("reported_model"):
                    continue
                role = details.get("role")
                from services.agents.assessment_workflow import AnalystDraft, ReviewerResult

                if role == "strategy_reviewer":
                    value = ReviewerResult.model_validate(value).model_dump(mode="json")
                    if value == expected.get("review") and value["approved"] is True:
                        valid_roles.add(role)
                if role == "strategy_analyst":
                    value = AnalystDraft.model_validate(value).model_dump(mode="json")
                    if all(expected.get(k) == v for k, v in value.items()):
                        if value["disposition"] == "SELECT" and value["assessment_id"] == plan.assessment_id:
                            valid_roles.add(role)
            if valid_roles == {"strategy_analyst", "strategy_reviewer"}:
                return True
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return False
