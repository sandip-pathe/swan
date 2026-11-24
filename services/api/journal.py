"""Owner-scoped cursor pages for closed paper positions."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.models import Account, InstrumentRecord, PaperPosition

router = APIRouter()


@router.get("/api/paper/journal")
def journal(
    request: Request,
    before: UUID | None = None,
    limit: int = Query(20, ge=1, le=50),
    owner: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        if db.get(Account, owner) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        statement = select(PaperPosition).where(
            PaperPosition.account_id == owner,
            PaperPosition.closed_at.is_not(None),
        )
        if before:
            cursor = db.get(PaperPosition, before)
            if (
                cursor is None
                or cursor.account_id != owner
                or cursor.closed_at is None
            ):
                raise HTTPException(400, "JOURNAL_CURSOR_INVALID")
            statement = statement.where(
                tuple_(PaperPosition.closed_at, PaperPosition.id)
                < (cursor.closed_at, cursor.id)
            )
        positions = list(
            db.scalars(
                statement.order_by(PaperPosition.closed_at.desc(), PaperPosition.id.desc())
                .limit(limit + 1)
            )
        )
        more = len(positions) > limit
        positions = positions[:limit]
        instruments = {
            item.id: item.payload
            for item in db.scalars(
                select(InstrumentRecord).where(
                    InstrumentRecord.id.in_({item.instrument_id for item in positions})
                )
            )
        }
        rows = []
        for item in positions:
            assert item.closed_at is not None  # Query is restricted to closed positions.
            rows.append(
                {
                    "id": str(item.id),
                    "instrument_id": item.instrument_id,
                    "quantity": item.quantity,
                    "closed_quantity": item.closed_quantity,
                    "remaining_quantity": item.quantity - item.closed_quantity,
                    "average_price": str(item.average_price),
                    "stop_loss": str(item.stop_loss),
                    "target": str(item.target) if item.target is not None else None,
                    "opened_at": item.opened_at.isoformat(),
                    "closed_at": item.closed_at.isoformat(),
                    "realized_pnl": str(item.realized_pnl)
                    if item.realized_pnl is not None
                    else None,
                    "entry_order_id": str(item.entry_order_id),
                    "instrument": instruments.get(item.instrument_id),
                }
            )
        return {
            "as_of": datetime.now(UTC).isoformat(),
            "rows": rows,
            "next_before": str(positions[-1].id) if more and positions else None,
        }
