"""Versioned paper execution policy and fee contracts; no implicit fee defaults."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from services.core.contracts import Contract, Money

FeeCode = Literal[
    "BROKERAGE", "EXCHANGE", "STT", "SEBI", "STAMP", "GST", "IPFT", "CLEARING", "OTHER"
]
REQUIRED_FEE_CODES = {"BROKERAGE", "EXCHANGE", "STT", "SEBI", "STAMP", "GST", "IPFT", "CLEARING"}


class SourceEvidence(Contract):
    url: HttpUrl
    checked_at: AwareDatetime
    finding: str = Field(min_length=1, max_length=2000)
    status: Literal["documented", "account_verified", "unverified"]


class FeeRule(Contract):
    code: FeeCode
    sides: tuple[Literal["BUY", "SELL"], ...] = Field(min_length=1)
    calculation: Literal["flat_per_order", "premium_rate", "charge_rate"]
    amount: Money | None = None
    rate: Annotated[Decimal, Field(ge=0, le=1)] | None = None
    charge_basis: tuple[FeeCode, ...] = ()
    cap_per_order: Money | None = None
    rounding_increment: Annotated[Decimal, Field(gt=0, le=1)]
    rounding_mode: Literal["HALF_UP", "CEILING", "FLOOR"]
    # Future accounting must accrue per fill, then reconcile at the declared scope.
    rounding_scope: Literal["cumulative_order", "session_contract_note"]
    sources: tuple[SourceEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_formula(self) -> Self:
        if self.rounding_increment < Decimal("0.01") or self.rounding_increment % Decimal("0.01"):
            raise ValueError("INR ledger rounding must be in whole paise")
        if len(set(self.sides)) != len(self.sides):
            raise ValueError("Duplicate fee sides")
        if self.calculation == "flat_per_order":
            if self.amount is None or self.rate is not None or self.charge_basis:
                raise ValueError("Flat fee needs amount only")
        elif self.rate is None or self.amount is not None:
            raise ValueError("Rate fee needs rate only")
        if self.calculation == "charge_rate":
            if not self.charge_basis or self.code in self.charge_basis:
                raise ValueError("Charge-based fee needs distinct upstream charge codes")
        elif self.charge_basis:
            raise ValueError("Only charge-rate fees have charge dependencies")
        if len(set(self.charge_basis)) != len(self.charge_basis):
            raise ValueError("Duplicate charge dependencies")
        return self


class FeeSchedule(Contract):
    version: str = Field(min_length=1)
    exchange: Literal["NFO", "BFO"]
    product: Literal["LONG_OPTION_INTRADAY"] = "LONG_OPTION_INTRADAY"
    effective_from: date
    effective_until: date | None = None  # Inclusive; missing end is open-ended.
    reviewed: bool = False
    account_pricing_verified: bool = False
    rules: tuple[FeeRule, ...] = Field(min_length=1)
    notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_schedule(self) -> Self:
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("Fee effective window is reversed")
        codes: set[str] = set()
        for rule in self.rules:
            if rule.code in codes or not set(rule.charge_basis) <= codes:
                raise ValueError("Unique fee codes and earlier declared dependencies required")
            codes.add(rule.code)
        if self.reviewed:
            if not REQUIRED_FEE_CODES <= codes or not self.account_pricing_verified:
                raise ValueError("Reviewed fees require all components and account pricing")
            if any(s.status == "unverified" for rule in self.rules for s in rule.sources):
                raise ValueError("Reviewed fees cannot contain unverified evidence")
        return self

    def applies(self, day: date) -> bool:
        return self.effective_from <= day and (
            self.effective_until is None or day <= self.effective_until
        )

    def blockers(self) -> list[str]:
        """Expose what a draft still lacks instead of just saying 'not reviewed'."""
        problems = []
        if not self.reviewed:
            problems.append(self.exchange + "_FEE_SCHEDULE_NOT_REVIEWED")
        if not self.account_pricing_verified:
            problems.append(self.exchange + "_ACCOUNT_PRICING_UNVERIFIED")
        codes = {rule.code for rule in self.rules}
        problems.extend(
            self.exchange + "_FEE_COMPONENT_" + code + "_MISSING"
            for code in sorted(REQUIRED_FEE_CODES - codes)
        )
        if any(s.status == "unverified" for rule in self.rules for s in rule.sources):
            problems.append(self.exchange + "_FEE_EVIDENCE_UNVERIFIED")
        return problems


class ExecutionPolicy(Contract):
    version: str = Field(min_length=1)
    reviewed: bool = False
    # None means undecided, never zero latency or unlimited liquidity.
    assumed_latency_ms: Annotated[int, Field(ge=0, le=60000, strict=True)] | None = None
    displayed_participation: Annotated[Decimal, Field(gt=0, le=1)] | None = None
    extra_adverse_slippage_bps: Annotated[Decimal, Field(ge=0, le=1000)] | None = None
    market_protection_bps: Annotated[Decimal, Field(gt=0, le=1000)] | None = None
    quote_max_age_ms: Annotated[int, Field(gt=0, le=10000, strict=True)] | None = None
    pending_entry_lifetime_ms: Annotated[int, Field(gt=0, le=180000, strict=True)] | None = None
    quantity_unit: Literal["units", "lots", "unknown"] = "unknown"
    quantity_unit_sources: tuple[SourceEvidence, ...] = ()
    # An assumption to resolve before future fills, not a broker capability claim.
    partial_fill_granularity: Literal["units", "lots"] | None = None
    sale_proceeds_reuse: Literal["block_until_verified", "same_session_verified"] = (
        "block_until_verified"
    )
    sale_proceeds_sources: tuple[SourceEvidence, ...] = ()
    notes: str = Field(min_length=1)

    def blockers(self) -> list[str]:
        problems = []
        if not self.reviewed:
            problems.append("EXECUTION_POLICY_NOT_REVIEWED")
        for name in (
            "assumed_latency_ms",
            "displayed_participation",
            "extra_adverse_slippage_bps",
            "market_protection_bps",
            "quote_max_age_ms",
            "pending_entry_lifetime_ms",
            "partial_fill_granularity",
        ):
            if getattr(self, name) is None:
                problems.append(name.upper() + "_REQUIRED")
        if (
            self.quantity_unit == "unknown"
            or not self.quantity_unit_sources
            or any(s.status == "unverified" for s in self.quantity_unit_sources)
        ):
            problems.append("QUANTITY_UNIT_UNVERIFIED")
        if self.sale_proceeds_reuse == "same_session_verified" and (
            not self.sale_proceeds_sources
            or any(s.status == "unverified" for s in self.sale_proceeds_sources)
        ):
            problems.append("SALE_PROCEEDS_REUSE_UNVERIFIED")
        return problems


class PaperExecutionConfig(Contract):
    version: str = Field(min_length=1)
    execution: ExecutionPolicy
    fee_schedules: tuple[FeeSchedule, ...] = ()

    @model_validator(mode="after")
    def unique_schedules(self) -> Self:
        for index, schedule in enumerate(self.fee_schedules):
            for other in self.fee_schedules[index + 1 :]:
                if schedule.version == other.version:
                    raise ValueError("Fee schedule versions must be unique")
                if (
                    schedule.exchange == other.exchange
                    and (
                        schedule.effective_until is None
                        or other.effective_from <= schedule.effective_until
                    )
                    and (
                        other.effective_until is None
                        or schedule.effective_from <= other.effective_until
                    )
                ):
                    raise ValueError("Fee schedule effective windows overlap")
        return self

    def blockers(self, day: date) -> list[str]:
        problems = self.execution.blockers()
        for exchange in ("NFO", "BFO"):
            matching = [s for s in self.fee_schedules if s.exchange == exchange and s.applies(day)]
            if not matching:
                problems.append(exchange + "_FEE_SCHEDULE_MISSING")
            else:
                problems.extend(matching[0].blockers())
        return problems
