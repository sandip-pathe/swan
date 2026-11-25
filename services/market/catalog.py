"""Normalize actual provider metadata and select bounded near-money subscriptions."""

import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import ijson
from pydantic import ValidationError

from services.core.contracts import IST, Instrument
from services.market.settings import ProviderError

MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
EXCHANGE_TYPES = {"NFO": 2, "BFO": 4}


class InstrumentCatalog:
    def __init__(self, instruments: list[Instrument], fetched_at: datetime, rejected: int):
        self.instruments = {item.id: item for item in instruments}
        self.fetched_at = fetched_at
        self.rejected = rejected

    @classmethod
    async def fetch(cls, underlyings: tuple[str, ...] = ("NIFTY", "SENSEX")):
        with tempfile.TemporaryFile() as downloaded:
            try:
                async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
                    total = 0
                    async with client.stream("GET", MASTER_URL) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            total += len(chunk)
                            if total > 100_000_000:
                                raise ProviderError("INSTRUMENT_MASTER_TOO_LARGE")
                            downloaded.write(chunk)
                downloaded.seek(0)

                def selected_rows():
                    return [
                        row
                        for row in ijson.items(downloaded, "item")
                        if isinstance(row, dict)
                        and row.get("name") in underlyings
                        and row.get("instrumenttype") == "OPTIDX"
                    ]

                rows = await asyncio.to_thread(selected_rows)
            except (httpx.HTTPError, ValueError, ijson.JSONError):
                raise ProviderError("INSTRUMENT_MASTER_UNAVAILABLE") from None
        now = datetime.now(UTC)
        instruments = []
        rejected = 0
        for row in rows:
            if (
                row.get("name") not in {"NIFTY", "SENSEX"}
                or row.get("instrumenttype") != "OPTIDX"
                or row.get("exch_seg") not in EXCHANGE_TYPES
            ):
                continue
            try:
                symbol = str(row["symbol"])
                suffix = symbol[-2:]
                if suffix not in {"CE", "PE"}:
                    raise ValueError("Unrecognized option type")
                instrument = Instrument(
                    id=f"{row['exch_seg']}:{row['token']}",
                    provider_token=str(row["token"]),
                    exchange=row["exch_seg"],
                    underlying=row["name"],
                    expiry=datetime.strptime(row["expiry"], "%d%b%Y").date(),
                    strike=Decimal(str(row["strike"])) / 100,
                    option_type="CALL" if suffix == "CE" else "PUT",
                    lot_size=int(row["lotsize"]),
                    tick_size=Decimal(str(row["tick_size"])) / 100,
                    metadata_source="angelone-instrument-master:paise-v1",
                    verified_at=now,
                )
                if (
                    instrument.underlying == "NIFTY"
                    and instrument.exchange != "NFO"
                    or instrument.underlying == "SENSEX"
                    and instrument.exchange != "BFO"
                ):
                    raise ValueError("Underlying exchange mismatch")
                instruments.append(instrument)
            except (KeyError, ValueError, TypeError, ValidationError):
                rejected += 1
        if not instruments:
            raise ProviderError("NO_SUPPORTED_OPTION_INSTRUMENTS")
        return cls(instruments, now, rejected)

    def select(
        self,
        spots: dict[str, Decimal],
        now: datetime,
        each_side: int,
        maximum: int,
        pinned: list[Instrument],
    ) -> list[Instrument]:
        if self.fetched_at.astimezone(IST).date() != now.astimezone(IST).date():
            raise ProviderError("INSTRUMENT_MASTER_REQUIRES_REFRESH")
        today = now.astimezone(IST).date()
        selected = {item.id: item for item in pinned}
        candidates = [
            item
            for item in self.instruments.values()
            if today <= item.expiry <= today + timedelta(days=7)
        ]
        for name, spot in spots.items():
            group = [item for item in candidates if item.underlying == name]
            strikes = sorted({item.strike for item in group})
            nearest = sorted(strikes, key=lambda strike: (abs(strike - spot), strike))[
                : 2 * each_side + 1
            ]
            for item in group:
                if item.strike in nearest:
                    selected[item.id] = item
        if len(selected) > maximum:
            raise ProviderError("UNIVERSE_EXCEEDS_SUBSCRIPTION_BUDGET")
        if not selected:
            raise ProviderError("NO_ELIGIBLE_LISTED_CONTRACTS")
        return sorted(
            selected.values(),
            key=lambda item: (item.underlying, item.expiry, item.strike, item.option_type),
        )
