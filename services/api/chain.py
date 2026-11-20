"""Cached quote chain, paged by strike so calls/puts are not split across pages."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Numeric, func, select
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.api.instruments import owner
from services.core.contracts import IST
from services.core.models import InstrumentRecord
from services.market.references import reference_context
from services.worker.models import LatestMarketQuote

router = APIRouter()
PAGE_SIZE = 50


@router.get("/api/chain")
def chain(
    request: Request,
    underlying: str = Query("NIFTY", pattern="^(NIFTY|SENSEX)$"),
    expiry: date | None = None,
    sort: Literal["latest", "strike"] = "latest",
    offset: int = Query(0, ge=0, le=10000),
    identifier: UUID = Depends(account_identity),
):
    now = datetime.now(UTC)
    with Session(request.app.state.engine) as db:
        owner(db, identifier)
        fields = InstrumentRecord.payload
        expiry_field = fields["expiry"].as_string()
        strike = fields["strike"].as_string().cast(Numeric)
        filters = [
            fields["underlying"].as_string() == underlying,
            expiry_field >= now.astimezone(IST).date().isoformat(),
        ]
        expiries: list[str] = list(
            db.scalars(
                select(expiry_field.label("expiry"))
                .join(LatestMarketQuote, LatestMarketQuote.instrument_id == InstrumentRecord.id)
                .where(*filters)
                .distinct()
                .order_by("expiry")
                .limit(100)
            )
        )
        chosen = expiry.isoformat() if expiry else expiries[0] if expiries else None
        filters.append(expiry_field == chosen)
        strikes: list[Decimal] = list(
            db.scalars(
                select(strike.label("strike"))
                .join(LatestMarketQuote, LatestMarketQuote.instrument_id == InstrumentRecord.id)
                .where(*filters)
                .group_by(strike)
                .order_by(
                    *(
                        [func.max(LatestMarketQuote.timestamp).desc(), strike]
                        if sort == "latest"
                        else [strike]
                    )
                )
                .offset(offset)
                .limit(PAGE_SIZE + 1)
            )
        )
        records = db.execute(
            select(InstrumentRecord, LatestMarketQuote)
            .join(LatestMarketQuote, LatestMarketQuote.instrument_id == InstrumentRecord.id)
            .where(*filters, strike.in_(strikes[:PAGE_SIZE]))
            .order_by(strike, fields["option_type"].as_string(), InstrumentRecord.id)
            .limit(201)
        ).all()
        rank = {value: index for index, value in enumerate(strikes[:PAGE_SIZE])}
        records = sorted(
            records,
            key=lambda row: (
                rank[Decimal(row[0].payload["strike"])],
                row[0].payload["option_type"],
                row[0].id,
            ),
        )
        return {
            "reference": reference_context(
                db, underlying, date.fromisoformat(chosen) if chosen else None
            ),
            "sort": sort,
            "as_of": now.isoformat(),
            "underlying": underlying,
            "expiry": chosen,
            "expiries": expiries,
            "page_size": PAGE_SIZE,
            "next_offset": offset + PAGE_SIZE if len(strikes) > PAGE_SIZE else None,
            "truncated": len(records) > 200,
            "provider_called": False,
            "coverage": "saved_quotes_only_not_complete_exchange_chain",
            "rows": [
                {"instrument": item.payload, "quote": quote.payload}
                for item, quote in records[:200]
            ],
        }
