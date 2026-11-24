"""Owned chart annotations from retained paper fills and current positions."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import IST
from services.core.models import Account, PaperFill, PaperOrder, PaperPosition
from services.paper.accounting import ACTIVE

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(UTC)


@router.get("/api/paper/chart-trades")
def chart_trades(
    request: Request,
    day: date,
    instrument_id: str = Query(..., min_length=1, max_length=100),
    owner: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        if db.get(Account, owner) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        now = utc_now()
        start = datetime.combine(day, time.min, IST)
        end = start + timedelta(days=1)
        fills = list(
            db.execute(
                select(PaperFill, PaperOrder.side)
                .join(PaperOrder, PaperOrder.id == PaperFill.order_id)
                .where(
                    PaperOrder.account_id == owner,
                    PaperOrder.instrument_id == instrument_id,
                    PaperFill.timestamp >= start,
                    PaperFill.timestamp < end,
                )
                .order_by(PaperFill.timestamp.desc(), PaperFill.id.desc())
                .limit(201)
            )
        )
        current_day = day == now.astimezone(IST).date()
        positions = (
            list(
                db.scalars(
                    select(PaperPosition)
                    .where(
                        PaperPosition.account_id == owner,
                        PaperPosition.instrument_id == instrument_id,
                        PaperPosition.closed_at.is_(None),
                    )
                    .order_by(PaperPosition.opened_at.desc(), PaperPosition.id)
                    .limit(21)
                )
            )
            if current_day
            else []
        )
        pending_orders = list(
            db.scalars(
                select(PaperOrder)
                .where(
                    PaperOrder.account_id == owner,
                    PaperOrder.instrument_id == instrument_id,
                    PaperOrder.timestamp >= start,
                    PaperOrder.timestamp < end,
                    PaperOrder.status.in_(ACTIVE),
                )
                .order_by(PaperOrder.timestamp.desc(), PaperOrder.id.desc())
                .limit(201)
            )
        )
        positions_truncated = len(positions) > 20
        positions = positions[:20]
        exits = (
            list(
                db.scalars(
                    select(PaperOrder)
                    .where(
                        PaperOrder.account_id == owner,
                        PaperOrder.position_id.in_([p.id for p in positions]),
                        PaperOrder.side == "SELL",
                        PaperOrder.status.in_(ACTIVE),
                    )
                    .order_by(PaperOrder.timestamp.desc(), PaperOrder.id)
                    .limit(101)
                )
            )
            if positions
            else []
        )
        return {
            "as_of": now.isoformat(),
            "day": day.isoformat(),
            "instrument_id": instrument_id,
            "current_day": current_day,
            "fills_truncated": len(fills) > 200,
            "positions_truncated": positions_truncated,
            "exits_truncated": len(exits) > 100,
            "pending_orders_truncated": len(pending_orders) > 200,
            "pending_orders": [
                {
                    "id": str(order.id),
                    "position_id": str(order.position_id) if order.position_id else None,
                    "side": order.side,
                    "status": order.status,
                    "order_type": order.order_type,
                    "quantity_remaining": order.quantity - order.filled_quantity,
                    "timestamp": order.timestamp.isoformat(),
                    "trigger_price": str(order.trigger_price) if order.trigger_price is not None else None,
                    "limit_price": str(order.limit_price) if order.limit_price is not None else None,
                }
                for order in pending_orders[:200]
            ],
            "fills": [
                {
                    "id": str(fill.id),
                    "order_id": str(fill.order_id),
                    "side": side,
                    "quantity": fill.quantity,
                    "price": str(fill.price),
                    "timestamp": fill.timestamp.isoformat(),
                }
                for fill, side in fills[:200]
                if fill.timestamp is not None
            ],
            "positions": [
                {
                    "id": str(p.id),
                    "entry_order_id": str(p.entry_order_id),
                    "opened_at": p.opened_at.isoformat(),
                    "remaining_quantity": p.quantity - p.closed_quantity,
                    "average_price": str(p.average_price),
                    "stop_loss": str(p.stop_loss),
                    "target": str(p.target) if p.target is not None else None,
                    "pending_exit": p.pending_exit,
                }
                for p in positions
            ],
            "exit_orders": [
                {
                    "id": str(o.id),
                    "position_id": str(o.position_id),
                    "remaining_quantity": o.quantity - o.filled_quantity,
                    "status": o.status,
                    "order_type": o.order_type,
                    "trigger_price": str(o.trigger_price) if o.trigger_price is not None else None,
                    "limit_price": str(o.limit_price) if o.limit_price is not None else None,
                }
                for o in exits[:100]
            ],
        }
