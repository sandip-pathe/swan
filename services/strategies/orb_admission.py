"""Stage reviewed ORB plans through existing paper authority, never create it."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from services.core.contracts import ExchangeSession, Instrument, Quote, RiskConfig
from services.core.execution import PaperExecutionConfig
from services.core.models import DecisionRecord, StrategyPaperPlanCandidateRecord
from services.market.reference_contracts import IndexReference
from services.paper.engine import PaperEngine
from services.paper.matching import mapped_quote
from services.paper.qualification import entry_permission, flat
from services.paper.settings import DEFAULT_CONFIG, configuration_status
from services.strategies.contracts import StrategyPaperPlanCandidate
from services.strategies.orb_execution import PreparedORB, prepare_orb_execution
from services.strategies.paper_admission import candidate_provenance_valid
from services.worker.models import RuntimeControl


def stage_orb_candidate(
    engine: Engine,
    account_id: UUID,
    candidate_id: str,
    *,
    instruments: list[Instrument],
    quotes: dict[str, Quote],
    reference: IndexReference,
    session: ExchangeSession,
    now: datetime,
) -> PreparedORB:
    """Stage only under an existing scoped validation session or paper arm.

    This does not start a worker, enable entries, qualify, arm, place an order,
    or mutate the research candidate. Normal coordinator admission still runs.
    """
    with Session(engine) as db, db.begin():
        account = PaperEngine._account(db, account_id)
        control = db.get(RuntimeControl, account_id)
        if (
            account.daily_blocked or account.session_key != session.key
            or control is None or control.mode not in {"AUTONOMOUS", "VALIDATION"}
            or not (account.enabled or control.resume_requested)
        ):
            raise ValueError("ORB_ARMED_AUTONOMOUS_ACCOUNT_REQUIRED")
        if control.active_envelope or not flat(db, account):
            raise ValueError("ORB_EXISTING_STRATEGY_OR_EXPOSURE")
        record = db.get(StrategyPaperPlanCandidateRecord, candidate_id)
        if record is None:
            raise ValueError("PAPER_PLAN_CANDIDATE_NOT_FOUND")
        candidate = StrategyPaperPlanCandidate.model_validate(record.payload)
        if not candidate_provenance_valid(db, record, candidate, account_id=account_id):
            raise ValueError("PAPER_CANDIDATE_PROVENANCE_INVALID")
        risk = RiskConfig.model_validate(account.config)
        execution = PaperExecutionConfig.model_validate_json(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        quotes = {key: mapped_quote(quote, execution) for key, quote in quotes.items()}
        prepared = prepare_orb_execution(
            candidate, account_id=account_id, instruments=instruments, quotes=quotes,
            reference=reference, session=session, risk=risk, now=now,
        )
        lease = entry_permission(
            db, account, now, prepared.instrument.id,
            strategy_version=prepared.envelope.version, instrument=prepared.instrument,
        )
        if lease.arm_id is None and lease.validation_id is None:
            raise ValueError("EXPLICIT_CURRENT_PAPER_ARM_REQUIRED")
        status = configuration_status(session.key, qualification_valid=lease.arm_id is not None)
        configuration_ready = (
            status.get("engine_ready") if lease.arm_id is not None
            else status.get("configuration_ready")
        )
        if not configuration_ready:
            raise ValueError("ORB_EXECUTION_CONFIGURATION_NOT_READY")
        # Stable account/day identity prevents a different candidate from buying
        # a second chance after a rejected, cancelled or filled entry decision.
        if db.get(DecisionRecord, prepared.decision.id) is not None:
            raise ValueError("ORB_SESSION_ENTRY_ALREADY_ATTEMPTED")
        PaperEngine._persist_instrument(db, prepared.instrument)
        PaperEngine._persist_quote(db, quotes[prepared.instrument.id])
        control.active_envelope = prepared.envelope.model_dump(mode="json")
        control.attempted_envelope_id = None
        PaperEngine._event(
            db, account, "ORB_CANDIDATE_STAGED", now,
            candidate_id=candidate_id, strategy_id=str(prepared.envelope.id),
            review_artifact_id=str(candidate.review_artifact_id),
            underlying_reference=reference.model_dump(mode="json"),
        )
        return prepared


def latest_orb_candidate(engine: Engine, account_id: UUID, session: ExchangeSession) -> str | None:
    """Read only the owner's candidate through its reviewed assignment."""
    from services.core.models import AgentAssignment, StrategyAssessmentRecord

    with Session(engine) as db:
        return db.scalar(
            select(StrategyPaperPlanCandidateRecord.candidate_id)
            .join(AgentAssignment,
                  AgentAssignment.id == StrategyPaperPlanCandidateRecord.review_assignment_id)
            .join(StrategyAssessmentRecord,
                  StrategyAssessmentRecord.id == StrategyPaperPlanCandidateRecord.assessment_id)
            .where(AgentAssignment.account_id == account_id,
                   StrategyAssessmentRecord.session_key == session.key)
            .order_by(StrategyPaperPlanCandidateRecord.created_at.desc())
            .limit(1)
        )
