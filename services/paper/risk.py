"""Deterministic, read-only sizing for the durable execution engine.

The caller supplies a reconciled account snapshot and loaded liquidity budgets.
This function does not persist approval, reserve cash, or authorize worker startup.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from uuid import UUID

from services.core.contracts import (
    IST,
    ExchangeSession,
    Instrument,
    Quote,
    RiskConfig,
    StrategyEnvelope,
    TradeDecision,
)
from services.core.execution import FeeSchedule, PaperExecutionConfig
from services.core.models import PaperLiquidityLevel
from services.paper.contracts import OrderRiskApproval
from services.paper.fees import raw_charge
from services.paper.liquidity import (
    buy_capacity,
    execution_price,
    protection_price,
)
from services.risk.engine import PortfolioState, entry_problem


@dataclass(frozen=True)
class DepthRiskResult:
    reason: str
    approval: OrderRiskApproval | None = None
    entry_limit: Decimal | None = None
    estimated_stop_price: Decimal | None = None


def fee_ceiling(schedule: FeeSchedule, side: str, premium: Decimal) -> Decimal:
    """Upper allowance independent of prior session-rounding allocations.

    Rounding upward per component also bounds charge-based downstream taxes.
    This is a reservation estimate; actual fills still use incremental_fees.
    """
    charges: dict[str, Decimal] = {}
    for rule in schedule.rules:
        raw = raw_charge(rule, side, premium, charges)
        charges[rule.code] = (raw / rule.rounding_increment).to_integral_value(
            rounding=ROUND_CEILING
        ) * rule.rounding_increment
    return sum(charges.values(), Decimal(0))


def size_entry(
    decision: TradeDecision,
    instrument: Instrument,
    quote: Quote,
    envelope: StrategyEnvelope,
    config: RiskConfig,
    state: PortfolioState,
    session: ExchangeSession,
    now: datetime,
    *,
    execution: PaperExecutionConfig,
    account_id: UUID,
    account_revision: int,
    budgets: dict[Decimal, PaperLiquidityLevel] | None,
) -> DepthRiskResult:
    """Size whole lots against available depth and worst permitted entry price.

    state.cash must exclude pending reservations and restricted sale proceeds;
    state.equity must be complete net liquidation equity (not available cash).
    state.reserved_risk includes positions and pending entry orders. A missing
    valuation or budget read must be reported unavailable, never replaced by zero.
    The resulting limit must be used for a LIMIT order. A market order may anchor
    a different price bound on a later observation and is outside this approval.
    """
    if account_revision < 0:
        return DepthRiskResult("INVALID_ACCOUNT_REVISION")
    amounts = (state.cash, state.equity, state.session_opening_equity, state.reserved_risk)
    if any(not value.is_finite() for value in amounts) or state.reserved_risk < 0:
        return DepthRiskResult("INVALID_PORTFOLIO_AMOUNTS")
    if state.session_opening_equity <= 0:
        return DepthRiskResult("INVALID_SESSION_EQUITY")
    problem = entry_problem(decision, instrument, quote, envelope, config, state, session, now)
    if problem:
        return DepthRiskResult(problem)
    policy = execution.execution
    if policy.blockers():
        return DepthRiskResult("EXECUTION_POLICY_UNAVAILABLE")
    day = now.astimezone(IST).date()
    schedules = [
        s for s in execution.fee_schedules if s.exchange == instrument.exchange and s.applies(day)
    ]
    if not schedules or not schedules[0].reviewed:
        return DepthRiskResult("FEE_SCHEDULE_UNAVAILABLE")
    schedule = schedules[0]
    assert policy.quote_max_age_ms is not None
    assert policy.extra_adverse_slippage_bps is not None
    assert policy.market_protection_bps is not None
    assert policy.pending_entry_lifetime_ms is not None
    assert policy.assumed_latency_ms is not None
    if (now - quote.timestamp).total_seconds() * 1000 > policy.quote_max_age_ms:
        return DepthRiskResult("STALE_EXECUTION_QUOTE")
    if (
        quote.timestamp_basis != "exchange_feed"
        or not quote.market_event_id
        or quote.depth_kind != "best_five"
        or not quote.ask_depth
        or quote.quantity_unit == "unknown"
        or quote.quantity_unit != policy.quantity_unit
        or not quote.quantity_unit_source
    ):
        return DepthRiskResult("EXECUTABLE_DEPTH_UNAVAILABLE")
    if budgets is None:
        return DepthRiskResult("LIQUIDITY_BUDGET_UNAVAILABLE")
    assert quote.ask is not None
    entry_limit = min(
        envelope.max_entry,
        protection_price(quote.ask, instrument.tick_size, "BUY", policy.market_protection_bps),
    )
    entry_limit = (entry_limit / instrument.tick_size).to_integral_value(
        rounding=ROUND_FLOOR
    ) * instrument.tick_size
    if (
        decision.entry is None
        or not envelope.min_entry <= decision.entry <= envelope.max_entry
        or not envelope.min_entry <= entry_limit < envelope.target
    ):
        return DepthRiskResult("ENTRY_PREDICATE_FAILED")
    try:
        capacity = buy_capacity(
            quote,
            instrument,
            execution,
            account_id,
            day,
            budgets,
            minimum=envelope.min_entry,
            limit=entry_limit,
        )
    except ValueError as error:
        return DepthRiskResult(str(error))
    headroom = (
        state.session_opening_equity * config.max_daily_loss_pct
        - max(Decimal(0), state.session_opening_equity - state.equity)
        - state.reserved_risk
    )
    budget = min(min(config.capital, state.equity) * config.max_trade_risk_pct, headroom)
    if budget <= 0 or state.cash <= 0:
        return DepthRiskResult("NO_RISK_OR_CAPITAL")
    try:
        stop_price = execution_price(
            envelope.stop_loss, instrument.tick_size, "SELL", policy.extra_adverse_slippage_bps
        )
    except ValueError:
        return DepthRiskResult("INVALID_STOP_ESTIMATE")
    # Unit-level cent rounding bounds fragmented fill-premium rounding as well.
    entry_unit = entry_limit.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    stop_unit = stop_price.quantize(Decimal("0.01"), rounding=ROUND_FLOOR)

    def costs(quantity: int) -> tuple[Decimal, Decimal]:
        premium = entry_unit * quantity
        debit = premium + fee_ceiling(schedule, "BUY", premium)
        proceeds = stop_unit * quantity
        risk = debit - proceeds + fee_ceiling(schedule, "SELL", proceeds)
        return debit, risk

    low, high = 0, min(capacity, config.max_fill_quantity) // instrument.lot_size
    while low < high:
        lots = (low + high + 1) // 2
        debit, risk = costs(lots * instrument.lot_size)
        if debit <= state.cash and risk <= budget:
            low = lots
        else:
            high = lots - 1
    if not low:
        return DepthRiskResult("ONE_LOT_DOES_NOT_FIT")
    quantity = low * instrument.lot_size
    debit, risk = costs(quantity)
    expires = min(
        decision.expires_at,
        envelope.expires_at,
        session.closes_at - timedelta(minutes=config.entry_cutoff_minutes),
        now + timedelta(milliseconds=policy.pending_entry_lifetime_ms),
        quote.timestamp + timedelta(milliseconds=policy.quote_max_age_ms),
    )
    if expires <= now + timedelta(milliseconds=policy.assumed_latency_ms):
        return DepthRiskResult("INSUFFICIENT_EXECUTION_WINDOW")
    return DepthRiskResult(
        "APPROVED",
        OrderRiskApproval(
            quantity=quantity,
            cash_budget=debit,
            risk_budget=risk,
            account_revision=account_revision,
            risk_config_version=config.version,
            execution_config_version=execution.version,
            expires_at=expires,
            evidence_ids=tuple(
                sorted(set(decision.snapshot_ids) | set(envelope.evidence_ids), key=str)
            ),
            net_liquidation_equity=state.equity,
            entry_limit=entry_limit,
        ),
        entry_limit,
        stop_price,
    )
