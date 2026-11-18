"""Effective-dated incremental fees. Decimal arithmetic; no implicit tax rates."""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.contracts import IST, money
from services.core.execution import FeeRule, FeeSchedule
from services.core.models import PaperFill, PaperOrder

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class FeeContext:
    side: Side
    premium: Decimal = Decimal(0)
    booked: dict[str, Decimal] = field(default_factory=dict)


def rounded(value: Decimal, rule: FeeRule) -> Decimal:
    modes = {"HALF_UP": ROUND_HALF_UP, "CEILING": ROUND_CEILING, "FLOOR": ROUND_FLOOR}
    return money(
        (value / rule.rounding_increment).to_integral_value(rounding=modes[rule.rounding_mode])
        * rule.rounding_increment
    )


def raw_charge(rule: FeeRule, side: str, premium: Decimal, charges: dict[str, Decimal]) -> Decimal:
    if side not in rule.sides or premium <= 0:
        return Decimal(0)
    if rule.calculation == "flat_per_order":
        assert rule.amount is not None
        value = rule.amount
    elif rule.calculation == "premium_rate":
        assert rule.rate is not None
        value = premium * rule.rate
    else:
        assert rule.rate is not None
        # Tax bases are actual cumulative upstream charges, including their declared rounding.
        value = (
            sum((charges.get(code, Decimal(0)) for code in rule.charge_basis), Decimal(0))
            * rule.rate
        )
    return min(value, rule.cap_per_order) if rule.cap_per_order is not None else value


def incremental_fees(
    schedule: FeeSchedule,
    current: FeeContext,
    premium_delta: Decimal,
    others: tuple[FeeContext, ...] = (),
) -> dict[str, Decimal]:
    """Charge the increase in the rounded order/session total, never a fresh flat fee per fill.

    Session rounding is allocated chronologically to the order being filled. Existing
    immutable allocations are not rewritten; later deltas reconcile the aggregate.
    """
    if not schedule.reviewed:
        raise ValueError("Reviewed fee schedule required")
    codes = {rule.code for rule in schedule.rules}
    for context in (current, *others):
        if not context.premium.is_finite() or context.premium < 0:
            raise ValueError("Invalid cumulative premium")
        if context.premium > 0 and set(context.booked) != codes:
            raise ValueError("Prior fee components are incomplete; missing is not zero")
        if any(not value.is_finite() or value < 0 for value in context.booked.values()):
            raise ValueError("Invalid cumulative charge history")
    if not premium_delta.is_finite() or premium_delta <= 0 or current.premium < 0:
        raise ValueError("Positive finite incremental premium required")
    if any(value < 0 or not value.is_finite() for value in current.booked.values()):
        raise ValueError("Invalid previously booked charges")
    new_premium = current.premium + premium_delta
    updated = dict(current.booked)
    increments: dict[str, Decimal] = {}
    for rule in schedule.rules:
        before = current.booked.get(rule.code, Decimal(0))
        if current.side not in rule.sides:
            if before:
                raise ValueError("Booked fee conflicts with schedule side")
            increments[rule.code] = Decimal(0)
            updated[rule.code] = Decimal(0)
            continue
        new_raw = raw_charge(rule, current.side, new_premium, updated)
        if rule.rounding_scope == "cumulative_order":
            delta = rounded(new_raw, rule) - before
        else:
            session_raw = new_raw + sum(
                (raw_charge(rule, other.side, other.premium, other.booked) for other in others),
                Decimal(0),
            )
            previously_booked = before + sum(
                (other.booked.get(rule.code, Decimal(0)) for other in others), Decimal(0)
            )
            delta = rounded(session_raw, rule) - previously_booked
        if delta < 0:
            raise ValueError("Fee history needs explicit reconciliation; negative fill fee denied")
        increments[rule.code] = delta
        updated[rule.code] = before + delta
    if set(current.booked) - {rule.code for rule in schedule.rules}:
        raise ValueError("Booked charges are absent from the frozen fee schedule")
    return increments


def estimate_fees(schedule: FeeSchedule, side: Side, premium: Decimal) -> Decimal:
    return sum(incremental_fees(schedule, FeeContext(side), premium).values(), Decimal(0))


def fee_contexts(
    db: Session, order: PaperOrder, schedule: FeeSchedule
) -> tuple[FeeContext, tuple[FeeContext, ...]]:
    """Read account/session/schedule scope under the caller's account lock."""
    if order.accepted_at is None:
        raise ValueError("Accepted order required")
    day = order.accepted_at.astimezone(IST).date()
    starts = datetime.combine(day, time.min, IST)
    rows = db.execute(
        select(PaperFill, PaperOrder)
        .join(PaperOrder, PaperFill.order_id == PaperOrder.id)
        .where(
            PaperOrder.account_id == order.account_id,
            PaperFill.cost_version == schedule.version,
            PaperFill.timestamp >= starts,
            PaperFill.timestamp < starts + timedelta(days=1),
        )
    ).all()
    contexts: dict[UUID, FeeContext] = {}
    for fill, related_order in rows:
        if fill.timestamp is None or fill.timestamp.astimezone(IST).date() != day:
            continue
        if related_order.side not in ("BUY", "SELL"):
            raise ValueError("Unknown fee side")
        side: Side = "BUY" if related_order.side == "BUY" else "SELL"
        previous = contexts.get(related_order.id, FeeContext(side))
        charges = dict(previous.booked)
        for code, value in fill.fee_breakdown.items():
            charges[code] = charges.get(code, Decimal(0)) + Decimal(str(value))
        contexts[related_order.id] = FeeContext(
            previous.side, previous.premium + money(fill.price * fill.quantity), charges
        )
    if order.side not in ("BUY", "SELL"):
        raise ValueError("Unknown fee side")
    current = contexts.pop(order.id, FeeContext("BUY" if order.side == "BUY" else "SELL"))
    return current, tuple(contexts.values())
