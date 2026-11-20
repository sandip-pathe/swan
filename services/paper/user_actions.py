"""Owned, idempotent paper controls. Exit intent is durable; fills stay with the watchdog."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from services.core.models import Account, AuditEvent, PaperOrder, PaperPosition
from services.paper.accounting import LEGACY
from services.paper.coordinator import PRIORITY
from services.paper.engine import ConflictError, PaperEngine
from services.paper.orders import DurableOrderLedger
from services.paper.qualification import disarm
from services.paper.validation import current, halt
from services.worker.models import RuntimeControl


class PaperUserActions:
    def __init__(
        self, engine: Engine, account_id: UUID, clock: Callable[[], datetime] | None = None
    ):
        self.engine, self.account_id = engine, account_id
        self.clock = clock or (lambda: datetime.now(UTC))
        self.ledger = DurableOrderLedger(engine, self.clock)

    @staticmethod
    def _intent(
        db: Session, account: Account, request_id: UUID, kind: str, target: UUID, now: datetime
    ) -> bool:
        prior = db.get(AuditEvent, request_id)
        details = {"resource_id": str(target), "source": "USER"}
        if prior:
            if prior.account_id != account.id or prior.kind != kind or prior.details != details:
                raise ConflictError("PAPER_ACTION_REQUEST_CONFLICT")
            return False
        db.add(
            AuditEvent(
                id=request_id, account_id=account.id, kind=kind, timestamp=now, details=details
            )
        )
        return True

    def cancel_entry(self, order_id: UUID, request_id: UUID) -> dict:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            order = db.get(PaperOrder, order_id)
            if order is None or order.account_id != account.id:
                raise ValueError("PAPER_ORDER_NOT_FOUND")
            if order.execution_version == LEGACY or order.side != "BUY":
                raise ValueError("PAPER_ENTRY_CANCEL_ONLY")
            self.ledger._check(db, account)
            self._intent(db, account, request_id, "USER_ENTRY_CANCEL", order.id, self.clock())
        # The ledger owns the fill/cancel race. Until acknowledgment, holds remain.
        key = "user-cancel:" + str(request_id)
        self.ledger.cancel(self.account_id, order_id, key + ":request", self.clock())
        result = self.ledger.cancel(
            self.account_id, order_id, key + ":ack", self.clock(), confirm=True
        )
        return {**result, "request_id": str(request_id), "kind": "CANCEL_ENTRY"}

    def exit_position(self, position_id: UUID, request_id: UUID) -> dict:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            position = db.get(PaperPosition, position_id)
            if position is None or position.account_id != account.id:
                raise ValueError("PAPER_POSITION_NOT_FOUND")
            entry = db.get(PaperOrder, position.entry_order_id)
            if entry is None or entry.account_id != account.id or entry.execution_version == LEGACY:
                raise ValueError("PAPER_DURABLE_POSITION_REQUIRED")
            self.ledger._check(db, account)
            fresh = self._intent(
                db, account, request_id, "USER_POSITION_EXIT", position.id, self.clock()
            )
            if fresh and position.closed_at is None:
                now = self.clock()
                disarm(db, account, now, "USER_EXIT")
                lease = current(db, account.id)
                if lease:
                    halt(db, account, lease, now, "USER_EXIT")
                account.enabled = False
                control = db.get(RuntimeControl, account.id)
                if control:
                    control.resume_requested, control.active_envelope = False, None
                    control.status = "USER_EXIT_REQUESTED"
                if position.pending_exit is None or PRIORITY.get("USER_EXIT", 0) < PRIORITY.get(
                    position.pending_exit, 0
                ):
                    position.pending_exit = "USER_EXIT"
                account.revision += 1
                PaperEngine._event(
                    db,
                    account,
                    "USER_EXIT_REQUESTED",
                    now,
                    position_id=str(position.id),
                    request_id=str(request_id),
                )
            return {
                "request_id": str(request_id),
                "position_id": str(position.id),
                "status": "CLOSED" if position.closed_at else "EXIT_REQUESTED",
                "remaining_quantity": position.quantity - position.closed_quantity,
                "pending_exit": position.pending_exit,
                "new_entries_paused": not account.enabled,
            }
