"""Liquidation estimates from actual displayed bids, never last-traded-price marks."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from services.core.contracts import IST, Instrument, Quote, money
from services.core.execution import ExecutionPolicy, FeeSchedule
from services.core.models import PaperLiquidityLevel
from services.paper.fees import FeeContext, incremental_fees
from services.paper.liquidity import available_units, displayed_units, execution_price
from services.risk.engine import quote_problem


@dataclass(frozen=True)
class LiquidationEstimate:
    requested_quantity: int
    covered_quantity: int
    gross_value: Decimal | None
    estimated_fees: Decimal | None
    net_value: Decimal | None
    reason: str


def liquidation_estimate(
    instrument: Instrument,
    quote: Quote,
    quantity: int,
    policy: ExecutionPolicy,
    schedule: FeeSchedule,
    now: datetime,
    *,
    configuration_version: str,
    budgets: dict[Decimal, PaperLiquidityLevel] | None = None,
    fee_context: tuple[FeeContext, ...] = (),
) -> LiquidationEstimate:
    """An estimate at this observation, not a fill and not a guarantee of liquidation.

    Budget data is required: an empty mapping means no budget has been consumed;
    None means it is unavailable and cannot be guessed as an unused order book.
    """

    def unavailable(reason: str, covered: int = 0) -> LiquidationEstimate:
        return LiquidationEstimate(quantity, covered, None, None, None, reason)

    if quantity <= 0:
        raise ValueError("Positive held quantity required")
    if now.tzinfo is None:
        return unavailable("INVALID_VALUATION_CLOCK")
    if policy.blockers() or not schedule.reviewed:
        return unavailable("EXECUTION_OR_FEE_POLICY_UNAVAILABLE")
    if quote.instrument_id != instrument.id or schedule.exchange != instrument.exchange:
        return unavailable("INSTRUMENT_OR_FEE_MISMATCH")
    if not schedule.applies(now.astimezone(IST).date()):
        return unavailable("FEE_SCHEDULE_OUTSIDE_EFFECTIVE_WINDOW")
    max_age, adverse = policy.quote_max_age_ms, policy.extra_adverse_slippage_bps
    assert max_age is not None and adverse is not None
    if quote_problem(quote, now, 10) or (now - quote.timestamp).total_seconds() * 1000 > max_age:
        return unavailable("VALUATION_QUOTE_UNAVAILABLE_OR_STALE")
    if (
        quote.quantity_unit == "unknown"
        or quote.quantity_unit != policy.quantity_unit
        or not quote.bid_depth
        or quote.timestamp_basis != "exchange_feed"
        or quote.depth_kind != "best_five"
    ):
        return unavailable("VALUATION_DEPTH_OR_UNITS_UNAVAILABLE")
    if budgets is None:
        return unavailable("LIQUIDITY_BUDGET_UNAVAILABLE")
    remaining, gross = quantity, Decimal(0)
    for level in quote.bid_depth:
        previous = budgets.get(level.price)
        if previous is not None and (
            previous.instrument_id != instrument.id
            or previous.side != "SELL"
            or previous.session_key != now.astimezone(IST).date()
            or previous.config_version != configuration_version
        ):
            return unavailable("LIQUIDITY_BUDGET_SCOPE_MISMATCH", quantity - remaining)
        try:
            available = available_units(
                previous, quote, displayed_units(level, quote, instrument), policy
            )
        except ValueError:
            return unavailable("VALUATION_DEPTH_OLDER_THAN_BUDGET", quantity - remaining)
        take = min(remaining, available)
        if policy.partial_fill_granularity == "lots":
            take = take // instrument.lot_size * instrument.lot_size
        if take:
            price = execution_price(level.price, instrument.tick_size, "SELL", adverse)
            gross += money(price * take)
            remaining -= take
        if not remaining:
            break
    if remaining:
        return unavailable("INSUFFICIENT_EXECUTABLE_DEPTH", quantity - remaining)
    charges = sum(
        incremental_fees(schedule, FeeContext("SELL"), gross, fee_context).values(), Decimal(0)
    )
    return LiquidationEstimate(quantity, quantity, gross, charges, gross - charges, "ESTIMATED")
