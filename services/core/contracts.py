"""Provider-independent contracts. Decimal strings are the JSON money representation."""

from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

IST = ZoneInfo("Asia/Kolkata")
ZERO = Decimal("0")
Price = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
NonnegativeInt = Annotated[int, Field(ge=0, strict=True)]


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    schema_version: Literal[1] = 1


class Instrument(Contract):
    id: str = Field(min_length=1, max_length=100)
    provider_token: str = Field(min_length=1)
    exchange: str = Field(min_length=1)
    underlying: Literal["NIFTY", "SENSEX"]
    expiry: date
    strike: Price
    option_type: Literal["CALL", "PUT"]
    lot_size: PositiveInt
    tick_size: Price
    metadata_source: str = Field(min_length=1)
    verified_at: AwareDatetime


class DepthLevel(Contract):
    price: Price
    quantity: PositiveInt
    orders: NonnegativeInt | None = None


class Quote(Contract):
    id: UUID = Field(default_factory=uuid4)
    instrument_id: str
    timestamp: AwareDatetime
    received_at: AwareDatetime
    source: str = Field(min_length=1)
    # Provider observation identity survives later Greek enrichment and local receipt retries.
    market_event_id: str | None = None
    sequence: NonnegativeInt | None = None
    stream_id: UUID | None = None
    timestamp_basis: Literal["exchange_feed", "unknown"] = "unknown"
    bid_depth: tuple[DepthLevel, ...] = ()
    ask_depth: tuple[DepthLevel, ...] = ()
    depth_kind: Literal["best_five", "unavailable"] = "unavailable"
    quantity_unit: Literal["units", "lots", "unknown"] = "unknown"
    quantity_unit_source: str | None = None
    bid: Price | None = None
    ask: Price | None = None
    bid_quantity: NonnegativeInt | None = None
    ask_quantity: NonnegativeInt | None = None
    # Display/analysis observations only; execution still uses retained bid/ask depth.
    last_price: Price | None = None
    session_open: Price | None = None
    session_high: Price | None = None
    session_low: Price | None = None
    previous_close: Price | None = None
    average_price: Price | None = None
    last_trade_at: AwareDatetime | None = None
    last_trade_quantity: NonnegativeInt | None = None
    volume: NonnegativeInt | None = None
    oi: NonnegativeInt | None = None
    iv: Annotated[Decimal, Field(ge=0)] | None = None
    greeks: dict[str, Decimal] | None = None
    metrics_timestamp: AwareDatetime | None = None
    metrics_received_at: AwareDatetime | None = None
    metrics_source: str | None = None
    iv_unit: Literal["percent"] | None = None

    @model_validator(mode="after")
    def valid_depth(self) -> Self:
        for levels, best, size, descending in (
            (self.bid_depth, self.bid, self.bid_quantity, True),
            (self.ask_depth, self.ask, self.ask_quantity, False),
        ):
            prices = [level.price for level in levels]
            if len(prices) > 5 or len(set(prices)) != len(prices):
                raise ValueError("Depth must contain at most five distinct price levels")
            if prices != sorted(prices, reverse=descending):
                raise ValueError("Depth must be sorted best price first")
            if levels and (best != levels[0].price or size != levels[0].quantity):
                raise ValueError("Best quote must match retained depth")
        if (self.bid_depth or self.ask_depth) and self.depth_kind == "unavailable":
            raise ValueError("Retained depth requires a declared depth kind")
        if self.quantity_unit != "unknown" and not self.quantity_unit_source:
            raise ValueError("Quantity unit requires verification provenance")
        return self


class UnderlyingExitPolicy(Contract):
    underlying: Literal["NIFTY", "SENSEX"]
    direction: Literal["BULLISH", "BEARISH"]
    invalidation: Price
    target: Price
    premium_stop_fraction: Annotated[Decimal, Field(gt=0, lt=1)] | None = None
    entry_lower: Price | None = None
    entry_upper: Price | None = None
    entry_deadline_only: bool = False

    def premium_stop(self, average_price: Decimal, tick_size: Decimal) -> Decimal:
        if self.premium_stop_fraction is None:
            raise ValueError("No fill-relative premium stop configured")
        return (average_price * (1 - self.premium_stop_fraction) / tick_size).to_integral_value(
            rounding=ROUND_CEILING
        ) * tick_size

    @model_validator(mode="after")
    def valid_levels(self) -> Self:
        if (self.entry_lower is None) != (self.entry_upper is None):
            raise ValueError("Underlying entry bounds must be supplied together")
        if self.entry_lower is not None and self.entry_upper is not None:
            if self.entry_lower >= self.entry_upper:
                raise ValueError("Underlying entry bounds must be ordered")
        if self.direction == "BULLISH" and self.invalidation >= self.target:
            raise ValueError("Bullish invalidation must be below target")
        if self.direction == "BEARISH" and self.invalidation <= self.target:
            raise ValueError("Bearish invalidation must be above target")
        return self


class ExchangeSession(Contract):
    key: date
    opens_at: AwareDatetime
    closes_at: AwareDatetime
    calendar_source: str = Field(min_length=1)
    verified: bool

    @model_validator(mode="after")
    def valid_window(self) -> Self:
        if self.opens_at >= self.closes_at:
            raise ValueError("Session close must follow open")
        if any(t.astimezone(IST).date() != self.key for t in (self.opens_at, self.closes_at)):
            raise ValueError("Session key must match its local exchange date")
        return self


class CostModel(Contract):
    version: str = Field(min_length=1)
    label: str = Field(min_length=1)
    flat_per_fill: Money
    turnover_rate: Annotated[Decimal, Field(ge=0, le=1)]
    slippage_bps: Annotated[Decimal, Field(ge=0, le=1000)]

    def fees(self, price: Decimal, quantity: int) -> dict[str, Decimal]:
        return {
            "flat": self.flat_per_fill,
            "turnover": money(money(price * quantity) * self.turnover_rate),
        }

    def price(self, quote_price: Decimal, tick: Decimal, side: str) -> Decimal:
        adjustment = self.slippage_bps / Decimal(10000)
        value = quote_price * (1 + adjustment if side == "BUY" else 1 - adjustment)
        rounding = ROUND_CEILING if side == "BUY" else ROUND_FLOOR
        return (value / tick).to_integral_value(rounding=rounding) * tick


class RiskConfig(Contract):
    version: str = Field(min_length=1)
    capital: Money = Decimal("100000")
    max_trade_risk_pct: Annotated[Decimal, Field(gt=0, le=1)] = Decimal("0.005")
    max_daily_loss_pct: Annotated[Decimal, Field(gt=0, le=1)] = Decimal("0.02")
    max_positions: PositiveInt = 1
    quote_max_age_seconds: Annotated[int, Field(ge=1, le=10, strict=True)] = 2
    entry_cutoff_minutes: PositiveInt = 20
    flatten_minutes: PositiveInt = 10
    max_holding_seconds: PositiveInt = 300
    max_spread_bps: Annotated[Decimal, Field(gt=0, le=10000)]
    min_volume: NonnegativeInt
    min_oi: NonnegativeInt
    max_fill_quantity: PositiveInt
    # Legacy immediate-fill costs are not needed by the durable fee-schedule engine.
    costs: CostModel | None = None

    @model_validator(mode="after")
    def valid_limits(self) -> Self:
        if self.capital <= 0 or self.entry_cutoff_minutes <= self.flatten_minutes:
            raise ValueError("Positive capital and entry cutoff before flatten time required")
        if self.max_trade_risk_pct > self.max_daily_loss_pct:
            raise ValueError("Trade risk must not exceed the daily limit")
        return self


class StrategyEnvelope(Contract):
    id: UUID = Field(default_factory=uuid4)
    version: str = Field(min_length=1)
    instrument_ids: tuple[str, ...] = Field(min_length=1)
    action: Literal["BUY_CALL", "BUY_PUT"]
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    min_entry: Price
    max_entry: Price
    stop_loss: Price
    target: Price | None
    max_holding_seconds: PositiveInt = 300
    underlying_exit_policy: UnderlyingExitPolicy | None = None
    required_metrics: tuple[Literal["oi", "volume", "iv", "greeks"], ...] = ("oi", "volume")
    invalidated: bool = False

    @model_validator(mode="after")
    def valid_envelope(self) -> Self:
        if not self.stop_loss < self.min_entry <= self.max_entry:
            raise ValueError("Envelope must satisfy stop < entry range < target")
        if self.target is None:
            if self.underlying_exit_policy is None:
                raise ValueError("Missing premium target requires an underlying exit policy")
        elif self.max_entry >= self.target:
            raise ValueError("Envelope must satisfy stop < entry range < target")
        if not timedelta(0) < self.expires_at - self.issued_at <= timedelta(seconds=180):
            raise ValueError("Envelope lifetime must be positive and no longer than 180 seconds")
        return self


class TradeDecision(Contract):
    id: UUID = Field(default_factory=uuid4)
    action: Literal["BUY_CALL", "BUY_PUT", "WAIT"]
    timestamp: AwareDatetime
    expires_at: AwareDatetime
    rationale: str = Field(min_length=1, max_length=5000)
    snapshot_ids: tuple[UUID, ...] = ()
    instrument_id: str | None = None
    entry: Price | None = None
    stop_loss: Price | None = None
    target: Price | None = None
    strategy_id: UUID | None = None

    @model_validator(mode="after")
    def valid_proposal(self) -> Self:
        fields = (self.instrument_id, self.entry, self.stop_loss, self.strategy_id)
        if self.expires_at <= self.timestamp:
            raise ValueError("Decision must have a positive lifetime")
        if self.action == "WAIT":
            if any(field is not None for field in (*fields, self.target)):
                raise ValueError("WAIT cannot contain execution fields")
        else:
            if any(field is None for field in fields) or not self.snapshot_ids:
                raise ValueError(
                    "Entry proposals require instrument, prices, strategy and evidence"
                )
            if not self.stop_loss < self.entry:  # type: ignore[operator]
                raise ValueError("Long option proposal must satisfy stop < entry < target")
            if self.target is not None and self.entry >= self.target:  # type: ignore[operator]
                raise ValueError("Long option proposal must satisfy stop < entry < target")
        return self
