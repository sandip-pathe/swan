from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.core.contracts import (
    ExchangeSession,
    Instrument,
    Quote,
    RiskConfig,
    StrategyEnvelope,
)
from services.core.models import (
    Account,
    AuditEvent,
    DisplaySelection,
    InstrumentRecord,
    PaperOrder,
    PaperPosition,
    SnapshotRecord,
    WatchlistItem,
)
from services.paper.accounting import ACTIVE
from services.paper.engine import PaperEngine
from services.worker.models import EvaluationSlot, LatestMarketQuote, RuntimeControl


class RuntimeStore:
    def __init__(self, engine: Engine, account_id: UUID):
        self.engine, self.account_id = engine, account_id

    def publish_references(self, references) -> None:
        from services.market.references import save_reference

        with Session(self.engine) as db, db.begin():
            for reference in references:
                save_reference(db, reference)

    def display_instruments(self, now: datetime) -> list[Instrument]:
        with Session(self.engine) as db:
            selected = db.scalar(
                select(DisplaySelection).where(
                    DisplaySelection.account_id == self.account_id,
                    DisplaySelection.expires_at > now,
                )
            )
            ids = ([selected.instrument_id] if selected else []) + list(
                db.scalars(
                    select(WatchlistItem.instrument_id)
                    .where(WatchlistItem.account_id == self.account_id)
                    .order_by(WatchlistItem.saved_at.desc(), WatchlistItem.instrument_id)
                    .limit(50)
                )
            )
            records = {
                row.id: row
                for row in db.scalars(select(InstrumentRecord).where(InstrumentRecord.id.in_(ids)))
            }
            return [
                Instrument.model_validate(records[key].payload)
                for key in dict.fromkeys(ids)
                if key in records
            ]

    def initialize(self, now: datetime, mode: str = "OBSERVATION") -> None:
        from services.paper.qualification import disarm
        from services.paper.validation import current, halt, settle

        if mode not in {"OBSERVATION", "VALIDATION", "AUTONOMOUS"}:
            raise ValueError("Unknown worker mode")
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            disarm(db, account, now, "WORKER_RESTART")
            validation = current(db, account.id)
            if validation:
                halt(db, account, validation, now, "WORKER_RESTART")
                settle(db, account, validation, now)
            if account.enabled:
                account.enabled = False
                account.revision += 1
            control = db.get(RuntimeControl, self.account_id)
            if control is None:
                control = RuntimeControl(account_id=self.account_id)
                db.add(control)
            control.resume_requested = False
            control.mode = mode
            control.active_envelope = None
            control.status = "STARTING"
            control.heartbeat = now

    def publish_quotes(self, instruments: dict[str, Instrument], quotes: list[Quote]) -> None:
        if not quotes:
            return
        # All bulk publishers acquire shared instrument rows in the same order.
        quotes = sorted(quotes, key=lambda quote: quote.instrument_id)
        with Session(self.engine) as db, db.begin():
            for quote in quotes:
                PaperEngine._persist_instrument(db, instruments[quote.instrument_id])
            statement = insert(LatestMarketQuote).values(
                [
                    {
                        "instrument_id": quote.instrument_id,
                        "timestamp": quote.timestamp,
                        "payload": quote.model_dump(mode="json"),
                    }
                    for quote in quotes
                ]
            )
            db.execute(
                statement.on_conflict_do_update(
                    index_elements=[LatestMarketQuote.instrument_id],
                    set_={
                        "timestamp": statement.excluded.timestamp,
                        "payload": statement.excluded.payload,
                    },
                    where=LatestMarketQuote.timestamp <= statement.excluded.timestamp,
                )
            )

    def state(self) -> dict:
        with Session(self.engine) as db:
            account = db.get(Account, self.account_id)
            control = db.get(RuntimeControl, self.account_id)
            if account is None or control is None:
                raise ValueError("Runtime account is not initialized")
            return {
                "enabled": account.enabled,
                "daily_blocked": account.daily_blocked,
                "session_key": account.session_key,
                "config": RiskConfig.model_validate(account.config),
                "resume_requested": control.resume_requested,
                "session": ExchangeSession.model_validate(control.session_payload)
                if control.session_payload
                else None,
                "envelope": StrategyEnvelope.model_validate(control.active_envelope)
                if control.active_envelope
                else None,
                "attempted_envelope_id": control.attempted_envelope_id,
                "runtime_status": control.status,
                "mode": control.mode,
                "problem": control.problem,
                "heartbeat": control.heartbeat.isoformat() if control.heartbeat else None,
            }

    def enable_requested(self, envelope_id: UUID, generation: int, now: datetime) -> bool:
        """Recheck the request under lock so a concurrent user pause always wins."""
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            control = db.scalar(
                select(RuntimeControl)
                .where(RuntimeControl.account_id == self.account_id)
                .with_for_update()
            )
            if (
                control is None
                or not control.resume_requested
                or account.daily_blocked
                or account.session_key is None
                or not PaperEngine._reconcile(db, account)
                or any(
                    position.pending_exit
                    for position in PaperEngine._open_positions(db, account.id)
                )
                or control.stream_generation != generation
                or not control.active_envelope
            ):
                return False
            envelope = StrategyEnvelope.model_validate(control.active_envelope)
            if envelope.id != envelope_id or not envelope.issued_at <= now < envelope.expires_at:
                return False
            from services.paper.qualification import entry_permission

            try:
                for identifier in envelope.instrument_ids:
                    entry_permission(
                        db, account, now, identifier, strategy_version=envelope.version
                    )
            except ValueError:
                return False
            account.enabled = True
            account.revision += 1
            control.status, control.problem = "RUNNING", None
            db.add(
                AuditEvent(
                    account_id=self.account_id,
                    kind="RESUME_PREFLIGHT_PASSED",
                    timestamp=now,
                    details={"envelope_id": str(envelope_id)},
                )
            )
            return True

    def enable_manual_requested(self, validation_id: UUID, generation: int, now: datetime) -> bool:
        """Enable only a still-requested, bounded HUMAN lease; a pause always wins."""
        from services.paper.validation import current, entry_lease

        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            control = db.scalar(
                select(RuntimeControl)
                .where(RuntimeControl.account_id == account.id)
                .with_for_update()
            )
            if (
                control is None
                or control.mode != "VALIDATION"
                or not control.resume_requested
                or control.active_envelope
                or control.stream_generation != generation
                or account.daily_blocked
                or not PaperEngine._reconcile(db, account)
                or PaperEngine._open_positions(db, account.id)
            ):
                return False
            lease = current(db, account.id)
            if (
                lease is None
                or lease.id != validation_id
                or account.session_key != lease.session_key
            ):
                return False
            try:
                entry_lease(db, account, now, lease.instrument_id, entry_source="HUMAN")
            except ValueError:
                return False
            if not account.enabled:
                account.enabled = True
                account.revision += 1
                PaperEngine._event(
                    db,
                    account,
                    "MANUAL_PREFLIGHT_PASSED",
                    now,
                    validation_id=str(lease.id),
                    entry_source="HUMAN",
                )
            control.status, control.problem = "MANUAL_READY", None
            return True

    def update(self, **changes) -> None:
        with Session(self.engine) as db, db.begin():
            # Admission captures its clock while holding this same account
            # lock. Serialize heartbeat writes with it so a concurrent update
            # cannot appear newer than that admission's observation time.
            PaperEngine._account(db, self.account_id)
            control = db.scalar(
                select(RuntimeControl)
                .where(RuntimeControl.account_id == self.account_id)
                .with_for_update()
            )
            if control is None:
                raise ValueError("Unknown runtime")
            for name, value in changes.items():
                if name not in {
                    "status",
                    "problem",
                    "heartbeat",
                    "session_payload",
                    "resume_requested",
                    "active_envelope",
                    "attempted_envelope_id",
                    "stream_generation",
                }:
                    raise ValueError("Unsupported runtime field")
                setattr(control, name, value)

    def open_instruments(self) -> list[Instrument]:
        with Session(self.engine) as db:
            records = db.scalars(
                select(InstrumentRecord).where(
                    InstrumentRecord.id.in_(
                        select(PaperPosition.instrument_id).where(
                            PaperPosition.account_id == self.account_id,
                            PaperPosition.closed_at.is_(None),
                        )
                    )
                    | InstrumentRecord.id.in_(
                        select(PaperOrder.instrument_id).where(
                            PaperOrder.account_id == self.account_id, PaperOrder.status.in_(ACTIVE)
                        )
                    )
                )
            )
            return [Instrument.model_validate(record.payload) for record in records]

    def save_evaluation(
        self,
        session: ExchangeSession,
        slot: datetime,
        instruments: dict[str, Instrument],
        quotes: list[Quote],
        now: datetime,
    ) -> UUID | None:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            validation_id = None
            arm_id = None
            control = db.get(RuntimeControl, account.id)
            if control and control.mode == "VALIDATION":
                from services.paper.validation import entry_lease

                try:
                    for quote in quotes:
                        lease = entry_lease(db, account, now, quote.instrument_id)
                        validation_id = lease.id
                except ValueError:
                    return None
                if validation_id is None:
                    return None
            elif control and control.mode == "AUTONOMOUS":
                from services.paper.qualification import entry_permission

                try:
                    for quote in quotes:
                        permission = entry_permission(db, account, now, quote.instrument_id)
                        arm_id = permission.arm_id
                except ValueError:
                    return None
                if arm_id is None:
                    return None
            else:
                return None
            existing = db.scalar(
                select(EvaluationSlot).where(
                    EvaluationSlot.account_id == account.id,
                    EvaluationSlot.session_key == session.key,
                    EvaluationSlot.slot_at == slot,
                )
            )
            if existing:
                return None
            evidence = []
            for quote in sorted(quotes, key=lambda quote: quote.instrument_id):
                PaperEngine._persist_instrument(db, instruments[quote.instrument_id])
                PaperEngine._persist_quote(db, quote)
                evidence.append(str(quote.id))
            record = EvaluationSlot(
                arm_id=arm_id,
                validation_id=validation_id,
                account_id=account.id,
                session_key=session.key,
                slot_at=slot,
                status="AWAITING_AGENT" if evidence else "BLOCKED_NO_FRESH_DATA",
                evidence_ids=evidence,
            )
            db.add(record)
            db.flush()
            return record.id

    def finish_evaluation(
        self,
        identifier: UUID,
        status: str,
        generation: int,
        envelope: StrategyEnvelope | None,
        now: datetime,
    ) -> None:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            control = db.scalar(
                select(RuntimeControl)
                .where(RuntimeControl.account_id == self.account_id)
                .with_for_update()
            )
            slot = db.get(EvaluationSlot, identifier)
            if control is None or slot is None or slot.account_id != self.account_id:
                raise ValueError("Unknown evaluation")
            preserve_orb = bool(
                control.active_envelope
                and control.active_envelope.get("version", "").startswith("S01-NIFTY-ORB-PAPER:")
            )
            if preserve_orb:
                status, envelope = "SUPERSEDED_BY_ORB_PLAN", None
            if (
                envelope is not None
                and slot.validation_id is not None
                and control.mode != "VALIDATION"
            ):
                status, envelope = "INVALIDATED_DURING_ANALYSIS", None
            if envelope is not None:
                if control.mode == "VALIDATION":
                    from services.paper.validation import entry_lease

                    try:
                        for instrument_id in envelope.instrument_ids:
                            lease = entry_lease(db, account, now, instrument_id)
                            if lease.id != slot.validation_id:
                                raise ValueError("VALIDATION_EVALUATION_MISMATCH")
                    except ValueError:
                        status, envelope = "INVALIDATED_DURING_ANALYSIS", None
                elif control.mode == "AUTONOMOUS":
                    from services.paper.qualification import entry_permission

                    try:
                        for instrument_id in envelope.instrument_ids:
                            permission = entry_permission(
                                db, account, now, instrument_id, strategy_version=envelope.version
                            )
                            if permission.arm_id != slot.arm_id:
                                raise ValueError("PAPER_ARM_EVALUATION_MISMATCH")
                    except ValueError:
                        status, envelope = "INVALIDATED_DURING_ANALYSIS", None
                else:
                    status, envelope = "INVALIDATED_DURING_ANALYSIS", None
            if envelope is not None:
                if (
                    control.stream_generation != generation
                    or envelope.invalidated
                    or not envelope.issued_at <= now < envelope.expires_at
                    or not set(map(str, envelope.evidence_ids)) <= set(slot.evidence_ids)
                ):
                    status, envelope = "INVALIDATED_DURING_ANALYSIS", None
            slot.status = status
            if control.stream_generation == generation and not preserve_orb:
                control.active_envelope = envelope.model_dump(mode="json") if envelope else None
                control.attempted_envelope_id = None
            db.add(
                AuditEvent(
                    account_id=self.account_id,
                    kind="AGENT_EVALUATION",
                    timestamp=now,
                    details={
                        "evaluation_id": str(identifier),
                        "status": status,
                        "envelope": envelope.model_dump(mode="json") if envelope else None,
                    },
                )
            )

    def approve_envelope(self, envelope: StrategyEnvelope, now: datetime) -> None:
        """Internal integration point for the future real agent, never a public route."""
        if envelope.invalidated or not envelope.issued_at <= now < envelope.expires_at:
            raise ValueError("Strategy envelope is not current")
        with Session(self.engine) as db, db.begin():
            control = db.scalar(
                select(RuntimeControl)
                .where(RuntimeControl.account_id == self.account_id)
                .with_for_update()
            )
            if control is None:
                raise ValueError("Unknown runtime")
            if not all(db.get(SnapshotRecord, identifier) for identifier in envelope.evidence_ids):
                raise ValueError("Strategy evidence is unavailable")
            control.active_envelope = envelope.model_dump(mode="json")
            control.attempted_envelope_id = None
