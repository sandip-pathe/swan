"""Versioned advisory records. None of these contracts authorize an order."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Idea(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal[2] = 2
    id: str
    revision: int = Field(default=1, ge=1)
    kind: Literal["idea"] = "idea"
    underlying: Literal["SENSEX"] = "SENSEX"
    horizon: Literal["intraday", "weekly"]
    strategy: str
    direction: Literal["CALL", "PUT"]
    state: Literal["watch", "trigger_pending", "eligible", "suspended", "invalidated", "expired"]
    as_of: AwareDatetime
    published_at: AwareDatetime
    expires_at: AwareDatetime
    title: str
    summary: str
    limitation: str = "Experimental research, not a proven edge. You decide and place all orders."
    trigger: str
    invalidation: str
    trigger_level: Decimal = Field(gt=0)
    invalidation_level: Decimal = Field(gt=0)
    target_level: Decimal = Field(gt=0)
    reasons: list[str] = Field(default_factory=list, max_length=30)
    evidence_ids: list[str] = Field(max_length=100)
    facts: dict
    contract: dict | None = None
    economics: dict | None = None
    research: dict | None = None
    rank: int = 0
    experimental: Literal[True] = True

    @model_validator(mode="after")
    def levels(self):
        if (
            self.direction == "CALL"
            and not self.invalidation_level < self.trigger_level < self.target_level
        ):
            raise ValueError("CALL_LEVELS_INVALID")
        if (
            self.direction == "PUT"
            and not self.target_level < self.trigger_level < self.invalidation_level
        ):
            raise ValueError("PUT_LEVELS_INVALID")
        if self.expires_at <= self.as_of:
            if self.state not in {"expired", "invalidated"}:
                raise ValueError("IDEA_ALREADY_EXPIRED")
        return self


class Research(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thesis: str = Field(min_length=1, max_length=1800)
    counterargument: str = Field(min_length=1, max_length=1200)
    next_observation: str = Field(min_length=1, max_length=800)
    evidence_ids: list[str] = Field(min_length=1, max_length=40)
    abstain: bool


class ReportedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    expected_revision: int = Field(ge=1)
    premium: Decimal = Field(gt=0, le=1000000, max_digits=12, decimal_places=4)
    quantity: int = Field(gt=0, le=100000, strict=True)
    entered_at: AwareDatetime


def active(idea: dict, now: datetime) -> bool:
    return (
        idea.get("kind") == "idea"
        and idea["state"] not in {"invalidated", "expired"}
        and datetime.fromisoformat(idea["expires_at"]) > now
    )


class ConversationAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=5000)
    evidence_ids: list[str] = Field(max_length=40)
