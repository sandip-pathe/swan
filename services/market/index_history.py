"""Bounded NIFTY index-bar query and provenance-preserving normalization."""

import hashlib
import json
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from services.core.contracts import IST, ExchangeSession
from services.market.settings import MarketSettings, ProviderError
from services.strategies.contracts import IndexBar

INDEX_HISTORY_SOURCE = "angelone-historical:getCandleData"
MAX_INDEX_BARS = 400
ONE_MINUTE = timedelta(minutes=1)


class IndexHistoryQuery(BaseModel):
    """One bounded, regular-session NIFTY/NSE one-minute history request."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    underlying: Literal["NIFTY", "SENSEX"] = "NIFTY"
    exchange: Literal["NSE", "BSE"] = "NSE"
    session: ExchangeSession
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def bounded_session_window(self) -> Self:
        start, end = self.start.astimezone(IST), self.end.astimezone(IST)
        if (self.underlying, self.exchange) not in {("NIFTY", "NSE"), ("SENSEX", "BSE")}:
            raise ValueError("INDEX_HISTORY_IDENTITY_MISMATCH")
        session_open = self.session.opens_at.astimezone(IST)
        session_close = self.session.closes_at.astimezone(IST)
        if not self.session.verified or session_open != datetime.combine(
            self.session.key, time(9, 15), IST
        ):
            raise ValueError("INDEX_HISTORY_SESSION_UNVERIFIED")
        if start >= end or start < session_open or end > session_close:
            raise ValueError("INDEX_HISTORY_INVALID_WINDOW")
        if any(stamp.second or stamp.microsecond for stamp in (start, end)):
            raise ValueError("INDEX_HISTORY_MINUTE_BOUNDARIES_REQUIRED")
        if (end - start) > MAX_INDEX_BARS * ONE_MINUTE:
            raise ValueError("INDEX_HISTORY_BAR_LIMIT")
        if start.date() != self.session.key or end.date() != self.session.key:
            raise ValueError("INDEX_HISTORY_CROSS_SESSION")
        return self

    def provider_body(self, settings: MarketSettings, requested_at: datetime) -> dict[str, str]:
        token = settings.nifty_index_token if self.underlying == "NIFTY" else settings.sensex_index_token
        if not token:
            raise ProviderError("INDEX_HISTORY_TOKEN_UNAVAILABLE")
        if requested_at.tzinfo is None or requested_at.utcoffset() is None:
            raise ProviderError("INDEX_HISTORY_REQUEST_TIME_INVALID")
        if self.end > requested_at:
            raise ProviderError("INDEX_HISTORY_FUTURE_RANGE")
        return {
            "exchange": self.exchange,
            "symboltoken": token,
            "interval": "ONE_MINUTE",
            "fromdate": self.start.astimezone(IST).strftime("%Y-%m-%d %H:%M"),
            "todate": self.end.astimezone(IST).strftime("%Y-%m-%d %H:%M"),
        }


class IndexHistoryResult(BaseModel):
    """In-memory source snapshot; not a persisted market acceptance record."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot_id: str
    source: Literal["angelone-historical:getCandleData"] = "angelone-historical:getCandleData"
    underlying: Literal["NIFTY", "SENSEX"] = "NIFTY"
    exchange: Literal["NSE", "BSE"] = "NSE"
    received_at: AwareDatetime
    provider_request: dict[str, str]
    response_sha256: str
    bars: tuple[IndexBar, ...] = Field(max_length=MAX_INDEX_BARS)


def normalize_index_bars(
    rows: object,
    query: IndexHistoryQuery,
    received_at: datetime,
    provider_request: dict[str, str],
) -> IndexHistoryResult:
    """Validate the provider response and attach stable bar-level provenance."""
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ProviderError("INDEX_HISTORY_RECEIPT_TIME_INVALID")
    if not isinstance(rows, list) or len(rows) > MAX_INDEX_BARS:
        raise ProviderError("INDEX_HISTORY_INVALID_RESPONSE")

    normalized: dict[datetime, tuple[tuple[object, ...], IndexBar]] = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != 6 or not isinstance(row[0], str):
            raise ProviderError("INDEX_HISTORY_INVALID_BAR")
        try:
            opened = datetime.fromisoformat(row[0])
            if opened.tzinfo is None or opened.utcoffset() != timedelta(hours=5, minutes=30):
                raise ValueError
            opened = opened.astimezone(IST)
            if opened.second or opened.microsecond or not query.start.astimezone(IST) <= opened <= query.end.astimezone(IST):
                raise ValueError
            if any(isinstance(value, bool) for value in row[1:5]):
                raise ValueError
            opening, high, low, close = (Decimal(str(value)) for value in row[1:5])
            volume = Decimal(str(row[5]))
            if not volume.is_finite() or volume < 0 or volume != volume.to_integral_value():
                raise ValueError
            if not all(value.is_finite() for value in (opening, high, low, close)):
                raise ValueError
            if not 0 < low <= min(opening, close) <= max(opening, close) <= high:
                raise ValueError
        except (ValueError, InvalidOperation, TypeError, OverflowError):
            raise ProviderError("INDEX_HISTORY_INVALID_BAR") from None

        # SmartAPI's `todate` is inclusive. Validate its boundary row but keep
        # our assessment window half-open: that minute has not completed yet.
        # The raw response hash below still retains this source observation.
        if opened == query.end.astimezone(IST):
            continue

        closes_at = opened + ONE_MINUTE
        values = (opening, high, low, close)
        available = received_at.astimezone(IST)
        final = closes_at <= available
        identity = {
            "underlying": query.underlying,
            "exchange": query.exchange,
            "source": INDEX_HISTORY_SOURCE,
            "opens_at": opened.isoformat(),
            "ohlc": [str(value) for value in values],
            "available_at": available.isoformat(),
        }
        evidence_id = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        bar = IndexBar(
            evidence_id=evidence_id,
            underlying=query.underlying,
            exchange=query.exchange,
            source=INDEX_HISTORY_SOURCE,
            opens_at=opened,
            closes_at=closes_at,
            available_at=available,
            final=final,
            open=opening,
            high=high,
            low=low,
            close=close,
        )
        previous = normalized.get(opened)
        if previous is not None and previous[0] != (*values, volume):
            raise ProviderError("INDEX_HISTORY_CONFLICTING_DUPLICATE")
        normalized[opened] = ((*values, volume), bar)

    bars = tuple(normalized[stamp][1] for stamp in sorted(normalized))
    raw_canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    response_sha256 = hashlib.sha256(raw_canonical.encode()).hexdigest()
    snapshot_identity = json.dumps(
        {
            "request": provider_request,
            "received_at": received_at.isoformat(),
            "response_sha256": response_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    snapshot_id = hashlib.sha256(snapshot_identity.encode()).hexdigest()
    return IndexHistoryResult(
        underlying=query.underlying,
        exchange=query.exchange,
        snapshot_id=snapshot_id,
        received_at=received_at,
        provider_request=provider_request,
        response_sha256=response_sha256,
        bars=bars,
    )
