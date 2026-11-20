"""Server-derived live evidence and explicit, expiring autonomous paper permission."""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from services.core.contracts import IST, Instrument, Quote, RiskConfig, StrategyEnvelope
from services.core.models import (
    Account,
    AuditEvent,
    DecisionRecord,
    InstrumentRecord,
    PaperArm,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PaperQualification,
    PaperValidation,
    SnapshotRecord,
    StrategyRecord,
)
from services.core.setup import CONFIG_FILES
from services.market.calendar import SessionCalendar
from services.market.credentials import SessionStore
from services.market.diagnostics import evidence_context
from services.market.readiness import readiness
from services.market.settings import MarketSettings
from services.paper.accounting import ACTIVE, reconcile_account
from services.paper.bindings import qualification_binding
from services.paper.engine import PaperEngine
from services.paper.settings import configuration_status
from services.worker.models import EvaluationSlot, LatestMarketQuote, RuntimeControl

MATRIX_VERSION = "paper-live-v1"
VENUES = ("NFO", "BFO")
CRITERIA = (
    "round_trip",
    "protective_order",
    "stop_exit",
    "target_exit",
    "pause_cancel",
    "restart_recovery",
    "feed_gap",
    "expiry",
)
LIVE_SOURCES = {"angelone-websocket-v2:snapquote", "angelone-rest:full"}


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    session_ids: list[UUID] = Field(min_length=1, max_length=100)


class ArmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    qualification_id: UUID


def session_facts(db: Session, account: Account, row: PaperValidation, binding: str) -> dict:
    """Inspect original records, never accept outcome JSON as proof of fills."""
    facts: dict = {"session_id": str(row.id), "exchange": row.exchange, "checks": [], "scope": {}}
    if (
        row.request.get("entry_source", "AI") != "AI"
        or row.status != "STOPPED"
        or row.qualification_binding != binding
        or not row.stopped_at
    ):
        return facts
    if not all(
        row.preflight.get(key) is True
        for key in ("configuration_complete", "connections_verified", "worker_online")
    ):
        return facts
    orders = list(
        db.scalars(
            select(PaperOrder).where(
                PaperOrder.validation_id == row.id, PaperOrder.account_id == account.id
            )
        )
    )
    buys = [o for o in orders if o.side == "BUY"]
    if len(buys) != 1 or any(o.status in ACTIVE for o in orders):
        return facts
    buy = buys[0]
    stops = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.account_id == account.id,
                AuditEvent.kind == "VALIDATION_STOP_REQUESTED",
                AuditEvent.timestamp >= row.started_at,
                AuditEvent.timestamp <= row.stopped_at,
            )
        )
    )
    stop = next(
        (
            event
            for event in stops
            if event.details.get("validation_id") == str(row.id)
            and event.details.get("reason") == row.stop_reason
        ),
        None,
    )
    if stop is None or buy.accepted_at is None or buy.accepted_at >= stop.timestamp:
        return facts
    instrument_row = db.get(InstrumentRecord, row.instrument_id)
    decision = db.get(DecisionRecord, buy.decision_id) if buy.decision_id else None
    if instrument_row is None or decision is None or decision.account_id != account.id:
        return facts
    frozen_instrument = row.preflight.get("instrument")
    if not frozen_instrument:
        return facts
    instrument = Instrument.model_validate(frozen_instrument)
    current_instrument = Instrument.model_validate(instrument_row.payload)
    if instrument.model_dump(exclude={"verified_at"}) != current_instrument.model_dump(
        exclude={"verified_at"}
    ):
        return facts
    if (
        instrument.exchange != row.exchange
        or buy.instrument_id != row.instrument_id
        or buy.quantity > row.max_quantity
        or row.max_quantity != instrument.lot_size
    ):
        return facts
    strategy = db.get(StrategyRecord, UUID(decision.payload["strategy_id"]))
    slots = list(
        db.scalars(
            select(EvaluationSlot).where(
                EvaluationSlot.account_id == account.id,
                EvaluationSlot.validation_id == row.id,
                EvaluationSlot.status == "STRATEGY_APPROVED",
            )
        )
    )
    if strategy is None or strategy.account_id != account.id or not slots:
        return facts
    envelope = StrategyEnvelope.model_validate(strategy.payload)
    if not any(set(map(str, envelope.evidence_ids)) <= set(slot.evidence_ids) for slot in slots):
        return facts
    evaluations = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.account_id == account.id,
                AuditEvent.kind == "AGENT_EVALUATION",
                AuditEvent.timestamp >= row.started_at,
                AuditEvent.timestamp <= row.stopped_at,
            )
        )
    )
    if not any(
        a.details.get("evaluation_id") in {str(slot.id) for slot in slots}
        and (a.details.get("envelope") or {}).get("id") == str(envelope.id)
        for a in evaluations
    ):
        return facts
    outputs = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.account_id == account.id,
                AuditEvent.kind == "AI_OUTPUT",
                AuditEvent.timestamp >= row.started_at,
                AuditEvent.timestamp <= row.stopped_at,
            )
        )
    )
    reviews = [
        a
        for a in outputs
        if a.details.get("role") == "review"
        and a.details.get("response_id")
        and a.details.get("output", {}).get("approved") is True
        and set(map(str, envelope.evidence_ids)) <= set(a.details["output"].get("evidence_ids", []))
    ]
    if not reviews:
        return facts
    # Decision observations establish actual market provenance even for an unfilled cancellation.
    for identifier in envelope.evidence_ids:
        snapshot = db.get(SnapshotRecord, identifier)
        if snapshot is None:
            return facts
        quote = Quote.model_validate(snapshot.payload)
        if (
            quote.source not in LIVE_SOURCES
            or quote.timestamp_basis != "exchange_feed"
            or not quote.market_event_id
            or quote.instrument_id != row.instrument_id
        ):
            return facts
    fills = list(
        db.scalars(select(PaperFill).join(PaperOrder).where(PaperOrder.validation_id == row.id))
    )
    sides = {o.id: o.side for o in orders}
    for fill in fills:
        snapshot = db.get(SnapshotRecord, fill.snapshot_id)
        if snapshot is None or fill.timestamp is None:
            return facts
        quote = Quote.model_validate(snapshot.payload)
        if (
            quote.source not in LIVE_SOURCES
            or quote.timestamp_basis != "exchange_feed"
            or quote.depth_kind != "best_five"
            or quote.market_event_id != fill.market_event_id
            or not quote.market_event_id
            or quote.instrument_id != row.instrument_id
            or quote.quantity_unit != "units"
        ):
            return facts
        if not timedelta(0) <= fill.timestamp - quote.timestamp <= timedelta(seconds=2):
            return facts
        if sides[fill.order_id] == "BUY" and not row.started_at <= fill.timestamp < row.expires_at:
            return facts
        if sides[fill.order_id] == "BUY" and fill.timestamp >= stop.timestamp:
            return facts
    evidence_quotes = {str(f.snapshot_id) for f in fills}
    bought = sum(f.quantity for f in fills if sides[f.order_id] == "BUY")
    sold = sum(f.quantity for f in fills if sides[f.order_id] == "SELL")
    held = db.scalar(
        select(PaperPosition.id).where(
            PaperPosition.entry_order_id == buy.id, PaperPosition.closed_at.is_(None)
        )
    )
    if held or reconcile_account(db, account):
        return facts
    checks = facts["checks"]
    if bought > 0 and bought == sold and len(evidence_quotes) >= 2:
        checks.append("round_trip")
        facts["scope"] = {
            "instrument_id": instrument.id,
            "exchange": instrument.exchange,
            "max_quantity": instrument.lot_size,
            "expiry": instrument.expiry.isoformat(),
            "strategy_version": envelope.version,
            "instrument": instrument.model_dump(mode="json", exclude={"verified_at"}),
        }
        if any(
            o.side == "SELL" and o.order_type == "STOP_MARKET" and o.position_id for o in orders
        ):
            checks.append("protective_order")
        for code, reason in (("stop_exit", "STOP_LOSS"), ("target_exit", "TARGET")):
            if any(o.reason == reason and o.filled_quantity > 0 for o in orders):
                checks.append(code)
    if row.stop_reason == "USER_STOP" and not bought and buy.status == "CANCELLED":
        checks.append("pause_cancel")
    if row.stop_reason == "WORKER_RESTART":
        recovery = db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.account_id == account.id,
                AuditEvent.kind == "DURABLE_RECOVERY",
                AuditEvent.timestamp >= row.started_at,
                AuditEvent.timestamp <= row.stopped_at,
            )
            .order_by(AuditEvent.timestamp.desc())
            .limit(1)
        )
        if recovery and recovery.details.get("problems") == []:
            checks.append("restart_recovery")
    if row.stop_reason in {
        "VALIDATION_STREAM_CHANGED",
        "STREAM_NOT_READY",
        "EXIT_DATA_UNAVAILABLE",
    }:
        checks.append("feed_gap")
    if row.stop_reason == "VALIDATION_EXPIRED" and row.stopped_at >= row.expires_at:
        checks.append("expiry")
    return facts


def assess(db: Session, account: Account, rows: list[PaperValidation], binding: str) -> dict:
    facts = [session_facts(db, account, row, binding) for row in rows]
    checks = [
        {
            "code": venue + "_" + code.upper(),
            "passed": bool(
                proof := [
                    f["session_id"] for f in facts if f["exchange"] == venue and code in f["checks"]
                ]
            ),
            "evidence": proof,
        }
        for venue in VENUES
        for code in CRITERIA
    ]
    days = {
        row.session_key
        for row in rows
        if any(f["session_id"] == str(row.id) and "round_trip" in f["checks"] for f in facts)
    }
    starts = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.account_id == account.id, AuditEvent.kind == "SESSION_STARTED"
            )
        )
    )
    rollover = len(days) >= 2 and all(
        any(a.details.get("session") == day.isoformat() for a in starts) for day in days
    )
    checks.append(
        {
            "code": "SESSION_ROLLOVER",
            "passed": rollover,
            "evidence": [
                str(a.id)
                for a in starts
                if a.details.get("session") in {d.isoformat() for d in days}
            ],
        }
    )
    scope = [f["scope"] for f in facts if f["scope"]]
    return {
        "matrix_version": MATRIX_VERSION,
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "sessions": facts,
        "scope": scope,
    }


def qualified(db: Session, account: Account, row: PaperQualification | None, now: datetime) -> bool:
    if (
        row is None
        or row.account_id != account.id
        or row.revoked_at is not None
        or row.matrix_version != MATRIX_VERSION
        or not row.created_at <= now < row.valid_until
    ):
        return False
    try:
        if row.binding != qualification_binding(account):
            return False
        scopes = row.scope.get("instruments", [])
        for scope in scopes:
            record = db.get(InstrumentRecord, scope["instrument_id"])
            if record is None or Instrument.model_validate(record.payload).model_dump(
                mode="json", exclude={"verified_at"}
            ) != scope.get("instrument"):
                return False
        return bool(scopes)
    except ValueError:
        return False


def qualification_context(db: Session, account: Account, now: datetime) -> dict:
    latest = db.scalar(
        select(PaperQualification)
        .where(PaperQualification.account_id == account.id)
        .order_by(PaperQualification.created_at.desc())
        .limit(1)
    )
    return {"valid": qualified(db, account, latest, now), "id": str(latest.id) if latest else None}


def active_arm(db: Session, account: Account) -> PaperArm | None:
    return db.scalar(
        select(PaperArm)
        .where(PaperArm.account_id == account.id, PaperArm.status == "ACTIVE")
        .with_for_update()
    )


def arm_problem(db: Session, account: Account, arm: PaperArm, now: datetime) -> str | None:
    control = db.get(RuntimeControl, account.id)
    if arm.status != "ACTIVE" or not arm.started_at <= now < arm.expires_at:
        return "PAPER_ARM_EXPIRED"
    if control is None or control.mode != "AUTONOMOUS" or control.status == "MODE_SWITCHING":
        return "AUTONOMOUS_WORKER_REQUIRED"
    if account.daily_blocked or account.session_key != now.astimezone(IST).date():
        return "PAPER_ARM_SESSION_OR_LOSS_BLOCK"
    if control.heartbeat is None or not timedelta(0) <= now - control.heartbeat <= timedelta(
        seconds=10
    ):
        return "PAPER_ARM_WORKER_STALE"
    if control.stream_generation != arm.stream_generation:
        return "PAPER_ARM_STREAM_CHANGED"
    if not qualified(db, account, db.get(PaperQualification, arm.qualification_id), now):
        return "PAPER_QUALIFICATION_INVALIDATED"
    report = readiness(
        now,
        account={"config": account.config},
        runtime={"heartbeat": control.heartbeat},
        **evidence_context(db, account.id),
    )
    if not all(
        report[k] for k in ("configuration_complete", "connections_verified", "worker_online")
    ):
        return "PAPER_ARM_PREFLIGHT_INVALIDATED"
    return None


def disarm(db: Session, account: Account, now: datetime, reason: str) -> None:
    arm = active_arm(db, account)
    if arm:
        arm.status, arm.stopped_at, arm.stop_reason = "STOPPED", now, reason
        account.enabled = False
        account.revision += 1
        control = db.get(RuntimeControl, account.id)
        if control:
            control.resume_requested, control.active_envelope = False, None
            control.status = "PAPER_DISARMED"
        PaperEngine._event(db, account, "PAPER_DISARMED", now, arm_id=str(arm.id), reason=reason)


@dataclass(frozen=True)
class EntryPermission:
    validation_id: UUID | None
    arm_id: UUID | None
    max_quantity: int
    expires_at: datetime


def entry_permission(
    db: Session,
    account: Account,
    now: datetime,
    instrument_id: str,
    quantity: int | None = None,
    order_id: UUID | None = None,
    strategy_version: str | None = None,
    instrument: Instrument | None = None,
    entry_source: str = "AI",
) -> EntryPermission:
    control = db.scalar(
        select(RuntimeControl).where(RuntimeControl.account_id == account.id).with_for_update()
    )
    if control and control.mode == "VALIDATION":
        if entry_source == "HUMAN" and control.active_envelope:
            raise ValueError("ENTRY_SOURCE_MISMATCH")
        from services.paper.validation import entry_lease

        lease = entry_lease(db, account, now, instrument_id, quantity, order_id, entry_source)
        return EntryPermission(lease.id, None, lease.max_quantity, lease.expires_at)
    if entry_source != "AI":
        raise ValueError("MANUAL_VALIDATION_REQUIRED")
    arm = active_arm(db, account)
    if arm is None:
        raise ValueError("EXPLICIT_PAPER_ARM_REQUIRED")
    reason = arm_problem(db, account, arm, now)
    if reason:
        raise ValueError(reason)
    qualification = db.get(PaperQualification, arm.qualification_id)
    assert qualification is not None
    scopes = [
        s
        for s in qualification.scope["instruments"]
        if s["instrument_id"] == instrument_id
        and (strategy_version is None or s["strategy_version"] == strategy_version)
    ]
    record = db.get(InstrumentRecord, instrument_id)
    metadata = instrument or (Instrument.model_validate(record.payload) if record else None)
    scopes = [
        scope
        for scope in scopes
        if metadata is not None
        and metadata.model_dump(mode="json", exclude={"verified_at"}) == scope.get("instrument")
    ]
    if not scopes or quantity is not None and quantity > min(s["max_quantity"] for s in scopes):
        raise ValueError("PAPER_QUALIFICATION_SCOPE_EXCEEDED")
    return EntryPermission(None, arm.id, min(s["max_quantity"] for s in scopes), arm.expires_at)


def flat(db: Session, account: Account) -> bool:
    return (
        not db.scalar(
            select(PaperOrder.id)
            .where(PaperOrder.account_id == account.id, PaperOrder.status.in_(ACTIVE))
            .limit(1)
        )
        and not PaperEngine._open_positions(db, account.id)
        and not reconcile_account(db, account)
    )


def arm_view(row: PaperArm | None) -> dict | None:
    return (
        None
        if row is None
        else {
            "id": str(row.id),
            "status": row.status,
            "qualification_id": str(row.qualification_id),
            "expires_at": row.expires_at.astimezone(UTC).isoformat(),
            "stop_reason": row.stop_reason,
        }
    )


class QualificationService:
    def __init__(self, engine: Engine, account_id: UUID):
        self.engine, self.account_id = engine, account_id

    def status(self, now: datetime) -> dict:
        with Session(self.engine) as db:
            account = db.get(Account, self.account_id)
            if account is None:
                raise ValueError("PAPER_ACCOUNT_NOT_CONFIGURED")
            rows = list(
                db.scalars(
                    select(PaperValidation)
                    .where(PaperValidation.account_id == account.id)
                    .order_by(PaperValidation.started_at.desc())
                    .limit(101)
                )
            )
            binding = qualification_binding(account)
            truncated, rows = len(rows) > 100, rows[:100]
            latest = db.scalar(
                select(PaperQualification)
                .where(PaperQualification.account_id == account.id)
                .order_by(PaperQualification.created_at.desc())
                .limit(1)
            )
            arm = db.scalar(
                select(PaperArm)
                .where(PaperArm.account_id == account.id)
                .order_by(PaperArm.started_at.desc())
                .limit(1)
            )
            request_event = db.scalar(
                select(AuditEvent)
                .where(
                    AuditEvent.account_id == account.id, AuditEvent.kind == "WORKER_MODE_REQUESTED"
                )
                .order_by(AuditEvent.timestamp.desc())
                .limit(1)
            )
            switching = request_event is not None and now - request_event.timestamp < timedelta(
                seconds=45
            )
            return {
                "revision": account.revision,
                "history_truncated": truncated,
                "runtime": None
                if (control := db.get(RuntimeControl, account.id)) is None
                else {
                    "mode": control.mode,
                    "status": control.status,
                    "heartbeat": control.heartbeat.isoformat() if control.heartbeat else None,
                },
                "can_prepare": control is not None
                and (control.status != "MODE_SWITCHING" or not switching)
                and not account.enabled
                and not control.resume_requested
                and (arm is None or arm.status != "ACTIVE")
                and not db.scalar(
                    select(PaperValidation.id)
                    .where(
                        PaperValidation.account_id == account.id,
                        PaperValidation.status.in_(("ACTIVE", "STOPPING")),
                    )
                    .limit(1)
                )
                and flat(db, account),
                "binding": binding,
                "assessment": assess(db, account, rows, binding),
                "qualification": None
                if latest is None
                else {
                    "id": str(latest.id),
                    "valid": qualified(db, account, latest, now),
                    "valid_until": latest.valid_until.isoformat(),
                    "scope": latest.scope,
                },
                "arm": arm_view(arm),
            }

    def review(self, request: ReviewRequest, now: datetime) -> dict:
        from services.paper.validation import current

        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            previous = db.get(PaperQualification, request.request_id)
            if previous:
                if previous.account_id != account.id or previous.request != request.model_dump(
                    mode="json"
                ):
                    raise ValueError("QUALIFICATION_REQUEST_CONFLICT")
                return {"id": str(previous.id), "valid": qualified(db, account, previous, now)}
            if account.revision != request.expected_revision:
                raise ValueError("SETTINGS_CHANGED_REFRESH_REQUIRED")
            control = db.get(RuntimeControl, account.id)
            if (
                account.enabled
                or control
                and control.resume_requested
                or active_arm(db, account)
                or current(db, account.id)
                or not flat(db, account)
            ):
                raise ValueError("QUALIFICATION_REQUIRES_FLAT_PAUSED_ACCOUNT")
            if not configuration_status(now.astimezone(IST).date(), CONFIG_FILES["execution"])[
                "configuration_ready"
            ]:
                raise ValueError("QUALIFICATION_CONFIGURATION_INCOMPLETE")
            rows = list(
                db.scalars(
                    select(PaperValidation).where(
                        PaperValidation.account_id == account.id,
                        PaperValidation.id.in_(request.session_ids),
                    )
                )
            )
            if len(rows) != len(set(request.session_ids)):
                raise ValueError("QUALIFICATION_EVIDENCE_NOT_FOUND")
            binding = qualification_binding(account)
            report = assess(db, account, rows, binding)
            if not report["passed"]:
                raise ValueError("QUALIFICATION_EVIDENCE_INCOMPLETE")
            scopes = list(
                {(s["instrument_id"], s["strategy_version"]): s for s in report["scope"]}.values()
            )
            until = min(
                datetime.combine(
                    datetime.fromisoformat(s["expiry"]).date() + timedelta(days=1), time.min, IST
                )
                for s in scopes
            )
            if until <= now:
                raise ValueError("QUALIFICATION_CONTRACTS_EXPIRED")
            row = PaperQualification(
                id=request.request_id,
                account_id=account.id,
                binding=binding,
                matrix_version=MATRIX_VERSION,
                created_at=now,
                valid_until=until,
                evidence=report,
                scope={"instruments": scopes},
                request=request.model_dump(mode="json"),
            )
            db.add(row)
            account.revision += 1
            PaperEngine._event(
                db,
                account,
                "PAPER_QUALIFICATION_REVIEWED",
                now,
                qualification_id=str(row.id),
                binding=binding,
            )
            return {"id": str(row.id), "valid": True}

    def arm(self, request: ArmRequest, now: datetime) -> dict:
        from services.paper.validation import current

        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            previous = db.get(PaperArm, request.request_id)
            if previous:
                if previous.account_id != account.id or previous.request != request.model_dump(
                    mode="json"
                ):
                    raise ValueError("PAPER_ARM_REQUEST_CONFLICT")
                return arm_view(previous) or {}
            control = db.get(RuntimeControl, account.id)
            if (
                control is None
                or control.mode != "AUTONOMOUS"
                or control.status == "MODE_SWITCHING"
            ):
                raise ValueError("AUTONOMOUS_WORKER_REQUIRED")
            if account.revision != request.expected_revision:
                raise ValueError("SETTINGS_CHANGED_REFRESH_REQUIRED")
            if (
                account.enabled
                or control.resume_requested
                or active_arm(db, account)
                or current(db, account.id)
                or not flat(db, account)
            ):
                raise ValueError("PAPER_ARM_REQUIRES_FLAT_PAUSED_ACCOUNT")
            qualification = db.get(PaperQualification, request.qualification_id)
            if not qualified(db, account, qualification, now):
                raise ValueError("PAPER_QUALIFICATION_REQUIRED")
            assert qualification is not None
            report = readiness(
                now,
                account={"config": account.config},
                runtime={"heartbeat": control.heartbeat},
                **evidence_context(db, account.id),
            )
            if (
                not all(
                    report[k]
                    for k in ("configuration_complete", "connections_verified", "worker_online")
                )
                or account.daily_blocked
            ):
                raise ValueError("PAPER_ARM_PREFLIGHT_INCOMPLETE")
            settings, risk = MarketSettings(), RiskConfig.model_validate(account.config)
            ends = [
                qualification.valid_until,
                SessionStore(settings.session_file, settings.client_code.get_secret_value())
                .load()
                .expires_at,
            ]
            day = now.astimezone(IST).date()
            for scope in qualification.scope["instruments"]:
                record = db.get(InstrumentRecord, scope["instrument_id"])
                quote_row = db.get(LatestMarketQuote, scope["instrument_id"])
                if record is None or quote_row is None:
                    raise ValueError("PAPER_ARM_FRESH_SCOPE_REQUIRED")
                instrument = Instrument.model_validate(record.payload)
                if instrument.model_dump(mode="json", exclude={"verified_at"}) != scope.get(
                    "instrument"
                ):
                    raise ValueError("PAPER_ARM_FRESH_SCOPE_REQUIRED")
                session = SessionCalendar(settings.calendar_file).get(instrument.exchange, day)
                from services.risk.engine import quote_problem

                if (
                    instrument.verified_at.astimezone(IST).date() != day
                    or instrument.expiry < day
                    or instrument.lot_size != scope["max_quantity"]
                    or session is None
                    or not session.opens_at <= now < session.closes_at
                    or quote_problem(
                        Quote.model_validate(quote_row.payload), now, risk.quote_max_age_seconds
                    )
                    or account.session_key != day
                ):
                    raise ValueError("PAPER_ARM_FRESH_SCOPE_REQUIRED")
                ends.append(session.closes_at - timedelta(minutes=risk.entry_cutoff_minutes))
            ends.extend(
                datetime.fromisoformat(c["checked_at"]) + timedelta(minutes=15)
                for c in report["checks"]
                if c.get("diagnostic")
            )
            until = min(ends)
            if until <= now:
                raise ValueError("PAPER_ARM_WINDOW_CLOSED")
            row = PaperArm(
                id=request.request_id,
                account_id=account.id,
                qualification_id=qualification.id,
                status="ACTIVE",
                started_at=now,
                expires_at=until,
                stream_generation=control.stream_generation,
                request=request.model_dump(mode="json"),
            )
            db.add(row)
            control.resume_requested, control.active_envelope = True, None
            control.status = "PAPER_ARMED_AWAITING_STRATEGY"
            account.revision += 1
            PaperEngine._event(
                db,
                account,
                "PAPER_ARMED",
                now,
                arm_id=str(row.id),
                qualification_id=str(qualification.id),
                expires_at=until.isoformat(),
            )
            return arm_view(row) or {}

    def tick(self, now: datetime, reason: str | None = None) -> dict | None:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            arm = active_arm(db, account)
            if arm:
                problem = reason or arm_problem(db, account, arm, now)
                if problem:
                    disarm(db, account, now, problem)
            return arm_view(arm)

    def revoke(self, identifier: UUID, now: datetime) -> None:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            selected = db.get(PaperQualification, identifier)
            if selected is None or selected.account_id != account.id:
                raise ValueError("QUALIFICATION_NOT_FOUND")
            for row in db.scalars(
                select(PaperQualification).where(
                    PaperQualification.account_id == account.id,
                    PaperQualification.revoked_at.is_(None),
                )
            ):
                row.revoked_at = now
            disarm(db, account, now, "QUALIFICATION_REVOKED")
            account.revision += 1
            PaperEngine._event(
                db, account, "PAPER_QUALIFICATIONS_REVOKED", now, selected_id=str(identifier)
            )

    def scope(self, now: datetime) -> dict | None:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            arm = active_arm(db, account)
            if arm is None or arm_problem(db, account, arm, now):
                return None
            qualification = db.get(PaperQualification, arm.qualification_id)
            assert qualification is not None
            return {"arm_id": arm.id, "instruments": qualification.scope["instruments"]}
