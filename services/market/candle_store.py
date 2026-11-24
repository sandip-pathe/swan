"""Account-scoped observed candles and non-additive history reconciliation."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Engine, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.core.contracts import ExchangeSession, Instrument
from services.core.models import LiveCandleSegment, MarketHistoryBatch
from services.market.live_candles import minute
from services.paper.engine import PaperEngine


class CandleStore:
    def __init__(self, engine: Engine, account_id: UUID):
        self.engine, self.account_id = engine, account_id

    def save(self, rows: list[dict]) -> None:
        if not rows:
            return
        # Match quote publication's instrument-row lock order, regardless of
        # the order in which independent stream packets arrived.
        rows = sorted(rows, key=lambda row: (row["instrument"]["id"], row["stream_id"], row["opens_at"]))
        with Session(self.engine) as db, db.begin():
            for row in rows:
                instrument = Instrument.model_validate(row["instrument"])
                PaperEngine._persist_instrument(db, instrument)
            statement = insert(LiveCandleSegment).values(
                [
                    {
                        "account_id": self.account_id,
                        "instrument_id": row["instrument"]["id"],
                        "stream_id": UUID(row["stream_id"]),
                        "opens_at": datetime.fromisoformat(row["opens_at"]),
                        "last_observed_at": datetime.fromisoformat(row["last_observed_at"]),
                        "payload": row,
                    }
                    for row in rows
                ]
            )
            db.execute(
                statement.on_conflict_do_update(
                    index_elements=[
                        LiveCandleSegment.account_id,
                        LiveCandleSegment.instrument_id,
                        LiveCandleSegment.stream_id,
                        LiveCandleSegment.opens_at,
                    ],
                    set_={
                        "last_observed_at": statement.excluded.last_observed_at,
                        "payload": statement.excluded.payload,
                    },
                    where=LiveCandleSegment.last_observed_at <= statement.excluded.last_observed_at,
                )
            )

    def recovery_start(
        self, instrument_id: str, stream_id: UUID, session: ExchangeSession, target: datetime
    ) -> datetime:
        with Session(self.engine) as db:
            stamp = db.scalar(
                select(func.max(LiveCandleSegment.last_observed_at)).where(
                    LiveCandleSegment.account_id == self.account_id,
                    LiveCandleSegment.instrument_id == instrument_id,
                    LiveCandleSegment.opens_at >= session.opens_at,
                    LiveCandleSegment.opens_at <= target,
                    or_(
                        LiveCandleSegment.stream_id != stream_id,
                        LiveCandleSegment.opens_at < target,
                    ),
                )
            )
        return minute(stamp, session) if stamp else session.opens_at


def reconciled_bars(
    segments: list[dict],
    batches: list[MarketHistoryBatch],
    start: datetime,
    end: datetime,
    now: datetime,
) -> list[dict]:
    """Batches are newest first. Never add provider volume to observed volume."""
    grouped: dict[datetime, list[dict]] = {}
    for row in segments:
        opening = datetime.fromisoformat(row["opens_at"])
        if start <= opening <= end:
            grouped.setdefault(opening, []).append(row)
    bars = {}
    for opening, pieces in grouped.items():
        pieces.sort(
            key=lambda p: (
                datetime.fromisoformat(p["first_observed_at"]),
                datetime.fromisoformat(p["last_observed_at"]),
            )
        )
        latest = max(pieces, key=lambda p: datetime.fromisoformat(p["last_observed_at"]))
        bars[opening] = {
            "opens_at": opening.isoformat(),
            "open": pieces[0]["open"],
            "high": str(max(Decimal(p["high"]) for p in pieces)),
            "low": str(min(Decimal(p["low"]) for p in pieces)),
            "close": latest["close"],
            "volume": None,
            "oi": latest["oi"],
            "source": "observed_ltp_snapshots",
            "coverage": "observed_snapshots_not_all_exchange_trades",
            "state": "elapsed"
            if datetime.fromisoformat(latest["closes_at"]) <= now
            else "provisional",
            "last_observed_at": latest["last_observed_at"],
            "observed_segments": len(pieces),
            "issues": sorted({issue for p in pieces for issue in p["issues"]}),
        }
    covered: set[datetime] = set()
    for batch in batches:
        if batch.payload.get("status") not in {"available", "empty"}:
            continue
        left = max(start, datetime.fromisoformat(batch.request["start"]))
        right = min(end, datetime.fromisoformat(batch.request["end"]))
        for bar in batch.payload.get("bars", []):
            opening = datetime.fromisoformat(bar["opens_at"])
            if not left <= opening <= right or opening in covered:
                continue
            observed = bars.get(opening)
            received = datetime.fromisoformat(batch.payload["received_at"])
            if (
                bar["state"] == "closed"
                or observed is None
                or (received >= datetime.fromisoformat(observed["last_observed_at"]))
            ):
                bars[opening] = {
                    **bar,
                    "source": batch.payload["source"],
                    "batch_id": str(batch.id),
                    "coverage": "provider_returned_bar",
                    "observed_segments": len(grouped.get(opening, [])),
                    "reconciliation": "provider_selected_not_summed",
                }
        # Empty newer batches must not silently resurrect older provider bars.
        while left <= right:
            covered.add(left)
            left += timedelta(minutes=1)
    return [bars[stamp] for stamp in sorted(bars)]
