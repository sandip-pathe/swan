"""Bounded provider candle history, separate from executable market evidence."""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal, Self, get_args

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from services.core.contracts import IST, Instrument
from services.market.settings import ProviderError

Interval = Literal[
    "ONE_MINUTE",
    "THREE_MINUTE",
    "FIVE_MINUTE",
    "TEN_MINUTE",
    "FIFTEEN_MINUTE",
    "THIRTY_MINUTE",
    "ONE_HOUR",
    "ONE_DAY",
]
MINUTES = dict(zip(get_args(Interval), (1, 3, 5, 10, 15, 30, 60, 1440), strict=True))
MAX_DAYS = dict(zip(get_args(Interval), (30, 60, 100, 100, 200, 200, 400, 2000), strict=True))
MAX_BARS = 5000
SOURCE = "angelone-historical:getCandleData"


class HistoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    instrument_id: str
    interval: Interval
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.start >= self.end:
            raise ValueError("HISTORY_INVALID_RANGE")
        if any(t.astimezone(IST).second or t.microsecond for t in (self.start, self.end)):
            raise ValueError("HISTORY_REQUIRES_MINUTE_BOUNDARIES")
        duration = self.end - self.start
        if duration > timedelta(days=MAX_DAYS[self.interval]):
            raise ValueError("HISTORY_PROVIDER_RANGE_LIMIT")
        # Deliberately tighter than provider limits: no automatic paging/fan-out.
        if duration > timedelta(minutes=MINUTES[self.interval] * MAX_BARS):
            raise ValueError("HISTORY_BAR_LIMIT")
        return self

    def provider_body(self, instrument: Instrument, now: datetime) -> dict:
        if instrument.id != self.instrument_id or instrument.exchange not in {"NFO", "BFO"}:
            raise ProviderError("HISTORY_UNSUPPORTED_INSTRUMENT")
        if self.end > now:
            raise ProviderError("HISTORY_FUTURE_RANGE")
        if self.end.astimezone(IST).date() > instrument.expiry:
            raise ProviderError("HISTORY_RANGE_AFTER_EXPIRY")
        return {
            "exchange": instrument.exchange,
            "symboltoken": instrument.provider_token,
            "interval": self.interval,
            "fromdate": self.start.astimezone(IST).strftime("%Y-%m-%d %H:%M"),
            "todate": self.end.astimezone(IST).strftime("%Y-%m-%d %H:%M"),
        }


def normalize_bars(rows: object, query: HistoryQuery, received_at: datetime) -> list[dict]:
    if not isinstance(rows, list) or len(rows) > MAX_BARS:
        raise ProviderError("HISTORY_INVALID_RESPONSE")
    result: dict[datetime, dict] = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != 6 or not isinstance(row[0], str):
            raise ProviderError("HISTORY_INVALID_BAR")
        try:
            stamp = datetime.fromisoformat(row[0])
            if stamp.tzinfo is None or stamp.utcoffset() != timedelta(hours=5, minutes=30):
                raise ValueError
            if stamp.second or stamp.microsecond or not query.start <= stamp <= query.end:
                raise ValueError
            if any(isinstance(value, bool) for value in row[1:]):
                raise ValueError
            opening, high, low, close, volume = (Decimal(str(value)) for value in row[1:])
            if not all(value.is_finite() for value in (opening, high, low, close, volume)):
                raise ValueError
            if not 0 < low <= min(opening, close) <= max(opening, close) <= high:
                raise ValueError
            if volume < 0 or volume != volume.to_integral_value():
                raise ValueError
        except (ValueError, InvalidOperation, TypeError, OverflowError):
            raise ProviderError("HISTORY_INVALID_BAR") from None
        bar = {
            "opens_at": stamp.isoformat(),
            "open": str(opening),
            "high": str(high),
            "low": str(low),
            "close": str(close),
            "volume": int(volume),
            "oi": None,
            "state": "closed"
            if stamp + timedelta(minutes=MINUTES[query.interval]) <= received_at
            else "provisional",
        }
        if stamp in result and result[stamp] != bar:
            raise ProviderError("HISTORY_CONFLICTING_DUPLICATE")
        result[stamp] = bar
    return [result[stamp] for stamp in sorted(result)]
