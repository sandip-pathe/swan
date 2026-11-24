"""Fail-closed bridge from strategy drafts to existing paper controls.

This deliberately stops before the paper engine. An eligible plan must be
reviewed and represented through the existing manual intent/risk path first.
"""

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.models import (
    AgentArtifact,
    AgentAssignment,
    StrategyPaperPlanCandidateRecord,
    StrategyPlanDraftRecord,
)
from services.strategies.contracts import StrategyPaperPlanCandidate, StrategyPlanDraft


@dataclass(frozen=True)
class PaperPreflight:
    admitted: bool
    blockers: tuple[str, ...]


def preflight_strategy_plan(plan: StrategyPlanDraft) -> PaperPreflight:
    """Reject research drafts; do not translate one into an order or intent."""
    blockers = []
    if not plan.execution_eligible:
        blockers.append("PLAN_RESEARCH_ONLY")
    if plan.mandate_state != "REVIEWED":
        blockers.append("MANDATE_NOT_REVIEWED")
    if plan.outcome != "FIT":
        blockers.append("STRATEGY_NOT_FIT")
    if not plan.evidence_ids:
        blockers.append("NO_ASSESSMENT_EVIDENCE")
    return PaperPreflight(admitted=not blockers, blockers=tuple(blockers))


def preflight_paper_candidate(
    candidate: StrategyPaperPlanCandidate,
    *,
    account_ready: bool,
    qualification_valid: bool,
    paper_arm_active: bool,
    execution_blockers: tuple[str, ...],
    provenance_valid: bool,
    orb_exit_adapter_ready: bool = False,
) -> PaperPreflight:
    """Fail closed until reviewed ORB exits can be enforced by the paper engine."""
    blockers: list[str] = list(candidate.blocker_codes)
    if candidate.status != "READY":
        blockers.append("PAPER_PLAN_CANDIDATE_BLOCKED")
    if not provenance_valid:
        blockers.append("PAPER_CANDIDATE_PROVENANCE_INVALID")
    if not candidate.execution_eligible or candidate.source_plan.mandate_state != "REVIEWED":
        blockers.append("PAPER_MANDATE_NOT_APPROVED_FOR_EXECUTION")
    if not account_ready:
        blockers.append("CURRENT_ACCOUNT_RISK_CONFIGURATION_UNAVAILABLE")
    if not qualification_valid:
        blockers.append("CURRENT_PAPER_QUALIFICATION_REQUIRED")
    if not paper_arm_active:
        blockers.append("EXPLICIT_CURRENT_PAPER_ARM_REQUIRED")
    blockers.extend(execution_blockers)
    if not orb_exit_adapter_ready:
        blockers.append("ORB_PREMIUM_AND_UNDERLYING_EXIT_ADAPTER_REQUIRED")
    ordered = tuple(dict.fromkeys(blockers))
    return PaperPreflight(admitted=not ordered, blockers=ordered)


def candidate_provenance_valid(
    session: Session,
    record: StrategyPaperPlanCandidateRecord,
    candidate: StrategyPaperPlanCandidate,
    *,
    account_id: UUID,
) -> bool:
    """Recheck immutable source, review, and mandate fingerprints at preflight."""
    plan_row = session.scalar(
        select(StrategyPlanDraftRecord).where(
            StrategyPlanDraftRecord.plan_id == record.source_plan_id
        )
    )
    assignment = session.get(AgentAssignment, record.review_assignment_id)
    artifact = session.get(AgentArtifact, record.review_artifact_id)
    if (
        plan_row is None
        or plan_row.assessment_id != record.assessment_id
        or plan_row.payload != candidate.source_plan.model_dump(mode="json")
        or assignment is None
        or assignment.account_id != account_id
        or assignment.state != "COMPLETED"
        or (assignment.outcome or {}).get("result") != "REVIEWED_DRAFT_SAVED"
        or (assignment.outcome or {}).get("assessment_id") != record.assessment_id
        or artifact is None
        or artifact.assignment_id != assignment.id
        or artifact.kind != "REVIEWED_DRAFT"
    ):
        return False
    reviewed = artifact.payload
    review = reviewed.get("review")
    assessment = reviewed.get("assessment")
    plan = candidate.source_plan
    if (
        not isinstance(review, dict)
        or not isinstance(assessment, dict)
        or reviewed.get("disposition") != "SELECT"
        or reviewed.get("strategy_id") != plan.strategy_id
        or reviewed.get("strategy_version") != plan.version
        or reviewed.get("assessment_id") != record.assessment_id
        or review.get("approved") is not True
        or not set(reviewed.get("evidence_ids", ())) <= set(plan.evidence_ids)
        or not set(review.get("evidence_ids", ())) <= set(candidate.source_plan.evidence_ids)
        or not set(reviewed.get("evidence_ids", ())) <= set(review.get("evidence_ids", ()))
        or assessment.get("strategy_id") != plan.strategy_id
        or assessment.get("version") != plan.version
        or assessment.get("definition_fingerprint") != plan.definition_fingerprint
    ):
        return False
    fingerprint = hashlib.sha256(
        json.dumps(
            candidate.mandate.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    identity = {
        "candidate_version": candidate.candidate_version,
        "source_plan_id": record.source_plan_id,
        "review_assignment_id": str(record.review_assignment_id),
        "review_artifact_id": str(record.review_artifact_id),
        "mandate_fingerprint": fingerprint,
    }
    expected_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return (
        fingerprint == candidate.mandate_fingerprint
        and expected_id == candidate.candidate_id == record.candidate_id
        and record.payload == candidate.model_dump(mode="json")
        and record.review_assignment_id == candidate.review_assignment_id
        and record.review_artifact_id == candidate.review_artifact_id
        and assessment.get("snapshot_id") == candidate.source_plan.snapshot_id
        and assessment.get("assessment_id") == candidate.source_plan.assessment_id
        and tuple(assessment.get("evidence_ids", ())) == candidate.source_plan.evidence_ids
    )
