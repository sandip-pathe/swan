"""Durable, reasoning-only workflow over stored index evidence."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from pydantic import AwareDatetime, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.agents.contracts import Output
from services.agents.pipeline import AgentPipeline
from services.core.contracts import ExchangeSession
from services.core.models import AgentArtifact, AgentAssignment, IndexHistoryBatch
from services.market.indicators import indicator_series
from services.market.settings import ProviderError
from services.strategies.assessment_store import persist_assessment
from services.strategies.contracts import ORBSnapshot, StrategyPlanDraft
from services.strategies.orb import evaluate_orb
from services.strategies.paper_plan_candidates import attach_candidate_to_completed_workflow
from services.strategies.plan_store import draft_strategy_plan, persist_plan_draft

logger = logging.getLogger(__name__)


class AnalystDraft(Output):
    disposition: Literal["SELECT", "ABSTAIN", "RESEARCH", "INSUFFICIENT_DATA"]
    assessment_id: str = Field(min_length=1, max_length=64)
    strategy_id: str | None = None
    strategy_version: str | None = None
    rationale: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str]
    draft: str | None = Field(default=None, max_length=6000)


class AssessmentContext(Output):
    """Canonical assessment identity and bounded evidence allowed to the agent."""

    assessment_id: str
    strategy_id: str
    version: str
    definition_fingerprint: str
    snapshot_id: str
    status: str
    evidence_ids: tuple[str, ...]
    as_of: AwareDatetime
    expires_at: AwareDatetime


def validate_analyst_output(
    analyst: AnalystDraft,
    context: AssessmentContext,
) -> None:
    """Bind model disposition/version/citations to the deterministic assessment."""
    if analyst.assessment_id != context.assessment_id:
        raise ProviderError("AI_UNKNOWN_ASSESSMENT")
    if not analyst.evidence_ids or not set(analyst.evidence_ids) <= set(context.evidence_ids):
        raise ProviderError("AI_UNKNOWN_OR_MISSING_EVIDENCE")
    if analyst.disposition == "SELECT":
        if context.status not in {"BULLISH_SETUP", "BEARISH_SETUP"}:
            raise ProviderError("AI_INELIGIBLE_STRATEGY_SELECTION")
        if (analyst.strategy_id, analyst.strategy_version) != (context.strategy_id, context.version):
            raise ProviderError("AI_STRATEGY_VERSION_MISMATCH")
        if not analyst.draft:
            raise ProviderError("AI_INCOMPLETE_PROPOSAL")
    elif analyst.disposition == "RESEARCH":
        if context.status != "NO_SETUP" or analyst.strategy_id or analyst.strategy_version:
            raise ProviderError("AGENT_RESEARCH_BRANCH_NOT_JUSTIFIED")
    elif analyst.disposition == "INSUFFICIENT_DATA":
        if context.status not in {"UNAVAILABLE", "NOT_READY", "NOT_APPLICABLE"}:
            raise ProviderError("AI_INSUFFICIENT_DATA_MISMATCH")
    elif analyst.strategy_id or analyst.strategy_version or analyst.draft:
        raise ProviderError("AI_INVALID_ABSTENTION")


class ReviewerResult(Output):
    approved: bool
    rationale: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str]


class ResearchHypothesis(Output):
    scope: str = Field(min_length=1, max_length=1000)
    hypothesis: str = Field(min_length=1, max_length=3000)
    assumptions: list[str] = Field(max_length=10)
    required_evidence: list[str] = Field(max_length=10)
    evidence_ids: list[str] = Field(min_length=1, max_length=40)
    evaluation_method: str = Field(min_length=1, max_length=2000)


class SnapshotToolResult(Output):
    status: Literal["OK", "EMPTY", "UNAVAILABLE"]
    snapshot_id: str
    source: str | None = None
    underlying: str | None = None
    exchange: str | None = None
    received_at: datetime | None = None
    as_of: datetime
    response_sha256: str | None = None
    bar_count: int = Field(ge=0)
    evidence_ids: list[str]
    reason: str | None = None


class AssessmentToolResult(Output):
    status: Literal["OK", "UNAVAILABLE"]
    assessment_id: str | None = None
    assessment: dict | None = None
    context: AssessmentContext | None = None
    plan_draft: StrategyPlanDraft | None = None
    reason: str | None = None


WorkflowState = Literal[
    "QUEUED", "RUNNING", "COMPLETED", "UNAVAILABLE", "ABSTAINED",
    "REJECTED", "EXPIRED", "FAILED", "INTERRUPTED",
]


class WorkflowResult(Output):
    assignment_id: UUID
    state: WorkflowState
    outcome: dict
    artifacts: list[dict]
    linked_assignments: list[dict] = Field(default_factory=list)


def _as_utc(value: datetime) -> datetime:
    """SQLite drops timezone offsets; stored SWAN timestamps are UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _provider_failure_state(error: ProviderError) -> WorkflowState:
    """Keep access/transport limits distinct from a model or contract failure."""
    code = str(error)
    if "EXPIRED" in code:
        return "EXPIRED"
    if code in {
        "AI_NOT_CONFIGURED",
        "AI_DAILY_TOKEN_BUDGET",
        "AI_RESPONSE_UNAVAILABLE_OR_INVALID",
    } or (code.startswith("AI_HTTP_") and code[8:].isdigit()):
        return "UNAVAILABLE"
    return "FAILED"


def _create_assignment(
    engine, account_id: UUID, request_key: str, snapshot_id: str, as_of: datetime,
    *, kind: str = "EXPLICIT_STRATEGY_ASSESSMENT",
    linked_refs: dict | None = None,
    deadline: datetime | None = None,
) -> tuple[AgentAssignment, bool]:
    with Session(engine, expire_on_commit=False) as db, db.begin():
        existing = db.scalar(select(AgentAssignment).where(
            AgentAssignment.account_id == account_id,
            AgentAssignment.request_key == request_key,
        ))
        normalized_as_of = as_of.astimezone(UTC).isoformat()
        refs = {"snapshot_id": snapshot_id, "as_of": normalized_as_of, **(linked_refs or {})}
        if existing:
            if existing.input_refs != refs or existing.kind != kind:
                raise ValueError("AGENT_REQUEST_KEY_CONFLICT")
            return existing, False
        now = datetime.now(UTC)
        assignment = AgentAssignment(
            account_id=account_id,
            request_key=request_key,
            kind=kind,
            state="QUEUED",
            created_at=now,
            deadline=min(now + timedelta(seconds=100), _as_utc(deadline)) if deadline else now + timedelta(seconds=100),
            input_refs=refs,
        )
        db.add(assignment)
        db.flush()
        return assignment, True


def _save(engine, assignment_id: UUID, *, state: str | None = None,
          outcome: dict | None = None, artifact: tuple[str, dict] | None = None) -> None:
    with Session(engine) as db, db.begin():
        assignment = db.get(AgentAssignment, assignment_id)
        if assignment is None:
            raise ValueError("AGENT_ASSIGNMENT_NOT_FOUND")
        if state is not None:
            assignment.state = state
        if outcome is not None:
            assignment.outcome = outcome
        if artifact is not None:
            db.add(AgentArtifact(
                assignment_id=assignment_id,
                kind=artifact[0],
                created_at=datetime.now(UTC),
                payload=artifact[1],
            ))


def _read_result(engine, assignment_id: UUID, account_id: UUID) -> WorkflowResult | None:
    with Session(engine) as db:
        assignment = db.get(AgentAssignment, assignment_id)
        if assignment is None or assignment.account_id != account_id:
            return None
        rows = db.scalars(select(AgentArtifact).where(
            AgentArtifact.assignment_id == assignment_id
        ).order_by(AgentArtifact.created_at, AgentArtifact.id).limit(100))
        return WorkflowResult(
            assignment_id=assignment_id,
            state=cast(WorkflowState, assignment.state),
            outcome=assignment.outcome or {},
            artifacts=[{"id": str(row.id), "kind": row.kind, **row.payload} for row in rows],
        )


def _require_result(engine, assignment_id: UUID, account_id: UUID) -> WorkflowResult:
    result = _read_result(engine, assignment_id, account_id)
    if result is None:
        raise ValueError("AGENT_ASSIGNMENT_NOT_FOUND")
    return result


def _claim_watcher_assignment(engine, assignment_id: UUID, account_id: UUID) -> tuple[dict, str]:
    """Atomically claim queued watcher work; expired and duplicate work never runs."""
    now = datetime.now(UTC)
    with Session(engine, expire_on_commit=False) as db, db.begin():
        assignment = db.scalar(
            select(AgentAssignment)
            .where(AgentAssignment.id == assignment_id, AgentAssignment.account_id == account_id)
            .with_for_update()
        )
        if assignment is None:
            raise ValueError("AGENT_ASSIGNMENT_NOT_FOUND")
        if assignment.kind != "WATCHER_STRATEGY_ASSESSMENT":
            raise ValueError("AGENT_ASSIGNMENT_NOT_WATCHER_WORK")
        if assignment.state == "RUNNING" and now >= _as_utc(assignment.deadline):
            payload = {"reason": "RUNNING_ASSIGNMENT_EXPIRED_AFTER_RESTART"}
            assignment.state = "EXPIRED"
            assignment.outcome = payload
            db.add(AgentArtifact(
                assignment_id=assignment.id,
                kind="OUTCOME",
                created_at=now,
                payload=payload,
            ))
            return {"id": assignment.id, "state": "EXPIRED", "outcome": payload}, "EXPIRED"
        if assignment.state != "QUEUED":
            return {
                "id": assignment.id,
                "state": assignment.state,
                "outcome": assignment.outcome or {},
            }, "NOT_QUEUED"
        if now >= _as_utc(assignment.deadline):
            payload = {"reason": "OPPORTUNITY_EXPIRED_BEFORE_CLAIM"}
            assignment.state = "EXPIRED"
            assignment.outcome = payload
            db.add(AgentArtifact(
                assignment_id=assignment.id,
                kind="OUTCOME",
                created_at=now,
                payload=payload,
            ))
            return {"id": assignment.id, "state": "EXPIRED", "outcome": payload}, "EXPIRED"
        assignment.state = "RUNNING"
        return {
            "id": assignment.id,
            "state": "RUNNING",
            "request_key": assignment.request_key,
            "deadline": assignment.deadline,
            "input_refs": dict(assignment.input_refs),
        }, "CLAIMED"


class AssessmentWorkflow:
    """Bounded reasoning path; no order creation or execution authority."""

    def __init__(self, engine, account_id: UUID, pipeline: AgentPipeline | None = None):
        self.engine = engine
        self.account_id = account_id
        self.pipeline = pipeline or AgentPipeline(engine, account_id)

    async def readback(self, assignment_id: UUID) -> WorkflowResult | None:
        """Read the assignment, bounded artifacts, and at most one research child."""
        result = await asyncio.to_thread(_read_result, self.engine, assignment_id, self.account_id)
        if result is None:
            return None
        links = []
        for artifact in result.artifacts:
            if artifact.get("kind") != "RESEARCH_ASSIGNMENT":
                continue
            child_id = UUID(str(artifact["child_assignment_id"]))
            child = await asyncio.to_thread(_read_result, self.engine, child_id, self.account_id)
            if child is not None:
                links.append({
                    "assignment_id": str(child.assignment_id),
                    "kind": "EXPLICIT_STRATEGY_RESEARCH",
                    "state": child.state,
                    "outcome": child.outcome,
                    "artifacts": child.artifacts,
                })
        return result.model_copy(update={"linked_assignments": links[:1]})

    async def request(
        self,
        *,
        request_key: str,
        snapshot_id: str,
        as_of: datetime,
        session: ExchangeSession,
    ) -> WorkflowResult:
        if not request_key or len(request_key) > 200:
            raise ValueError("AGENT_REQUEST_KEY_INVALID")
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("AGENT_AS_OF_MUST_BE_AWARE")
        assignment, created = await asyncio.to_thread(
            _create_assignment, self.engine, self.account_id, request_key, snapshot_id, as_of
        )
        if not created:
            current = await asyncio.to_thread(_read_result, self.engine, assignment.id, self.account_id)
            if current is not None:
                if current.state in {"RUNNING", "QUEUED"} and datetime.now(UTC) >= _as_utc(assignment.deadline):
                    payload = {"reason": "ORPHANED_ASSIGNMENT_EXPIRED"}
                    await asyncio.to_thread(_save, self.engine, assignment.id, state="EXPIRED",
                                            outcome=payload, artifact=("OUTCOME", payload))
                    return await self.readback(assignment.id) or current
                return await self.readback(assignment.id) or current
        await asyncio.to_thread(_save, self.engine, assignment.id, state="RUNNING")
        try:
            result = await self._run(assignment.id, snapshot_id, as_of, session)
        except asyncio.CancelledError:
            await asyncio.to_thread(
                _close_research_child, self.engine, self.account_id, request_key,
                "INTERRUPTED", {"reason": "PARENT_INTERRUPTED"},
            )
            await asyncio.to_thread(_save, self.engine, assignment.id, state="INTERRUPTED")
            raise
        except (ProviderError, ValueError) as error:
            state = _provider_failure_state(error) if isinstance(error, ProviderError) else "FAILED"
            result_payload = {"reason": str(error)[:120]}
            await asyncio.to_thread(
                _close_research_child, self.engine, self.account_id, request_key, state, result_payload
            )
            await asyncio.to_thread(
                _save, self.engine, assignment.id, state=state, outcome=result_payload,
                artifact=("OUTCOME", result_payload),
            )
            result = await asyncio.to_thread(_require_result, self.engine, assignment.id, self.account_id)
        except Exception as error:
            logger.exception("Assessment workflow failed", extra={"assignment_id": str(assignment.id)})
            result_payload = {
                "reason": "WORKFLOW_FAILURE",
                "error_type": type(error).__name__,
            }
            await asyncio.to_thread(
                _save, self.engine, assignment.id, state="FAILED", outcome=result_payload,
                artifact=("OUTCOME", result_payload),
            )
            result = await asyncio.to_thread(_require_result, self.engine, assignment.id, self.account_id)
        if result is None:
            raise ValueError("AGENT_ASSIGNMENT_NOT_FOUND")
        return await self.readback(assignment.id) or result

    async def run_queued_watcher_assignment(
        self, assignment_id: UUID, session: ExchangeSession
    ) -> WorkflowResult:
        """Claim and process one persisted watcher assignment with fixed input refs."""
        assignment, claim = await asyncio.to_thread(
            _claim_watcher_assignment, self.engine, assignment_id, self.account_id
        )
        if claim != "CLAIMED":
            return await self.readback(assignment_id) or WorkflowResult(
                assignment_id=assignment_id,
                state=cast(WorkflowState, assignment["state"]),
                outcome=assignment.get("outcome", {}),
                artifacts=[],
            )
        refs = assignment["input_refs"]
        if refs.get("session_key") != session.key.isoformat():
            payload = {"reason": "WATCHER_SESSION_MISMATCH"}
            await asyncio.to_thread(
                _save, self.engine, assignment_id, state="FAILED", outcome=payload,
                artifact=("OUTCOME", payload),
            )
            readback = await self.readback(assignment_id)
            if readback is not None:
                return readback
            return await asyncio.to_thread(
                _require_result, self.engine, assignment_id, self.account_id
            )
        snapshot_id = refs.get("snapshot_id")
        as_of_text = refs.get("as_of")
        try:
            as_of = datetime.fromisoformat(as_of_text)
        except (TypeError, ValueError):
            as_of = None
        if not isinstance(snapshot_id, str) or as_of is None or as_of.tzinfo is None:
            payload = {"reason": "WATCHER_INPUT_REFS_INVALID"}
            await asyncio.to_thread(
                _save, self.engine, assignment_id, state="FAILED", outcome=payload,
                artifact=("OUTCOME", payload),
            )
            readback = await self.readback(assignment_id)
            if readback is not None:
                return readback
            return await asyncio.to_thread(
                _require_result, self.engine, assignment_id, self.account_id
            )
        try:
            await self._guard_deadline(assignment_id)
            await self._run(assignment_id, snapshot_id, as_of, session)
        except asyncio.CancelledError:
            await asyncio.to_thread(
                _close_research_child, self.engine, self.account_id,
                assignment["request_key"], "INTERRUPTED", {"reason": "PARENT_INTERRUPTED"},
            )
            await asyncio.to_thread(_save, self.engine, assignment_id, state="INTERRUPTED")
            raise
        except (ProviderError, ValueError) as error:
            state = _provider_failure_state(error) if isinstance(error, ProviderError) else "FAILED"
            payload = {"reason": str(error)[:120]}
            await asyncio.to_thread(
                _close_research_child, self.engine, self.account_id,
                assignment["request_key"], state, payload,
            )
            await asyncio.to_thread(
                _save, self.engine, assignment_id, state=state, outcome=payload,
                artifact=("OUTCOME", payload),
            )
        except Exception as error:
            payload = {"reason": "WORKFLOW_FAILURE", "error_type": type(error).__name__}
            await asyncio.to_thread(
                _save, self.engine, assignment_id, state="FAILED", outcome=payload,
                artifact=("OUTCOME", payload),
            )
        readback = await self.readback(assignment_id)
        if readback is not None:
            return readback
        return await asyncio.to_thread(
            _require_result, self.engine, assignment_id, self.account_id
        )

    async def _run(
        self, assignment_id: UUID, snapshot_id: str, as_of: datetime, session: ExchangeSession
    ) -> WorkflowResult:
        def load_snapshot():
            with Session(self.engine) as db:
                batch = db.get(IndexHistoryBatch, snapshot_id)
                if batch is None or _as_utc(batch.received_at) > _as_utc(as_of):
                    return None
                raw = batch.payload.get("bars", [])
                bars = tuple(item for item in raw if datetime.fromisoformat(item["available_at"]) <= as_of)
                snapshot = ORBSnapshot(
                    snapshot_id=batch.snapshot_id,
                    source=batch.source,
                    underlying=batch.underlying,
                    exchange=batch.exchange,
                    as_of=as_of,
                    bars=bars,
                )
                metadata = {
                    "source": batch.source,
                    "underlying": batch.underlying,
                    "exchange": batch.exchange,
                    "received_at": _as_utc(batch.received_at),
                    "response_sha256": batch.response_sha256,
                }
                return snapshot, metadata

        loaded = await asyncio.to_thread(load_snapshot)
        if loaded is None:
            missing_result = SnapshotToolResult(
                status="UNAVAILABLE", snapshot_id=snapshot_id, as_of=as_of,
                bar_count=0, evidence_ids=[], reason="SNAPSHOT_MISSING_OR_LATE",
            )
            await asyncio.to_thread(_save, self.engine, assignment_id,
                                    artifact=("TOOL_RESULTS", {
                                        "read_index_snapshot": missing_result.model_dump(mode="json"),
                                        "assess_predefined_strategy": AssessmentToolResult(
                                            status="UNAVAILABLE", reason="SNAPSHOT_MISSING_OR_LATE"
                                        ).model_dump(mode="json"),
                                    }))
            return await self._finish(assignment_id, "UNAVAILABLE", {"reason": "SNAPSHOT_MISSING_OR_LATE"})
        snapshot, snapshot_metadata = loaded

        assessment = evaluate_orb(snapshot, session)
        def save_assessment():
            with Session(self.engine) as db, db.begin():
                saved_assessment = persist_assessment(db, assessment)
                plan = draft_strategy_plan(saved_assessment.id, assessment)
                persist_plan_draft(db, plan)
                return saved_assessment.id, plan
        assessment_id, plan_draft = await asyncio.to_thread(save_assessment)
        assignment_deadline = _as_utc(
            await asyncio.to_thread(_read_assignment_deadline, self.engine, assignment_id)
        )
        assessment_expiry = assessment.expires_at or session.closes_at
        context_expiry = min(_as_utc(assessment_expiry), assignment_deadline)
        assessment_context = AssessmentContext(
            assessment_id=assessment_id, strategy_id=assessment.strategy_id,
            version=assessment.version, definition_fingerprint=assessment.definition_fingerprint,
            snapshot_id=assessment.snapshot_id, status=assessment.status,
            evidence_ids=tuple(assessment.evidence_ids), as_of=assessment.as_of,
            expires_at=context_expiry,
        )
        evidence = {bar.evidence_id for bar in snapshot.bars}
        assessment_evidence = set(assessment_context.evidence_ids)
        typed_tools = {
            "read_indicator_context": {
                "status": "CONTEXT_ONLY_NOT_STRATEGY_OVERRIDE",
                **indicator_series({
                    "as_of": snapshot.as_of.isoformat(),
                    "sessions": [session.model_dump(mode="json")],
                    "bars": [{"opens_at": b.opens_at.isoformat(), "high": str(b.high),
                              "low": str(b.low), "close": str(b.close), "volume": None,
                              "state": "closed" if b.final else "provisional"} for b in snapshot.bars],
                }),
                "volume_semantics": "The index is not a traded instrument; no index VWAP is inferred.",
                "authority": "ORB assessment determines plan levels. Indicators cannot override it.",
            },
            "read_index_snapshot": SnapshotToolResult(
                status="OK" if snapshot.bars else "EMPTY",
                snapshot_id=snapshot.snapshot_id,
                source=snapshot_metadata["source"],
                underlying=snapshot_metadata["underlying"],
                exchange=snapshot_metadata["exchange"],
                received_at=snapshot_metadata["received_at"],
                as_of=snapshot.as_of,
                response_sha256=snapshot_metadata["response_sha256"],
                bar_count=len(snapshot.bars),
                evidence_ids=sorted(evidence),
            ).model_dump(mode="json"),
            "assess_predefined_strategy": AssessmentToolResult(
                status="OK", assessment_id=assessment_id,
                assessment=assessment.model_dump(mode="json"),
                context=assessment_context,
                plan_draft=plan_draft,
            ).model_dump(mode="json"),
        }
        await asyncio.to_thread(_save, self.engine, assignment_id, artifact=("TOOL_RESULTS", typed_tools))
        if assessment.status in {"UNAVAILABLE", "NOT_READY", "EXPIRED", "NOT_APPLICABLE"} or not snapshot.bars:
            classification = (
                "INSUFFICIENT_DATA" if assessment.status in {"UNAVAILABLE", "NOT_READY"}
                else "OUT_OF_SCOPE" if assessment.status == "NOT_APPLICABLE"
                else "EXPIRED"
            )
            return await self._finish(assignment_id, "UNAVAILABLE", {
                "reason": assessment.reason_codes[0] if assessment.reason_codes else assessment.status,
                "assessment_id": assessment_id,
                "classification": classification,
            })
        if datetime.now(UTC) >= _as_utc(await asyncio.to_thread(_read_assignment_deadline, self.engine, assignment_id)):
            return await self._finish(assignment_id, "EXPIRED", {"reason": "DEADLINE_EXPIRED"})
        if not self.pipeline.settings.ready():
            return await self._finish(assignment_id, "UNAVAILABLE", {"reason": "AI_NOT_CONFIGURED", "assessment_id": assessment_id})

        context = {
            "assignment_id": str(assignment_id),
            "objective": "Create a reviewed research/trading-plan draft. This artifact is never executable.",
            "assessment": assessment_context.model_dump(mode="json"),
            "plan_draft": plan_draft.model_dump(mode="json"),
            "selection_rules": {
                "SELECT": "Only when assessment status is BULLISH_SETUP or BEARISH_SETUP; copy exact strategy ID and version.",
                "RESEARCH": "Only when assessment status is NO_SETUP; propose an inactive candidate.",
                "INSUFFICIENT_DATA": "Use when evidence is missing or unavailable; never call it strategy failure.",
                "ABSTAIN": "Use when no supported judgment is appropriate.",
                "citations": "Cite only evidence IDs listed by the deterministic assessment.",
                "expiry": "Assessment expires_at is fixed; never extend it.",
            },
            "tools": typed_tools,
        }
        await self._guard_deadline(assignment_id)
        self._guard_context_expiry(assessment_context)
        analyst = await self.pipeline.provider.generate("strategy_analyst", context, AnalystDraft)
        await self._guard_deadline(assignment_id)
        self._guard_context_expiry(assessment_context)
        validate_analyst_output(analyst, assessment_context)
        analyst_payload = analyst.model_dump(mode="json")
        await asyncio.to_thread(_save, self.engine, assignment_id, artifact=("ANALYST_DRAFT", analyst_payload))
        if analyst.disposition == "ABSTAIN":
            return await self._finish(assignment_id, "ABSTAINED", {"reason": analyst.rationale})
        if analyst.disposition == "INSUFFICIENT_DATA":
            return await self._finish(assignment_id, "UNAVAILABLE", {
                "reason": analyst.rationale,
                "classification": "INSUFFICIENT_DATA",
                "assessment_id": assessment_id,
            })
        if analyst.disposition == "RESEARCH":
            if assessment.status != "NO_SETUP":
                raise ProviderError("AGENT_RESEARCH_BRANCH_NOT_JUSTIFIED")
            research_assignment, is_new = await asyncio.to_thread(
                _create_assignment, self.engine, self.account_id,
                f"{assignment_id}:research", snapshot_id, as_of,
                kind="EXPLICIT_STRATEGY_RESEARCH",
                linked_refs={
                    "parent_assignment_id": str(assignment_id),
                    "assessment_id": assessment_id,
                },
                deadline=assignment_deadline,
            )
            if not is_new:
                if research_assignment.state == "COMPLETED":
                    return await self._finish(assignment_id, "COMPLETED", {
                        "result": "RESEARCH_SAVED",
                        "research_assignment_id": str(research_assignment.id),
                        "assessment_id": assessment_id,
                    })
                parent_states: dict[str, WorkflowState] = {
                    "QUEUED": "RUNNING", "RUNNING": "RUNNING",
                    "UNAVAILABLE": "UNAVAILABLE", "ABSTAINED": "ABSTAINED",
                    "REJECTED": "REJECTED", "EXPIRED": "EXPIRED",
                    "FAILED": "FAILED", "INTERRUPTED": "INTERRUPTED",
                }
                parent_state = parent_states.get(research_assignment.state, "FAILED")
                partial = {
                    "result": "RESEARCH_NOT_COMPLETED",
                    "research_state": research_assignment.state,
                    "research_assignment_id": str(research_assignment.id),
                    "assessment_id": assessment_id,
                }
                await asyncio.to_thread(
                    _save, self.engine, assignment_id, state=parent_state, outcome=partial,
                    artifact=("RESEARCH_ASSIGNMENT", {
                        "child_assignment_id": str(research_assignment.id),
                        "assessment_id": assessment_id,
                        "snapshot_id": snapshot_id,
                    }),
                )
                return await asyncio.to_thread(_require_result, self.engine, assignment_id, self.account_id)
            await asyncio.to_thread(_save, self.engine, research_assignment.id, state="RUNNING")
            await asyncio.to_thread(
                _save, self.engine, assignment_id,
                outcome={"research_assignment_id": str(research_assignment.id),
                         "assessment_id": assessment_id, "state": "RESEARCH_PENDING"},
                artifact=("RESEARCH_ASSIGNMENT", {
                    "child_assignment_id": str(research_assignment.id),
                    "assessment_id": assessment_id,
                    "snapshot_id": snapshot_id,
                }),
            )
            await asyncio.to_thread(
                _save, self.engine, research_assignment.id,
                artifact=("RESEARCH_CONTEXT", {
                    "parent_assignment_id": str(assignment_id),
                    "assessment_id": assessment_id,
                    "snapshot_id": snapshot_id,
                    "strategy_id": assessment.strategy_id,
                    "strategy_version": assessment.version,
                    "assessment_status": assessment.status,
                    "as_of": assessment.as_of.isoformat(),
                    "expires_at": context_expiry.isoformat(),
                    "deadline": _as_utc(research_assignment.deadline).isoformat(),
                    "evidence_ids": sorted(assessment_evidence),
                }),
            )
            research_context = {**context, "assignment_id": str(research_assignment.id), "analyst_draft": analyst_payload,
                                "objective": "Propose one inactive, bounded alternative hypothesis and its evaluation method."}
            await self._guard_deadline(assignment_id)
            self._guard_context_expiry(assessment_context)
            hypothesis = await self.pipeline.provider.generate("strategy_research", research_context, ResearchHypothesis)
            await self._guard_deadline(assignment_id)
            self._guard_context_expiry(assessment_context)
            if not hypothesis.evidence_ids or not set(hypothesis.evidence_ids) <= assessment_evidence:
                raise ProviderError("AI_UNKNOWN_OR_MISSING_EVIDENCE")
            hypothesis_artifact = {
                **hypothesis.model_dump(mode="json"),
                "activation_state": "INACTIVE",
                "parent_assignment_id": str(assignment_id),
                "assessment_id": assessment_id,
                "snapshot_id": snapshot_id,
                "strategy_id": assessment.strategy_id,
                "strategy_version": assessment.version,
            }
            await asyncio.to_thread(_save, self.engine, research_assignment.id,
                                    state="COMPLETED", outcome={"result": "RESEARCH_SAVED"},
                                    artifact=("RESEARCH_HYPOTHESIS", hypothesis_artifact))
            return await self._finish(assignment_id, "COMPLETED", {
                "result": "RESEARCH_SAVED", "research_assignment_id": str(research_assignment.id),
                "assessment_id": assessment_id,
            })
        if not analyst.draft:
            raise ProviderError("AI_INCOMPLETE_PROPOSAL")
        review_context = {**context, "analyst_draft": analyst_payload}
        await self._guard_deadline(assignment_id)
        self._guard_context_expiry(assessment_context)
        review = await self.pipeline.provider.generate("strategy_reviewer", review_context, ReviewerResult)
        await self._guard_deadline(assignment_id)
        self._guard_context_expiry(assessment_context)
        if not review.evidence_ids or not set(review.evidence_ids) <= assessment_evidence:
            raise ProviderError("AI_UNKNOWN_OR_MISSING_EVIDENCE")
        if not set(analyst.evidence_ids) <= set(review.evidence_ids):
            raise ProviderError("AI_REVIEW_MISSING_EVIDENCE")
        review_payload = review.model_dump(mode="json")
        await asyncio.to_thread(_save, self.engine, assignment_id, artifact=("REVIEW", review_payload))
        if not review.approved:
            return await self._finish(assignment_id, "REJECTED", {"reason": review.rationale})
        await asyncio.to_thread(_save, self.engine, assignment_id,
                                artifact=("REVIEWED_DRAFT", {**analyst_payload, "review": review_payload,
                                                            "assessment": assessment_context.model_dump(mode="json")}))
        await self._finish(
            assignment_id, "COMPLETED",
            {"result": "REVIEWED_DRAFT_SAVED", "assessment_id": assessment_id},
        )

        def save_candidate():
            with Session(self.engine) as db, db.begin():
                return attach_candidate_to_completed_workflow(
                    db,
                    account_id=self.account_id,
                    assignment_id=assignment_id,
                    assessment_id=assessment_id,
                )

        await asyncio.to_thread(save_candidate)
        return await asyncio.to_thread(_require_result, self.engine, assignment_id, self.account_id)

    async def _finish(self, assignment_id: UUID, state: str, outcome: dict) -> WorkflowResult:
        await asyncio.to_thread(_save, self.engine, assignment_id, state=state,
                                outcome=outcome, artifact=("OUTCOME", outcome))
        result = await asyncio.to_thread(_read_result, self.engine, assignment_id, self.account_id)
        if result is None:
            raise ValueError("AGENT_ASSIGNMENT_NOT_FOUND")
        return result

    async def _guard_deadline(self, assignment_id: UUID) -> None:
        deadline = await asyncio.to_thread(_read_assignment_deadline, self.engine, assignment_id)
        if datetime.now(UTC) >= _as_utc(deadline):
            raise ProviderError("AGENT_ASSIGNMENT_EXPIRED")

    @staticmethod
    def _guard_context_expiry(context: AssessmentContext) -> None:
        if datetime.now(UTC) >= _as_utc(context.expires_at):
            raise ProviderError("AGENT_ASSESSMENT_CONTEXT_EXPIRED")


def _read_assignment_deadline(engine, assignment_id: UUID) -> datetime:
    with Session(engine) as db:
        row = db.get(AgentAssignment, assignment_id)
        if row is None:
            raise ValueError("AGENT_ASSIGNMENT_NOT_FOUND")
        return row.deadline


def _close_research_child(engine, account_id: UUID, request_key: str, state: str, outcome: dict) -> None:
    with Session(engine) as db, db.begin():
        child = db.scalar(select(AgentAssignment).where(
            AgentAssignment.account_id == account_id,
            AgentAssignment.request_key == f"{request_key}:research",
        ))
        if child is not None and child.state in {"QUEUED", "RUNNING"}:
            child.state = state
            child.outcome = outcome
