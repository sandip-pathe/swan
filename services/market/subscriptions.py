"""Bounded display additions cannot displace the worker's protected universe."""

from datetime import datetime

from services.core.contracts import IST, Instrument
from services.market.catalog import InstrumentCatalog


def add_display_contracts(
    protected: list[Instrument],
    requested: list[Instrument],
    catalog: InstrumentCatalog,
    now: datetime,
    maximum: int,
) -> list[Instrument]:
    selected = {item.id: item for item in protected}
    if len(selected) > maximum:
        raise ValueError("PROTECTED_UNIVERSE_EXCEEDS_BUDGET")
    if catalog.fetched_at.astimezone(IST).date() != now.astimezone(IST).date():
        return list(selected.values())
    for item in requested[:51]:
        current = catalog.instruments.get(item.id)
        if current is None or current.expiry < now.astimezone(IST).date():
            continue
        if current.model_dump(exclude={"verified_at"}) != item.model_dump(exclude={"verified_at"}):
            continue
        if item.id not in selected and len(selected) < maximum:
            selected[item.id] = current
    return list(selected.values())
