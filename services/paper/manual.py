"""Human paper admission, using owned plans and bounded source-specific permission."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from services.core.contracts import ExchangeSession, Instrument, Quote, RiskConfig
from services.core.execution import PaperExecutionConfig
from services.core.models import (
    InstrumentRecord,
    ManualIntentRecord,
    ManualPaperPlan,
    PaperLiquidityLevel,
    PaperOrder,
)
from services.paper.contracts import ManualEntryIntent, OrderRequest, OrderRiskApproval
from services.paper.engine import ConflictError, PaperEngine
from services.paper.matching import mapped_quote
from services.paper.orders import DurableOrderLedger
from services.paper.portfolio import portfolio_snapshot
from services.paper.qualification import entry_permission
from services.paper.risk import size_manual_entry
from services.paper.settings import DEFAULT_CONFIG


class ManualPaperService:
    def __init__(
        self, engine: Engine, account_id: UUID, clock: Callable[[], datetime] | None = None
    ):
        self.engine, self.account_id = engine, account_id
        self.clock = clock or (lambda: datetime.now(UTC))
        self.ledger = DurableOrderLedger(engine, self.clock)

    def submit(
        self,
        plan_id: UUID,
        request_id: UUID,
        expected_revision: int,
        observed: Quote,
        session: ExchangeSession,
        quotes: dict[str, Quote],
    ) -> dict:
        command = dict(plan_id=str(plan_id), expected_revision=expected_revision)
        approval: OrderRiskApproval | None
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            now = self.clock()
            previous = db.get(ManualIntentRecord, request_id)
            if previous:
                if previous.account_id != account.id or previous.request_payload != command:
                    raise ConflictError("MANUAL_REQUEST_CONFLICT")
                existing = db.scalar(
                    select(PaperOrder).where(PaperOrder.manual_intent_id == request_id)
                )
                if existing:
                    return self.ledger.view(existing)
                if previous.result.get("status") != "APPROVED":
                    return previous.result
            execution = PaperExecutionConfig.model_validate_json(
                DEFAULT_CONFIG.read_text(encoding="utf-8")
            )
            if previous:
                intent = ManualEntryIntent.model_validate(previous.payload)
                approval = OrderRiskApproval.model_validate(previous.result["approval"])
                instrument = Instrument.model_validate(previous.result["instrument"])
            else:
                plan = db.get(ManualPaperPlan, plan_id)
                if plan is None or plan.account_id != account.id or plan.archived_at is not None:
                    raise ValueError("PAPER_PLAN_NOT_FOUND")
                if account.revision != expected_revision:
                    raise ValueError("PREVIEW_ACCOUNT_CHANGED")
                record = db.get(InstrumentRecord, plan.instrument_id)
                if record is None:
                    raise ValueError("INSTRUMENT_NOT_SAVED")
                instrument = Instrument.model_validate(record.payload)
                if instrument.model_dump(mode="json", exclude={"verified_at"}) != {
                    k: v for k, v in plan.instrument_payload.items() if k != "verified_at"
                }:
                    raise ValueError("MANUAL_CONTRACT_CHANGED")
                lease = entry_permission(
                    db, account, now, instrument.id, instrument=instrument, entry_source="HUMAN"
                )
                risk = RiskConfig.model_validate(account.config)
                inputs = plan.request_payload
                intent = ManualEntryIntent(
                    id=request_id,
                    plan_id=plan.id,
                    instrument_id=instrument.id,
                    quantity=inputs["lots"] * instrument.lot_size,
                    entry_limit=inputs["entry"],
                    stop_loss=inputs["stop_loss"],
                    target=inputs["target"],
                    max_holding_seconds=risk.max_holding_seconds,
                    submitted_at=now,
                    expires_at=min(lease.expires_at, now + timedelta(seconds=5)),
                )
                entry_permission(
                    db,
                    account,
                    now,
                    instrument.id,
                    intent.quantity,
                    instrument=instrument,
                    entry_source="HUMAN",
                )
                quote = mapped_quote(observed, execution)
                snapshot = portfolio_snapshot(db, account, quotes, now)
                levels = db.scalars(
                    select(PaperLiquidityLevel).where(
                        PaperLiquidityLevel.account_id == account.id,
                        PaperLiquidityLevel.session_key == session.key,
                        PaperLiquidityLevel.instrument_id == instrument.id,
                        PaperLiquidityLevel.side == "BUY",
                    )
                )
                result = size_manual_entry(
                    intent,
                    instrument,
                    quote,
                    risk,
                    snapshot.state,
                    session,
                    now,
                    execution=execution,
                    account_id=account.id,
                    account_revision=account.revision,
                    budgets={level.price: level for level in levels},
                )
                approval = result.approval
                payload = dict(
                    status="APPROVED" if approval else "REJECTED",
                    reason=result.reason,
                    source="HUMAN",
                    instrument=instrument.model_dump(mode="json"),
                )
                if approval:
                    max_age = execution.execution.quote_max_age_ms
                    assert max_age is not None
                    expires = min(
                        [
                            approval.expires_at,
                            *(
                                q.timestamp + timedelta(milliseconds=max_age)
                                for q in snapshot.evidence
                            ),
                        ]
                    )
                    if snapshot.valid_until:
                        expires = min(expires, snapshot.valid_until)
                    approval = approval.model_copy(
                        update={
                            "expires_at": expires,
                            "evidence_ids": tuple(
                                dict.fromkeys(
                                    (*approval.evidence_ids, *(q.id for q in snapshot.evidence))
                                )
                            ),
                        }
                    )
                    payload["approval"] = approval.model_dump(mode="json")
                PaperEngine._persist_quote(db, observed)
                PaperEngine._persist_quote(db, quote)
                for evidence in snapshot.evidence:
                    PaperEngine._persist_quote(db, evidence)
                db.add(
                    ManualIntentRecord(
                        id=intent.id,
                        account_id=account.id,
                        plan_id=plan.id,
                        created_at=now,
                        request_payload=command,
                        payload=intent.model_dump(mode="json"),
                        result=payload,
                    )
                )
                PaperEngine._event(
                    db,
                    account,
                    "MANUAL_RISK_DECISION",
                    now,
                    manual_intent_id=str(intent.id),
                    reason=result.reason,
                )
                if approval is None:
                    return payload
        assert approval is not None
        request = OrderRequest(
            idempotency_key="manual:" + str(intent.id),
            instrument_id=intent.instrument_id,
            side="BUY",
            quantity=intent.quantity,
            order_type="LIMIT",
            limit_price=intent.entry_limit,
            submitted_at=intent.submitted_at,
            expires_at=approval.expires_at,
            manual_intent_id=intent.id,
            cash_budget=approval.cash_budget,
            risk_budget=approval.risk_budget,
            reason="APPROVED_MANUAL_PLAN",
        )
        return self.ledger.submit(
            self.account_id, request, instrument, execution, session, self.clock()
        )
