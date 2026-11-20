"""Derived display metrics. These values never authorize executable prices."""

from decimal import Decimal

from services.core.contracts import Quote


def quote_statistics(quote: Quote | None) -> dict[str, str | None]:
    change = percent = spread = bps = None
    if quote is not None:
        if (
            quote.last_price is not None
            and quote.previous_close is not None
            and quote.previous_close > 0
        ):
            change = quote.last_price - quote.previous_close
            percent = change / quote.previous_close * 100
        if quote.bid is not None and quote.ask is not None and 0 < quote.bid <= quote.ask:
            spread = quote.ask - quote.bid
            bps = spread / ((quote.bid + quote.ask) / Decimal(2)) * 10000
    return {
        name: str(value) if value is not None else None
        for name, value in (
            ("change", change),
            ("change_pct", percent),
            ("spread", spread),
            ("spread_bps", bps),
        )
    }
