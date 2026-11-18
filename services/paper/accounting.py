"""Shared aggregation and reconciliation for historical and durable paper ledgers."""

from collections import defaultdict
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.contracts import money
from services.core.models import (
    Account,
    LedgerEntry,
    PaperFill,
    PaperFundsHold,
    PaperLiquidityLevel,
    PaperLiquidityUse,
    PaperOrder,
    PaperOrderEvent,
    PaperPosition,
)

ACTIVE = frozenset({"SUBMITTED", "OPEN", "PARTIALLY_FILLED", "CANCEL_REQUESTED"})
TERMINAL = frozenset({"FILLED", "CANCELLED", "REJECTED", "EXPIRED"})
LEGACY = "legacy-immediate-v1"


def evidence_decimal(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def order_fills(db: Session, order_id: UUID) -> list[PaperFill]:
    return list(db.scalars(select(PaperFill).where(PaperFill.order_id == order_id)))


def prorated_risk(order: PaperOrder, quantity: int) -> Decimal:
    """Historical pro-rata allocation or the explicit conservative new-order policy."""
    if (order.request_payload or {}).get("risk_allocation") == "whole_order_until_flat":
        return order.risk_budget if quantity > 0 else Decimal(0)
    return (order.risk_budget * quantity / order.quantity).quantize(
        Decimal("0.01"), rounding=ROUND_CEILING
    )


def fill_totals(fills: list[PaperFill]) -> tuple[int, Decimal, Decimal, Decimal]:
    quantity = sum(f.quantity for f in fills)
    exact_notional = sum((f.price * f.quantity for f in fills), Decimal(0))
    premium = sum((money(f.price * f.quantity) for f in fills), Decimal(0))
    charges = sum((f.fees for f in fills), Decimal(0))
    average = (
        (exact_notional / quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if quantity
        else Decimal(0)
    )
    return quantity, premium, charges, average


def position_fills(db: Session, position: PaperPosition) -> tuple[list[PaperFill], list[PaperFill]]:
    entries = order_fills(db, position.entry_order_id)
    exits = list(
        db.scalars(
            select(PaperFill)
            .join(PaperOrder, PaperFill.order_id == PaperOrder.id)
            .where(
                PaperOrder.side == "SELL",
                (PaperOrder.position_id == position.id) | (PaperOrder.id == position.exit_order_id),
            )
        )
    )
    return entries, exits


def project_fills(entries: list[PaperFill], exits: list[PaperFill]) -> dict:
    bought, debit, entry_fees, average = fill_totals(entries)
    sold, credit, exit_fees, _ = fill_totals(exits)
    realized = (
        credit - money((debit + entry_fees) * sold / bought) - exit_fees if bought else Decimal(0)
    )
    return {
        "quantity": bought,
        "closed_quantity": sold,
        "average_price": average,
        "entry_fees": entry_fees,
        "realized_pnl": realized,
    }


def position_projection(db: Session, position: PaperPosition) -> dict:
    return project_fills(*position_fills(db, position))


def refresh_position(db: Session, position: PaperPosition) -> None:
    for name, value in position_projection(db, position).items():
        setattr(position, name, value)


def reservations(db: Session, account_id: UUID) -> tuple[Decimal, Decimal, int]:
    orders = list(
        db.scalars(
            select(PaperOrder).where(
                PaperOrder.account_id == account_id,
                PaperOrder.status.in_(ACTIVE),
                PaperOrder.side == "BUY",
            )
        )
    )
    return (
        sum((o.reserved_cash for o in orders), Decimal(0)),
        sum((o.reserved_risk for o in orders), Decimal(0)),
        len(orders),
    )


def restricted_proceeds(db: Session, account_id: UUID) -> Decimal:
    holds = list(
        db.scalars(
            select(PaperFundsHold).where(
                PaperFundsHold.account_id == account_id, PaperFundsHold.released_at.is_(None)
            )
        )
    )
    return sum((hold.amount for hold in holds), Decimal(0))


def reconcile_account(db: Session, account: Account) -> list[str]:
    """Recompute from immutable fills/ledger; a pending order legitimately has no fill."""
    problems: list[str] = []
    ledger = list(db.scalars(select(LedgerEntry).where(LedgerEntry.account_id == account.id)))
    if sum((entry.amount for entry in ledger), Decimal(0)) != account.cash:
        problems.append("CASH_LEDGER_MISMATCH")
    orders = list(db.scalars(select(PaperOrder).where(PaperOrder.account_id == account.id)))
    positions = list(
        db.scalars(select(PaperPosition).where(PaperPosition.account_id == account.id))
    )
    entry_positions = {p.entry_order_id: p for p in positions}
    positions_by_id = {p.id: p for p in positions}
    events = list(
        db.scalars(select(PaperOrderEvent).where(PaperOrderEvent.account_id == account.id))
    )
    events_by_key = {(e.order_id, e.event_key): e for e in events}
    holds = list(db.scalars(select(PaperFundsHold).where(PaperFundsHold.account_id == account.id)))
    holds_by_fill = {hold.fill_id: hold for hold in holds}
    fills_by_order: dict[UUID, list[PaperFill]] = defaultdict(list)
    all_fills = list(
        db.scalars(
            select(PaperFill)
            .join(PaperOrder, PaperFill.order_id == PaperOrder.id)
            .where(PaperOrder.account_id == account.id)
        )
    )
    for fill in all_fills:
        fills_by_order[fill.order_id].append(fill)
    movements_by_fill: dict[UUID, list[LedgerEntry]] = defaultdict(list)
    all_movements = list(
        db.scalars(
            select(LedgerEntry).where(
                (LedgerEntry.account_id == account.id)
                | LedgerEntry.fill_id.in_(
                    select(PaperFill.id)
                    .join(PaperOrder, PaperFill.order_id == PaperOrder.id)
                    .where(PaperOrder.account_id == account.id)
                )
            )
        )
    )
    for movement in all_movements:
        if movement.fill_id is not None:
            movements_by_fill[movement.fill_id].append(movement)
    owned_fills: set[UUID] = set()
    for order in orders:
        fills = fills_by_order[order.id]
        quantity, premium, charges, _ = fill_totals(fills)
        if order.execution_version != LEGACY and (
            not order.request_payload
            or not order.execution_config
            or order.accepted_at is None
            or order.eligible_at is None
            or order.expires_at is None
        ):
            problems.append("DURABLE_ORDER_EVIDENCE_MISSING")
        if quantity != order.filled_quantity or quantity > order.quantity:
            problems.append("ORDER_FILLED_QUANTITY_MISMATCH")
        if order.status == "FILLED" and quantity != order.quantity:
            problems.append("INCOMPLETE_FILLED_ORDER")
        if order.status == "PARTIALLY_FILLED" and not 0 < quantity < order.quantity:
            problems.append("INVALID_PARTIAL_ORDER")
        if order.status in {"SUBMITTED", "OPEN", "REJECTED"} and quantity:
            problems.append("UNEXPECTED_ORDER_FILL")
        if order.status in ACTIVE and quantity == order.quantity:
            problems.append("FULL_ORDER_STILL_ACTIVE")
        if order.status in TERMINAL and (order.reserved_cash or order.reserved_risk):
            problems.append("TERMINAL_ORDER_RESERVATION")
        if order.execution_version != LEGACY and order.side == "BUY" and order.status in ACTIVE:
            if order.reserved_cash != order.cash_budget - premium - charges:
                problems.append("CASH_RESERVATION_MISMATCH")
            if order.reserved_risk != order.risk_budget - prorated_risk(order, quantity):
                problems.append("RISK_RESERVATION_MISMATCH")
        if quantity:
            position = (
                entry_positions.get(order.id)
                if order.side == "BUY"
                else positions_by_id.get(order.position_id)
                if order.position_id is not None
                else None
            )
            if position is None and order.side == "SELL":
                position = next((p for p in positions if p.exit_order_id == order.id), None)
            if position is None or position.instrument_id != order.instrument_id:
                problems.append("ORPHAN_OR_MISMATCHED_ORDER_FILL")
        for fill in fills:
            owned_fills.add(fill.id)
            movements = movements_by_fill[fill.id]
            amounts = {entry.category: entry.amount for entry in movements}
            sign = -1 if order.side == "BUY" else 1
            if (
                len(movements) != 2
                or any(e.account_id != account.id for e in movements)
                or amounts
                != {
                    "PREMIUM": money(fill.price * fill.quantity) * sign,
                    "FEE": -fill.fees,
                }
            ):
                problems.append("FILL_LEDGER_MISMATCH")
            fee_parts = [evidence_decimal(v) for v in fill.fee_breakdown.values()]
            if (
                any(v is None for v in fee_parts)
                or sum((v for v in fee_parts if v is not None), Decimal(0)) != fill.fees
            ):
                problems.append("FILL_FEE_BREAKDOWN_MISMATCH")
            if order.execution_version != LEGACY:
                event = events_by_key.get((order.id, "fill:" + (fill.event_key or "")))
                if (
                    event is None
                    or event.kind != "FILL"
                    or event.timestamp != fill.timestamp
                    or (
                        event.payload.get("snapshot_id") != str(fill.snapshot_id)
                        or event.payload.get("quantity") != fill.quantity
                        or evidence_decimal(event.payload.get("price")) != fill.price
                        or evidence_decimal(event.payload.get("fees")) != fill.fees
                        or event.payload.get("market_event_id") != fill.market_event_id
                        or event.payload.get("cost_version") != fill.cost_version
                        or event.payload.get("fee_breakdown") != fill.fee_breakdown
                    )
                ):
                    problems.append("FILL_EVENT_MISMATCH")
                policy = (order.execution_config or {}).get("execution", {})
                if (
                    order.side == "SELL"
                    and policy.get("sale_proceeds_reuse") == "block_until_verified"
                    and money(fill.price * fill.quantity) > fill.fees
                    and fill.id not in holds_by_fill
                ):
                    problems.append("SALE_PROCEEDS_HOLD_MISSING")
    if any(e.fill_id is not None and e.fill_id not in owned_fills for e in ledger):
        problems.append("ORPHAN_LEDGER_MOVEMENT")
    for position in positions:
        exits = [
            fill
            for order in orders
            if order.side == "SELL"
            and (order.position_id == position.id or order.id == position.exit_order_id)
            for fill in fills_by_order[order.id]
        ]
        projection = project_fills(fills_by_order[position.entry_order_id], exits)
        if not projection["quantity"] or projection["closed_quantity"] > projection["quantity"]:
            problems.append("POSITION_FILL_BOUNDS")
        for name, expected in projection.items():
            actual = getattr(position, name)
            if name == "realized_pnl" and actual is None and expected == 0:
                continue  # Historical open positions have null realized P&L.
            if actual != expected:
                problems.append("POSITION_" + name.upper() + "_MISMATCH")
        if (position.closed_at is not None) != (position.closed_quantity == position.quantity):
            problems.append("POSITION_CLOSE_MISMATCH")
        entry_order = next((o for o in orders if o.id == position.entry_order_id), None)
        if (
            entry_order is not None
            and entry_order.execution_version != LEGACY
            and position.planned_risk
            != prorated_risk(entry_order, position.quantity - position.closed_quantity)
        ):
            problems.append("POSITION_RISK_ALLOCATION_MISMATCH")
        reserved_sells = [
            o
            for o in orders
            if o.position_id == position.id and o.side == "SELL" and o.status in ACTIVE
        ]
        if (
            sum(o.quantity - o.filled_quantity for o in reserved_sells)
            > position.quantity - position.closed_quantity
        ):
            problems.append("EXIT_QUANTITY_OVERRESERVED")
    reserved_cash = sum(
        (o.reserved_cash for o in orders if o.side == "BUY" and o.status in ACTIVE), Decimal(0)
    )
    fills_by_id = {fill.id: fill for fill in all_fills}
    orders_by_id = {order.id: order for order in orders}
    for hold in holds:
        hold_fill = fills_by_id.get(hold.fill_id)
        hold_order = orders_by_id.get(hold_fill.order_id) if hold_fill else None
        if (
            hold_fill is None
            or hold_order is None
            or hold_order.account_id != account.id
            or hold_order.side != "SELL"
            or hold.amount
            != max(Decimal(0), money(hold_fill.price * hold_fill.quantity) - hold_fill.fees)
        ):
            problems.append("FUNDS_HOLD_FILL_MISMATCH")
        if hold.released_at is not None and not hold.release_evidence:
            problems.append("FUNDS_RELEASE_EVIDENCE_MISSING")
    restricted = sum((h.amount for h in holds if h.released_at is None), Decimal(0))
    if reserved_cash + restricted > account.cash:
        problems.append("CASH_OVERRESERVED")
    levels = list(
        db.scalars(select(PaperLiquidityLevel).where(PaperLiquidityLevel.account_id == account.id))
    )
    levels_by_id = {level.id: level for level in levels}
    uses = list(
        db.scalars(
            select(PaperLiquidityUse).where(
                PaperLiquidityUse.level_id.in_(
                    select(PaperLiquidityLevel.id).where(
                        PaperLiquidityLevel.account_id == account.id
                    )
                )
                | PaperLiquidityUse.fill_id.in_(
                    select(PaperFill.id)
                    .join(PaperOrder, PaperFill.order_id == PaperOrder.id)
                    .where(PaperOrder.account_id == account.id)
                )
            )
        )
    )
    used_by_fill = {use.fill_id: use for use in uses}
    for level in levels:
        if level.consumed != sum(use.quantity for use in uses if use.level_id == level.id):
            problems.append("LIQUIDITY_CONSUMPTION_MISMATCH")
    for use in uses:
        used_fill = fills_by_id.get(use.fill_id)
        used_level = levels_by_id.get(use.level_id)
        used_order = orders_by_id.get(used_fill.order_id) if used_fill else None
        if (
            used_fill is None
            or used_level is None
            or used_order is None
            or use.quantity != used_fill.quantity
            or use.raw_price != used_level.price
            or used_level.instrument_id != used_order.instrument_id
            or used_level.side != used_order.side
        ):
            problems.append("LIQUIDITY_FILL_EVIDENCE_MISMATCH")
        elif (
            used_order.id,
            "fill:" + (used_fill.event_key or ""),
        ) in events_by_key and evidence_decimal(
            events_by_key[(used_order.id, "fill:" + (used_fill.event_key or ""))].payload.get(
                "raw_price"
            )
        ) != use.raw_price:
            problems.append("LIQUIDITY_EVENT_PRICE_MISMATCH")
    if any(fill.execution_version != LEGACY and fill.id not in used_by_fill for fill in all_fills):
        problems.append("FILL_LIQUIDITY_EVIDENCE_MISSING")
    return sorted(set(problems))
