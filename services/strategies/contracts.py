"""Typed, immutable contracts for deterministic strategy evidence."""

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from services.core.contracts import Contract


class IndexBar(Contract):
    evidence_id: str = Field(min_length=1, max_length=200)
    underlying: str = Field(min_length=1, max_length=20)
    exchange: str = Field(min_length=1, max_length=10)
    source: str = Field(min_length=1, max_length=200)
    opens_at: AwareDatetime
    closes_at: AwareDatetime
    available_at: AwareDatetime
    final: bool
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    @model_validator(mode="after")
    def valid_bar(self):
        vals = (self.open, self.high, self.low, self.close)
        if any(not value.is_finite() or value <= 0 for value in vals):
            raise ValueError("OHLC values must be finite and positive")
        if not (self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high):
            raise ValueError("OHLC values are not ordered")
        if self.opens_at >= self.closes_at:
            raise ValueError("Bar close must follow its open")
        if (self.opens_at.second or self.opens_at.microsecond
                or self.closes_at - self.opens_at != timedelta(minutes=1)):
            raise ValueError("Bars must span one minute from a minute boundary")
        if self.final and self.available_at < self.closes_at:
            raise ValueError("A final bar cannot be available before it closes")
        return self


class ORBSnapshot(Contract):
    snapshot_id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=200)
    underlying: str = Field(min_length=1, max_length=20)
    exchange: str = Field(min_length=1, max_length=10)
    as_of: AwareDatetime
    bars: tuple[IndexBar, ...] = Field(max_length=400)


class ORBDefinition(Contract):
    strategy_id: Literal["S01-NIFTY-ORB"] = "S01-NIFTY-ORB"
    version: Literal["0.1-setup"] = "0.1-setup"
    opening_minutes: int = 15
    buffer_fraction: Decimal = Decimal("0.05")
    extension_fraction: Decimal = Decimal("0.25")
    cutoff_hour: int = 11
    cutoff_minute: int = 0


class ORBAssessment(Contract):
    strategy_id: str
    version: str
    definition_fingerprint: str
    snapshot_id: str
    as_of: AwareDatetime
    session_key: str
    status: Literal[
        "NOT_READY", "UNAVAILABLE", "NOT_APPLICABLE", "NO_SETUP",
        "BULLISH_SETUP", "BEARISH_SETUP", "EXPIRED",
    ]
    reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()
    excluded_bar_ids: tuple[str, ...] = ()
    missing_intervals: tuple[tuple[AwareDatetime, AwareDatetime], ...] = ()
    range_high: Decimal | None = None
    range_low: Decimal | None = None
    range_width: Decimal | None = None
    buffer: Decimal | None = None
    trigger_evidence_id: str | None = None
    trigger_closes_at: AwareDatetime | None = None
    trigger_close: Decimal | None = None
    invalidation: Decimal | None = None
    target: Decimal | None = None
    expires_at: AwareDatetime | None = None
    rejected_candidates: tuple[tuple[AwareDatetime, str], ...] = ()


class StrategyPlanDraft(Contract):
    """Research-only plan derived from an assessment; never an order instruction."""

    plan_id: str = Field(min_length=64, max_length=64)
    assessment_id: str = Field(min_length=64, max_length=64)
    snapshot_id: str
    strategy_id: str
    version: str
    definition_fingerprint: str = Field(min_length=64, max_length=64)
    session_key: str
    as_of: AwareDatetime
    outcome: Literal["FIT", "DOES_NOT_FIT", "INSUFFICIENT_DATA", "OUT_OF_SCOPE"]
    reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    option_underlying: Literal["NIFTY"] = "NIFTY"
    option_exchange: Literal["NFO"] = "NFO"
    option_type: Literal["CALL", "PUT"] | None = None
    expiry_policy: Literal["NEXT_LISTED_EXPIRY_AFTER_SESSION"] = "NEXT_LISTED_EXPIRY_AFTER_SESSION"
    strike_policy: Literal["CLOSEST_ATM_LOWER_STRIKE_TIE"] = "CLOSEST_ATM_LOWER_STRIKE_TIE"
    contract_fallback: Literal["SKIP_IF_SELECTED_CONTRACT_INELIGIBLE"] = (
        "SKIP_IF_SELECTED_CONTRACT_INELIGIBLE"
    )
    maximum_expiry_days: int = Field(default=7, ge=1, le=7)
    maximum_holding_seconds: int = Field(default=300, ge=1, le=300)
    maximum_entry_attempts_per_session: Literal[1] = 1
    entry_limit_policy: Literal["OBSERVED_ASK_NO_CHASE"] = "OBSERVED_ASK_NO_CHASE"
    sizing_policy: Literal["CURRENT_ACCOUNT_RISK_POLICY_REQUIRED"] = (
        "CURRENT_ACCOUNT_RISK_POLICY_REQUIRED"
    )
    direction: Literal["BULLISH", "BEARISH"] | None = None
    trigger_operator: Literal["GT", "LT"] | None = None
    trigger_threshold: Decimal | None = None
    trigger_ceiling_or_floor: Decimal | None = None
    invalidation: Decimal | None = None
    target: Decimal | None = None
    valid_until: AwareDatetime | None = None
    execution_eligible: Literal[False] = False
    mandate_state: Literal["PENDING_REVIEW"] = "PENDING_REVIEW"
    unresolved_policy: tuple[str, ...] = (
        "CURRENT_ACCOUNT_RISK_REVIEW", "LIVE_OPTION_CONTRACT_AND_QUOTE_EVIDENCE",
        "PREMIUM_EXIT_AND_FEES_REVIEW",
    )


class ORBPaperMandate(Contract):
    """Frozen candidate paper behavior, separate from the original setup draft."""

    mandate_id: Literal["S01-NIFTY-ORB-PAPER"] = "S01-NIFTY-ORB-PAPER"
    version: Literal["0.1-candidate"] = "0.1-candidate"
    expiry_policy: Literal["FIRST_LISTED_STRICTLY_AFTER_SESSION_DATE"] = (
        "FIRST_LISTED_STRICTLY_AFTER_SESSION_DATE"
    )
    maximum_expiry_days: Literal[7] = 7
    strike_policy: Literal["CLOSEST_TO_FRESH_UNDERLYING_LOWER_TIE"] = (
        "CLOSEST_TO_FRESH_UNDERLYING_LOWER_TIE"
    )
    contract_fallback: Literal["SKIP_IF_SELECTED_CONTRACT_INELIGIBLE"] = (
        "SKIP_IF_SELECTED_CONTRACT_INELIGIBLE"
    )
    maximum_entry_attempts_per_session: Literal[1] = 1
    opportunity_lifetime_seconds: Literal[60] = 60
    entry_order_type: Literal["BUY_LIMIT"] = "BUY_LIMIT"
    entry_limit_policy: Literal["CAPTURED_QUALIFYING_ASK_NO_CHASE"] = (
        "CAPTURED_QUALIFYING_ASK_NO_CHASE"
    )
    unfilled_order_policy: Literal["CANCEL_REMAINDER_AT_OPPORTUNITY_DEADLINE"] = (
        "CANCEL_REMAINDER_AT_OPPORTUNITY_DEADLINE"
    )
    partial_fill_policy: Literal["CANCEL_REMAINDER_AND_PROTECT_FILLED_QUANTITY"] = (
        "CANCEL_REMAINDER_AND_PROTECT_FILLED_QUANTITY"
    )
    unresolved_order_policy: Literal["RECONCILE_BEFORE_ANY_RETRY_OR_NEW_ENTRY"] = (
        "RECONCILE_BEFORE_ANY_RETRY_OR_NEW_ENTRY"
    )
    premium_stop_fraction: Decimal = Decimal("0.20")
    premium_stop_reference: Literal["AVERAGE_ACTUAL_ENTRY_FILL"] = (
        "AVERAGE_ACTUAL_ENTRY_FILL"
    )
    maximum_holding_seconds: Literal[300] = 300
    mandatory_exit_policy: Literal["CURRENT_ACCOUNT_FLATTEN_CUTOFF"] = (
        "CURRENT_ACCOUNT_FLATTEN_CUTOFF"
    )
    exit_priority_policy: Literal["PROTECTIVE_AND_MANDATORY_EXITS_BEFORE_TARGET"] = (
        "PROTECTIVE_AND_MANDATORY_EXITS_BEFORE_TARGET"
    )
    missing_exit_quote_policy: Literal["KEEP_EXPOSURE_UNRESOLVED_NO_FICTIONAL_FILL"] = (
        "KEEP_EXPOSURE_UNRESOLVED_NO_FICTIONAL_FILL"
    )
    sizing_policy: Literal["CURRENT_ACCOUNT_RISK_AND_QUALIFICATION_REQUIRED"] = (
        "CURRENT_ACCOUNT_RISK_AND_QUALIFICATION_REQUIRED"
    )
    fee_policy: Literal["CURRENT_REVIEWED_NFO_FEE_SCHEDULE_REQUIRED"] = (
        "CURRENT_REVIEWED_NFO_FEE_SCHEDULE_REQUIRED"
    )
    loss_scenario_policy: Literal["FULL_PREMIUM_PLUS_FEES_RECORDED"] = (
        "FULL_PREMIUM_PLUS_FEES_RECORDED"
    )

    @model_validator(mode="after")
    def frozen_experimental_stop(self):
        if self.premium_stop_fraction != Decimal("0.20"):
            raise ValueError("This candidate mandate freezes the experimental stop at 20 percent")
        return self


class StrategyPaperPlanCandidate(Contract):
    """Versioned, review-linked paper candidate that remains blocked from execution."""

    candidate_id: str = Field(min_length=64, max_length=64)
    candidate_version: Literal["0.1-candidate"] = "0.1-candidate"
    source_plan: StrategyPlanDraft
    mandate: ORBPaperMandate = Field(default_factory=ORBPaperMandate)
    mandate_fingerprint: str = Field(min_length=64, max_length=64)
    review_assignment_id: UUID
    review_artifact_id: UUID
    reviewed_at: AwareDatetime
    status: Literal["BLOCKED"] = "BLOCKED"
    blocker_codes: tuple[
        Literal[
            "CURRENT_ACCOUNT_RISK_CONFIGURATION_REQUIRED",
            "CURRENT_PAPER_QUALIFICATION_REQUIRED",
            "FRESH_UNDERLYING_REVALIDATION_AND_EXIT_MONITOR_REQUIRED",
            "REVIEWED_NFO_FEE_SCHEDULE_REQUIRED",
            "SELECTED_OPTION_CONTRACT_REQUIRED",
            "FRESH_EXECUTABLE_OPTION_QUOTE_AND_DEPTH_REQUIRED",
        ], ...
    ]
    selected_instrument_id: str | None = None
    selected_expiry: date | None = None
    selected_strike: Decimal | None = None
    selected_lot_size: int | None = None
    selected_tick_size: Decimal | None = None
    entry_quote_id: UUID | None = None
    entry_quote_as_of: AwareDatetime | None = None
    captured_entry_ask: Decimal | None = None
    account_risk_config_version: str | None = None
    fee_schedule_version: str | None = None
    paper_qualification_id: UUID | None = None
    execution_eligible: Literal[False] = False

    @model_validator(mode="after")
    def candidate_stays_blocked(self):
        mandate_payload = self.mandate.model_dump(mode="json")
        expected_fingerprint = hashlib.sha256(
            json.dumps(mandate_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if self.mandate_fingerprint != expected_fingerprint:
            raise ValueError("Candidate mandate fingerprint mismatch")
        identity = {
            "candidate_version": self.candidate_version,
            "source_plan_id": self.source_plan.plan_id,
            "review_assignment_id": str(self.review_assignment_id),
            "review_artifact_id": str(self.review_artifact_id),
            "mandate_fingerprint": expected_fingerprint,
        }
        expected_candidate_id = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if self.candidate_id != expected_candidate_id:
            raise ValueError("Candidate identity mismatch")
        if self.source_plan.outcome != "FIT":
            raise ValueError("Only a fitting reviewed plan can become a paper candidate")
        if self.source_plan.execution_eligible or self.source_plan.mandate_state != "PENDING_REVIEW":
            raise ValueError("Research drafts cannot grant paper execution eligibility")
        if set(self.blocker_codes) != {
            "CURRENT_ACCOUNT_RISK_CONFIGURATION_REQUIRED",
            "CURRENT_PAPER_QUALIFICATION_REQUIRED",
            "FRESH_UNDERLYING_REVALIDATION_AND_EXIT_MONITOR_REQUIRED",
            "REVIEWED_NFO_FEE_SCHEDULE_REQUIRED",
            "SELECTED_OPTION_CONTRACT_REQUIRED",
            "FRESH_EXECUTABLE_OPTION_QUOTE_AND_DEPTH_REQUIRED",
        }:
            raise ValueError("Paper candidate must retain every explicit admission blocker")
        if any((
            self.selected_instrument_id,
            self.selected_expiry,
            self.selected_strike,
            self.selected_lot_size,
            self.selected_tick_size,
            self.entry_quote_id,
            self.entry_quote_as_of,
            self.captured_entry_ask,
            self.account_risk_config_version,
            self.fee_schedule_version,
            self.paper_qualification_id,
        )):
            raise ValueError("Contract and quote evidence must be added through a later reviewed admission")
        return self


class StrategyResearchCandidate(Contract):
    """Immutable, inactive hypothesis. It cannot change an executable strategy."""

    candidate_id: str = Field(min_length=64, max_length=64)
    strategy_id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    parent_version: str | None = Field(default=None, max_length=100)
    hypothesis: str = Field(min_length=1, max_length=2000)
    scope: str = Field(min_length=1, max_length=1000)
    evidence_ids: tuple[str, ...] = Field(max_length=100)
    assumptions: tuple[str, ...] = Field(max_length=50)
    evaluation_method: str = Field(min_length=1, max_length=2000)
    status: Literal["INACTIVE_RESEARCH"] = "INACTIVE_RESEARCH"
