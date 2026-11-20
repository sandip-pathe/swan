"""Owned, bounded order history projected from recorded ledger evidence."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.models import (
    InstrumentRecord,
    PaperFill,
    PaperOrder,
    PaperOrderEvent,
    PaperPosition,
)
from services.paper.accounting import LEGACY

router = APIRouter()


def order_view(order: PaperOrder) -> dict:
    return {
        "id": str(order.id),
        "side": order.side,
        "status": order.status,
        "quantity": order.quantity,
        "filled_quantity": order.filled_quantity,
        "order_type": order.order_type,
        "reason": order.reason,
        "limit_price": str(order.limit_price) if order.limit_price is not None else None,
        "trigger_price": str(order.trigger_price) if order.trigger_price is not None else None,
    }


@router.get("/api/paper/orders/{order_id}/history")
def history(
    order_id: UUID,
    request: Request,
    before: UUID | None = None,
    limit: int = Query(30, ge=1, le=100),
    owner: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        # Keep the summary, events, fills and position in the same read snapshot.
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        order = db.get(PaperOrder, order_id)
        if order is None or order.account_id != owner:
            raise HTTPException(404, "PAPER_ORDER_NOT_FOUND")
        statement = select(PaperOrderEvent).where(
            PaperOrderEvent.account_id == owner, PaperOrderEvent.order_id == order.id
        )
        if before:
            cursor = db.get(PaperOrderEvent, before)
            if cursor is None or cursor.account_id != owner or cursor.order_id != order.id:
                raise HTTPException(400, "PAPER_HISTORY_CURSOR_INVALID")
            statement = statement.where(
                tuple_(PaperOrderEvent.timestamp, PaperOrderEvent.id)
                < (cursor.timestamp, cursor.id)
            )
        events = list(
            db.scalars(
                statement.order_by(
                    PaperOrderEvent.timestamp.desc(), PaperOrderEvent.id.desc()
                ).limit(limit + 1)
            )
        )
        more = len(events) > limit
        events = events[:limit]
        fill_keys = [
            event.event_key.removeprefix("fill:") for event in events if event.kind == "FILL"
        ]
        fills = {
            fill.event_key: fill
            for fill in db.scalars(
                select(PaperFill).where(
                    PaperFill.order_id == order.id, PaperFill.event_key.in_(fill_keys)
                )
            )
        }
        quantity, premium, fees = db.execute(
            select(
                func.coalesce(func.sum(PaperFill.quantity), 0),
                func.coalesce(func.sum(PaperFill.quantity * PaperFill.price), 0),
                func.coalesce(func.sum(PaperFill.fees), 0),
            ).where(PaperFill.order_id == order.id)
        ).one()
        position = (
            db.scalar(
                select(PaperPosition).where(
                    PaperPosition.account_id == owner, PaperPosition.entry_order_id == order.id
                )
            )
            if order.side == "BUY"
            else db.scalar(
                select(PaperPosition).where(
                    PaperPosition.account_id == owner, PaperPosition.id == order.position_id
                )
            )
        )
        related = (
            list(
                db.scalars(
                    select(PaperOrder)
                    .where(
                        PaperOrder.account_id == owner,
                        PaperOrder.id != order.id,
                        or_(
                            PaperOrder.id == position.entry_order_id,
                            PaperOrder.position_id == position.id,
                        ),
                    )
                    .order_by(PaperOrder.timestamp.desc(), PaperOrder.id.desc())
                    .limit(51)
                )
            )
            if position
            else []
        )
        entry = (
            db.get(PaperOrder, position.entry_order_id)
            if position
            else order
            if order.side == "BUY"
            else None
        )
        source = (
            "HUMAN"
            if entry and entry.account_id == owner and entry.manual_intent_id
            else "AI"
            if entry and entry.account_id == owner and entry.decision_id
            else "UNKNOWN"
        )
        instrument = db.get(InstrumentRecord, order.instrument_id)
        rows = []
        for event in events:
            detail: dict = {}
            if event.kind == "ACCEPTED":
                accepted = event.payload.get("request", {})
                detail = {
                    key: accepted.get(key) for key in ("quantity", "limit_price", "trigger_price")
                }
            elif event.kind == "AMENDED":
                detail = {
                    key: {
                        field: event.payload.get(key, {}).get(field)
                        for field in (
                            "entry",
                            "stop_loss",
                            "target",
                            "reserved_cash",
                            "reserved_risk",
                        )
                    }
                    for key in ("before", "after")
                }
            elif event.kind in {"TRIGGERED", "PRICE_PROTECTION_SET"}:
                detail = {
                    key: event.payload[key]
                    for key in ("trigger_price", "limit_price")
                    if key in event.payload
                }
            fill = (
                fills.get(event.event_key.removeprefix("fill:")) if event.kind == "FILL" else None
            )
            if fill:
                detail = {
                    "quantity": fill.quantity,
                    "price": str(fill.price),
                    "fees": str(fill.fees),
                    "fee_breakdown": fill.fee_breakdown,
                }
            rows.append(
                {
                    "id": str(event.id),
                    "kind": event.kind,
                    "timestamp": event.timestamp.isoformat(),
                    "detail": detail,
                    "fill_recorded": bool(fill),
                }
            )
        return {
            "as_of": datetime.now(UTC).isoformat(),
            "order": {
                **order_view(order),
                "source": source,
                "legacy": order.execution_version == LEGACY,
            },
            "instrument": {
                key: instrument.payload.get(key)
                for key in ("underlying", "strike", "option_type", "expiry", "exchange")
            }
            if instrument
            else None,
            "fills": {
                "quantity": quantity,
                "average_price": str(premium / quantity) if quantity else None,
                "premium": str(premium),
                "fees": str(fees),
                "cash_movement": str((premium if order.side == "SELL" else -premium) - fees),
            },
            "position": {
                "id": str(position.id),
                "remaining_quantity": position.quantity - position.closed_quantity,
                "closed": position.closed_at is not None,
                "stop_loss": str(position.stop_loss),
                "target": str(position.target),
                "pending_exit": position.pending_exit,
                "realized_pnl": str(position.realized_pnl)
                if position.realized_pnl is not None
                else None,
            }
            if position
            else None,
            "related_orders": [order_view(value) for value in related[:50]],
            "related_truncated": len(related) > 50,
            "events": rows,
            "next_before": str(events[-1].id) if more else None,
        }
