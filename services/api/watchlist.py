"""Owner-scoped watchlist. No provider access or execution/subscription changes."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.api.instruments import Selection, owner, persist_listing
from services.core.contracts import IST
from services.core.models import InstrumentRecord, ListedInstrument, WatchlistItem
from services.worker.models import LatestMarketQuote

router = APIRouter()
LIMIT = 50


def write_lock(db: Session, identifier: UUID) -> None:
    # Serialize capacity checks per owner without taking the execution account lock.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"watchlist:{identifier}"},
    )


@router.get("/api/watchlist")
def watchlist(request: Request, identifier: UUID = Depends(account_identity)):
    now = datetime.now(UTC)
    today = now.astimezone(IST).date().isoformat()
    with Session(request.app.state.engine) as db:
        owner(db, identifier)
        latest = db.scalar(select(func.max(ListedInstrument.catalog_at)))
        rows = db.execute(
            select(WatchlistItem, InstrumentRecord, LatestMarketQuote, ListedInstrument)
            .join(InstrumentRecord, InstrumentRecord.id == WatchlistItem.instrument_id)
            .outerjoin(
                LatestMarketQuote, LatestMarketQuote.instrument_id == WatchlistItem.instrument_id
            )
            .outerjoin(ListedInstrument, ListedInstrument.id == WatchlistItem.instrument_id)
            .where(WatchlistItem.account_id == identifier)
            .order_by(WatchlistItem.saved_at.desc(), WatchlistItem.instrument_id)
            .limit(LIMIT)
        ).all()
        return {
            "as_of": now.isoformat(),
            "limit": LIMIT,
            "provider_called": False,
            "rows": [
                {
                    "instrument": instrument.payload,
                    "quote": quote.payload if quote else None,
                    "saved_at": item.saved_at.isoformat(),
                    "status": "expired"
                    if instrument.payload["expiry"] < today
                    else "not_listed"
                    if listing is None
                    or listing.catalog_at != latest
                    or {k: v for k, v in listing.payload.items() if k != "verified_at"}
                    != {k: v for k, v in instrument.payload.items() if k != "verified_at"}
                    else "listed",
                }
                for item, instrument, quote, listing in rows
            ],
        }


@router.post("/api/watchlist/save")
def save(body: Selection, request: Request, identifier: UUID = Depends(account_identity)):
    with Session(request.app.state.engine) as db, db.begin():
        owner(db, identifier)
        write_lock(db, identifier)
        if db.get(WatchlistItem, (identifier, body.instrument_id)) is None:
            count = db.scalar(
                select(func.count())
                .select_from(WatchlistItem)
                .where(WatchlistItem.account_id == identifier)
            )
            if count is not None and count >= LIMIT:
                raise HTTPException(409, "WATCHLIST_FULL")
            instrument = persist_listing(db, body.instrument_id)
            db.add(
                WatchlistItem(
                    account_id=identifier, instrument_id=instrument.id, saved_at=datetime.now(UTC)
                )
            )
    return {"instrument_id": body.instrument_id, "saved": True}


@router.post("/api/watchlist/remove")
def remove(body: Selection, request: Request, identifier: UUID = Depends(account_identity)):
    with Session(request.app.state.engine) as db, db.begin():
        owner(db, identifier)
        write_lock(db, identifier)
        db.execute(
            delete(WatchlistItem).where(
                WatchlistItem.account_id == identifier,
                WatchlistItem.instrument_id == body.instrument_id,
            )
        )
    return {"instrument_id": body.instrument_id, "saved": False}
