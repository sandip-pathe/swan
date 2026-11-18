"""Explicit exchange sessions only. Unknown dates are closed for new entries."""

from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.core.contracts import ExchangeSession
from services.market.settings import ProviderError


class CalendarEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exchange: str
    session: ExchangeSession
    official_source_url: str


class ClosedDay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exchange: str
    day: date
    reason: str = Field(min_length=1)
    official_source_url: str


class CalendarDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    sessions: list[CalendarEntry]
    closed_days: list[ClosedDay] = Field(default_factory=list)

    @model_validator(mode="after")
    def verified_entries(self):
        if self.schema_version != 1:
            raise ValueError("UNSUPPORTED_CALENDAR_VERSION")
        seen = set()
        entries: list[CalendarEntry | ClosedDay] = [*self.sessions, *self.closed_days]
        for entry in entries:
            source = urlparse(entry.official_source_url)
            host = source.hostname or ""
            if (
                entry.exchange not in {"NFO", "BFO"}
                or source.scheme != "https"
                or source.username
                or source.password
                or not any(
                    host == domain or host.endswith("." + domain)
                    for domain in ("nseindia.com", "bseindia.com")
                )
                or isinstance(entry, CalendarEntry)
                and not entry.session.verified
            ):
                raise ValueError("UNVERIFIED_CALENDAR_ENTRY")
            key = (
                entry.exchange,
                entry.session.key if isinstance(entry, CalendarEntry) else entry.day,
            )
            if key in seen:
                raise ValueError("DUPLICATE_CALENDAR_DAY")
            seen.add(key)
        return self


class SessionCalendar:
    def __init__(self, path: Path, *, strict: bool = True):
        self.path = path
        self.sessions: dict[tuple[str, date], ExchangeSession] = {}
        self.closed_days: dict[tuple[str, date], str] = {}
        try:
            self.reload()
        except ProviderError:
            if strict:
                raise

    def reload(self) -> None:
        try:
            document = CalendarDocument.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ProviderError("VERIFIED_EXCHANGE_CALENDAR_REQUIRED") from None
        self.sessions = {(e.exchange, e.session.key): e.session for e in document.sessions}
        self.closed_days = {(e.exchange, e.day): e.reason for e in document.closed_days}

    def get(self, exchange: str, day: date) -> ExchangeSession | None:
        return self.sessions.get((exchange, day))

    def state(self, exchange: str, now: datetime) -> str:
        from services.core.contracts import IST

        day = now.astimezone(IST).date()
        session = self.get(exchange, day)
        if session:
            return "open" if session.opens_at <= now < session.closes_at else "closed"
        return "closed" if (exchange, day) in self.closed_days else "unknown"

    def describe(self, exchange: str, now: datetime) -> dict:
        """Report only imported coverage; never infer the next weekday session."""
        from services.core.contracts import IST

        day = now.astimezone(IST).date()
        session = self.get(exchange, day)
        upcoming = sorted(
            (
                s
                for (venue, _), s in self.sessions.items()
                if venue == exchange and s.opens_at > now
            ),
            key=lambda s: s.opens_at,
        )
        covered = {d for venue, d in (*self.sessions, *self.closed_days) if venue == exchange}
        return {
            "exchange": exchange,
            "state": self.state(exchange, now),
            "day": day.isoformat(),
            "opens_at": session.opens_at.isoformat() if session else None,
            "closes_at": session.closes_at.isoformat() if session else None,
            "closure_reason": self.closed_days.get((exchange, day)),
            "next_verified_open": upcoming[0].opens_at.isoformat() if upcoming else None,
            "last_covered_day": max(covered).isoformat() if covered else None,
        }
