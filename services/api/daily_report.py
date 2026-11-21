"""Daily paper report from dated ledger/fill records, without generated commentary."""

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import Session

from services.agents.contracts import Proposal, Review
from services.api.agent_activity import evaluation
from services.api.auth import account_identity
from services.core.contracts import IST, money
from services.core.models import (
    Account,
    AuditEvent,
    InstrumentRecord,
    LedgerEntry,
    PaperFill,
    PaperOrder,
    PaperPosition,
)
from services.paper.accounting import project_fills, reconcile_account

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(UTC)


def realized_during(
    buys: list[PaperFill], sells: list[PaperFill], start: datetime, cutoff: datetime
) -> Decimal:
    entries = [fill for fill in buys if fill.timestamp and fill.timestamp < cutoff]
    exits = [fill for fill in sells if fill.timestamp and fill.timestamp < cutoff]
    before = project_fills(
        [fill for fill in entries if fill.timestamp and fill.timestamp < start],
        [fill for fill in exits if fill.timestamp and fill.timestamp < start],
    )
    return project_fills(entries, exits)["realized_pnl"] - before["realized_pnl"]


@router.get("/api/paper/daily-report")
def daily_report(
    day: date, request: Request, fills_before: UUID | None = None, owner: UUID = Depends(account_identity)
):
    now = utc_now()
    today = now.astimezone(IST).date()
    if day > today:
        raise HTTPException(422, "REPORT_DAY_NOT_STARTED")
    start = datetime.combine(day, time.min, IST)
    cutoff = min(start + timedelta(days=1), now)
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        account = db.get(Account, owner)
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        reconciled = not reconcile_account(db, account)
        undated = (
            db.scalar(
                select(func.count())
                .select_from(PaperFill)
                .join(PaperOrder)
                .where(PaperOrder.account_id == owner, PaperFill.timestamp.is_(None))
            )
            or 0
        )
        complete = reconciled and not undated
        scope = (
            PaperOrder.account_id == owner,
            PaperFill.timestamp >= start,
            PaperFill.timestamp < cutoff,
        )
        fill_count, fees = db.execute(
            select(func.count(), func.coalesce(func.sum(PaperFill.fees), 0))
            .select_from(PaperFill)
            .join(PaperOrder)
            .where(*scope)
        ).one()
        quantities = dict(
            db.execute(
                select(PaperOrder.side, func.sum(PaperFill.quantity))
                .join(PaperFill)
                .where(*scope)
                .group_by(PaperOrder.side)
            ).all()
        )
        all_units = dict(
            db.execute(
                select(PaperOrder.side, func.sum(PaperFill.quantity))
                .join(PaperFill)
                .where(PaperOrder.account_id == owner, PaperFill.timestamp < cutoff)
                .group_by(PaperOrder.side)
            ).all()
        )
        opening = db.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == owner, LedgerEntry.timestamp < start
            )
        ) or Decimal(0)
        closing = db.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == owner, LedgerEntry.timestamp < cutoff
            )
        ) or Decimal(0)
        day_exits = select(PaperOrder.id).join(PaperFill).where(*scope, PaperOrder.side == "SELL")
        position_ids = select(PaperOrder.position_id).where(PaperOrder.id.in_(day_exits))
        positions = list(
            db.scalars(
                select(PaperPosition).where(
                    PaperPosition.account_id == owner,
                    or_(
                        PaperPosition.id.in_(position_ids),
                        PaperPosition.exit_order_id.in_(day_exits),
                    ),
                )
            )
        )
        entry_ids = [position.entry_order_id for position in positions]
        legacy_exit_ids = [
            position.exit_order_id for position in positions if position.exit_order_id
        ]
        related = db.execute(
            select(PaperFill, PaperOrder)
            .join(PaperOrder)
            .where(
                PaperOrder.account_id == owner,
                PaperFill.timestamp < cutoff,
                or_(
                    PaperOrder.id.in_(entry_ids),
                    PaperOrder.position_id.in_([p.id for p in positions]),
                    PaperOrder.id.in_(legacy_exit_ids),
                ),
            )
        )
        entries: dict[UUID, list[PaperFill]] = defaultdict(list)
        exits: dict[UUID, list[PaperFill]] = defaultdict(list)
        legacy_positions = {p.exit_order_id: p.id for p in positions if p.exit_order_id}
        for fill, order in related:
            if order.side == "BUY":
                entries[order.id].append(fill)
            elif position_id := order.position_id or legacy_positions.get(order.id):
                exits[position_id].append(fill)
        realized = Decimal(0)
        for position in positions:
            realized += realized_during(
                entries[position.entry_order_id], exits[position.id], start, cutoff
            )
        activity_scope = (
            AuditEvent.account_id == owner,
            AuditEvent.timestamp >= start,
            AuditEvent.timestamp < cutoff,
            AuditEvent.kind.in_(("AI_OUTPUT", "AGENT_EVALUATION")),
        )
        activity = dict(
            proposals_wait=0,
            reviews_rejected=0,
            evaluations_failed=0,
            strategies_accepted=0,
            unclassified=0,
        )
        activity_cursor = None
        while True:
            activity_statement = select(AuditEvent).where(*activity_scope)
            if activity_cursor:
                activity_statement = activity_statement.where(
                    tuple_(AuditEvent.timestamp, AuditEvent.id) > activity_cursor
                )
            activity_rows = list(
                db.scalars(
                    activity_statement.order_by(AuditEvent.timestamp, AuditEvent.id).limit(501)
                )
            )
            for event in activity_rows[:500]:
                try:
                    if event.kind == "AGENT_EVALUATION":
                        state, _, _ = evaluation(str(event.details.get("status", "")))
                        key = (
                            "strategies_accepted"
                            if state == "ready"
                            else "evaluations_failed"
                            if state == "failed"
                            else "unclassified"
                        )
                        activity[key] += 1
                    elif event.details.get("role") == "proposal":
                        activity["proposals_wait"] += (
                            Proposal.model_validate(event.details.get("output")).action == "WAIT"
                        )
                    elif event.details.get("role") == "review":
                        activity["reviews_rejected"] += not Review.model_validate(
                            event.details.get("output")
                        ).approved
                except (ValueError, TypeError, KeyError):
                    activity["unclassified"] += 1
            if len(activity_rows) <= 500:
                break
            last = activity_rows[499]
            activity_cursor = (last.timestamp, last.id)
        fill_statement = (
            select(PaperFill, PaperOrder, InstrumentRecord)
            .join(PaperOrder, PaperOrder.id == PaperFill.order_id)
            .outerjoin(InstrumentRecord, InstrumentRecord.id == PaperOrder.instrument_id)
            .where(*scope)
        )
        if fills_before:
            cursor = db.get(PaperFill, fills_before)
            cursor_order = db.get(PaperOrder, cursor.order_id) if cursor else None
            if (
                cursor is None
                or cursor_order is None
                or cursor_order.account_id != owner
                or cursor.timestamp is None
                or not start <= cursor.timestamp < cutoff
            ):
                raise HTTPException(400, "REPORT_CURSOR_INVALID")
            fill_statement = fill_statement.where(
                tuple_(PaperFill.timestamp, PaperFill.id) < (cursor.timestamp, cursor.id)
            )
        fills = list(
            db.execute(
                fill_statement.order_by(PaperFill.timestamp.desc(), PaperFill.id.desc()).limit(21)
            )
        )
        fills_more = len(fills) > 20
        fills = fills[:20]
        return {
            "day": day.isoformat(),
            "as_of": now.isoformat(),
            "cutoff": cutoff.isoformat(),
            "day_ended": day < today,
            "status": "RECONCILED"
            if complete
            else "UNRECONCILED"
            if not reconciled
            else "UNDATED_FILLS",
            "fill_count": fill_count,
            "buy_units": quantities.get("BUY", 0),
            "sell_units": quantities.get("SELL", 0),
            "open_units_at_cutoff": all_units.get("BUY", 0) - all_units.get("SELL", 0)
            if complete
            else None,
            "cash_opening": str(money(opening)) if complete else None,
            "cash_at_cutoff": str(money(closing)) if complete else None,
            "cash_movement": str(money(closing - opening)) if complete else None,
            "fees": str(money(fees)) if complete else None,
            "realized_pnl": str(money(realized)) if complete else None,
            "activity": activity,
            "activity_complete": True,
            "fills_truncated": fills_more,
            "next_fills_before": str(fills[-1][0].id) if fills_more else None,
            "fills": [
                {
                    "id": str(fill.id),
                    "order_id": str(order.id),
                    "side": order.side,
                    "quantity": fill.quantity,
                    "price": str(fill.price),
                    "fees": str(fill.fees),
                    "timestamp": fill.timestamp.isoformat(),
                    "instrument": {
                        key: instrument.payload.get(key)
                        for key in ("underlying", "strike", "option_type", "expiry")
                    }
                    if instrument
                    else None,
                }
                for fill, order, instrument in fills
                if fill.timestamp is not None
            ],
        }
