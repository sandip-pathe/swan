"""Cached discovery only. Search never subscribes, fetches prices or admits an order."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Numeric, case, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import IST, Instrument
from services.core.models import Account, AuditEvent, InstrumentRecord, ListedInstrument
from services.market.catalog import InstrumentCatalog
from services.market.settings import ProviderError
from services.paper.engine import ConflictError, PaperEngine
from services.worker.models import LatestMarketQuote

router = APIRouter()
CATALOG_LOCK = 726230519845


def owner(db: Session, identifier: UUID) -> None:
    if db.get(Account, identifier) is None:
        raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")


@router.post("/api/market/instruments/refresh")
def refresh_catalog(request: Request, identifier: UUID = Depends(account_identity)):
    now, failed = datetime.now(UTC), False
    result: dict[str, object]
    with Session(request.app.state.engine) as db, db.begin():
        owner(db, identifier)
        if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": CATALOG_LOCK}):
            raise HTTPException(429, "CATALOG_REFRESH_BUSY")
        previous = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.kind == "CATALOG_REFRESHED")
            .order_by(AuditEvent.timestamp.desc())
            .limit(1)
        )
        if previous and now - previous.timestamp < timedelta(seconds=60):
            raise HTTPException(429, "CATALOG_REFRESH_RATE_LIMIT")
        try:
            catalog = asyncio.run(InstrumentCatalog.fetch())
            items = list(catalog.instruments.values())
            if not items or len(items) > 50000:
                raise ProviderError("CATALOG_SIZE_LIMIT")
        except (ProviderError, ValueError, TypeError, OSError, TimeoutError):
            failed = True
            result = {"status": "unavailable"}
        else:
            for index in range(0, len(items), 500):
                statement = insert(ListedInstrument).values(
                    [
                        {
                            "id": item.id,
                            "catalog_at": catalog.fetched_at,
                            "payload": item.model_dump(mode="json"),
                        }
                        for item in items[index : index + 500]
                    ]
                )
                db.execute(
                    statement.on_conflict_do_update(
                        index_elements=[ListedInstrument.id],
                        set_={
                            "catalog_at": statement.excluded.catalog_at,
                            "payload": statement.excluded.payload,
                        },
                    )
                )
            result = {
                "status": "available",
                "contracts": len(items),
                "catalog_at": catalog.fetched_at.isoformat(),
            }
        db.add(
            AuditEvent(
                account_id=identifier, kind="CATALOG_REFRESHED", timestamp=now, details=result
            )
        )
    if failed:
        raise HTTPException(503, "CATALOG_UNAVAILABLE")
    return result


@router.get("/api/market/instruments")
def search(
    request: Request,
    underlying: Literal["NIFTY", "SENSEX"] = "NIFTY",
    q: str = Query("", max_length=60),
    expiry: date | None = None,
    option_type: Literal["CALL", "PUT"] | None = None,
    offset: int = Query(0, ge=0, le=10000),
    identifier: UUID = Depends(account_identity),
):
    today = datetime.now(UTC).astimezone(IST).date()
    with Session(request.app.state.engine) as db:
        owner(db, identifier)
        latest = db.scalar(select(func.max(ListedInstrument.catalog_at)))
        if latest is None:
            return {
                "rows": [],
                "expiries": [],
                "next_offset": None,
                "catalog_at": None,
                "stale": True,
                "provider_called": False,
            }
        fields = ListedInstrument.payload
        filters = [
            ListedInstrument.catalog_at == latest,
            fields["underlying"].as_string() == underlying,
            fields["expiry"].as_string() >= today.isoformat(),
        ]
        expiries: list[str] = list(
            db.scalars(
                select(fields["expiry"].as_string().label("expiry"))
                .where(*filters)
                .distinct()
                .order_by("expiry")
                .limit(100)
            )
        )
        if expiry:
            filters.append(fields["expiry"].as_string() == expiry.isoformat())
        if option_type:
            filters.append(fields["option_type"].as_string() == option_type)
        label = func.concat(
            fields["underlying"].as_string(),
            " ",
            fields["strike"].as_string(),
            " ",
            fields["option_type"].as_string(),
            " ",
            case((fields["option_type"].as_string() == "CALL", "CE"), else_="PE"),
            " ",
            fields["expiry"].as_string(),
        )
        for term in q.split():
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(label.ilike(f"%{escaped}%", escape="\\"))
        rows = list(
            db.scalars(
                select(ListedInstrument)
                .where(*filters)
                .order_by(
                    fields["expiry"].as_string(),
                    fields["strike"].as_string().cast(Numeric),
                    fields["option_type"].as_string(),
                    ListedInstrument.id,
                )
                .offset(offset)
                .limit(31)
            )
        )
        return {
            "rows": [row.payload for row in rows[:30]],
            "expiries": expiries,
            "next_offset": offset + 30 if len(rows) > 30 else None,
            "catalog_at": latest.isoformat(),
            "stale": latest.astimezone(IST).date() != today,
            "provider_called": False,
        }


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument_id: str = Field(min_length=1, max_length=100)


def selected(db: Session, identifier: str) -> dict:
    record = db.get(InstrumentRecord, identifier)
    if record is None:
        raise HTTPException(404, "INSTRUMENT_NOT_SAVED")
    quote = db.get(LatestMarketQuote, identifier)
    return {"instrument": record.payload, "quote": quote.payload if quote else None}


@router.get("/api/market/instruments/selected")
def selected_instrument(
    request: Request,
    instrument_id: str = Query(min_length=1, max_length=100),
    identifier: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        owner(db, identifier)
        return selected(db, instrument_id)


@router.post("/api/market/instruments/selected")
def select_instrument(
    body: Selection, request: Request, identifier: UUID = Depends(account_identity)
):
    with Session(request.app.state.engine) as db, db.begin():
        owner(db, identifier)
        instrument = persist_listing(db, body.instrument_id)
        return selected(db, instrument.id)


def persist_listing(db: Session, instrument_id: str) -> Instrument:
    today = datetime.now(UTC).astimezone(IST).date()
    listing = db.get(ListedInstrument, instrument_id)
    latest = db.scalar(select(func.max(ListedInstrument.catalog_at)))
    if listing is None or listing.catalog_at != latest:
        raise HTTPException(404, "INSTRUMENT_NOT_LISTED")
    if listing.catalog_at.astimezone(IST).date() != today:
        raise HTTPException(409, "CATALOG_REFRESH_REQUIRED")
    instrument = Instrument.model_validate(listing.payload)
    if instrument.expiry < today:
        raise HTTPException(409, "INSTRUMENT_EXPIRED")
    try:
        PaperEngine._persist_instrument(db, instrument)
    except ConflictError:
        raise HTTPException(409, "INSTRUMENT_IDENTITY_CHANGED") from None
    db.flush()
    return instrument
