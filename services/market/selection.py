"""Bounded display subscriptions; never substitutes for worker entry preflight."""

from datetime import datetime, timedelta
from decimal import Decimal

from services.core.contracts import IST, Instrument
from services.market.catalog import InstrumentCatalog
from services.market.settings import ProviderError


def display_contracts(
    catalog: InstrumentCatalog, underlying: str, spot: Decimal, now: datetime
) -> list[Instrument]:
    """Nearest listed expiry and at most five strikes, using a real reference price."""
    day = now.astimezone(IST).date()
    if catalog.fetched_at.astimezone(IST).date() != day:
        raise ProviderError("INSTRUMENT_MASTER_REQUIRES_REFRESH")
    if not spot.is_finite() or spot <= 0:
        raise ProviderError("INDEX_REFERENCE_UNAVAILABLE")
    exchange = {"NIFTY": "NFO", "SENSEX": "BFO"}.get(underlying)
    eligible = [
        item
        for item in catalog.instruments.values()
        if item.underlying == underlying
        and item.exchange == exchange
        and day <= item.expiry <= day + timedelta(days=7)
    ]
    if not eligible:
        raise ProviderError("NO_ELIGIBLE_LISTED_CONTRACTS")
    expiry = min(item.expiry for item in eligible)
    eligible = [item for item in eligible if item.expiry == expiry]
    strikes = sorted({item.strike for item in eligible}, key=lambda s: (abs(s - spot), s))[:5]
    return sorted(
        (item for item in eligible if item.strike in strikes),
        key=lambda item: (item.strike, item.option_type),
    )
