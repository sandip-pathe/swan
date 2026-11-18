"""Observed chain metrics. Missing values and partial coverage stay explicit."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid5

from services.core.contracts import IST, DepthLevel, Instrument, Quote
from services.market.angelone import AngelOneClient
from services.market.evidence import identify_quote
from services.market.settings import ProviderError
from services.market.stream import QuoteCache
from services.risk.engine import quote_problem


def provider_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def provider_integer(value) -> int | None:
    result = provider_decimal(value)
    return (
        int(result)
        if result is not None and result >= 0 and result == result.to_integral_value()
        else None
    )


def provider_price(value) -> Decimal | None:
    result = provider_decimal(value)
    return result if result is not None and result > 0 else None


def optional_provider_time(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return provider_time(value)
    except (ValueError, OverflowError):
        return None


def provider_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = datetime.strptime(value, "%d-%b-%Y %H:%M:%S")
    return parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed


def normalize_rest_quote(row: dict, instrument: Instrument, now: datetime) -> Quote:
    if str(row.get("symbolToken", row.get("symboltoken"))) != instrument.provider_token:
        raise ProviderError("REST_INSTRUMENT_MISMATCH")
    if row.get("exchange") != instrument.exchange or not row.get("exchFeedTime"):
        raise ProviderError("REST_QUOTE_TIME_OR_EXCHANGE_MISSING")
    depth = row.get("depth")
    if depth is None:
        depth = {}
    if not isinstance(depth, dict):
        raise ProviderError("INVALID_REST_DEPTH")

    def levels(side: str) -> tuple[DepthLevel, ...]:
        items = depth.get(side, [])
        if not isinstance(items, list) or len(items) > 5:
            raise ProviderError("INVALID_REST_DEPTH")
        result = []
        for item in items:
            if not isinstance(item, dict):
                raise ProviderError("INVALID_REST_DEPTH_LEVEL")
            price = provider_decimal(item.get("price"))
            quantity = provider_integer(item.get("quantity"))
            orders = provider_integer(item.get("orders"))
            if price is None or price < 0 or quantity is None or price == 0 and quantity > 0:
                raise ProviderError("INVALID_REST_DEPTH_LEVEL")
            if item.get("orders") is not None and orders is None:
                raise ProviderError("INVALID_REST_DEPTH_ORDERS")
            if price > 0 and quantity > 0:
                result.append(DepthLevel(price=price, quantity=quantity, orders=orders))
        return tuple(sorted(result, key=lambda level: level.price, reverse=side == "buy"))

    bids, asks = levels("buy"), levels("sell")
    bid, ask = bids[0] if bids else None, asks[0] if asks else None
    return identify_quote(
        Quote(
            instrument_id=instrument.id,
            timestamp=provider_time(row["exchFeedTime"]),
            received_at=now,
            source="angelone-rest:full",
            timestamp_basis="exchange_feed",
            bid_depth=bids,
            ask_depth=asks,
            depth_kind="best_five" if depth else "unavailable",
            bid=bid.price if bid else None,
            ask=ask.price if ask else None,
            bid_quantity=bid.quantity if bid else None,
            ask_quantity=ask.quantity if ask else None,
            last_price=provider_price(row.get("ltp")),
            session_open=provider_price(row.get("open")),
            session_high=provider_price(row.get("high")),
            session_low=provider_price(row.get("low")),
            previous_close=provider_price(row.get("close")),
            average_price=provider_price(row.get("avgPrice")),
            last_trade_at=optional_provider_time(row.get("exchTradeTime")),
            last_trade_quantity=provider_integer(row.get("lastTradeQty")),
            oi=provider_integer(row.get("opnInterest")),
            volume=provider_integer(row.get("tradeVolume")),
        )
    )


@dataclass(frozen=True)
class GreekObservation:
    values: dict[str, Decimal]
    iv: Decimal | None
    received_at: datetime


class ChainAnalysis:
    def __init__(self, cache: QuoteCache, max_metric_age: int):
        self.cache = cache
        self.max_metric_age = max_metric_age
        self.greeks: dict[tuple[str, object, Decimal, str], GreekObservation] = {}
        self.problems: dict[str, str] = {}

    async def refresh_greeks(self, client: AngelOneClient, instruments: list[Instrument]) -> None:
        now = datetime.now(UTC)
        self.greeks = {
            key: value
            for key, value in self.greeks.items()
            if (now - value.received_at).total_seconds() <= self.max_metric_age
        }
        for underlying, expiry in sorted({(item.underlying, item.expiry) for item in instruments}):
            key = f"{underlying}:{expiry}"
            if underlying != "NIFTY":
                self.problems[key] = "BSE_GREEKS_NOT_ESTABLISHED"
                continue
            try:
                rows = await client.greeks(underlying, expiry)
                received = datetime.now(UTC)
                for row in rows:
                    if (
                        row.get("name") != underlying
                        or provider_time_expiry(row.get("expiry")) != expiry
                    ):
                        continue
                    strike = provider_decimal(row.get("strikePrice"))
                    option_type = {"CE": "CALL", "PE": "PUT"}.get(str(row.get("optionType", "")))
                    values = {
                        name: provider_decimal(row.get(name))
                        for name in ("delta", "gamma", "theta", "vega")
                    }
                    if (
                        strike is None
                        or option_type is None
                        or any(value is None for value in values.values())
                    ):
                        continue
                    iv = provider_decimal(row.get("impliedVolatility"))
                    self.greeks[(underlying, expiry, strike, option_type)] = GreekObservation(
                        {name: value for name, value in values.items() if value is not None},
                        iv if iv is not None and iv >= 0 else None,
                        received,
                    )
                self.problems.pop(key, None)
            except (ProviderError, ValueError, TypeError):
                self.problems[key] = "GREEKS_UNAVAILABLE"

    def observed_quote(self, instrument: Instrument, now: datetime) -> Quote | None:
        quote = self.cache.quotes.get(instrument.id)
        if quote is None:
            return None
        observation = self.greeks.get(
            (instrument.underlying, instrument.expiry, instrument.strike, instrument.option_type)
        )
        if observation and (now - observation.received_at).total_seconds() <= self.max_metric_age:
            return quote.model_copy(
                update={
                    "id": uuid5(quote.id, observation.received_at.isoformat()),
                    "greeks": observation.values,
                    "iv": observation.iv,
                    "metrics_source": "angelone-optionGreek:provider-time-unavailable",
                    "metrics_received_at": observation.received_at,
                    "iv_unit": "percent",
                }
            )
        return quote

    def view(self, instruments: list[Instrument], now: datetime, quote_max_age: int) -> dict:
        rows: list[dict[str, Any]] = []
        for instrument in instruments:
            quote = self.observed_quote(instrument, now)
            problem = quote_problem(quote, now, quote_max_age)
            history = self.cache.history.get(instrument.id)
            trend = None
            if problem is None and history and len(history) >= 2:
                first, last = history[0], history[-1]
                trend = {
                    "midpoint_change_pct": str((last[1] / first[1] - 1) * 100),
                    "observed_window_seconds": str((last[0] - first[0]).total_seconds()),
                }
            rows.append(
                {
                    "instrument": instrument.model_dump(mode="json"),
                    "quote": quote.model_dump(mode="json") if quote else None,
                    "problem": problem,
                    "observed_trend": trend,
                }
            )
        aggregates = []
        for underlying, expiry in sorted(
            {(item.underlying, str(item.expiry)) for item in instruments}
        ):
            group = [
                row
                for row in rows
                if row["instrument"]["underlying"] == underlying
                and row["instrument"]["expiry"] == expiry
            ]
            complete = bool(group) and all(
                row["problem"] is None and row["quote"]["oi"] is not None for row in group
            )
            calls = [row for row in group if row["instrument"]["option_type"] == "CALL"]
            puts = [row for row in group if row["instrument"]["option_type"] == "PUT"]
            call_oi = sum(row["quote"]["oi"] for row in calls) if complete else None
            put_oi = sum(row["quote"]["oi"] for row in puts) if complete else None
            pcr = (
                str(Decimal(put_oi) / Decimal(call_oi))
                if calls and puts and call_oi and put_oi is not None
                else None
            )
            aggregates.append(
                {
                    "underlying": underlying,
                    "expiry": expiry,
                    "selected_contracts_pcr": pcr,
                    "oi_complete": complete,
                }
            )
        return {
            "timestamp": now.isoformat(),
            "observation_rejections": dict(self.cache.rejected),
            "coverage": "selected_contracts_only",
            "contract_count": len(rows),
            "groups": aggregates,
            "greeks_problems": dict(self.problems),
            "rows": rows,
        }


def provider_time_expiry(value: str | None):
    if not value:
        raise ValueError("Provider expiry is missing")
    return datetime.strptime(value, "%d%b%Y").date()
