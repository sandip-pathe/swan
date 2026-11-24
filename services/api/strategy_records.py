"""Authenticated, read-only access to durable strategy intelligence records."""

import asyncio
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.agents.assessment_workflow import AssessmentWorkflow
from services.api.auth import account_identity
from services.core.contracts import IST, RiskConfig
from services.core.models import (
    Account,
    AgentArtifact,
    AgentAssignment,
    StrategyPaperPlanCandidateRecord,
)
from services.market.calendar import SessionCalendar
from services.market.settings import MarketSettings
from services.paper.qualification import active_arm, arm_problem, qualification_context
from services.paper.settings import configuration_status
from services.strategies.assessment_store import read_assessments
from services.strategies.contracts import StrategyPaperPlanCandidate
from services.strategies.paper_admission import (
    candidate_provenance_valid,
    preflight_paper_candidate,
)
from services.strategies.paper_plan_candidates import read_paper_plan_candidates
from services.strategies.plan_store import read_plan_drafts
from services.strategies.research_store import read_candidates

router = APIRouter()


def _candidate_runtime_context(db: Session, account: Account, now: datetime) -> dict:
    try:
        RiskConfig.model_validate(account.config)
        account_ready = True
    except ValueError:
        account_ready = False
    qualification = qualification_context(db, account, now)
    paper_config = configuration_status(
        now.astimezone(IST).date(), qualification_valid=qualification["valid"]
    )
    arm = active_arm(db, account)
    arm_ready = arm is not None and arm_problem(db, account, arm, now) is None
    return {
        "account_ready": account_ready,
        "qualification_valid": qualification["valid"],
        "execution_blockers": tuple(paper_config.get("blockers", ())),
        "paper_arm_active": arm_ready,
    }


def _preflight_candidate(
    db: Session, owner: UUID, account: Account, record, now: datetime,
    runtime_context: dict | None = None,
):
    candidate = StrategyPaperPlanCandidate.model_validate(record.payload)
    runtime_context = runtime_context or _candidate_runtime_context(db, account, now)
    result = preflight_paper_candidate(
        candidate,
        **runtime_context,
        provenance_valid=candidate_provenance_valid(
            db, record, candidate, account_id=owner
        ),
    )
    return {
        "candidate_id": candidate.candidate_id,
        "as_of": now.isoformat(),
        "status": "READY" if result.admitted else "BLOCKED",
        "can_submit": result.admitted,
        "blocker_codes": list(result.blockers),
        "execution_path": "EXISTING_PAPER_ENGINE",
        "order_created": False,
        "provider_called": False,
    }


@router.get("/api/strategies/paper-plan-candidates/{candidate_id}/preflight")
def paper_candidate_preflight(
    candidate_id: str,
    request: Request,
    owner: UUID = Depends(account_identity),
):
    """Read current admission blockers without changing account or paper state."""
    now = datetime.now(UTC)
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        account = db.get(Account, owner)
        record = db.get(StrategyPaperPlanCandidateRecord, candidate_id)
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        if record is None:
            raise HTTPException(404, "PAPER_PLAN_CANDIDATE_NOT_FOUND")
        return _preflight_candidate(db, owner, account, record, now)


@router.get("/api/strategies/paper-plan-candidates/preflight")
def paper_candidates_preflight(
    request: Request,
    as_of: datetime,
    limit: int = Query(default=25, ge=1, le=50),
    owner: UUID = Depends(account_identity),
):
    """Bounded current admission snapshot for candidates, without order side effects."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HTTPException(422, "AWARE_AS_OF_REQUIRED")
    now = datetime.now(UTC)
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        account = db.get(Account, owner)
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        records = db.scalars(
            select(StrategyPaperPlanCandidateRecord)
            .where(StrategyPaperPlanCandidateRecord.created_at <= as_of)
            .order_by(
                StrategyPaperPlanCandidateRecord.created_at.desc(),
                StrategyPaperPlanCandidateRecord.candidate_id.desc(),
            )
            .limit(limit)
        )
        runtime_context = _candidate_runtime_context(db, account, now)
        return [
            _preflight_candidate(db, owner, account, row, now, runtime_context)
            for row in records
        ]


@router.get("/api/strategies/assignments")
def strategy_assignments(
    request: Request,
    session_key: date,
    as_of: datetime,
    limit: int = Query(default=50, ge=1, le=100),
    owner: UUID = Depends(account_identity),
):
    """Read bounded watcher workflow states and safe summaries of their artifacts."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HTTPException(422, "AWARE_AS_OF_REQUIRED")
    with Session(request.app.state.engine) as db:
        rows = list(db.scalars(
            select(AgentAssignment)
            .where(
                AgentAssignment.account_id == owner,
                AgentAssignment.kind == "WATCHER_STRATEGY_ASSESSMENT",
                AgentAssignment.created_at <= as_of,
                AgentAssignment.input_refs["session_key"].as_string() == session_key.isoformat(),
            )
            .order_by(AgentAssignment.created_at.desc(), AgentAssignment.id.desc())
            .limit(limit)
        ))
        if not rows:
            return []
        assignment_ids = [row.id for row in rows]
        artifacts = list(db.scalars(
            select(AgentArtifact)
            .where(AgentArtifact.assignment_id.in_(assignment_ids))
            .order_by(AgentArtifact.created_at, AgentArtifact.id)
            .limit(limit * 12)
        ))
        grouped: dict[UUID, list[dict]] = {identifier: [] for identifier in assignment_ids}
        for artifact in artifacts:
            payload = artifact.payload if isinstance(artifact.payload, dict) else {}
            summary: dict = {"kind": artifact.kind}
            if artifact.kind == "OUTCOME":
                summary["outcome"] = payload
            elif artifact.kind in {"ANALYST_DRAFT", "REVIEW"}:
                summary.update({
                    "approved": payload.get("approved"),
                    "disposition": payload.get("disposition"),
                    "rationale": str(payload.get("rationale", ""))[:600],
                    "evidence_count": len(payload.get("evidence_ids", [])),
                })
            elif artifact.kind == "RESEARCH_HYPOTHESIS":
                summary.update({
                    "scope": str(payload.get("scope", ""))[:500],
                    "hypothesis": str(payload.get("hypothesis", ""))[:900],
                    "evaluation_method": str(payload.get("evaluation_method", ""))[:900],
                    "activation_state": payload.get("activation_state", "INACTIVE"),
                })
            elif artifact.kind == "PAPER_PLAN_CANDIDATE":
                summary.update({
                    "candidate_id": payload.get("candidate_id"),
                    "status": payload.get("status"),
                    "blocker_codes": payload.get("blocker_codes", []),
                })
            elif artifact.kind == "TOOL_RESULTS":
                summary["tool_statuses"] = {
                    key: value.get("status")
                    for key, value in payload.items()
                    if isinstance(value, dict) and "status" in value
                }
            grouped[artifact.assignment_id].append(summary)
        return [
            {
                "assignment_id": str(row.id),
                "state": row.state,
                "created_at": row.created_at.isoformat(),
                "deadline": row.deadline.isoformat(),
                "snapshot_id": row.input_refs.get("snapshot_id"),
                "watcher_event_key": row.input_refs.get("watcher_event_key"),
                "outcome": row.outcome or {},
                "artifacts": grouped[row.id],
            }
            for row in rows
        ]


@router.post("/api/strategies/watcher-assignments/{assignment_id}/run")
def run_watcher_assignment(
    assignment_id: UUID,
    request: Request,
    owner: UUID = Depends(account_identity),
):
    """Explicitly claim one queued watcher item and run its bounded workflow."""
    with Session(request.app.state.engine) as db:
        assignment = db.get(AgentAssignment, assignment_id)
        if assignment is None or assignment.account_id != owner:
            raise HTTPException(404, "AGENT_ASSIGNMENT_NOT_FOUND")
        if assignment.kind != "WATCHER_STRATEGY_ASSESSMENT":
            raise HTTPException(409, "AGENT_ASSIGNMENT_NOT_WATCHER_WORK")
        try:
            session_key = date.fromisoformat(assignment.input_refs["session_key"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(409, "WATCHER_SESSION_REFERENCE_INVALID") from None

    exchange_session = SessionCalendar(MarketSettings().calendar_file, strict=False).get(
        "NFO", session_key
    )
    if exchange_session is None:
        raise HTTPException(409, "WATCHER_SESSION_UNAVAILABLE")
    workflow = AssessmentWorkflow(request.app.state.engine, owner)
    try:
        result = asyncio.run(
            workflow.run_queued_watcher_assignment(assignment_id, exchange_session)
        )
    except ValueError as error:
        code = str(error)
        status = 404 if code == "AGENT_ASSIGNMENT_NOT_FOUND" else 409
        raise HTTPException(status, code) from None
    return result.model_dump(mode="json")


@router.get("/api/strategies/assessments")
def assessments(
    request: Request,
    session_key: date,
    as_of: datetime,
    limit: int = Query(default=50, ge=1, le=100),
    owner: UUID = Depends(account_identity),
):
    del owner
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HTTPException(422, "AWARE_AS_OF_REQUIRED")
    with Session(request.app.state.engine) as db:
        return [item.model_dump(mode="json") for item in read_assessments(
            db, session_key=session_key, as_of=as_of, limit=limit
        )]


@router.get("/api/strategies/plans")
def plans(
    request: Request,
    session_key: date,
    as_of: datetime,
    limit: int = Query(default=50, ge=1, le=100),
    owner: UUID = Depends(account_identity),
):
    del owner  # Strategy evidence is single-user workspace data, not account order data.
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HTTPException(422, "AWARE_AS_OF_REQUIRED")
    with Session(request.app.state.engine) as db:
        return [item.model_dump(mode="json") for item in read_plan_drafts(
            db, session_key=session_key, as_of=as_of, limit=limit
        )]


@router.get("/api/strategies/research-candidates")
def research_candidates(
    request: Request,
    as_of: datetime,
    limit: int = Query(default=50, ge=1, le=100),
    owner: UUID = Depends(account_identity),
):
    del owner
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HTTPException(422, "AWARE_AS_OF_REQUIRED")
    with Session(request.app.state.engine) as db:
        return [item.model_dump(mode="json") for item in read_candidates(
            db, as_of=as_of, limit=limit
        )]


@router.get("/api/strategies/paper-plan-candidates")
def paper_plan_candidates(
    request: Request,
    as_of: datetime,
    limit: int = Query(default=50, ge=1, le=100),
    owner: UUID = Depends(account_identity),
):
    del owner
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HTTPException(422, "AWARE_AS_OF_REQUIRED")
    with Session(request.app.state.engine) as db:
        return [item.model_dump(mode="json") for item in read_paper_plan_candidates(
            db, as_of=as_of, limit=limit
        )]
