"""Transactional paper execution. This module has no broker or HTTP client."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.core.contracts import (
    ExchangeSession,
    Instrument,
    Quote,
    RiskConfig,
    StrategyEnvelope,
    TradeDecision,
    UnderlyingExitPolicy,
    money,
)
from services.core.models import (
    Account,
    AuditEvent,
    DecisionRecord,
    InstrumentRecord,
    LedgerEntry,
    PaperFill,
    PaperOrder,
    PaperPosition,
    SnapshotRecord,
    StrategyRecord,
)
from services.market.reference_contracts import IndexReference
from services.paper.accounting import (
    ACTIVE,
    LEGACY,
    reconcile_account,
    reservations,
    restricted_proceeds,
)
from services.risk.engine import (
    PortfolioState,
    daily_limit_reached,
    evaluate_risk,
    fees,
    quote_problem,
)


class ConflictError(ValueError):
    """A supposedly immutable identifier was reused with different contents."""


@dataclass(frozen=True)
class Execution:
    status: str
    reason: str
    order_id: str | None = None
    quantity: int = 0
    fill_price: str | None = None


class PaperEngine:
    def __init__(self, engine: Engine, clock: Callable[[], datetime] | None = None):
        self.engine = engine
        self.clock = clock

    @staticmethod
    def _account(db: Session, account_id: UUID) -> Account:
        account = db.scalar(select(Account).where(Account.id == account_id).with_for_update())
        if account is None:
            raise ValueError("Unknown paper account")
        return account

    @staticmethod
    def _event(db: Session, account: Account, kind: str, now: datetime, **details: object) -> None:
        db.add(AuditEvent(account_id=account.id, kind=kind, timestamp=now, details=details))

    @staticmethod
    def _open_positions(db: Session, account_id: UUID) -> list[PaperPosition]:
        return list(
            db.scalars(
                select(PaperPosition).where(
                    PaperPosition.account_id == account_id, PaperPosition.closed_at.is_(None)
                )
            )
        )

    @staticmethod
    def _persist_instrument(db: Session, instrument: Instrument) -> None:
        existing = db.get(InstrumentRecord, instrument.id)
        payload = instrument.model_dump(mode="json")
        if existing is None:
            db.execute(
                insert(InstrumentRecord)
                .values(id=instrument.id, payload=payload)
                .on_conflict_do_nothing(index_elements=[InstrumentRecord.id])
            )
            existing = db.get(InstrumentRecord, instrument.id)
        identity = {name: value for name, value in payload.items() if name != "verified_at"}
        previous = (
            {name: value for name, value in existing.payload.items() if name != "verified_at"}
            if existing
            else None
        )
        if existing and previous != identity:
            raise ConflictError("Instrument identifier metadata changed")
        if (
            existing and existing.payload != payload
            and Instrument.model_validate(existing.payload).verified_at < instrument.verified_at
        ):
            existing.payload = payload

    @staticmethod
    def _persist_quote(db: Session, quote: Quote) -> None:
        existing = db.get(SnapshotRecord, quote.id)
        payload = quote.model_dump(mode="json")
        if existing and existing.payload != payload:
            raise ConflictError("Snapshot identifier reused")
        if existing is None:
            db.add(
                SnapshotRecord(
                    id=quote.id,
                    instrument_id=quote.instrument_id,
                    timestamp=quote.timestamp,
                    payload=payload,
                )
            )
            db.flush()

    def create_account(self, config: RiskConfig, now: datetime) -> UUID:
        if now.tzinfo is None:
            raise ValueError("Timezone-aware clock required")
        with Session(self.engine) as db, db.begin():
            account = Account(cash=config.capital, config=config.model_dump(mode="json"))
            db.add(account)
            db.flush()
            db.add(
                LedgerEntry(
                    account_id=account.id, category="CAPITAL", amount=config.capital, timestamp=now
                )
            )
            self._event(db, account, "ACCOUNT_CREATED", now, config_version=config.version)
            return account.id

    def start_session(self, account_id: UUID, session: ExchangeSession, now: datetime) -> None:
        if not session.verified or now.tzinfo is None:
            raise ValueError("Verified session and timezone-aware clock required")
        with Session(self.engine) as db, db.begin():
            account = self._account(db, account_id)
            if account.session_key == session.key:
                return  # Never reset a daily-loss baseline on a retry/restart.
            if account.session_key and session.key < account.session_key:
                raise ValueError("Cannot rewind the account session")
            if self._open_positions(db, account.id):
                raise ValueError("Unresolved positions block a new session")
            if db.scalar(
                select(PaperOrder.id)
                .where(PaperOrder.account_id == account.id, PaperOrder.status.in_(ACTIVE))
                .limit(1)
            ):
                raise ValueError("Unresolved orders block a new session")
            if not self._reconcile(db, account):
                raise ValueError("Unreconciled account")
            account.session_key = session.key
            account.session_opening_equity = account.cash
            account.daily_blocked = False
            account.enabled = False
            account.revision += 1
            self._event(db, account, "SESSION_STARTED", now, session=session.key.isoformat())

    def set_enabled(self, account_id: UUID, enabled: bool, now: datetime) -> None:
        with Session(self.engine) as db, db.begin():
            account = self._account(db, account_id)
            if enabled and (
                account.session_key is None
                or account.daily_blocked
                or not self._reconcile(db, account)
                or any(p.pending_exit for p in self._open_positions(db, account.id))
            ):
                raise ValueError("Account cannot resume until preflight passes")
            account.enabled = enabled
            account.revision += 1
            self._event(db, account, "RESUMED" if enabled else "PAUSED", now)

    @staticmethod
    def _reconcile(db: Session, account: Account) -> bool:
        return not reconcile_account(db, account)

    def _state(
        self,
        db: Session,
        account: Account,
        config: RiskConfig,
        quotes: dict[str, Quote],
        now: datetime,
    ) -> PortfolioState:
        positions = self._open_positions(db, account.id)
        if any(
            (entry := db.get(PaperOrder, position.entry_order_id)) is not None
            and entry.execution_version != LEGACY
            for position in positions
        ):
            from services.paper.portfolio import portfolio_snapshot

            return portfolio_snapshot(db, account, quotes, now).state
        reserved_cash, pending_risk, _ = reservations(db, account.id)
        pending_entries = list(
            db.scalars(
                select(PaperOrder).where(
                    PaperOrder.account_id == account.id,
                    PaperOrder.side == "BUY",
                    PaperOrder.status.in_(ACTIVE),
                )
            )
        )
        equity = account.cash
        fresh = True
        for position in positions:
            entry_order = db.get(PaperOrder, position.entry_order_id)
            if entry_order is not None and entry_order.execution_version != LEGACY:
                fresh = False  # Step 3 must provide depth/fee-aware liquidation valuation.
                continue
            quote = quotes.get(position.instrument_id)
            position_config = RiskConfig.model_validate(position.config)
            if quote_problem(quote, now, config.quote_max_age_seconds):
                fresh = False
                continue
            assert quote is not None and quote.bid is not None
            record = db.get(InstrumentRecord, position.instrument_id)
            assert record is not None
            instrument = Instrument.model_validate(record.payload)
            if position_config.costs is None:
                fresh = False
                continue
            price = position_config.costs.price(quote.bid, instrument.tick_size, "SELL")
            remaining = position.quantity - position.closed_quantity
            equity += money(price * remaining) - fees(position_config.costs, price, remaining)
        return PortfolioState(
            cash=account.cash - reserved_cash - restricted_proceeds(db, account.id),
            equity=money(equity),
            session_opening_equity=account.session_opening_equity or account.cash,
            open_positions=len(positions)
            + sum(o.id not in {p.entry_order_id for p in positions} for o in pending_entries),
            reserved_risk=pending_risk + sum((p.planned_risk for p in positions), Decimal(0)),
            enabled=account.enabled,
            daily_blocked=account.daily_blocked,
            reconciled=self._reconcile(db, account),
            valuation_fresh=fresh,
        )

    def enter(
        self,
        account_id: UUID,
        decision: TradeDecision,
        instrument: Instrument,
        quote: Quote,
        envelope: StrategyEnvelope,
        session: ExchangeSession,
        now: datetime,
    ) -> Execution:
        with Session(self.engine) as db, db.begin():
            account = self._account(db, account_id)
            now = self.clock() if self.clock else now
            existing = db.get(DecisionRecord, decision.id)
            if existing:
                if existing.account_id != account.id or existing.payload != decision.model_dump(
                    mode="json"
                ):
                    raise ConflictError("Decision identifier reused")
                return Execution(**existing.result)
            config = RiskConfig.model_validate(account.config)
            state = self._state(db, account, config, {instrument.id: quote}, now)
            if account.session_key != session.key:
                from dataclasses import replace

                state = replace(state, session_matches=False)
            if state.valuation_fresh and daily_limit_reached(state, config):
                account.daily_blocked = True
                account.enabled = False
                self._event(db, account, "DAILY_LOSS_LIMIT", now)
            risk = evaluate_risk(decision, instrument, quote, envelope, config, state, session, now)
            if risk.approved:
                self._persist_instrument(db, instrument)
                self._persist_quote(db, quote)
                for evidence in {*decision.snapshot_ids, *envelope.evidence_ids}:
                    record = db.get(SnapshotRecord, evidence)
                    if record is None or record.timestamp > now:
                        risk = type(risk)(False, "UNAVAILABLE_EVIDENCE")
                        break
            if not risk.approved:
                result = Execution("WAIT" if decision.action == "WAIT" else "REJECTED", risk.reason)
                db.add(
                    DecisionRecord(
                        id=decision.id,
                        account_id=account.id,
                        payload=decision.model_dump(mode="json"),
                        result=asdict(result),
                    )
                )
                self._event(
                    db,
                    account,
                    "ENTRY_REJECTED",
                    now,
                    decision_id=str(decision.id),
                    reason=risk.reason,
                )
                return result
            strategy = db.get(StrategyRecord, envelope.id)
            if strategy and (
                strategy.account_id != account.id
                or strategy.payload != envelope.model_dump(mode="json")
            ):
                raise ConflictError("Strategy identifier reused")
            if strategy is None:
                db.add(
                    StrategyRecord(
                        id=envelope.id,
                        account_id=account.id,
                        payload=envelope.model_dump(mode="json"),
                    )
                )
            decision_record = DecisionRecord(
                id=decision.id,
                account_id=account.id,
                payload=decision.model_dump(mode="json"),
                result={},
            )
            db.add(decision_record)
            db.flush()
            if self.clock:
                now = self.clock()
                risk = evaluate_risk(
                    decision, instrument, quote, envelope, config, state, session, now
                )
                if not risk.approved:
                    result = Execution("REJECTED", risk.reason)
                    decision_record.result = asdict(result)
                    self._event(
                        db,
                        account,
                        "ENTRY_REJECTED",
                        now,
                        reason=risk.reason,
                        decision_id=str(decision.id),
                    )
                    return result
            order = PaperOrder(
                account_id=account.id,
                decision_id=decision.id,
                instrument_id=instrument.id,
                side="BUY",
                quantity=risk.quantity,
                idempotency_key=f"entry:{decision.id}",
                reason="APPROVED",
                timestamp=now,
            )
            fill = self._record_fill(db, account, order, quote, risk.fill_price, config)
            db.add(
                PaperPosition(
                    account_id=account.id,
                    instrument_id=instrument.id,
                    entry_order_id=order.id,
                    quantity=risk.quantity,
                    average_price=risk.fill_price,
                    entry_fees=fill.fees,
                    stop_loss=(
                        envelope.underlying_exit_policy.premium_stop(
                            risk.fill_price, instrument.tick_size
                        )
                        if envelope.underlying_exit_policy is not None
                        and envelope.underlying_exit_policy.premium_stop_fraction is not None
                        else envelope.stop_loss
                    ),
                    target=envelope.target,
                    planned_risk=risk.planned_risk,
                    max_holding_seconds=min(
                        config.max_holding_seconds, envelope.max_holding_seconds
                    ),
                    opened_at=now,
                    underlying_exit_policy=(
                        envelope.underlying_exit_policy.model_dump(mode="json")
                        if envelope.underlying_exit_policy is not None
                        else None
                    ),
                    config=config.model_dump(mode="json"),
                )
            )
            result = Execution(
                "FILLED", "APPROVED", str(order.id), risk.quantity, str(risk.fill_price)
            )
            decision_record.result = asdict(result)
            self._event(
                db,
                account,
                "ENTRY_FILLED",
                now,
                order_id=str(order.id),
                risk=str(risk.planned_risk),
                budget=str(risk.budget),
                config=config.version,
            )
            return result

    @staticmethod
    def _record_fill(
        db: Session,
        account: Account,
        order: PaperOrder,
        quote: Quote,
        price: Decimal,
        config: RiskConfig,
    ) -> PaperFill:
        order.status = "FILLED"
        order.filled_quantity = order.quantity
        order.accepted_at = order.eligible_at = order.completed_at = order.timestamp
        db.add(order)
        db.flush()
        if config.costs is None:
            raise ValueError("Legacy fee configuration unavailable")
        breakdown = config.costs.fees(price, order.quantity)
        cost = sum(breakdown.values(), Decimal(0))
        fill = PaperFill(
            order_id=order.id,
            snapshot_id=quote.id,
            quantity=order.quantity,
            price=price,
            fees=cost,
            fee_breakdown={k: str(v) for k, v in breakdown.items()},
            config_version=config.version,
            cost_version=config.costs.version,
            timestamp=order.timestamp,
            event_key="legacy:" + str(order.id),
        )
        db.add(fill)
        db.flush()
        premium = money(price * order.quantity) * (-1 if order.side == "BUY" else 1)
        db.add_all(
            [
                LedgerEntry(
                    account_id=account.id,
                    fill_id=fill.id,
                    category="PREMIUM",
                    amount=premium,
                    timestamp=order.timestamp,
                ),
                LedgerEntry(
                    account_id=account.id,
                    fill_id=fill.id,
                    category="FEE",
                    amount=-cost,
                    timestamp=order.timestamp,
                ),
            ]
        )
        account.cash += premium - cost
        db.flush()
        return fill

    def monitor(
        self,
        account_id: UUID,
        quotes: dict[str, Quote],
        session: ExchangeSession | None,
        now: datetime,
        *,
        invalidated: bool = False,
        references: dict[str, IndexReference] | None = None,
    ) -> list[Execution]:
        if now.tzinfo is None:
            raise ValueError("Timezone-aware clock required")
        results = []
        with Session(self.engine) as db, db.begin():
            account = self._account(db, account_id)
            now = self.clock() if self.clock else now
            config = RiskConfig.model_validate(account.config)
            state = self._state(db, account, config, quotes, now)
            if not state.reconciled:
                account.enabled = False
                self._event(db, account, "RECONCILIATION_FAILED", now)
                return [Execution("BLOCKED", "UNRECONCILED_ACCOUNT")]
            if state.valuation_fresh and daily_limit_reached(state, config):
                account.daily_blocked = True
                account.enabled = False
                self._event(db, account, "DAILY_LOSS_LIMIT", now)
            for position in self._open_positions(db, account.id):
                entry_order = db.get(PaperOrder, position.entry_order_id)
                if entry_order is not None and entry_order.execution_version != LEGACY:
                    results.append(Execution("PENDING", "DURABLE_MATCHER_PENDING"))
                    continue
                quote = quotes.get(position.instrument_id)
                reason = position.pending_exit
                if not reason:
                    if account.daily_blocked:
                        reason = "DAILY_LOSS_LIMIT"
                    elif (
                        session is None
                        or session.key != account.session_key
                        or not session.verified
                    ):
                        reason = "SESSION_UNVERIFIED"
                    elif now >= session.closes_at - timedelta(minutes=config.flatten_minutes):
                        reason = "SESSION_FLATTEN"
                    elif invalidated:
                        reason = "STRATEGY_INVALIDATED"
                    elif now >= position.opened_at + timedelta(
                        seconds=position.max_holding_seconds
                    ):
                        reason = "MAX_HOLDING_TIME"
                    elif quote and not quote_problem(quote, now, config.quote_max_age_seconds):
                        assert quote.bid is not None
                        if quote.bid <= position.stop_loss:
                            reason = "STOP_LOSS"
                        elif position.target is not None and quote.bid >= position.target:
                            reason = "TAKE_PROFIT"
                    if not reason and position.underlying_exit_policy is not None:
                        try:
                            policy = UnderlyingExitPolicy.model_validate(
                                position.underlying_exit_policy
                            )
                            reference = (references or {}).get(policy.underlying)
                            if (
                                reference is None
                                or reference.underlying != policy.underlying
                                or reference.timestamp > now
                                or reference.received_at > now
                                or (now - reference.timestamp).total_seconds()
                                > config.quote_max_age_seconds
                                or (now - reference.received_at).total_seconds()
                                > config.quote_max_age_seconds
                            ):
                                reason = "UNDERLYING_REFERENCE_UNAVAILABLE"
                            elif policy.direction == "BULLISH":
                                if reference.last_price <= policy.invalidation:
                                    reason = "UNDERLYING_INVALIDATION"
                                elif reference.last_price >= policy.target:
                                    reason = "UNDERLYING_TARGET"
                            else:
                                if reference.last_price >= policy.invalidation:
                                    reason = "UNDERLYING_INVALIDATION"
                                elif reference.last_price <= policy.target:
                                    reason = "UNDERLYING_TARGET"
                        except (ValueError, TypeError, KeyError):
                            reason = "UNDERLYING_REFERENCE_UNAVAILABLE"
                problem = quote_problem(quote, now, config.quote_max_age_seconds)
                if not reason:
                    if problem:
                        self._event(db, account, "VALUATION_UNAVAILABLE", now, reason=problem)
                    continue
                position.pending_exit = reason
                if problem or quote is None or quote.instrument_id != position.instrument_id:
                    self._event(
                        db,
                        account,
                        "EXIT_PENDING",
                        now,
                        reason=reason,
                        data_problem=problem or "INSTRUMENT_MISMATCH",
                    )
                    results.append(Execution("PENDING", reason))
                    continue
                if (quote.bid_quantity or 0) < position.quantity:
                    self._event(db, account, "EXIT_PENDING", now, reason="INSUFFICIENT_DEPTH")
                    results.append(Execution("PENDING", "INSUFFICIENT_DEPTH"))
                    continue
                record = db.get(InstrumentRecord, position.instrument_id)
                assert record is not None and quote.bid is not None
                instrument = Instrument.model_validate(record.payload)
                position_config = RiskConfig.model_validate(position.config)
                if position_config.costs is None:
                    results.append(Execution("PENDING", "LEGACY_COSTS_UNAVAILABLE"))
                    continue
                price = position_config.costs.price(quote.bid, instrument.tick_size, "SELL")
                if price <= 0:
                    results.append(Execution("PENDING", "INVALID_EXIT_PRICE"))
                    continue
                self._persist_quote(db, quote)
                if self.clock:
                    now = self.clock()
                    if quote_problem(quote, now, config.quote_max_age_seconds):
                        results.append(Execution("PENDING", "QUOTE_EXPIRED_DURING_EXECUTION"))
                        self._event(db, account, "EXIT_PENDING", now, reason=reason)
                        continue
                order = PaperOrder(
                    account_id=account.id,
                    instrument_id=instrument.id,
                    side="SELL",
                    position_id=position.id,
                    quantity=position.quantity,
                    idempotency_key=f"exit:{position.id}",
                    reason=reason,
                    timestamp=now,
                )
                fill = self._record_fill(db, account, order, quote, price, position_config)
                position.closed_at = now
                position.closed_quantity = position.quantity
                position.exit_order_id = order.id
                position.pending_exit = None
                position.realized_pnl = (
                    money(price * position.quantity)
                    - money(position.average_price * position.quantity)
                    - position.entry_fees
                    - fill.fees
                )
                self._event(db, account, "EXIT_FILLED", now, order_id=str(order.id), reason=reason)
                results.append(
                    Execution("FILLED", reason, str(order.id), position.quantity, str(price))
                )
            db.flush()
            if not self._open_positions(db, account.id) and account.session_opening_equity:
                if account.cash <= account.session_opening_equity * (1 - config.max_daily_loss_pct):
                    account.daily_blocked = True
                    account.enabled = False
        return results

    def recover(self, account_id: UUID, now: datetime) -> bool:
        with Session(self.engine) as db, db.begin():
            account = self._account(db, account_id)
            account.enabled = False
            account.revision += 1
            reconciled = self._reconcile(db, account)
            self._event(db, account, "RECOVERED" if reconciled else "RECONCILIATION_FAILED", now)
            return reconciled

    def portfolio(self, account_id: UUID, quotes: dict[str, Quote], now: datetime) -> dict:
        with Session(self.engine) as db, db.begin():
            account = self._account(db, account_id)
            config = RiskConfig.model_validate(account.config)
            state = self._state(db, account, config, quotes, now)
            positions = list(
                db.scalars(select(PaperPosition).where(PaperPosition.account_id == account.id))
            )
            costs = db.scalar(
                select(func.coalesce(func.sum(PaperFill.fees), 0))
                .join(PaperOrder, PaperFill.order_id == PaperOrder.id)
                .where(PaperOrder.account_id == account.id)
            )
            return {
                "account_id": str(account.id),
                "cash": str(account.cash),
                "reserved_cash": str(reservations(db, account.id)[0]),
                "restricted_proceeds": str(restricted_proceeds(db, account.id)),
                "available_cash": str(state.cash),
                "equity": str(state.equity) if state.valuation_fresh else None,
                "valuation_fresh": state.valuation_fresh,
                "reconciled": state.reconciled,
                "open_positions": sum(p.closed_at is None for p in positions),
                "position_slots_used": state.open_positions,
                "pending_entry_orders": reservations(db, account.id)[2],
                "realized_pnl": str(
                    sum((p.realized_pnl or Decimal(0) for p in positions), Decimal(0))
                ),
                "fees": str(costs),
                "enabled": account.enabled,
                "daily_blocked": account.daily_blocked,
                "session_opening_equity": str(account.session_opening_equity),
            }
