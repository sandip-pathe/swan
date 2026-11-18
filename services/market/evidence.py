"""Stable identities for observed depth; receipt time never creates market liquidity."""

import hashlib
import json

from services.core.contracts import Quote


def identify_quote(quote: Quote) -> Quote:
    payload = quote.model_dump(
        mode="json",
        include={
            "instrument_id",
            "timestamp",
            "source",
            "sequence",
            "timestamp_basis",
            "bid_depth",
            "ask_depth",
            "depth_kind",
            "bid",
            "ask",
            "bid_quantity",
            "ask_quantity",
            "volume",
            "oi",
        },
    )
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    identity = f"{quote.source}:{digest}"
    # Display-only LTP/OHLC/trade fields are also excluded: changed chart metadata
    # must not replenish executable depth at the same provider observation.
    # stream_id and received_at are deliberately excluded: a reconnect/retry is not a fill.
    # Keep the local snapshot UUID: two receipts may have different received_at values.
    # The market_event_id, not that local UUID, is the future liquidity-consumption key.
    return quote.model_copy(update={"market_event_id": identity})
