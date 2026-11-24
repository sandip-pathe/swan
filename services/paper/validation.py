"""Bounded paper-only leases. A stopped lease never grants autonomous qualification."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from services.core.contracts import IST, Instrument, Quote, RiskConfig
from services.core.models import (
    Account,
    AuditEvent,
    InstrumentRecord,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PaperValidation,
)
from services.core.setup import CONFIG_FILES, digest
from services.market.calendar import SessionCalendar
from services.market.credentials import SessionStore
from services.market.diagnostics import evidence_context
from services.market.readiness import connection_fingerprint, readiness
from services.market.settings import MarketSettings
from services.paper.accounting import ACTIVE, reconcile_account
from services.paper.bindings import qualification_binding
from services.paper.engine import PaperEngine
from services.paper.settings import configuration_status
from services.risk.engine import quote_problem
from services.worker.models import LatestMarketQuote, RuntimeControl


class ValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    instrument_id: str = Field(min_length=1, max_length=100)
    entry_source: Literal["AI", "HUMAN"] = "AI"
    duration_seconds: int = Field(default=300, ge=60, le=900, strict=True)


def input_binding(account: Account) -> str:
    """Persist hashes only; read current files so hot edits also invalidate a lease."""
    try:
        return digest(
            {
                "release": qualification_binding(account),
                "providers": {
                    name: connection_fingerprint(name) for name in ("broker", "ai", "news")
                },
            }
        )
    except (OSError, ValueError):
        raise ValueError("VALIDATION_INPUTS_UNAVAILABLE") from None


def current(db: Session, account_id: UUID) -> PaperValidation | None:
    return db.scalar(
        select(PaperValidation)
        .where(
            PaperValidation.account_id == account_id,
            PaperValidation.status.in_(("ACTIVE", "STOPPING")),
        )
        .with_for_update()
    )


def view(row: PaperValidation) -> dict:
    return {
        "id": str(row.id),
        "instrument_id": row.instrument_id,
        "exchange": row.exchange,
        "session_key": row.session_key.isoformat(),
        "status": row.status,
        "max_quantity": row.max_quantity,
        "max_entry_attempts": 1,
        "entry_source": row.request.get("entry_source", "AI"),
        "started_at": row.started_at.astimezone(UTC).isoformat(),
        "expires_at": row.expires_at.astimezone(UTC).isoformat(),
        "stopped_at": row.stopped_at.astimezone(UTC).isoformat() if row.stopped_at else None,
        "stop_reason": row.stop_reason,
        "input_digest": row.binding,
        "outcome": row.outcome,
        "autonomous_qualified": False,
    }


def event(db: Session, account: Account, name: str, now: datetime, **details) -> None:
    db.add(AuditEvent(account_id=account.id, kind=name, timestamp=now, details=details))


def problem(db: Session, account: Account, lease: PaperValidation, now: datetime) -> str | None:
    if lease.status != "ACTIVE":
        return "VALIDATION_STOPPING"
    if account.daily_blocked:
        return "VALIDATION_DAILY_LOSS"
    if (
        not lease.started_at <= now < lease.expires_at
        or lease.session_key != now.astimezone(IST).date()
    ):
        return "VALIDATION_EXPIRED"
    control = db.scalar(
        select(RuntimeControl).where(RuntimeControl.account_id == account.id).with_for_update()
    )
    if control is None or control.mode != "VALIDATION" or control.status == "MODE_SWITCHING":
        return "VALIDATION_WORKER_REQUIRED"
    if control.stream_generation != lease.stream_generation:
        return "VALIDATION_STREAM_CHANGED"
    if control.heartbeat is None or not timedelta(0) <= now - control.heartbeat <= timedelta(
        seconds=10
    ):
        return "VALIDATION_WORKER_STALE"
    try:
        binding = input_binding(account)
    except ValueError:
        return "VALIDATION_INPUTS_UNAVAILABLE"
    if binding != lease.binding:
        return "VALIDATION_INPUTS_CHANGED"
    return None


def entry_lease(
    db: Session,
    account: Account,
    now: datetime,
    instrument_id: str,
    quantity: int | None = None,
    order_id: UUID | None = None,
    entry_source: str = "AI",
) -> PaperValidation:
    """Caller holds account lock. Rechecked at submission and every BUY fill."""
    lease = current(db, account.id)
    if lease is None:
        raise ValueError("CONTROLLED_VALIDATION_REQUIRED")
    if lease.request.get("entry_source", "AI") != entry_source:
        raise ValueError("ENTRY_SOURCE_MISMATCH")
    reason = problem(db, account, lease, now)
    if reason:
        raise ValueError(reason)
    if (
        lease.instrument_id != instrument_id
        or quantity is not None
        and quantity > lease.max_quantity
    ):
        raise ValueError("VALIDATION_SCOPE_EXCEEDED")
    statement = (
        select(func.count())
        .select_from(PaperOrder)
        .where(PaperOrder.validation_id == lease.id, PaperOrder.side == "BUY")
    )
    if order_id is not None:
        statement = statement.where(PaperOrder.id != order_id)
    count = db.scalar(statement)
    if count:
        raise ValueError("VALIDATION_ENTRY_LIMIT")
    return lease


def halt(db: Session, account: Account, lease: PaperValidation, now: datetime, reason: str) -> None:
    if lease.status == "ACTIVE":
        lease.status, lease.stop_reason = "STOPPING", reason
        account.enabled = False
        account.revision += 1
        control = db.get(RuntimeControl, account.id)
        if control:
            control.resume_requested, control.active_envelope = False, None
            control.status = "VALIDATION_DRAINING"
        event(
            db,
            account,
            "VALIDATION_STOP_REQUESTED",
            now,
            validation_id=str(lease.id),
            reason=reason,
        )


def settle(db: Session, account: Account, lease: PaperValidation, now: datetime) -> None:
    if lease.status != "STOPPING":
        return
    # No false completion: even unrelated unresolved account exposure blocks settlement.
    active = db.scalar(
        select(PaperOrder.id)
        .where(PaperOrder.account_id == account.id, PaperOrder.status.in_(ACTIVE))
        .limit(1)
    )
    held = db.scalar(
        select(PaperPosition.id)
        .where(PaperPosition.account_id == account.id, PaperPosition.closed_at.is_(None))
        .limit(1)
    )
    if active or held or reconcile_account(db, account):
        return
    orders = list(db.scalars(select(PaperOrder).where(PaperOrder.validation_id == lease.id)))
    fills = list(
        db.scalars(select(PaperFill).join(PaperOrder).where(PaperOrder.validation_id == lease.id))
    )
    lease.status, lease.stopped_at = "STOPPED", now
    control = db.get(RuntimeControl, account.id)
    if control:
        control.status, control.problem = "VALIDATION_COMPLETE", None
    lease.outcome = {
        "entry_attempts": sum(o.side == "BUY" for o in orders),
        "orders": [{"id": str(o.id), "side": o.side, "status": o.status} for o in orders],
        "fills": [
            {
                "id": str(f.id),
                "order_id": str(f.order_id),
                "snapshot_id": str(f.snapshot_id),
                "market_event_id": f.market_event_id,
                "quantity": f.quantity,
                "price": str(f.price),
                "fees": str(f.fees),
                "fee_breakdown": f.fee_breakdown,
                "execution_version": f.execution_version,
                "cost_version": f.cost_version,
            }
            for f in fills
        ],
        "fees": str(sum((f.fees for f in fills), Decimal(0))),
        "reconciled": True,
        "result": "RECORDED_FILLS" if fills else "NO_TRADE_OBSERVED",
        "autonomous_qualified": False,
    }
    event(
        db, account, "VALIDATION_STOPPED", now, validation_id=str(lease.id), outcome=lease.outcome
    )


class ValidationService:
    def __init__(self, engine: Engine, account_id: UUID, clock: Callable[[], datetime] | None = None):
        self.engine, self.account_id = engine, account_id
        self.clock = clock

    def start(self, request: ValidationRequest, now: datetime) -> dict:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            now = self.clock() if self.clock else now
            previous = db.get(PaperValidation, request.request_id)
            if previous:
                if previous.account_id != account.id or {
                    "entry_source": "AI",
                    **previous.request,
                } != request.model_dump(mode="json"):
                    raise ValueError("VALIDATION_REQUEST_CONFLICT")
                return view(previous)
            control = db.scalar(
                select(RuntimeControl)
                .where(RuntimeControl.account_id == account.id)
                .with_for_update()
            )
            if control is None or control.mode != "VALIDATION":
                raise ValueError("VALIDATION_WORKER_REQUIRED")
            if control.status == "MODE_SWITCHING":
                raise ValueError("VALIDATION_WORKER_REQUIRED")
            if current(db, account.id) or account.enabled or control.resume_requested:
                raise ValueError("VALIDATION_ALREADY_ACTIVE_OR_ARMED")
            if account.revision != request.expected_revision:
                raise ValueError("SETTINGS_CHANGED_REFRESH_REQUIRED")
            if (
                db.scalar(
                    select(PaperOrder.id)
                    .where(PaperOrder.account_id == account.id, PaperOrder.status.in_(ACTIVE))
                    .limit(1)
                )
                or PaperEngine._open_positions(db, account.id)
                or reconcile_account(db, account)
            ):
                raise ValueError("VALIDATION_REQUIRES_FLAT_RECONCILED_ACCOUNT")
            report = readiness(
                now,
                account={"config": account.config},
                runtime={"heartbeat": control.heartbeat},
                **evidence_context(db, account.id),
            )
            if (
                not report["configuration_complete"]
                or not report["connections_verified"]
                or not report["worker_online"]
            ):
                raise ValueError("VALIDATION_PREFLIGHT_INCOMPLETE")
            record = db.get(InstrumentRecord, request.instrument_id)
            observed = db.get(LatestMarketQuote, request.instrument_id)
            if record is None or observed is None:
                raise ValueError("VALIDATION_FRESH_CONTRACT_REQUIRED")
            instrument = Instrument.model_validate(record.payload)
            quote = Quote.model_validate(observed.payload)
            risk = RiskConfig.model_validate(account.config)
            day = now.astimezone(IST).date()
            settings = MarketSettings()
            session = SessionCalendar(settings.calendar_file).get(instrument.exchange, day)
            if (
                instrument.exchange not in {"NFO", "BFO"}
                or not 0 <= (instrument.expiry - day).days <= 7
                or instrument.verified_at.astimezone(IST).date() != day
                or instrument.verified_at > now
                or instrument.lot_size > risk.max_fill_quantity
            ):
                raise ValueError("VALIDATION_INELIGIBLE_CONTRACT")
            if (
                session is None
                or not session.opens_at <= now < session.closes_at
                or account.session_key != day
                or account.daily_blocked
            ):
                raise ValueError("VALIDATION_OPEN_CURRENT_SESSION_REQUIRED")
            config = configuration_status(day, CONFIG_FILES["execution"])
            if not config["configuration_ready"]:
                raise ValueError("VALIDATION_EXECUTION_CONFIGURATION_INCOMPLETE")
            from services.core.execution import PaperExecutionConfig

            execution = PaperExecutionConfig.model_validate_json(
                CONFIG_FILES["execution"].read_text(encoding="utf-8")
            )
            from services.paper.matching import mapped_quote

            quote = mapped_quote(quote, execution)
            if (
                quote_problem(quote, now, risk.quote_max_age_seconds)
                or not quote.bid_depth
                or not quote.ask_depth
                or quote.timestamp_basis != "exchange_feed"
                or quote.depth_kind != "best_five"
                or not quote.market_event_id
                or quote.source not in {"angelone-websocket-v2:snapquote", "angelone-rest:full"}
            ):
                raise ValueError("VALIDATION_FRESH_DEPTH_REQUIRED")
            assert execution.execution.quote_max_age_ms is not None
            if (
                now - quote.timestamp
            ).total_seconds() * 1000 > execution.execution.quote_max_age_ms:
                raise ValueError("VALIDATION_FRESH_DEPTH_REQUIRED")
            expiries = [
                now + timedelta(seconds=request.duration_seconds),
                session.closes_at - timedelta(minutes=risk.entry_cutoff_minutes),
                SessionStore(settings.session_file, settings.client_code.get_secret_value())
                .load()
                .expires_at,
            ]
            expiries.extend(
                datetime.fromisoformat(check["checked_at"]) + timedelta(minutes=15)
                for check in report["checks"]
                if check.get("diagnostic")
            )
            expires = min(expiries)
            if expires - now < timedelta(seconds=60):
                raise ValueError("VALIDATION_WINDOW_TOO_SHORT")
            lease = PaperValidation(
                id=request.request_id,
                account_id=account.id,
                instrument_id=instrument.id,
                exchange=instrument.exchange,
                session_key=day,
                status="ACTIVE",
                max_quantity=instrument.lot_size,
                stream_generation=control.stream_generation,
                binding=input_binding(account),
                qualification_binding=qualification_binding(account),
                started_at=now,
                expires_at=expires,
                request=request.model_dump(mode="json"),
                preflight={**report, "instrument": instrument.model_dump(mode="json")},
            )
            db.add(lease)
            control.resume_requested, control.active_envelope, control.attempted_envelope_id = (
                True,
                None,
                None,
            )
            control.status = (
                "MANUAL_AWAITING_ENTRY"
                if request.entry_source == "HUMAN"
                else "VALIDATION_AWAITING_STRATEGY"
            )
            account.revision += 1
            event(
                db,
                account,
                "VALIDATION_STARTED",
                now,
                validation_id=str(lease.id),
                instrument_id=instrument.id,
                max_quantity=lease.max_quantity,
                expires_at=expires.isoformat(),
                input_digest=lease.binding,
            )
            return view(lease)

    def tick(self, now: datetime, *, force_reason: str | None = None) -> dict | None:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            now = self.clock() if self.clock else now
            lease = current(db, account.id)
            if lease is None:
                return None
            reason = force_reason or problem(db, account, lease, now)
            if lease.status == "ACTIVE" and not reason:
                entries = list(
                    db.scalars(
                        select(PaperOrder).where(
                            PaperOrder.validation_id == lease.id, PaperOrder.side == "BUY"
                        )
                    )
                )
                held = PaperEngine._open_positions(db, account.id)
                if entries and all(o.status not in ACTIVE for o in entries) and not held:
                    reason = "VALIDATION_ATTEMPT_FINISHED"
            if reason:
                halt(db, account, lease, now, reason)
            settle(db, account, lease, now)
            return view(lease)

    def stop(self, identifier: UUID, now: datetime) -> dict:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            lease = db.get(PaperValidation, identifier)
            if lease is None or lease.account_id != account.id:
                raise ValueError("VALIDATION_NOT_FOUND")
            halt(db, account, lease, now, "USER_STOP")
            settle(db, account, lease, now)
            return view(lease)

    def active_scope(self, now: datetime) -> dict | None:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            now = self.clock() if self.clock else now
            lease = current(db, account.id)
            if lease is None or problem(db, account, lease, now):
                return None
            used = db.scalar(
                select(PaperOrder.id)
                .where(PaperOrder.validation_id == lease.id, PaperOrder.side == "BUY")
                .limit(1)
            )
            return {**view(lease), "entry_used": used is not None}
