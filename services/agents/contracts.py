from typing import Literal

from pydantic import BaseModel, ConfigDict


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Analysis(Output):
    outlook: Literal["BULLISH", "BEARISH", "UNCERTAIN"]
    rationale: str
    evidence_ids: list[str]
    news_ids: list[str]
    concerns: list[str]


class Proposal(Output):
    action: Literal["BUY_CALL", "BUY_PUT", "WAIT"]
    instrument_id: str | None
    min_entry: str | None
    max_entry: str | None
    stop_loss: str | None
    target: str | None
    rationale: str
    evidence_ids: list[str]


class Review(Output):
    approved: bool
    rationale: str
    evidence_ids: list[str]
