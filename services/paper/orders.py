"""Transactional durable ledger for approved orders and matched fills.

Internal persistence boundary only: no routes, broker client, market matcher or AI calls.
Risk approval, sourced fee calculation and depth matching are required upstream.
"""

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
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
    money,
)
from services.core.execution import PaperExecutionConfig
from services.core.models import (
    Account,
    DecisionRecord,
    InstrumentRecord,
    LedgerEntry,
    ManualIntentRecord,
    ManualPaperPlan,
    PaperFill,
    PaperFundsHold,
    PaperLiquidityLevel,
    PaperLiquidityUse,
    PaperOrder,
    PaperOrderEvent,
    PaperPosition,
    SnapshotRecord,
    StrategyRecord,
)
from services.paper.accounting import (
    ACTIVE,
    LEGACY,
    TERMINAL,
    fill_totals,
    order_fills,
    prorated_risk,
    reconcile_account,
    refresh_position,
    reservations,
    restricted_proceeds,
)
from services.paper.contracts import FillBooking, ManualEntryIntent, OrderRequest, OrderRiskApproval
from services.paper.engine import ConflictError, PaperEngine
from services.paper.fees import fee_contexts, incremental_fees
from services.paper.liquidity import (
    available_units,
    capacity_state,
    displayed_units,
    execution_price,
    level_budget,
    protection_price,
)
from services.risk.engine import quote_problem


class DurableOrderLedger:
    def __init__(self, engine: Engine, clock: Callable[[], datetime] | None = None):
        self.engine = engine
        self.clock = clock or (lambda: datetime.now(UTC))

    def _lock(self, db: Session, account_id: UUID) -> tuple[Account, datetime]:
        account = PaperEngine._account(db, account_id)
        now = self.clock()  # Re-read after waiting for a competing account transaction.
        self._clock(now)
        return account, now

    @staticmethod
    def _clock(now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError("Timezone-aware clock required")

    @staticmethod
    def _order(db: Session, account_id: UUID, order_id: UUID) -> PaperOrder:
        order = db.get(PaperOrder, order_id)
        if order is None or order.account_id != account_id or order.execution_version == LEGACY:
            raise ValueError("Unknown durable paper order")
        return order

    @staticmethod
    def _manual_intent(
        db: Session, account: Account, identifier: UUID, instrument: Instrument, now: datetime
    ) -> ManualEntryIntent:
        row = db.get(ManualIntentRecord, identifier)
        if row is None or row.account_id != account.id or row.result.get("status") != "APPROVED":
            raise ValueError("Approved owned manual intent required")
        intent = ManualEntryIntent.model_validate(row.payload)
        frozen = Instrument.model_validate(row.result["instrument"])
        if (
            intent.id != row.id
            or intent.plan_id != row.plan_id
            or intent.instrument_id != instrument.id
            or not intent.submitted_at <= now < intent.expires_at
            or frozen.model_dump(exclude={"verified_at"})
            != instrument.model_dump(exclude={"verified_at"})
        ):
            raise ValueError("Manual intent scope expired or changed")
        return intent

    @staticmethod
    def view(order: PaperOrder) -> dict:
        return {
            "order_id": str(order.id),
            "status": order.status,
            "quantity": order.quantity,
            "filled_quantity": order.filled_quantity,
            "remaining_quantity": order.quantity - order.filled_quantity,
            "reserved_cash": str(order.reserved_cash),
            "reserved_risk": str(order.reserved_risk),
        }

    @staticmethod
    def _event(
        db: Session, order: PaperOrder, key: str, kind: str, payload: dict, now: datetime
    ) -> bool:
        existing = db.scalar(
            select(PaperOrderEvent).where(
                PaperOrderEvent.account_id == order.account_id, PaperOrderEvent.event_key == key
            )
        )
        if existing:
            if (
                existing.order_id != order.id
                or existing.kind != kind
                or existing.payload != payload
            ):
                raise ConflictError("Order event identity reused with different contents")
            return False
        db.add(
            PaperOrderEvent(
                account_id=order.account_id,
                order_id=order.id,
                event_key=key,
                kind=kind,
                timestamp=now,
                payload=payload,
            )
        )
        return True

    @staticmethod
    def _finish(order: PaperOrder, status: str, now: datetime) -> None:
        order.status, order.completed_at = status, now
        order.reserved_cash = order.reserved_risk = Decimal(0)

    @staticmethod
    def _check(db: Session, account: Account) -> None:
        db.flush()
        if reconcile_account(db, account):
            raise ValueError("Paper account reconciliation failed; transaction rolled back")

    def submit(
        self,
        account_id: UUID,
        request: OrderRequest,
        instrument: Instrument,
        config: PaperExecutionConfig,
        session: ExchangeSession,
        now: datetime,
    ) -> dict:
        """Persist an upstream risk-approved order; never creates an execution/fill."""
        self._clock(now)
        request_payload = request.model_dump(mode="json")
        if request.manual_intent_id is None:
            request_payload.pop("manual_intent_id", None)
        payload = {
            "request": request_payload,
            "configuration": config.model_dump(mode="json"),
            "risk_allocation": "whole_order_until_flat",
        }
        with Session(self.engine) as db, db.begin():
            account, now = self._lock(db, account_id)
            existing = db.scalar(
                select(PaperOrder).where(
                    PaperOrder.account_id == account_id,
                    PaperOrder.idempotency_key == request.idempotency_key,
                )
            )
            if existing:
                comparison = dict(payload)
                if "risk_allocation" not in (existing.request_payload or {}):
                    comparison.pop("risk_allocation")
                if existing.request_payload != comparison:
                    raise ConflictError("Order identity reused with different contents")
                return self.view(existing)
            self._check(db, account)
            day = now.astimezone(IST).date()
            if config.blockers(day) or config.execution.version == LEGACY:
                raise ValueError("Reviewed execution and fee configuration required")
            day_start = datetime.combine(day, time.min, IST)
            previous_models = list(
                db.scalars(
                    select(PaperOrder).where(
                        PaperOrder.account_id == account_id,
                        PaperOrder.accepted_at >= day_start,
                        PaperOrder.accepted_at < day_start + timedelta(days=1),
                    )
                )
            )
            if any(
                o.execution_version == LEGACY
                or o.execution_config != config.model_dump(mode="json")
                for o in previous_models
            ):
                raise ValueError("Execution/fee model is frozen for the account session")
            if instrument.id != request.instrument_id or instrument.verified_at > now:
                raise ValueError("Instrument metadata mismatch")
            if not 0 <= (instrument.expiry - day).days <= 7:
                raise ValueError("Ineligible contract expiry")
            if request.quantity % instrument.lot_size and (
                request.side == "BUY" or config.execution.partial_fill_granularity != "units"
            ):
                raise ValueError("Submitted quantity must be whole lots")
            for price in (request.limit_price, request.trigger_price):
                if price is not None and price % instrument.tick_size:
                    raise ValueError("Order price must respect instrument tick")
            if not session.verified or session.key != day or account.session_key != day:
                raise ValueError("Verified current account session required")
            if (
                not session.opens_at <= now < session.closes_at
                or not request.submitted_at <= now < request.expires_at
            ):
                raise ValueError("Order submitted outside its session/lifetime")
            risk_config = RiskConfig.model_validate(account.config)
            reserved_cash, reserved_risk, _ = reservations(db, account_id)
            positions = PaperEngine._open_positions(db, account_id)
            expires_at = min(request.expires_at, session.closes_at)
            validation_id = None
            arm_id = None
            if request.side == "BUY":
                from services.paper.qualification import entry_permission

                validation = entry_permission(
                    db,
                    account,
                    now,
                    instrument.id,
                    request.quantity,
                    instrument=instrument,
                    entry_source="HUMAN" if request.manual_intent_id else "AI",
                )
                validation_id, arm_id = validation.validation_id, validation.arm_id
                expires_at = min(expires_at, validation.expires_at)
                if not account.enabled or account.daily_blocked:
                    raise ValueError("Entries paused or daily blocked")
                cutoff = session.closes_at - timedelta(minutes=risk_config.entry_cutoff_minutes)
                if now >= cutoff:
                    raise ValueError("Entry cutoff")
                pending = list(
                    db.scalars(
                        select(PaperOrder).where(
                            PaperOrder.account_id == account_id,
                            PaperOrder.side == "BUY",
                            PaperOrder.status.in_(ACTIVE),
                        )
                    )
                )
                occupied = len(positions) + sum(
                    o.id not in {p.entry_order_id for p in positions} for o in pending
                )
                if (
                    occupied >= risk_config.max_positions
                    or request.quantity > risk_config.max_fill_quantity
                ):
                    raise ValueError("Position/quantity limit")
                held_risk = sum((p.planned_risk for p in positions), Decimal(0))
                if request.cash_budget > account.cash - reserved_cash - restricted_proceeds(
                    db, account_id
                ):
                    raise ValueError("Insufficient unreserved cash")
                if request.risk_budget > risk_config.capital * risk_config.max_trade_risk_pct:
                    raise ValueError("Per-trade risk limit")
                decision = (
                    db.get(ManualIntentRecord, request.manual_intent_id)
                    if request.manual_intent_id
                    else db.get(DecisionRecord, request.decision_id)
                )
                if (
                    decision is None
                    or decision.account_id != account_id
                    or decision.result.get("status") != "APPROVED"
                ):
                    raise ValueError("Upstream approved entry source required")
                approval = OrderRiskApproval.model_validate(decision.result.get("approval"))
                if (
                    approval.quantity != request.quantity
                    or approval.cash_budget != request.cash_budget
                    or approval.risk_budget != request.risk_budget
                    or approval.account_revision != account.revision
                    or approval.risk_config_version != risk_config.version
                    or approval.execution_config_version != config.version
                    or now >= approval.expires_at
                    or approval.net_liquidation_equity is None
                    or request.order_type != "LIMIT"
                    or request.limit_price != approval.entry_limit
                ):
                    raise ValueError("Order differs from current deterministic risk approval")
                baseline = account.session_opening_equity
                equity = approval.net_liquidation_equity
                assert equity is not None
                if (
                    baseline is None
                    or request.risk_budget + held_risk + reserved_risk
                    > baseline * risk_config.max_daily_loss_pct - max(Decimal(0), baseline - equity)
                ):
                    raise ValueError("Daily net-liquidation/risk headroom unavailable")
                if any(
                    db.get(SnapshotRecord, identifier) is None
                    for identifier in approval.evidence_ids
                ):
                    raise ValueError("Risk approval evidence unavailable")
                source_expires = []
                if request.manual_intent_id:
                    intent = self._manual_intent(
                        db, account, request.manual_intent_id, instrument, now
                    )
                    plan = db.get(ManualPaperPlan, intent.plan_id)
                    if plan is None or plan.archived_at is not None:
                        raise ValueError("PAPER_PLAN_NOT_FOUND")
                    if (
                        request.quantity != intent.quantity
                        or request.limit_price != intent.entry_limit
                        or request.submitted_at != intent.submitted_at
                    ):
                        raise ValueError("Order differs from approved manual intent")
                    source_expires.append(intent.expires_at)
                else:
                    if decision.payload.get(
                        "instrument_id"
                    ) != instrument.id or decision.payload.get("action") != (
                        "BUY_CALL" if instrument.option_type == "CALL" else "BUY_PUT"
                    ):
                        raise ValueError("Decision instrument/action mismatch")
                    strategy_id = decision.payload.get("strategy_id")
                    from services.worker.models import RuntimeControl

                    control = db.scalar(
                        select(RuntimeControl)
                        .where(RuntimeControl.account_id == account_id)
                        .with_for_update()
                    )
                    if (
                        control is None
                        or not control.active_envelope
                        or control.active_envelope.get("id") != strategy_id
                        or control.active_envelope.get("invalidated")
                    ):
                        raise ValueError("Runtime strategy invalidated before admission")
                    strategy = db.get(StrategyRecord, UUID(strategy_id)) if strategy_id else None
                    if strategy is None or strategy.account_id != account_id:
                        raise ValueError("Approved strategy required")
                    envelope = StrategyEnvelope.model_validate(strategy.payload)
                    if envelope.invalidated or not envelope.issued_at <= now < envelope.expires_at:
                        raise ValueError("Strategy expired/invalidated")
                    entry_permission(
                        db,
                        account,
                        now,
                        instrument.id,
                        request.quantity,
                        strategy_version=envelope.version,
                    )
                    source_expires.extend(
                        [
                            envelope.expires_at,
                            datetime.fromisoformat(decision.payload["expires_at"]),
                        ]
                    )
                lifetime = config.execution.pending_entry_lifetime_ms
                assert lifetime is not None
                expires_at = min(
                    expires_at,
                    cutoff,
                    *source_expires,
                    now + timedelta(milliseconds=lifetime),
                    approval.expires_at,
                )
            else:
                position = db.get(PaperPosition, request.position_id)
                if (
                    position is None
                    or position.account_id != account_id
                    or position.instrument_id != instrument.id
                    or position.closed_at is not None
                ):
                    raise ValueError("Open owned position required")
                entry_order = db.get(PaperOrder, position.entry_order_id)
                if entry_order is None or entry_order.status in ACTIVE:
                    raise ValueError("Cancel entry remainder before accepting an exit")
                validation_id = entry_order.validation_id
                arm_id = entry_order.arm_id
                if (
                    entry_order.execution_version == LEGACY
                    or entry_order.execution_config != config.model_dump(mode="json")
                ):
                    raise ValueError("Exit must preserve the durable entry execution configuration")
                pending_sells = list(
                    db.scalars(
                        select(PaperOrder).where(
                            PaperOrder.position_id == position.id,
                            PaperOrder.side == "SELL",
                            PaperOrder.status.in_(ACTIVE),
                        )
                    )
                )
                reserved_units = sum(o.quantity - o.filled_quantity for o in pending_sells)
                if request.quantity > position.quantity - position.closed_quantity - reserved_units:
                    raise ValueError("Exit quantity exceeds unreserved held units")
            latency = config.execution.assumed_latency_ms
            assert latency is not None
            accepted_at = self.clock()
            self._clock(accepted_at)
            if accepted_at < now:
                raise ValueError("Accounting clock moved backward")
            now = accepted_at
            eligible_at = now + timedelta(milliseconds=latency)
            if eligible_at >= expires_at:
                raise ValueError("Order expires before execution eligibility")
            PaperEngine._persist_instrument(db, instrument)
            order = PaperOrder(
                arm_id=arm_id,
                validation_id=validation_id,
                account_id=account_id,
                decision_id=request.decision_id,
                manual_intent_id=request.manual_intent_id,
                instrument_id=instrument.id,
                idempotency_key=request.idempotency_key,
                side=request.side,
                quantity=request.quantity,
                reason=request.reason,
                timestamp=request.submitted_at,
                status="OPEN",
                filled_quantity=0,
                execution_version=config.execution.version,
                order_type=request.order_type,
                time_in_force=request.time_in_force,
                limit_price=request.limit_price,
                trigger_price=request.trigger_price,
                accepted_at=now,
                eligible_at=eligible_at,
                expires_at=expires_at,
                cash_budget=request.cash_budget,
                risk_budget=request.risk_budget,
                reserved_cash=request.cash_budget,
                reserved_risk=request.risk_budget,
                position_id=request.position_id,
                request_payload=payload,
                execution_config=config.model_dump(mode="json"),
            )
            db.add(order)
            account.revision += 1
            db.flush()
            self._event(db, order, "submit:" + request.idempotency_key, "ACCEPTED", payload, now)
            PaperEngine._event(db, account, "PAPER_ORDER_ACCEPTED", now, **self.view(order))
            self._check(db, account)
            return self.view(order)

    def cancel(
        self,
        account_id: UUID,
        order_id: UUID,
        event_key: str,
        now: datetime,
        *,
        confirm: bool = False,
    ) -> dict:
        """Request and acknowledge separately. Reserves remain held until terminal."""
        self._clock(now)
        if not event_key:
            raise ValueError("Cancellation event identity required")
        with Session(self.engine) as db, db.begin():
            account, now = self._lock(db, account_id)
            order = self._order(db, account_id, order_id)
            self._check(db, account)
            kind = "CANCELLED" if confirm else "CANCEL_REQUESTED"
            if not self._event(db, order, event_key, kind, {}, now):
                return self.view(order)
            if order.status not in TERMINAL:
                if confirm:
                    if order.status != "CANCEL_REQUESTED":
                        raise ValueError("Cancellation must be requested before acknowledgment")
                    self._finish(order, "CANCELLED", now)
                else:
                    order.status, order.cancel_requested_at = "CANCEL_REQUESTED", now
                account.revision += 1
                PaperEngine._event(db, account, "PAPER_ORDER_" + kind, now, **self.view(order))
            self._check(db, account)
            return self.view(order)

    def expire(self, account_id: UUID, now: datetime) -> int:
        self._clock(now)
        with Session(self.engine) as db, db.begin():
            account, now = self._lock(db, account_id)
            self._check(db, account)
            orders = list(
                db.scalars(
                    select(PaperOrder).where(
                        PaperOrder.account_id == account_id,
                        PaperOrder.execution_version != LEGACY,
                        PaperOrder.status.in_(ACTIVE),
                        PaperOrder.expires_at <= now,
                    )
                )
            )
            for order in orders:
                self._finish(order, "EXPIRED", now)
                account.revision += 1
                self._event(db, order, "expire:" + str(order.id), "EXPIRED", {}, now)
                PaperEngine._event(db, account, "PAPER_ORDER_EXPIRED", now, **self.view(order))
            self._check(db, account)
            return len(orders)

    def prepare_match(
        self, account_id: UUID, order_id: UUID, instrument: Instrument, quote: Quote, now: datetime
    ) -> dict:
        """Persist a real stop trigger and freeze market-style price protection once."""
        self._clock(now)
        with Session(self.engine) as db, db.begin():
            account, now = self._lock(db, account_id)
            order = self._order(db, account_id, order_id)
            self._check(db, account)
            if order.status not in ACTIVE:
                return {**self.view(order), "reason": "TERMINAL"}
            config = PaperExecutionConfig.model_validate(order.execution_config)
            if order.expires_at is None or order.eligible_at is None:
                raise ValueError("Accepted order timing required")
            if now >= order.expires_at:
                self._finish(order, "EXPIRED", now)
                self._event(db, order, "expire:" + str(order.id), "EXPIRED", {}, now)
                account.revision += 1
                return {**self.view(order), "reason": "EXPIRED"}
            age = config.execution.quote_max_age_ms
            assert age is not None
            if (
                quote_problem(quote, now, 10)
                or (now - quote.timestamp).total_seconds() * 1000 > age
            ):
                return {**self.view(order), "reason": "QUOTE_UNAVAILABLE_OR_STALE"}
            if (
                now < order.eligible_at
                or quote.timestamp < order.eligible_at
                or quote.received_at < order.eligible_at
            ):
                return {**self.view(order), "reason": "WAITING_FOR_LATER_OBSERVATION"}
            if quote.instrument_id != instrument.id or order.instrument_id != instrument.id:
                raise ValueError("Order/instrument/observation mismatch")
            if (
                quote.quantity_unit == "unknown"
                or quote.quantity_unit != config.execution.quantity_unit
            ):
                raise ValueError("Verified quantity mapping required")
            if not quote.market_event_id or not quote.bid_depth or not quote.ask_depth:
                return {**self.view(order), "reason": "DEPTH_UNAVAILABLE"}
            if quote.timestamp_basis != "exchange_feed" or quote.depth_kind != "best_five":
                return {**self.view(order), "reason": "UNVERIFIED_MARKET_EVIDENCE"}
            PaperEngine._persist_instrument(db, instrument)
            PaperEngine._persist_quote(db, quote)
            if order.order_type in {"STOP_MARKET", "STOP_LIMIT"}:
                triggered = db.scalar(
                    select(PaperOrderEvent).where(
                        PaperOrderEvent.order_id == order.id, PaperOrderEvent.kind == "TRIGGERED"
                    )
                )
                if triggered is None:
                    assert (
                        order.trigger_price is not None
                        and quote.bid is not None
                        and quote.ask is not None
                    )
                    crossed = (
                        quote.ask >= order.trigger_price
                        if order.side == "BUY"
                        else quote.bid <= order.trigger_price
                    )
                    if not crossed:
                        return {**self.view(order), "reason": "STOP_NOT_TRIGGERED"}
                    self._event(
                        db,
                        order,
                        "trigger:" + str(order.id),
                        "TRIGGERED",
                        {
                            "snapshot_id": str(quote.id),
                            "market_event_id": quote.market_event_id,
                            "trigger_price": str(order.trigger_price),
                        },
                        now,
                    )
                    latency = config.execution.assumed_latency_ms
                    assert latency is not None
                    order.eligible_at = now + timedelta(milliseconds=latency)
                    account.revision += 1
                    self._check(db, account)
                    return {**self.view(order), "reason": "WAITING_AFTER_STOP_TRIGGER"}
                if quote.received_at <= triggered.timestamp or triggered.payload.get(
                    "snapshot_id"
                ) == str(quote.id):
                    return {**self.view(order), "reason": "WAITING_AFTER_STOP_TRIGGER"}
            if order.order_type in {"MARKET", "STOP_MARKET"} and order.limit_price is None:
                protection = config.execution.market_protection_bps
                assert protection is not None and quote.ask is not None and quote.bid is not None
                anchor = quote.ask if order.side == "BUY" else quote.bid
                order.limit_price = protection_price(
                    anchor, instrument.tick_size, order.side, protection
                )
                self._event(
                    db,
                    order,
                    "protection:" + str(order.id),
                    "PRICE_PROTECTION_SET",
                    {
                        "snapshot_id": str(quote.id),
                        "anchor_price": str(anchor),
                        "limit_price": str(order.limit_price),
                        "basis": "paper_first_eligible_executable_quote",
                    },
                    now,
                )
                account.revision += 1
            self._check(db, account)
            return {**self.view(order), "reason": "READY"}

    def book_fill(
        self, account_id: UUID, order_id: UUID, booking: FillBooking, now: datetime
    ) -> dict:
        """Book an upstream matched fill atomically; this function is not a matcher."""
        self._clock(now)
        with Session(self.engine) as db, db.begin():
            account, now = self._lock(db, account_id)
            order = self._order(db, account_id, order_id)
            self._check(db, account)
            if not self._event(
                db, order, "fill:" + booking.event_key, "FILL", booking.model_dump(mode="json"), now
            ):
                return {**self.view(order), "duplicate": True}
            if order.status not in ACTIVE or order.eligible_at is None or order.expires_at is None:
                raise ValueError("Order cannot fill in its current state")
            if order.order_type in {"STOP_MARKET", "STOP_LIMIT"} and not db.scalar(
                select(PaperOrderEvent.id)
                .where(PaperOrderEvent.order_id == order.id, PaperOrderEvent.kind == "TRIGGERED")
                .limit(1)
            ):
                raise ValueError("Stop order requires a persisted upstream trigger event")
            if (
                not order.eligible_at <= now < order.expires_at
                or booking.quantity > order.quantity - order.filled_quantity
            ):
                raise ValueError("Fill outside eligibility, lifetime or remaining quantity")
            record = db.get(SnapshotRecord, booking.snapshot_id)
            if record is None or record.instrument_id != order.instrument_id:
                raise ValueError("Persisted market observation required")
            quote = Quote.model_validate(record.payload)
            config = PaperExecutionConfig.model_validate(order.execution_config)
            max_age = config.execution.quote_max_age_ms
            assert max_age is not None
            if (
                quote_problem(quote, now, 10)
                or (now - quote.timestamp).total_seconds() * 1000 > max_age
            ):
                raise ValueError("Invalid or stale supporting quote")
            if (
                quote.market_event_id != booking.market_event_id
                or quote.timestamp < order.eligible_at
                or quote.received_at < order.eligible_at
            ):
                raise ValueError("Fill cannot use pre-eligible or mismatched market evidence")
            if (
                quote.quantity_unit == "unknown"
                or quote.quantity_unit != config.execution.quantity_unit
                or not quote.bid_depth
                or not quote.ask_depth
            ):
                raise ValueError("Verified depth/quantity evidence required")
            if quote.timestamp_basis != "exchange_feed" or quote.depth_kind != "best_five":
                raise ValueError("Exchange-feed timestamp and depth provenance required")
            instrument_record = db.get(InstrumentRecord, order.instrument_id)
            assert instrument_record is not None
            instrument = Instrument.model_validate(instrument_record.payload)
            schedules = [
                s
                for s in config.fee_schedules
                if s.exchange == instrument.exchange and s.applies(now.astimezone(IST).date())
            ]
            if not schedules or schedules[0].version != booking.cost_version:
                raise ValueError("Fill cost version mismatch")
            levels = quote.ask_depth if order.side == "BUY" else quote.bid_depth
            depth_level = next(
                (level for level in levels if level.price == booking.raw_price), None
            )
            if depth_level is None or booking.raw_price % instrument.tick_size:
                raise ValueError("Fill must reference an observed on-tick depth level")
            adverse = config.execution.extra_adverse_slippage_bps
            assert adverse is not None
            if booking.price != execution_price(
                booking.raw_price, instrument.tick_size, order.side, adverse
            ):
                raise ValueError("Fill price differs from declared adverse execution model")
            if order.order_type in {"MARKET", "STOP_MARKET"} and order.limit_price is None:
                raise ValueError("Market-style order requires a fixed paper protection bound")
            assert order.accepted_at is not None
            day = order.accepted_at.astimezone(IST).date()
            if quote.timestamp.astimezone(IST).date() != day:
                raise ValueError("Liquidity evidence belongs to another session")
            previous_depth = level_budget(
                db, account_id, day, instrument, order.side, booking.raw_price
            )
            if previous_depth and previous_depth.config_version != config.version:
                raise ValueError("Liquidity model cannot change within an existing session/level")
            units = displayed_units(depth_level, quote, instrument)
            if booking.quantity > available_units(previous_depth, quote, units, config.execution):
                raise ValueError("Fill exceeds remaining observed participation capacity")
            new_capacity, new_displayed = capacity_state(
                previous_depth, quote, units, config.execution
            )
            current_fees, other_fees = fee_contexts(db, order, schedules[0])
            expected_fees = incremental_fees(
                schedules[0], current_fees, money(booking.price * booking.quantity), other_fees
            )
            if booking.fee_breakdown != expected_fees or booking.fees != sum(
                expected_fees.values(), Decimal(0)
            ):
                raise ValueError("Fill fees differ from frozen order/session accrual")
            if booking.price % instrument.tick_size:
                raise ValueError("Fill price is off tick")
            if (
                config.execution.partial_fill_granularity == "lots"
                and booking.quantity % instrument.lot_size
            ):
                raise ValueError("Fill violates configured lot granularity")
            if order.limit_price is not None and (
                order.side == "BUY"
                and booking.price > order.limit_price
                or order.side == "SELL"
                and booking.price < order.limit_price
            ):
                raise ValueError("Fill violates order limit")
            fills = order_fills(db, order.id)
            _, previous_premium, previous_fees, _ = fill_totals(fills)
            premium = money(booking.price * booking.quantity)
            if (
                order.side == "BUY"
                and previous_premium + previous_fees + premium + booking.fees > order.cash_budget
            ):
                raise ValueError("Fill exceeds approved entry cash budget")
            if order.side == "BUY" and (not account.enabled or account.daily_blocked):
                raise ValueError("Entry fill blocked by pause/daily risk state")
            if order.side == "BUY":
                from services.paper.qualification import entry_permission

                validation = entry_permission(
                    db,
                    account,
                    now,
                    instrument.id,
                    order.quantity,
                    order.id,
                    instrument=instrument,
                    entry_source="HUMAN" if order.manual_intent_id else "AI",
                )
                if (
                    validation.validation_id != order.validation_id
                    or validation.arm_id != order.arm_id
                ):
                    raise ValueError("VALIDATION_ORDER_MISMATCH")
                if order.manual_intent_id:
                    intent = self._manual_intent(
                        db, account, order.manual_intent_id, instrument, now
                    )
                    if (
                        not intent.stop_loss < booking.price <= intent.entry_limit
                        or booking.price >= intent.target
                    ):
                        raise ValueError("Fill violates human entry prices")
                else:
                    decision = db.get(DecisionRecord, order.decision_id)
                    assert decision is not None
                    from services.worker.models import RuntimeControl

                    control = db.scalar(
                        select(RuntimeControl)
                        .where(RuntimeControl.account_id == account_id)
                        .with_for_update()
                    )
                    if (
                        control is None
                        or not control.active_envelope
                        or control.active_envelope.get("id") != decision.payload["strategy_id"]
                        or control.active_envelope.get("invalidated")
                    ):
                        raise ValueError("Runtime strategy invalidated before entry fill")
                    strategy = db.get(StrategyRecord, UUID(decision.payload["strategy_id"]))
                    assert strategy is not None
                    envelope = StrategyEnvelope.model_validate(strategy.payload)
                    entry_permission(
                        db, account, now, instrument.id, order.quantity, order.id, envelope.version
                    )
                    if (
                        envelope.invalidated
                        or now >= envelope.expires_at
                        or not envelope.min_entry <= booking.price <= envelope.max_entry
                    ):
                        raise ValueError("Fill violates approved strategy envelope")
            position = (
                db.scalar(select(PaperPosition).where(PaperPosition.entry_order_id == order.id))
                if order.side == "BUY"
                else db.get(PaperPosition, order.position_id)
            )
            if (
                order.side == "BUY"
                and position is not None
                and (position.pending_exit or position.closed_quantity or position.closed_at)
            ):
                raise ValueError("Entry fills cannot resume after protection/exit begins")
            if order.side == "SELL" and (
                position is None or booking.quantity > position.quantity - position.closed_quantity
            ):
                raise ValueError("Fill would oversell position")
            other_cash, _, _ = reservations(db, account_id)
            new_hold = (
                max(Decimal(0), premium - booking.fees)
                if order.side == "SELL"
                and config.execution.sale_proceeds_reuse == "block_until_verified"
                else Decimal(0)
            )
            cash_after = (
                account.cash + (premium if order.side == "SELL" else -premium) - booking.fees
            )
            remaining_reserve = (
                order.cash_budget - previous_premium - previous_fees - premium - booking.fees
                if order.side == "BUY" and order.filled_quantity + booking.quantity < order.quantity
                else Decimal(0)
            )
            if (
                cash_after
                < other_cash
                - order.reserved_cash
                + remaining_reserve
                + restricted_proceeds(db, account_id)
                + new_hold
            ):
                raise ValueError("Fill would spend reserved/unavailable cash")
            commit_at = self.clock()
            self._clock(commit_at)
            if (
                commit_at < now
                or commit_at >= order.expires_at
                or quote_problem(quote, commit_at, 10)
                or (commit_at - quote.timestamp).total_seconds() * 1000 > max_age
            ):
                raise ValueError("Fill expired while waiting for accounting checks")
            fill = PaperFill(
                order_id=order.id,
                snapshot_id=booking.snapshot_id,
                quantity=booking.quantity,
                price=booking.price,
                fees=booking.fees,
                fee_breakdown={k: str(v) for k, v in booking.fee_breakdown.items()},
                config_version=config.version,
                cost_version=booking.cost_version,
                event_key=booking.event_key,
                market_event_id=booking.market_event_id,
                timestamp=now,
                execution_version=order.execution_version,
            )
            db.add(fill)
            db.flush()
            if previous_depth is None:
                previous_depth = PaperLiquidityLevel(
                    account_id=account_id,
                    session_key=day,
                    instrument_id=instrument.id,
                    side=order.side,
                    price=booking.raw_price,
                    displayed=new_displayed,
                    capacity=new_capacity,
                    consumed=0,
                    observation_at=quote.timestamp,
                    source=quote.source,
                    config_version=config.version,
                )
                db.add(previous_depth)
                db.flush()
            previous_depth.capacity = new_capacity
            previous_depth.displayed = new_displayed
            previous_depth.consumed += booking.quantity
            previous_depth.observation_at = quote.timestamp
            previous_depth.source = quote.source
            db.add(
                PaperLiquidityUse(
                    level_id=previous_depth.id,
                    fill_id=fill.id,
                    quantity=booking.quantity,
                    raw_price=booking.raw_price,
                )
            )
            if new_hold:
                db.add(
                    PaperFundsHold(
                        account_id=account_id,
                        fill_id=fill.id,
                        amount=new_hold,
                        created_at=now,
                        reason="SALE_PROCEEDS_REUSE_UNVERIFIED",
                    )
                )
            db.add_all(
                [
                    LedgerEntry(
                        account_id=account_id,
                        fill_id=fill.id,
                        category="PREMIUM",
                        amount=premium if order.side == "SELL" else -premium,
                        timestamp=now,
                    ),
                    LedgerEntry(
                        account_id=account_id,
                        fill_id=fill.id,
                        category="FEE",
                        amount=-booking.fees,
                        timestamp=now,
                    ),
                ]
            )
            account.cash = cash_after
            account.revision += 1
            order.filled_quantity += booking.quantity
            if order.filled_quantity == order.quantity:
                self._finish(order, "FILLED", now)
            else:
                if order.status != "CANCEL_REQUESTED":
                    order.status = "PARTIALLY_FILLED"
                order.reserved_cash = remaining_reserve
                order.reserved_risk = (
                    order.risk_budget - prorated_risk(order, order.filled_quantity)
                    if order.side == "BUY"
                    else Decimal(0)
                )
            if position is None:
                protection: ManualEntryIntent | StrategyEnvelope
                if order.manual_intent_id:
                    protection = self._manual_intent(
                        db, account, order.manual_intent_id, instrument, now
                    )
                else:
                    decision = db.get(DecisionRecord, order.decision_id)
                    assert decision is not None
                    strategy = db.get(StrategyRecord, UUID(decision.payload["strategy_id"]))
                    assert strategy is not None
                    envelope = StrategyEnvelope.model_validate(strategy.payload)
                    protection = envelope
                risk_config = RiskConfig.model_validate(account.config)
                position = PaperPosition(
                    account_id=account_id,
                    instrument_id=order.instrument_id,
                    entry_order_id=order.id,
                    quantity=booking.quantity,
                    closed_quantity=0,
                    average_price=booking.price,
                    entry_fees=booking.fees,
                    stop_loss=protection.stop_loss,
                    target=protection.target,
                    planned_risk=prorated_risk(order, order.filled_quantity),
                    max_holding_seconds=min(
                        risk_config.max_holding_seconds, protection.max_holding_seconds
                    ),
                    opened_at=now,
                    config=risk_config.model_dump(mode="json"),
                    realized_pnl=Decimal(0),
                )
                db.add(position)
                db.flush()
            refresh_position(db, position)
            if order.side == "BUY":
                position.planned_risk = prorated_risk(order, position.quantity)
            else:
                entry_order = db.get(PaperOrder, position.entry_order_id)
                assert entry_order is not None
                position.planned_risk = prorated_risk(
                    entry_order, position.quantity - position.closed_quantity
                )
                position.exit_order_id = order.id
                if position.quantity == position.closed_quantity:
                    position.closed_at, position.pending_exit = now, None
            PaperEngine._event(
                db, account, "PAPER_FILL_BOOKED", now, fill_id=str(fill.id), **self.view(order)
            )
            self._check(db, account)
            return {**self.view(order), "duplicate": False}

    def recover(self, account_id: UUID, now: datetime) -> dict:
        self._clock(now)
        with Session(self.engine) as db, db.begin():
            account, now = self._lock(db, account_id)
            account.enabled = False
            account.revision += 1
            problems = reconcile_account(db, account)
            PaperEngine._event(db, account, "DURABLE_RECOVERY", now, problems=problems)
            return {"reconciled": not problems, "problems": problems, "entries_paused": True}

    def reject(
        self, account_id: UUID, order_id: UUID, event_key: str, reason: str, now: datetime
    ) -> dict:
        self._clock(now)
        if not event_key or not reason:
            raise ValueError("Rejection event identity and reason required")
        with Session(self.engine) as db, db.begin():
            account, now = self._lock(db, account_id)
            order = self._order(db, account_id, order_id)
            self._check(db, account)
            if not self._event(db, order, event_key, "REJECTED", {"reason": reason}, now):
                return self.view(order)
            if order.status in TERMINAL or order.filled_quantity:
                raise ValueError(
                    "Only active unfilled orders can be rejected; cancel partial orders"
                )
            self._finish(order, "REJECTED", now)
            account.revision += 1
            PaperEngine._event(
                db,
                account,
                "PAPER_ORDER_REJECTED",
                now,
                rejection_reason=reason,
                **self.view(order),
            )
            self._check(db, account)
            return self.view(order)
