"""Internal requests from deterministic risk/matching layers, never agent tool inputs."""

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from services.core.contracts import Contract, Money, NonnegativeInt, PositiveInt, Price


class ManualEntryIntent(Contract):
    id: UUID
    plan_id: UUID
    instrument_id: str = Field(min_length=1, max_length=100)
    quantity: PositiveInt
    entry_limit: Price
    stop_loss: Price
    target: Price
    max_holding_seconds: PositiveInt
    submitted_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def valid_intent(self) -> Self:
        if not self.stop_loss < self.entry_limit < self.target:
            raise ValueError("Stop must be below limit and target above it")
        if self.expires_at <= self.submitted_at:
            raise ValueError("Intent expiry must follow submission")
        return self


class OrderRiskApproval(Contract):
    quantity: PositiveInt
    cash_budget: Money
    risk_budget: Money
    account_revision: NonnegativeInt
    risk_config_version: str = Field(min_length=1)
    execution_config_version: str = Field(min_length=1)
    expires_at: AwareDatetime
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    net_liquidation_equity: Money | None = None
    entry_limit: Price | None = None


class OrderRequest(Contract):
    idempotency_key: str = Field(min_length=1, max_length=200)
    instrument_id: str = Field(min_length=1)
    side: Literal["BUY", "SELL"]
    quantity: PositiveInt
    order_type: Literal["MARKET", "LIMIT", "STOP_MARKET", "STOP_LIMIT"] = "MARKET"
    time_in_force: Literal["DAY", "IOC"] = "DAY"
    limit_price: Price | None = None
    trigger_price: Price | None = None
    submitted_at: AwareDatetime
    expires_at: AwareDatetime
    decision_id: UUID | None = None
    manual_intent_id: UUID | None = None
    position_id: UUID | None = None
    cash_budget: Money
    risk_budget: Money
    reason: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def valid_order(self) -> Self:
        if self.expires_at <= self.submitted_at:
            raise ValueError("Order expiry must follow submission")
        if (self.order_type in {"LIMIT", "STOP_LIMIT"}) != (self.limit_price is not None):
            raise ValueError("Limit price required only for limit orders")
        if (self.order_type in {"STOP_MARKET", "STOP_LIMIT"}) != (self.trigger_price is not None):
            raise ValueError("Trigger price required only for stop orders")
        if self.side == "BUY":
            if (
                (self.decision_id is None) == (self.manual_intent_id is None)
                or self.position_id
                or not self.cash_budget
                or not self.risk_budget
            ):
                raise ValueError(
                    "Entry requires exactly one approved source and positive cash/risk budgets"
                )
        elif (
            not self.position_id
            or self.decision_id
            or self.manual_intent_id
            or self.cash_budget
            or self.risk_budget
        ):
            raise ValueError("Exit requires held position and zero entry budgets")
        return self


class FillBooking(Contract):
    event_key: str = Field(min_length=1, max_length=200)
    snapshot_id: UUID
    market_event_id: str = Field(min_length=1)
    quantity: PositiveInt
    price: Price
    raw_price: Price
    fees: Money
    fee_breakdown: dict[str, Money] = Field(min_length=1)
    cost_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def fee_total_matches(self) -> Self:
        if sum(self.fee_breakdown.values()) != self.fees:
            raise ValueError("Fill fees must equal itemized components")
        return self
