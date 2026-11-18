"""Pure entry checks; no IO, model calls, clocks or mutable global state."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from services.core.contracts import (
    IST,
    CostModel,
    ExchangeSession,
    Instrument,
    Quote,
    RiskConfig,
    StrategyEnvelope,
    TradeDecision,
    money,
)


@dataclass(frozen=True)
class PortfolioState:
    cash: Decimal
    equity: Decimal
    session_opening_equity: Decimal
    open_positions: int = 0
    reserved_risk: Decimal = Decimal(0)
    enabled: bool = False
    daily_blocked: bool = False
    reconciled: bool = True
    valuation_fresh: bool = True
    session_matches: bool = True


@dataclass(frozen=True)
class RiskResult:
    approved: bool
    reason: str
    quantity: int = 0
    fill_price: Decimal = Decimal(0)
    planned_risk: Decimal = Decimal(0)
    budget: Decimal = Decimal(0)


def quote_problem(quote: Quote | None, now: datetime, max_age: int) -> str | None:
    if quote is None:
        return "MISSING_QUOTE"
    if now.tzinfo is None:
        return "INVALID_CLOCK"
    if quote.timestamp > now or quote.received_at > now or quote.received_at < quote.timestamp:
        return "INVALID_QUOTE_TIME"
    if now - quote.timestamp > timedelta(seconds=max_age):
        return "STALE_QUOTE"
    if quote.bid is None or quote.ask is None:
        return "MISSING_BID_ASK"
    if quote.bid > quote.ask:
        return "CROSSED_QUOTE"
    return None


def fees(costs: CostModel, price: Decimal, quantity: int) -> Decimal:
    return sum(costs.fees(price, quantity).values(), Decimal(0))


def daily_limit_reached(state: PortfolioState, config: RiskConfig) -> bool:
    return state.equity <= state.session_opening_equity * (1 - config.max_daily_loss_pct)


def entry_problem(
    decision: TradeDecision,
    instrument: Instrument,
    quote: Quote,
    envelope: StrategyEnvelope,
    config: RiskConfig,
    state: PortfolioState,
    session: ExchangeSession,
    now: datetime,
) -> str | None:
    """Shared admission checks; execution costs and sizing belong to each engine."""

    def reject(reason: str) -> str:
        return reason

    if decision.action == "WAIT":
        return reject("WAIT")
    if now.tzinfo is None:
        return reject("INVALID_CLOCK")
    if not state.enabled:
        return reject("PAUSED")
    if not state.reconciled or not state.valuation_fresh:
        return reject("UNRECONCILED_OR_STALE_PORTFOLIO")
    if state.daily_blocked or daily_limit_reached(state, config):
        return reject("DAILY_LOSS_LIMIT")
    if not session.verified or not state.session_matches:
        return reject("SESSION_UNVERIFIED")
    if not session.opens_at <= now < session.closes_at:
        return reject("MARKET_CLOSED")
    if now >= session.closes_at - timedelta(minutes=config.entry_cutoff_minutes):
        return reject("ENTRY_CUTOFF")
    if not decision.timestamp <= now < decision.expires_at:
        return reject("EXPIRED_DECISION")
    if envelope.invalidated or not envelope.issued_at <= now < envelope.expires_at:
        return reject("INVALID_STRATEGY_ENVELOPE")
    if (
        decision.strategy_id != envelope.id
        or decision.action != envelope.action
        or instrument.id not in envelope.instrument_ids
    ):
        return reject("STRATEGY_MISMATCH")
    if decision.stop_loss != envelope.stop_loss or decision.target != envelope.target:
        return reject("STRATEGY_PRICE_MISMATCH")
    if instrument.id != quote.instrument_id or instrument.id != decision.instrument_id:
        return reject("INSTRUMENT_MISMATCH")
    if instrument.option_type != ("CALL" if decision.action == "BUY_CALL" else "PUT"):
        return reject("OPTION_TYPE_MISMATCH")
    if instrument.verified_at > now:
        return reject("INVALID_METADATA_TIME")
    days = (instrument.expiry - now.astimezone(IST).date()).days
    if not 0 <= days <= 7:
        return reject("INELIGIBLE_EXPIRY")
    problem = quote_problem(quote, now, config.quote_max_age_seconds)
    if problem:
        return reject(problem)
    if quote.id not in decision.snapshot_ids or not envelope.evidence_ids:
        return reject("MISSING_EVIDENCE")
    if any(
        getattr(quote, name) is None for name in set(envelope.required_metrics) | {"oi", "volume"}
    ):
        return reject("MISSING_METRICS")
    if quote.greeks is not None and "greeks" in envelope.required_metrics:
        if not {"delta", "gamma", "theta", "vega"} <= quote.greeks.keys():
            return reject("MISSING_METRICS")
    assert quote.ask is not None and quote.bid is not None
    assert quote.oi is not None and quote.volume is not None
    if quote.oi < config.min_oi or quote.volume < config.min_volume:
        return reject("INSUFFICIENT_LIQUIDITY")
    if (quote.ask - quote.bid) / quote.ask * 10000 > config.max_spread_bps:
        return reject("EXCESSIVE_SPREAD")
    if state.open_positions >= config.max_positions:
        return reject("POSITION_LIMIT")
    return None


def evaluate_risk(
    decision: TradeDecision,
    instrument: Instrument,
    quote: Quote,
    envelope: StrategyEnvelope,
    config: RiskConfig,
    state: PortfolioState,
    session: ExchangeSession,
    now: datetime,
) -> RiskResult:
    """Legacy immediate-fill sizing, retained for historical execution only."""
    problem = entry_problem(decision, instrument, quote, envelope, config, state, session, now)
    if problem:
        return RiskResult(False, problem)

    def reject(reason: str) -> RiskResult:
        return RiskResult(False, reason)

    assert quote.ask is not None
    if config.costs is None:
        return reject("LEGACY_COSTS_UNAVAILABLE")
    entry = config.costs.price(quote.ask, instrument.tick_size, "BUY")
    if not envelope.min_entry <= entry <= envelope.max_entry:
        return reject("ENTRY_PREDICATE_FAILED")
    if decision.entry is None or not envelope.min_entry <= decision.entry <= envelope.max_entry:
        return reject("ENTRY_PREDICATE_FAILED")
    if not envelope.stop_loss < entry < envelope.target:
        return reject("INVALID_EXECUTABLE_PRICES")
    stop_exit = config.costs.price(envelope.stop_loss, instrument.tick_size, "SELL")
    if stop_exit <= 0:
        return reject("INVALID_STOP_FILL")
    remaining = (
        state.session_opening_equity * config.max_daily_loss_pct
        - max(Decimal(0), state.session_opening_equity - state.equity)
        - state.reserved_risk
    )
    budget = min(min(state.equity, config.capital) * config.max_trade_risk_pct, remaining)
    if budget <= 0 or state.cash <= 0:
        return reject("NO_RISK_OR_CAPITAL")
    max_quantity = min(config.max_fill_quantity, quote.ask_quantity or 0)
    # All configured costs are nonnegative and monotonic, so whole-lot binary search is safe.
    low, high = 0, max_quantity // instrument.lot_size
    while low < high:
        lots = (low + high + 1) // 2
        quantity = lots * instrument.lot_size
        debit = money(entry * quantity) + fees(config.costs, entry, quantity)
        risk = debit - money(stop_exit * quantity) + fees(config.costs, stop_exit, quantity)
        if debit <= state.cash and risk <= budget:
            low = lots
        else:
            high = lots - 1
    quantity = low * instrument.lot_size
    if not quantity:
        return reject("ONE_LOT_DOES_NOT_FIT")
    risk = (
        money(entry * quantity)
        - money(stop_exit * quantity)
        + fees(config.costs, entry, quantity)
        + fees(config.costs, stop_exit, quantity)
    )
    return RiskResult(True, "APPROVED", quantity, entry, risk, money(budget))
