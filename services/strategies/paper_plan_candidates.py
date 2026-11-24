"""Persist a reviewed strategy draft as a blocked, versioned paper candidate."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.models import (
    AgentArtifact,
    AgentAssignment,
    StrategyPaperPlanCandidateRecord,
    StrategyPlanDraftRecord,
)
from services.strategies.contracts import (
    ORBPaperMandate,
    StrategyPaperPlanCandidate,
    StrategyPlanDraft,
)

MAX_CANDIDATE_READ = 100
PAPER_CANDIDATE_BLOCKERS: tuple[
    Literal[
        "CURRENT_ACCOUNT_RISK_CONFIGURATION_REQUIRED",
        "CURRENT_PAPER_QUALIFICATION_REQUIRED",
        "FRESH_UNDERLYING_REVALIDATION_AND_EXIT_MONITOR_REQUIRED",
        "REVIEWED_NFO_FEE_SCHEDULE_REQUIRED",
        "SELECTED_OPTION_CONTRACT_REQUIRED",
        "FRESH_EXECUTABLE_OPTION_QUOTE_AND_DEPTH_REQUIRED",
    ],
    ...,
] = (
    "CURRENT_ACCOUNT_RISK_CONFIGURATION_REQUIRED",
    "CURRENT_PAPER_QUALIFICATION_REQUIRED",
    "FRESH_UNDERLYING_REVALIDATION_AND_EXIT_MONITOR_REQUIRED",
    "REVIEWED_NFO_FEE_SCHEDULE_REQUIRED",
    "SELECTED_OPTION_CONTRACT_REQUIRED",
    "FRESH_EXECUTABLE_OPTION_QUOTE_AND_DEPTH_REQUIRED",
)


def create_reviewed_paper_candidate(
    session: Session,
    *,
    account_id: UUID,
    source_plan_id: str,
    review_assignment_id: UUID,
    review_artifact_id: UUID,
) -> StrategyPaperPlanCandidate:
    """Validate exact review links, then save an immutable candidate that cannot execute."""
    plan_row = session.scalar(
        select(StrategyPlanDraftRecord).where(StrategyPlanDraftRecord.plan_id == source_plan_id)
    )
    if plan_row is None:
        raise ValueError("PAPER_CANDIDATE_SOURCE_PLAN_NOT_FOUND")
    plan = StrategyPlanDraft.model_validate(plan_row.payload)
    if plan.outcome != "FIT" or not plan.evidence_ids:
        raise ValueError("PAPER_CANDIDATE_SOURCE_PLAN_NOT_FIT")

    assignment = session.get(AgentAssignment, review_assignment_id)
    artifact = session.get(AgentArtifact, review_artifact_id)
    if (
        assignment is None
        or assignment.account_id != account_id
        or assignment.state != "COMPLETED"
        or (assignment.outcome or {}).get("result") != "REVIEWED_DRAFT_SAVED"
    ):
        raise ValueError("PAPER_CANDIDATE_REVIEW_ASSIGNMENT_INVALID")
    if (
        artifact is None
        or artifact.assignment_id != review_assignment_id
        or artifact.kind != "REVIEWED_DRAFT"
    ):
        raise ValueError("PAPER_CANDIDATE_REVIEW_ARTIFACT_INVALID")

    reviewed = artifact.payload
    review = reviewed.get("review")
    assessment = reviewed.get("assessment")
    if (
        not isinstance(review, dict)
        or not isinstance(assessment, dict)
        or reviewed.get("disposition") != "SELECT"
        or reviewed.get("strategy_id") != plan.strategy_id
        or reviewed.get("strategy_version") != plan.version
        or review.get("approved") is not True
        or reviewed.get("assessment_id") != plan.assessment_id
        or assessment.get("assessment_id") != plan.assessment_id
        or assessment.get("snapshot_id") != plan.snapshot_id
        or assessment.get("strategy_id") != plan.strategy_id
        or assessment.get("version") != plan.version
        or assessment.get("definition_fingerprint") != plan.definition_fingerprint
        or tuple(assessment.get("evidence_ids", ())) != plan.evidence_ids
        or not set(reviewed.get("evidence_ids", ())) <= set(plan.evidence_ids)
        or not set(review.get("evidence_ids", ())) <= set(plan.evidence_ids)
    ):
        raise ValueError("PAPER_CANDIDATE_REVIEW_LINK_MISMATCH")

    mandate = ORBPaperMandate()
    mandate_fingerprint = hashlib.sha256(
        json.dumps(
            mandate.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    identity = {
        "candidate_version": "0.1-candidate",
        "source_plan_id": source_plan_id,
        "review_assignment_id": str(review_assignment_id),
        "review_artifact_id": str(review_artifact_id),
        "mandate_fingerprint": mandate_fingerprint,
    }
    candidate_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    candidate = StrategyPaperPlanCandidate(
        candidate_id=candidate_id,
        source_plan=plan,
        mandate=mandate,
        mandate_fingerprint=mandate_fingerprint,
        review_assignment_id=review_assignment_id,
        review_artifact_id=review_artifact_id,
        reviewed_at=(
            artifact.created_at.replace(tzinfo=timezone.utc)
            if artifact.created_at.tzinfo is None
            else artifact.created_at
        ),
        blocker_codes=PAPER_CANDIDATE_BLOCKERS,
    )
    existing = session.get(StrategyPaperPlanCandidateRecord, candidate_id)
    if existing is not None:
        if existing.payload != candidate.model_dump(mode="json"):
            raise ValueError("PAPER_CANDIDATE_IMMUTABILITY_CONFLICT")
        return StrategyPaperPlanCandidate.model_validate(existing.payload)

    record = StrategyPaperPlanCandidateRecord(
        candidate_id=candidate_id,
        assessment_id=plan.assessment_id,
        source_plan_id=source_plan_id,
        review_assignment_id=review_assignment_id,
        review_artifact_id=review_artifact_id,
        status=candidate.status,
        created_at=datetime.now(timezone.utc),
        payload=candidate.model_dump(mode="json"),
    )
    session.add(record)
    session.flush()
    return candidate


def attach_candidate_to_completed_workflow(
    session: Session, *, account_id: UUID, assignment_id: UUID, assessment_id: str
) -> StrategyPaperPlanCandidate:
    """Create the candidate after a completed, approved analyst/reviewer workflow."""
    assignment = session.get(AgentAssignment, assignment_id)
    if (
        assignment is None
        or assignment.account_id != account_id
        or assignment.state != "COMPLETED"
        or (assignment.outcome or {}).get("result") != "REVIEWED_DRAFT_SAVED"
        or (assignment.outcome or {}).get("assessment_id") != assessment_id
    ):
        raise ValueError("PAPER_CANDIDATE_WORKFLOW_NOT_COMPLETED")
    plan_row = session.scalar(
        select(StrategyPlanDraftRecord).where(
            StrategyPlanDraftRecord.assessment_id == assessment_id
        )
    )
    if plan_row is None:
        raise ValueError("PAPER_CANDIDATE_SOURCE_PLAN_NOT_FOUND")
    artifact = session.scalar(
        select(AgentArtifact)
        .where(
            AgentArtifact.assignment_id == assignment_id,
            AgentArtifact.kind == "REVIEWED_DRAFT",
        )
        .order_by(AgentArtifact.created_at.desc(), AgentArtifact.id.desc())
    )
    if artifact is None:
        raise ValueError("PAPER_CANDIDATE_REVIEW_ARTIFACT_NOT_FOUND")
    candidate = create_reviewed_paper_candidate(
        session,
        account_id=account_id,
        source_plan_id=plan_row.plan_id,
        review_assignment_id=assignment_id,
        review_artifact_id=artifact.id,
    )
    assignment.outcome = {
        **(assignment.outcome or {}),
        "paper_plan_candidate_id": candidate.candidate_id,
        "paper_plan_candidate_status": candidate.status,
    }
    existing_link = session.scalar(
        select(AgentArtifact).where(
            AgentArtifact.assignment_id == assignment_id,
            AgentArtifact.kind == "PAPER_PLAN_CANDIDATE",
        )
    )
    if existing_link is None:
        session.add(AgentArtifact(
            assignment_id=assignment_id,
            kind="PAPER_PLAN_CANDIDATE",
            created_at=datetime.now(timezone.utc),
            payload={
                "candidate_id": candidate.candidate_id,
                "candidate_version": candidate.candidate_version,
                "status": candidate.status,
                "blocker_codes": list(candidate.blocker_codes),
                "source_plan_id": plan_row.plan_id,
                "review_artifact_id": str(artifact.id),
            },
        ))
    session.flush()
    return candidate


def read_paper_plan_candidates(
    session: Session, *, as_of: datetime, limit: int = MAX_CANDIDATE_READ
) -> tuple[StrategyPaperPlanCandidate, ...]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("PAPER_CANDIDATE_AWARE_AS_OF_REQUIRED")
    if not 1 <= limit <= MAX_CANDIDATE_READ:
        raise ValueError("PAPER_CANDIDATE_READ_LIMIT_INVALID")
    rows = session.scalars(
        select(StrategyPaperPlanCandidateRecord)
        .where(StrategyPaperPlanCandidateRecord.created_at <= as_of)
        .order_by(
            StrategyPaperPlanCandidateRecord.created_at.desc(),
            StrategyPaperPlanCandidateRecord.candidate_id.desc(),
        )
        .limit(limit)
    )
    return tuple(StrategyPaperPlanCandidate.model_validate(row.payload) for row in rows)
