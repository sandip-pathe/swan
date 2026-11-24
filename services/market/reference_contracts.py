"""Provider-neutral contracts for timestamped index observations."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class IndexReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    underlying: Literal["NIFTY", "SENSEX"]
    exchange: Literal["NSE", "BSE"]
    provider_token: str
    timestamp: AwareDatetime
    received_at: AwareDatetime
    last_price: Decimal = Field(gt=0)
    previous_close: Decimal | None = Field(default=None, gt=0)
    source: str = "angelone-rest:full"
