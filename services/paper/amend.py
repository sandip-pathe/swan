"""Atomic amendment of wholly unfilled human orders, with immutable intent history."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.contracts import Instrument, Quote, RiskConfig
from services.core.execution import PaperExecutionConfig
from services.core.models import (
    InstrumentRecord,
    ManualIntentRecord,
    PaperLiquidityLevel,
    PaperOrder,
    PaperPosition,
)
from services.paper import manual
from services.paper.accounting import LEGACY
from services.paper.contracts import ManualEntryIntent
from services.paper.engine import ConflictError, PaperEngine
from services.paper.matching import mapped_quote
from services.paper.portfolio import portfolio_snapshot
from services.paper.qualification import entry_permission
from services.paper.risk import size_manual_entry
from services.worker.models import LatestMarketQuote


class ManualAmendService(manual.ManualPaperService):
    def amend(
        self,
        order_id: UUID,
        expected_revision: int,
        entry: Decimal,
        stop_loss: Decimal,
        target: Decimal,
        request_id: UUID | None = None,
    ) -> dict:
        command = {
            "order_id": str(order_id),
            "expected_revision": expected_revision,
            **{
                k: format(v.normalize(), "f")
                for k, v in dict(entry=entry, stop_loss=stop_loss, target=target).items()
            },
        }
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            order = db.get(PaperOrder, order_id)
            if order is None or order.account_id != account.id:
                raise ValueError("PAPER_ORDER_NOT_FOUND")
            previous = db.get(ManualIntentRecord, request_id) if request_id else None
            if previous:
                if previous.account_id != account.id or previous.request_payload != command:
                    raise ConflictError("MANUAL_REQUEST_CONFLICT")
                return {**self.ledger.view(order), "amendment_id": str(request_id), "amended": True}
            now = self.clock()
            self.ledger._check(db, account)
            if (
                order.execution_version == LEGACY
                or order.side != "BUY"
                or not order.manual_intent_id
                or order.order_type != "LIMIT"
                or order.status != "OPEN"
                or order.filled_quantity
                or order.expires_at is None
                or now >= order.expires_at
            ):
                raise ValueError("MANUAL_AMEND_UNAVAILABLE")
            if account.revision != expected_revision:
                raise ValueError("PREVIEW_ACCOUNT_CHANGED")
            record = db.get(InstrumentRecord, order.instrument_id)
            assert record is not None
            instrument = Instrument.model_validate(record.payload)
            current_intent = self.ledger._manual_intent(
                db, account, order.manual_intent_id, instrument, now
            )
            permission = entry_permission(
                db,
                account,
                now,
                instrument.id,
                order.quantity,
                order.id,
                instrument=instrument,
                entry_source="HUMAN",
            )
            if permission.validation_id != order.validation_id or permission.arm_id != order.arm_id:
                raise ValueError("VALIDATION_ORDER_MISMATCH")
            execution = PaperExecutionConfig.model_validate(order.execution_config)
            current = PaperExecutionConfig.model_validate_json(
                manual.DEFAULT_CONFIG.read_text(encoding="utf-8")
            )
            if execution != current:
                raise ValueError("MANUAL_EXECUTION_CHANGED")
            session = manual.load_session(instrument.exchange, now)
            if session is None:
                raise ValueError("MANUAL_MARKET_CLOSED")
            observed = db.get(LatestMarketQuote, instrument.id)
            if observed is None:
                raise ValueError("MANUAL_QUOTE_UNAVAILABLE")
            quote = mapped_quote(Quote.model_validate(observed.payload), execution)
            quotes = {
                r.instrument_id: Quote.model_validate(r.payload)
                for r in db.scalars(
                    select(LatestMarketQuote).where(
                        LatestMarketQuote.instrument_id.in_(
                            select(PaperPosition.instrument_id).where(
                                PaperPosition.account_id == account.id,
                                PaperPosition.closed_at.is_(None),
                            )
                        )
                    )
                )
            }
            snapshot = portfolio_snapshot(db, account, quotes, now)
            # Re-price this one reservation; all other exposure remains in the risk snapshot.
            state = replace(
                snapshot.state,
                cash=snapshot.state.cash + order.reserved_cash,
                reserved_risk=snapshot.state.reserved_risk - order.reserved_risk,
                open_positions=snapshot.state.open_positions - 1,
            )
            risk = RiskConfig.model_validate(account.config)
            intent = ManualEntryIntent(
                id=request_id or uuid4(),
                plan_id=current_intent.plan_id,
                instrument_id=instrument.id,
                quantity=order.quantity,
                entry_limit=entry,
                stop_loss=stop_loss,
                target=target,
                max_holding_seconds=min(
                    current_intent.max_holding_seconds, risk.max_holding_seconds
                ),
                submitted_at=now,
                expires_at=min(order.expires_at, permission.expires_at),
            )
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
                state,
                session,
                now,
                execution=execution,
                account_id=account.id,
                account_revision=account.revision,
                budgets={level.price: level for level in levels},
            )
            approval = result.approval
            if approval is None:
                raise ValueError("MANUAL_AMEND_RISK_" + result.reason)
            expiry = min(approval.expires_at, order.expires_at)
            if snapshot.valid_until:
                expiry = min(expiry, snapshot.valid_until)
            latency = execution.execution.assumed_latency_ms
            assert latency is not None
            eligible = now + timedelta(milliseconds=latency)
            if eligible >= expiry:
                raise ValueError("MANUAL_AMEND_EXECUTION_WINDOW")
            before = {
                k: str(v)
                for k, v in dict(
                    entry=order.limit_price,
                    stop_loss=current_intent.stop_loss,
                    target=current_intent.target,
                    reserved_cash=order.reserved_cash,
                    reserved_risk=order.reserved_risk,
                ).items()
            }
            preview = {
                "order_id": str(order.id),
                "account_revision": account.revision,
                "quantity": order.quantity,
                "before": before,
                "after": dict(
                    entry=str(entry),
                    stop_loss=str(stop_loss),
                    target=str(target),
                    reserved_cash=str(approval.cash_budget),
                    reserved_risk=str(approval.risk_budget),
                ),
                "expires_at": expiry.isoformat(),
                "eligible_at": eligible.isoformat(),
            }
            if request_id is None:
                return preview
            approval = approval.model_copy(
                update={
                    "expires_at": expiry,
                    "evidence_ids": tuple(
                        dict.fromkeys((*approval.evidence_ids, *(q.id for q in snapshot.evidence)))
                    ),
                }
            )
            PaperEngine._persist_quote(db, quote)
            for evidence in snapshot.evidence:
                PaperEngine._persist_quote(db, evidence)
            db.add(
                ManualIntentRecord(
                    id=request_id,
                    account_id=account.id,
                    plan_id=current_intent.plan_id,
                    created_at=now,
                    request_payload=command,
                    payload=intent.model_dump(mode="json"),
                    result={
                        "status": "APPROVED",
                        "source": "HUMAN",
                        "kind": "AMENDMENT",
                        "approval": approval.model_dump(mode="json"),
                        "instrument": instrument.model_dump(mode="json"),
                    },
                )
            )
            order.manual_intent_id = request_id
            order.limit_price = entry
            order.cash_budget = order.reserved_cash = approval.cash_budget
            order.risk_budget = order.reserved_risk = approval.risk_budget
            order.accepted_at, order.eligible_at, order.expires_at = now, eligible, expiry
            account.revision += 1
            self.ledger._event(
                db,
                order,
                "amend:" + str(request_id),
                "AMENDED",
                {**preview, "amendment_id": str(request_id)},
                now,
            )
            db.flush()
            self.ledger._check(db, account)
            return {**self.ledger.view(order), "amendment_id": str(request_id), "amended": True}
