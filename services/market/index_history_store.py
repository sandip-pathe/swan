"""Immutable persistence and bounded as-of reads for index-history snapshots."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.contracts import IST
from services.core.models import IndexHistoryBatch
from services.market.index_history import MAX_INDEX_BARS, ONE_MINUTE, IndexHistoryResult
from services.strategies.contracts import IndexBar


def persist_index_history(session: Session, result: IndexHistoryResult) -> IndexHistoryBatch:
    """Insert a source response once; a repeated identical snapshot is idempotent."""
    existing = session.get(IndexHistoryBatch, result.snapshot_id)
    if existing is not None:
        if existing.response_sha256 != result.response_sha256:
            raise ValueError("INDEX_HISTORY_SNAPSHOT_ID_CONFLICT")
        return existing
    session.add(
        IndexHistoryBatch(
            snapshot_id=result.snapshot_id,
            underlying=result.underlying,
            exchange=result.exchange,
            session_key=date.fromisoformat(result.provider_request["fromdate"][:10]),
            received_at=result.received_at.astimezone(IST),
            source=result.source,
            response_sha256=result.response_sha256,
            provider_request=result.provider_request,
            payload={"bars": [bar.model_dump(mode="json") for bar in result.bars]},
        )
    )
    session.flush()
    return session.get(IndexHistoryBatch, result.snapshot_id)  # type: ignore[return-value]


def read_index_history(
    session: Session,
    *,
    session_key: date,
    start: datetime,
    end: datetime,
    as_of: datetime,
    limit: int = MAX_INDEX_BARS,
) -> tuple[IndexBar, ...]:
    """Read a bounded view from the newest eligible full-prefix response.

    The deliberate assessment refresh stores the complete session prefix from
    09:15 through its cutoff. Keep source responses immutable so a later
    correction is represented by another batch and never rewrites past reads.
    """
    if any(value.tzinfo is None or value.utcoffset() is None for value in (start, end, as_of)):
        raise ValueError("INDEX_HISTORY_AWARE_TIMESTAMPS_REQUIRED")
    local_start, local_end = start.astimezone(IST), end.astimezone(IST)
    if (
        local_start.date() != session_key
        or local_end.date() != session_key
        or start >= end
        or end - start > MAX_INDEX_BARS * ONE_MINUTE
        or limit < 1
        or limit > MAX_INDEX_BARS
    ):
        raise ValueError("INDEX_HISTORY_INVALID_READ_WINDOW")
    batch = session.scalar(
        select(IndexHistoryBatch)
        .where(
            IndexHistoryBatch.underlying == "NIFTY",
            IndexHistoryBatch.exchange == "NSE",
            IndexHistoryBatch.session_key == session_key,
            IndexHistoryBatch.received_at <= as_of,
        )
        .order_by(IndexHistoryBatch.received_at.desc(), IndexHistoryBatch.snapshot_id.desc())
        .limit(1)
    )
    if batch is None:
        return ()
    raw_bars: Any = batch.payload.get("bars", [])
    if not isinstance(raw_bars, list):
        raise ValueError("INDEX_HISTORY_STORED_PAYLOAD_INVALID")
    bars = tuple(
        bar
        for item in raw_bars
        if (bar := IndexBar.model_validate(item)).opens_at.astimezone(IST).date() == session_key
        and start <= bar.opens_at < end
        and bar.available_at <= as_of
    )
    return bars[:limit]
