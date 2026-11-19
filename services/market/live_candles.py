"""One-minute OHLC from observed LTP snapshots, never executable-price evidence."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from services.core.contracts import ExchangeSession, Instrument, Quote


@dataclass
class Cursor:
    stream_id: UUID
    timestamp: datetime
    sequence: int
    volume: int | None
    session: ExchangeSession
    bar: dict


def minute(stamp: datetime, session: ExchangeSession) -> datetime:
    return session.opens_at + timedelta(
        minutes=int((stamp - session.opens_at).total_seconds()) // 60
    )


class LiveCandles:
    def __init__(self):
        self.cursors: dict[str, Cursor] = {}
        self.dirty: dict[tuple[str, UUID, datetime], dict] = {}
        self.recoveries: dict[str, tuple[UUID, ExchangeSession, datetime]] = {}

    def retain(self, identifiers: set[str]) -> None:
        self.cursors = {k: v for k, v in self.cursors.items() if k in identifiers}
        self.recoveries = {k: v for k, v in self.recoveries.items() if k in identifiers}

    def observe(self, quote: Quote, instrument: Instrument, session: ExchangeSession) -> bool:
        if (
            not session.verified
            or quote.instrument_id != instrument.id
            or instrument.exchange not in {"NFO", "BFO"}
            or quote.source != "angelone-websocket-v2:snapquote"
            or quote.timestamp_basis != "exchange_feed"
            or quote.stream_id is None
            or quote.sequence is None
            or quote.last_price is None
            or quote.timestamp > quote.received_at
            or not session.opens_at <= quote.timestamp < session.closes_at
            or quote.received_at - quote.timestamp > timedelta(seconds=10)
        ):
            return False
        previous = self.cursors.get(instrument.id)
        if previous and (
            quote.timestamp < previous.timestamp
            or quote.stream_id == previous.stream_id
            and quote.sequence <= previous.sequence
        ):
            return False
        opening = minute(quote.timestamp, session)
        continuous = bool(
            previous
            and previous.stream_id == quote.stream_id
            and previous.session == session
            and quote.timestamp - previous.timestamp <= timedelta(seconds=10)
        )
        reasons = []
        if not continuous:
            reasons.append("stream_start_or_gap")
            queued = self.recoveries.get(instrument.id)
            target = min(queued[2], opening) if queued and queued[0] == quote.stream_id else opening
            self.recoveries[instrument.id] = (quote.stream_id, session, target)
        delta = None
        if (
            continuous
            and previous is not None
            and previous.volume is not None
            and quote.volume is not None
        ):
            if quote.volume >= previous.volume:
                delta = quote.volume - previous.volume
            else:
                reasons.append("cumulative_volume_reset")
        else:
            reasons.append("volume_baseline_unavailable")
        same_bar = bool(
            previous
            and previous.stream_id == quote.stream_id
            and previous.bar["opens_at"] == opening.isoformat()
        )
        if same_bar and previous is not None:
            bar = dict(previous.bar)
            bar["high"] = str(max(quote.last_price, previous.bar["_high"]))
            bar["low"] = str(min(quote.last_price, previous.bar["_low"]))
            bar["_high"] = max(quote.last_price, previous.bar["_high"])
            bar["_low"] = min(quote.last_price, previous.bar["_low"])
            bar["close"] = str(quote.last_price)
            bar["observations"] += 1
            bar["observed_volume_delta"] += delta or 0
            if bar["volume"] is not None and delta is not None:
                bar["volume"] += delta
            else:
                bar["volume"] = None
            bar["issues"] = sorted(set(bar["issues"]) | set(reasons))
        else:
            # A cumulative delta straddling a minute boundary cannot be allocated
            # to either minute accurately. Do not invent a per-minute volume.
            reasons.append("partial_interval_start")
            bar = {
                "opens_at": opening.isoformat(),
                "open": str(quote.last_price),
                "high": str(quote.last_price),
                "low": str(quote.last_price),
                "close": str(quote.last_price),
                "_high": quote.last_price,
                "_low": quote.last_price,
                "volume": None,
                "observed_volume_delta": 0,
                "observations": 1,
                "issues": sorted(set(reasons)),
                "first_observed_at": quote.timestamp.isoformat(),
            }
        bar.update(
            last_observed_at=quote.timestamp.isoformat(),
            closes_at=min(opening + timedelta(minutes=1), session.closes_at).isoformat(),
            received_at=quote.received_at.isoformat(),
            oi=quote.oi,
            source="observed_ltp_snapshots",
            interval="ONE_MINUTE",
            state="provisional",
            coverage="observed_snapshots_not_all_exchange_trades",
            stream_id=str(quote.stream_id),
            instrument=instrument.model_dump(mode="json"),
            session=session.model_dump(mode="json"),
        )
        key = (instrument.id, quote.stream_id, opening)
        if key not in self.dirty and len(self.dirty) >= 4096:
            self.recoveries[instrument.id] = (quote.stream_id, session, opening)
            return False
        self.cursors[instrument.id] = Cursor(
            quote.stream_id, quote.timestamp, quote.sequence, quote.volume, session, bar
        )
        self.dirty[key] = {k: v for k, v in bar.items() if not k.startswith("_")}
        return True

    def drain(self) -> list[dict]:
        result = list(self.dirty.values())
        self.dirty.clear()
        return result

    def restore(self, rows: list[dict]) -> None:
        for row in rows:
            key = (
                row["instrument"]["id"],
                UUID(row["stream_id"]),
                datetime.fromisoformat(row["opens_at"]),
            )
            if key not in self.dirty and len(self.dirty) < 4096:
                self.dirty[key] = row
            elif key not in self.dirty:
                self.recoveries[key[0]] = (
                    key[1],
                    ExchangeSession.model_validate(row["session"]),
                    key[2],
                )
