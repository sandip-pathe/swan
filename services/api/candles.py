"""Cached reconciled candle delivery; polling never calls the provider."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import AwareDatetime
from sqlalchemy import DateTime, select
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.api.history import owner
from services.core.contracts import IST, Instrument
from services.core.models import InstrumentRecord, LiveCandleSegment, MarketHistoryBatch
from services.market.calendar import SessionCalendar
from services.market.candle_store import reconciled_bars
from services.market.history import HistoryQuery
from services.market.settings import MarketSettings

router = APIRouter()


@router.get("/api/market/candles")
def candles(
    request: Request,
    instrument_id: str,
    start: AwareDatetime,
    end: AwareDatetime,
    interval: Literal["ONE_MINUTE"] = "ONE_MINUTE",
    identifier: UUID = Depends(account_identity),
):
    now = datetime.now(UTC)
    try:
        HistoryQuery(instrument_id=instrument_id, interval=interval, start=start, end=end)
        if end > now or end - start >= timedelta(minutes=5000):
            raise ValueError("Bounded past range required")
    except ValueError:
        raise HTTPException(422, "CANDLE_INVALID_RANGE") from None
    with Session(request.app.state.engine) as db:
        owner(db, identifier)
        record = db.get(InstrumentRecord, instrument_id)
        if record is None:
            raise HTTPException(404, "HISTORY_INSTRUMENT_NOT_FOUND")
        instrument = Instrument.model_validate(record.payload)
        segments = list(
            db.scalars(
                select(LiveCandleSegment)
                .where(
                    LiveCandleSegment.account_id == identifier,
                    LiveCandleSegment.instrument_id == instrument_id,
                    LiveCandleSegment.opens_at >= start,
                    LiveCandleSegment.opens_at <= end,
                )
                .order_by(LiveCandleSegment.opens_at.desc(), LiveCandleSegment.stream_id)
                .limit(5001)
            )
        )
        batches = list(
            db.scalars(
                select(MarketHistoryBatch)
                .where(
                    MarketHistoryBatch.account_id == identifier,
                    MarketHistoryBatch.instrument_id == instrument_id,
                    MarketHistoryBatch.request["interval"].as_string() == interval,
                    MarketHistoryBatch.request["start"].as_string().cast(DateTime(timezone=True))
                    <= end,
                    MarketHistoryBatch.request["end"].as_string().cast(DateTime(timezone=True))
                    >= start,
                    MarketHistoryBatch.payload["status"].as_string().in_(["available", "empty"]),
                )
                .order_by(MarketHistoryBatch.requested_at.desc())
                .limit(21)
            )
        )
        bars = reconciled_bars(
            [row.payload for row in segments[:5000]], batches[:20], start, end, now
        )
    calendar = SessionCalendar(MarketSettings().calendar_file, strict=False)
    available = {datetime.fromisoformat(bar["opens_at"]) for bar in bars}
    gaps, unknown = [], set()
    stamp = start
    while stamp <= end:
        day = stamp.astimezone(IST).date()
        session = calendar.get(instrument.exchange, day)
        if session is None:
            unknown.add(day.isoformat())
        elif session.opens_at <= stamp < session.closes_at and stamp not in available:
            gaps.append(stamp.isoformat())
        stamp += timedelta(minutes=1)
    return {
        "instrument_id": instrument_id,
        "interval": interval,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "as_of": now.isoformat(),
        "bars": bars,
        "gaps": gaps,
        "unknown_session_dates": sorted(unknown),
        "truncated": len(segments) > 5000 or len(batches) > 20,
        "provider_called": False,
        "finality": "elapsed_interval_not_exchange_confirmation",
    }
