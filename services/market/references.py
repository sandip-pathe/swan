"""Index display context, isolated from option execution and account state."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import Numeric, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from services.core.contracts import IST
from services.core.models import ListedInstrument, UnderlyingReference
from services.market.analysis import provider_price, provider_time
from services.market.settings import ProviderError


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


def normalize_reference(row: dict, underlying: str, token: str, now: datetime) -> IndexReference:
    exchange = "NSE" if underlying == "NIFTY" else "BSE"
    if (
        underlying not in {"NIFTY", "SENSEX"}
        or row.get("exchange") != exchange
        or str(row.get("symbolToken", row.get("symboltoken"))) != token
    ):
        raise ProviderError("INDEX_REFERENCE_IDENTITY_INVALID")
    stamp = provider_time(row["exchFeedTime"])
    price = provider_price(row.get("ltp"))
    if stamp > now or price is None or price <= 0:
        raise ProviderError("INDEX_REFERENCE_UNAVAILABLE")
    return IndexReference.model_validate(
        dict(
            underlying=underlying,
            exchange=exchange,
            provider_token=token,
            timestamp=stamp,
            received_at=now,
            last_price=price,
            previous_close=provider_price(row.get("close")),
        )
    )


def save_reference(db: Session, reference: IndexReference) -> None:
    statement = insert(UnderlyingReference).values(
        underlying=reference.underlying,
        timestamp=reference.timestamp,
        payload=reference.model_dump(mode="json"),
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[UnderlyingReference.underlying],
            set_={"timestamp": statement.excluded.timestamp, "payload": statement.excluded.payload},
            where=UnderlyingReference.timestamp <= statement.excluded.timestamp,
        )
    )


def reference_context(db: Session, underlying: str, expiry: date | None) -> dict:
    record = db.get(UnderlyingReference, underlying)
    result = {
        "quote": record.payload if record else None,
        "change": None,
        "change_pct": None,
        "atm_strike": None,
        "atm_status": "reference_unavailable",
    }
    if record is None:
        return result
    reference = IndexReference.model_validate(record.payload)
    if reference.previous_close is not None:
        change = reference.last_price - reference.previous_close
        result.update(change=str(change), change_pct=str(change / reference.previous_close * 100))
    today = datetime.now(UTC).astimezone(IST).date()
    if reference.timestamp.astimezone(IST).date() != today:
        result["atm_status"] = "reference_from_another_session"
        return result
    latest = db.scalar(select(func.max(ListedInstrument.catalog_at)))
    if latest is None or latest.astimezone(IST).date() != today:
        result["atm_status"] = "catalog_refresh_required"
        return result
    if expiry is None:
        result["atm_status"] = "no_listed_strike"
        return result
    fields = ListedInstrument.payload
    strike = fields["strike"].as_string().cast(Numeric)
    nearest = db.scalar(
        select(strike)
        .where(
            ListedInstrument.catalog_at == latest,
            fields["underlying"].as_string() == underlying,
            fields["expiry"].as_string() == expiry.isoformat(),
            fields["expiry"].as_string() >= today.isoformat(),
        )
        .order_by(func.abs(strike - reference.last_price), strike)
        .limit(1)
    )
    result.update(
        atm_strike=str(nearest) if nearest is not None else None,
        atm_status="nearest_listed_strike_to_saved_index"
        if nearest is not None
        else "no_listed_strike",
    )
    return result
