"""Observed depth budgets. Displayed increases are an explicit conservative model."""

from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.contracts import DepthLevel, Instrument, Quote
from services.core.execution import ExecutionPolicy, PaperExecutionConfig
from services.core.models import PaperLiquidityLevel


def execution_price(raw: Decimal, tick: Decimal, side: str, adverse_bps: Decimal) -> Decimal:
    if side not in ("BUY", "SELL"):
        raise ValueError("Unknown execution side")
    adjusted = raw * (1 + adverse_bps / 10000 if side == "BUY" else 1 - adverse_bps / 10000)
    rounding = ROUND_CEILING if side == "BUY" else ROUND_FLOOR
    price = (adjusted / tick).to_integral_value(rounding=rounding) * tick
    if price <= 0:
        raise ValueError("Nonpositive modeled execution price")
    return price


def protection_price(raw: Decimal, tick: Decimal, side: str, protection_bps: Decimal) -> Decimal:
    if side not in ("BUY", "SELL"):
        raise ValueError("Unknown execution side")
    value = raw * (1 + protection_bps / 10000 if side == "BUY" else 1 - protection_bps / 10000)
    # Round inward so the configured protection percentage cannot be exceeded by a tick.
    rounding = ROUND_FLOOR if side == "BUY" else ROUND_CEILING
    result = (value / tick).to_integral_value(rounding=rounding) * tick
    if result <= 0:
        raise ValueError("Invalid market protection bound")
    return result


def displayed_units(level: DepthLevel, quote: Quote, instrument: Instrument) -> int:
    if quote.quantity_unit == "units":
        return level.quantity
    if quote.quantity_unit == "lots":
        return level.quantity * instrument.lot_size
    raise ValueError("Quantity units are unverified")


def capacity_state(
    previous: PaperLiquidityLevel | None, quote: Quote, units: int, policy: ExecutionPolicy
) -> tuple[int, int]:
    """Return cumulative capacity and displayed baseline; never infer hidden refresh.

    Same-time observations and source changes cannot add capacity. An absent price
    does not reset its baseline: moving out of best-five is not proof of depletion.
    """
    fraction = policy.displayed_participation
    assert fraction is not None
    cap = int((units * fraction).to_integral_value(rounding=ROUND_FLOOR))
    if previous is None:
        return cap, units
    if quote.timestamp < previous.observation_at:
        raise ValueError("Liquidity observation is older than durable budget")
    if quote.timestamp == previous.observation_at or quote.source != previous.source:
        return previous.capacity, max(previous.displayed, units)
    increase = max(0, units - previous.displayed)
    return previous.capacity + int(
        (increase * fraction).to_integral_value(rounding=ROUND_FLOOR)
    ), units


def level_budget(
    db: Session,
    account_id: UUID,
    session_key: date,
    instrument: Instrument,
    side: str,
    raw_price: Decimal,
) -> PaperLiquidityLevel | None:
    return db.scalar(
        select(PaperLiquidityLevel).where(
            PaperLiquidityLevel.account_id == account_id,
            PaperLiquidityLevel.session_key == session_key,
            PaperLiquidityLevel.instrument_id == instrument.id,
            PaperLiquidityLevel.side == side,
            PaperLiquidityLevel.price == raw_price,
        )
    )


def available_units(
    previous: PaperLiquidityLevel | None, quote: Quote, units: int, policy: ExecutionPolicy
) -> int:
    cap, _ = capacity_state(previous, quote, units, policy)
    assert policy.displayed_participation is not None
    visible_cap = int(
        (units * policy.displayed_participation).to_integral_value(rounding=ROUND_FLOOR)
    )
    return max(0, min(cap - (previous.consumed if previous else 0), visible_cap))


def buy_capacity(
    quote: Quote,
    instrument: Instrument,
    execution: PaperExecutionConfig,
    account_id: UUID,
    session_key: date,
    budgets: dict[Decimal, PaperLiquidityLevel] | None,
    *,
    minimum: Decimal,
    limit: Decimal,
) -> int:
    """Read usable BUY units without consuming or replenishing durable depth.

    Callers must first validate quote provenance, freshness and reviewed policy.
    A known empty budget map differs from an unavailable budget read (None).
    """
    if budgets is None:
        raise ValueError("LIQUIDITY_BUDGET_UNAVAILABLE")
    policy = execution.execution
    assert policy.extra_adverse_slippage_bps is not None
    capacity = 0
    for level in quote.ask_depth:
        previous = budgets.get(level.price)
        if previous is not None and (
            previous.account_id != account_id
            or previous.instrument_id != instrument.id
            or previous.session_key != session_key
            or previous.side != "BUY"
            or previous.price != level.price
            or previous.config_version != execution.version
        ):
            raise ValueError("LIQUIDITY_BUDGET_SCOPE_MISMATCH")
        price = execution_price(
            level.price, instrument.tick_size, "BUY", policy.extra_adverse_slippage_bps
        )
        if price > limit:
            break
        if price < minimum:
            continue
        try:
            units = available_units(
                previous, quote, displayed_units(level, quote, instrument), policy
            )
        except ValueError as error:
            raise ValueError("DEPTH_OLDER_THAN_LIQUIDITY_BUDGET") from error
        if policy.partial_fill_granularity == "lots":
            units = units // instrument.lot_size * instrument.lot_size
        capacity += units
    return capacity
