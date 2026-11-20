"""Durable paper admission and deterministic protection, without agent/network calls."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from services.core.contracts import (
    IST,
    ExchangeSession,
    Instrument,
    Quote,
    RiskConfig,
    StrategyEnvelope,
    TradeDecision,
)
from services.core.execution import PaperExecutionConfig
from services.core.models import (
    Account,
    DecisionRecord,
    InstrumentRecord,
    ManualIntentRecord,
    PaperLiquidityLevel,
    PaperOrder,
    PaperPosition,
    StrategyRecord,
)
from services.paper.accounting import ACTIVE, LEGACY
from services.paper.contracts import OrderRequest
from services.paper.engine import PaperEngine
from services.paper.matching import DepthMatcher, mapped_quote
from services.paper.orders import DurableOrderLedger
from services.paper.portfolio import portfolio_snapshot
from services.paper.qualification import entry_permission
from services.paper.risk import size_entry
from services.paper.settings import DEFAULT_CONFIG
from services.risk.engine import daily_limit_reached, quote_problem
from services.worker.models import RuntimeControl

PRIORITY = {
    "DAILY_LOSS_LIMIT": 0,
    "PRE_CLOSE": 1,
    "STOP_LOSS": 2,
    "STRATEGY_INVALIDATED": 3,
    "FEED_UNAVAILABLE": 3,
    "MANUAL_SESSION_STOPPED": 3,
    "MAX_HOLD": 4,
    "TARGET": 5,
}


class PaperCoordinator:
    def __init__(
        self, engine: Engine, account_id: UUID, clock: Callable[[], datetime] | None = None
    ):
        self.engine, self.account_id = engine, account_id
        self.clock = clock or (lambda: datetime.now(UTC))
        self.ledger = DurableOrderLedger(engine, self.clock)
        self.matcher = DepthMatcher(engine, self.clock)

    def admit(
        self,
        decision: TradeDecision,
        instrument: Instrument,
        observed: Quote,
        envelope: StrategyEnvelope,
        session: ExchangeSession,
        quotes: dict[str, Quote],
    ) -> dict:
        now = self.clock()
        execution = PaperExecutionConfig.model_validate_json(
            DEFAULT_CONFIG.read_text(encoding="utf-8")
        )
        quote = mapped_quote(observed, execution)
        decision = decision.model_copy(
            update={"snapshot_ids": tuple(dict.fromkeys((*decision.snapshot_ids, quote.id)))}
        )
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            now = self.clock()
            control = db.get(RuntimeControl, self.account_id)
            if (
                control is None
                or not control.active_envelope
                or control.active_envelope.get("id") != str(envelope.id)
            ):
                return {"status": "REJECTED", "reason": "STRATEGY_INVALIDATED"}
            previous = db.get(DecisionRecord, decision.id)
            if previous is not None:
                if previous.account_id != account.id or previous.payload != decision.model_dump(
                    mode="json"
                ):
                    raise ValueError("Decision identity reused with different contents")
                existing = db.scalar(
                    select(PaperOrder).where(PaperOrder.decision_id == decision.id)
                )
                return self.ledger.view(existing) if existing is not None else previous.result
            snapshot = portfolio_snapshot(db, account, quotes, now)
            try:
                lease = entry_permission(
                    db,
                    account,
                    now,
                    instrument.id,
                    strategy_version=envelope.version,
                    instrument=instrument,
                )
            except ValueError as error:
                return {"status": "REJECTED", "reason": str(error)}
            risk = RiskConfig.model_validate(account.config)
            risk = risk.model_copy(
                update={"max_fill_quantity": min(risk.max_fill_quantity, lease.max_quantity)}
            )
            levels = list(
                db.scalars(
                    select(PaperLiquidityLevel).where(
                        PaperLiquidityLevel.account_id == account.id,
                        PaperLiquidityLevel.session_key == session.key,
                        PaperLiquidityLevel.instrument_id == instrument.id,
                        PaperLiquidityLevel.side == "BUY",
                    )
                )
            )
            result = size_entry(
                decision,
                instrument,
                quote,
                envelope,
                risk,
                snapshot.state,
                session,
                now,
                execution=execution,
                account_id=account.id,
                account_revision=account.revision,
                budgets={level.price: level for level in levels},
            )
            PaperEngine._persist_instrument(db, instrument)
            PaperEngine._persist_quote(db, observed)
            PaperEngine._persist_quote(db, quote)
            for evidence in snapshot.evidence:
                PaperEngine._persist_quote(db, evidence)
            strategy = db.get(StrategyRecord, envelope.id)
            if strategy is None:
                db.add(
                    StrategyRecord(
                        id=envelope.id,
                        account_id=account.id,
                        payload=envelope.model_dump(mode="json"),
                    )
                )
            elif strategy.account_id != account.id or strategy.payload != envelope.model_dump(
                mode="json"
            ):
                raise ValueError("Strategy identity reused")
            approval = result.approval
            payload: dict = {
                "status": "APPROVED" if approval else "REJECTED",
                "reason": result.reason,
            }
            if approval is not None:
                # Bound approval by all observations used for net liquidation equity.
                max_age = execution.execution.quote_max_age_ms
                assert max_age is not None
                expiry = min(
                    [
                        approval.expires_at,
                        *(q.timestamp + timedelta(milliseconds=max_age) for q in snapshot.evidence),
                    ]
                )
                if snapshot.valid_until is not None:
                    expiry = min(expiry, snapshot.valid_until)
                approval = approval.model_copy(
                    update={
                        "expires_at": expiry,
                        "evidence_ids": tuple(
                            dict.fromkeys(
                                (*approval.evidence_ids, *(q.id for q in snapshot.evidence))
                            )
                        ),
                    }
                )
                payload["approval"] = approval.model_dump(mode="json")
            db.add(
                DecisionRecord(
                    id=decision.id,
                    account_id=account.id,
                    payload=decision.model_dump(mode="json"),
                    result=payload,
                )
            )
            PaperEngine._event(
                db,
                account,
                "DURABLE_RISK_DECISION",
                now,
                decision_id=str(decision.id),
                reason=result.reason,
            )
        if approval is None:
            return payload
        request = OrderRequest(
            idempotency_key="entry:" + str(decision.id),
            instrument_id=instrument.id,
            side="BUY",
            quantity=approval.quantity,
            order_type="LIMIT",
            limit_price=approval.entry_limit,
            submitted_at=now,
            expires_at=approval.expires_at,
            decision_id=decision.id,
            cash_budget=approval.cash_budget,
            risk_budget=approval.risk_budget,
            reason="APPROVED_STRATEGY",
        )
        # A pause, competing fill or configuration change between transactions invalidates revision.
        try:
            return self.ledger.submit(
                self.account_id, request, instrument, execution, session, self.clock()
            )
        except ValueError:
            with Session(self.engine) as db, db.begin():
                account = PaperEngine._account(db, self.account_id)
                stored = db.get(DecisionRecord, decision.id)
                if stored is not None:
                    stored.result = {
                        **stored.result,
                        "status": "ADMISSION_REJECTED",
                        "reason": "ACCOUNT_OR_MARKET_STATE_CHANGED",
                    }
                PaperEngine._event(
                    db,
                    account,
                    "DURABLE_ADMISSION_REJECTED",
                    self.clock(),
                    decision_id=str(decision.id),
                )
            raise

    def cancel(self, order: PaperOrder) -> None:
        self.ledger.cancel(
            self.account_id, order.id, "watch-request:" + str(order.id), self.clock()
        )
        self.ledger.cancel(
            self.account_id, order.id, "watch-ack:" + str(order.id), self.clock(), confirm=True
        )

    def _inventory(self) -> tuple[list[PaperPosition], list[PaperOrder], dict[str, Instrument]]:
        with Session(self.engine, expire_on_commit=False) as db:
            positions = list(
                db.scalars(
                    select(PaperPosition).where(
                        PaperPosition.account_id == self.account_id,
                        PaperPosition.closed_at.is_(None),
                    )
                )
            )
            orders = list(
                db.scalars(
                    select(PaperOrder)
                    .where(
                        PaperOrder.account_id == self.account_id,
                        PaperOrder.execution_version != LEGACY,
                        PaperOrder.status.in_(ACTIVE),
                    )
                    .order_by(PaperOrder.accepted_at)
                )
            )
            identifiers = {p.instrument_id for p in positions} | {o.instrument_id for o in orders}
            instruments = {
                row.id: Instrument.model_validate(row.payload)
                for row in db.scalars(
                    select(InstrumentRecord).where(InstrumentRecord.id.in_(identifiers))
                )
            }
            return positions, orders, instruments

    def _protection(
        self, quotes: dict[str, Quote], sessions: dict[str, ExchangeSession], healthy: bool
    ) -> None:
        now = self.clock()
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            snapshot = portfolio_snapshot(db, account, quotes, now)
            config = RiskConfig.model_validate(account.config)
            if not snapshot.state.reconciled:
                account.enabled = False
                raise ValueError("Protection requires reconciled holdings")
            if not snapshot.state.valuation_fresh and account.enabled:
                account.enabled = False
                account.revision += 1
                PaperEngine._event(
                    db,
                    account,
                    "ENTRIES_PAUSED_UNAVAILABLE_VALUATION",
                    now,
                    problems=list(snapshot.problems),
                )
            if (
                snapshot.state.valuation_fresh
                and account.session_key == now.astimezone(IST).date()
                and account.session_opening_equity
                and daily_limit_reached(snapshot.state, config)
            ):
                if not account.daily_blocked:
                    account.daily_blocked, account.enabled = True, False
                    account.revision += 1
                    PaperEngine._event(db, account, "DAILY_LOSS_BLOCK", now)
            control = db.get(RuntimeControl, account.id)
            active = control.active_envelope if control else None
            enabled, blocked = account.enabled, account.daily_blocked
        positions, orders, instruments = self._inventory()
        # Paused/recovered/invalidated pending entries cannot linger or acquire new exposure.
        for order in orders:
            if order.side == "BUY" and (
                order.filled_quantity
                or not enabled
                or not healthy
                or (not order.manual_intent_id and not active)
            ):
                self.cancel(order)
        for position in positions:
            try:
                self._protect_position(
                    position, instruments, quotes, sessions, healthy, active, blocked
                )
            except ValueError:
                self.incident(position.id, "PROTECTION_REJECTED")

    def _protect_position(
        self,
        position: PaperPosition,
        instruments: dict[str, Instrument],
        quotes: dict[str, Quote],
        sessions: dict[str, ExchangeSession],
        healthy: bool,
        active: dict | None,
        blocked: bool,
    ) -> None:
        now = self.clock()
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            entry = db.get(PaperOrder, position.entry_order_id)
            if entry is None or entry.execution_version == LEGACY:
                return
            manual_entry = entry.manual_intent_id is not None
            execution = PaperExecutionConfig.model_validate(entry.execution_config)
            manual_stopped = False
            strategy_id = None
            if manual_entry:
                intent = db.get(ManualIntentRecord, entry.manual_intent_id)
                if intent is None or intent.account_id != self.account_id:
                    raise ValueError("Held manual intent unavailable")
                try:
                    entry_permission(
                        db,
                        account,
                        now,
                        entry.instrument_id,
                        entry.quantity,
                        entry.id,
                        entry_source="HUMAN",
                    )
                    manual_stopped = not account.enabled
                except ValueError:
                    manual_stopped = True
            else:
                decision = db.get(DecisionRecord, entry.decision_id)
                if decision is None:
                    raise ValueError("Held entry decision evidence unavailable")
                strategy_id = decision.payload["strategy_id"]
        instrument = instruments[position.instrument_id]
        session = sessions.get(instrument.exchange)
        risk = RiskConfig.model_validate(position.config)
        reason = position.pending_exit
        candidates = []
        if blocked:
            candidates.append("DAILY_LOSS_LIMIT")
        if session is None or now >= session.closes_at - timedelta(minutes=risk.flatten_minutes):
            candidates.append("PRE_CLOSE")
        if manual_entry:
            if not healthy:
                candidates.append("FEED_UNAVAILABLE")
            if manual_stopped:
                candidates.append("MANUAL_SESSION_STOPPED")
        elif (
            not healthy
            or not active
            or active.get("id") != strategy_id
            or active.get("invalidated")
            or now >= datetime.fromisoformat(active["expires_at"])
        ):
            candidates.append("STRATEGY_INVALIDATED")
        if now >= position.opened_at + timedelta(seconds=position.max_holding_seconds):
            candidates.append("MAX_HOLD")
        observed = quotes.get(instrument.id)
        quote = None
        if observed is not None:
            try:
                quote = mapped_quote(observed, execution)
            except ValueError:
                pass
        max_age = execution.execution.quote_max_age_ms
        fresh = (
            quote is not None
            and quote_problem(quote, now, risk.quote_max_age_seconds) is None
            and max_age is not None
            and (now - quote.timestamp).total_seconds() * 1000 <= max_age
        )
        if fresh and quote is not None and quote.bid is not None:
            if quote.bid <= position.stop_loss:
                candidates.append("STOP_LOSS")
            elif quote.bid >= position.target:
                candidates.append("TARGET")
        if reason:
            candidates.append(reason)
        reason = min(candidates, key=lambda value: PRIORITY.get(value, 0)) if candidates else None
        if reason != position.pending_exit:
            with Session(self.engine) as db, db.begin():
                account = PaperEngine._account(db, self.account_id)
                held = db.get(PaperPosition, position.id)
                if held and held.closed_at is None:
                    held.pending_exit = reason
                    account.revision += 1
                    PaperEngine._event(
                        db,
                        account,
                        "PROTECTIVE_EXIT_REQUIRED",
                        now,
                        position_id=str(position.id),
                        reason=reason,
                    )
        _, pending, _ = self._inventory()
        exits = [o for o in pending if o.position_id == position.id and o.side == "SELL"]
        wanted = reason or "PROTECTIVE_STOP"
        # Only explicit reason escalation replaces a protected market order's fixed bound.
        for order in exits:
            if (
                reason
                and order.reason != wanted
                and (
                    order.reason == "PROTECTIVE_STOP"
                    or PRIORITY.get(wanted, 0) < PRIORITY.get(order.reason, 0)
                )
            ):
                self.cancel(order)
        _, pending, _ = self._inventory()
        if any(o.position_id == position.id and o.side == "SELL" for o in pending):
            return
        if session is None or not session.opens_at <= now < session.closes_at:
            self.incident(position.id, "NO_VERIFIED_EXIT_SESSION")
            return
        with Session(self.engine) as db:
            held = db.get(PaperPosition, position.id)
            current_entry = db.get(PaperOrder, position.entry_order_id)
            if (
                held is None
                or held.closed_at is not None
                or current_entry is None
                or current_entry.status in ACTIVE
            ):
                return
            quantity = held.quantity - held.closed_quantity
            # Revision in identity allows a later expired/cancelled order to be replaced.
            current_account = db.get(Account, self.account_id)
            assert current_account is not None
            key = f"protect:{position.id}:{current_account.revision}:{wanted}"
        self.ledger.submit(
            self.account_id,
            OrderRequest(
                idempotency_key=key,
                instrument_id=instrument.id,
                side="SELL",
                quantity=quantity,
                order_type="MARKET" if reason else "STOP_MARKET",
                trigger_price=None if reason else position.stop_loss,
                submitted_at=self.clock(),
                expires_at=session.closes_at,
                position_id=position.id,
                cash_budget=Decimal(0),
                risk_budget=Decimal(0),
                reason=wanted,
            ),
            instrument,
            execution,
            session,
            self.clock(),
        )

    def incident(self, position_id: UUID, code: str) -> None:
        with Session(self.engine) as db, db.begin():
            account = PaperEngine._account(db, self.account_id)
            control = db.get(RuntimeControl, self.account_id)
            if control and control.problem != code:
                control.status, control.problem = "EXPOSURE_UNRESOLVED", code
                account.enabled = False
                account.revision += 1
                PaperEngine._event(
                    db,
                    account,
                    "UNRESOLVED_EXPOSURE",
                    self.clock(),
                    position_id=str(position_id),
                    reason=code,
                )

    def cycle(
        self, quotes: dict[str, Quote], sessions: dict[str, ExchangeSession], healthy: bool
    ) -> None:
        held, pending, _ = self._inventory()
        if not held and not pending:
            return
        self.ledger.expire(self.account_id, self.clock())
        self._protection(quotes, sessions, healthy)
        _, orders, instruments = self._inventory()
        # One bounded pass, protective sells before buys. Latest observations coalesce upstream.
        for order in sorted(orders, key=lambda o: (o.side != "SELL", o.accepted_at))[:32]:
            quote = quotes.get(order.instrument_id)
            if quote is None:
                if order.position_id:
                    self.incident(order.position_id, "EXIT_QUOTE_UNAVAILABLE")
                continue
            if order.side == "BUY":
                self._protection(quotes, sessions, healthy)
            try:
                result = self.matcher.match_order(
                    self.account_id, order.id, instruments[order.instrument_id], quote
                )
            except ValueError:
                if order.position_id:
                    self.incident(order.position_id, "EXIT_MATCH_REJECTED")
                else:
                    self.cancel(order)
                continue
            if order.position_id and result.get("reason") not in {
                "MATCHED",
                "STOP_NOT_TRIGGERED",
                "WAITING_FOR_LATER_OBSERVATION",
                "WAITING_AFTER_STOP_TRIGGER",
                "TERMINAL",
            }:
                self.incident(order.position_id, "EXIT_PENDING:" + str(result.get("reason")))
            if result.get("matched_levels", 0):
                self._protection(quotes, sessions, healthy)
        held, pending, _ = self._inventory()
        if not held and not pending:
            with Session(self.engine) as db, db.begin():
                account = PaperEngine._account(db, self.account_id)
                control = db.scalar(
                    select(RuntimeControl)
                    .where(RuntimeControl.account_id == self.account_id)
                    .with_for_update()
                )
                if control and control.status == "EXPOSURE_UNRESOLVED":
                    control.status, control.problem = "PAUSED", None
                    account.enabled = False
                    account.revision += 1
                    PaperEngine._event(db, account, "EXPOSURE_RESOLVED", self.clock())
