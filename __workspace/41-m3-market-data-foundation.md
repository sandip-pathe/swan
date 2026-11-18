# M3: market-data foundation

Implemented 18 November 2026. M3 remains in progress; this delivers quote retention and the historical-data backend before chart implementation.

## Delivered

- The REST FULL and WebSocket SnapQuote adapters retain optional LTP, session open/high/low, previous close, average price and last-trade quantity. REST additionally retains its explicit trade timestamp. Unestablished WebSocket trade-timestamp units remain unparsed. Missing/zero optional price fields remain unavailable.
- Generated JSON/TypeScript quote contracts match the backend. Existing saved quotes remain compatible through optional fields.
- Display price changes cannot create a new executable-depth identity. Execution continues to use its existing bid/ask, depth, freshness, provenance and permission checks.
- `POST /api/market/history/refresh` performs one deliberate provider read for a stored current NFO/BFO contract. It supports the documented intervals, minute boundaries, aware times, provider range limits and an additional 5,000-bar bound. It rejects future ranges, ranges after contract expiry, expired contracts and metadata not verified today. It does not guess old/reused token mappings or page automatically.
- `GET /api/market/history?instrument_id=...&interval=...` reads the owner's latest cached batch for that instrument/interval without calling a provider. Responses include the exact requested range so consumers can reject stale selections. No frontend chart consumes this API yet.
- Immutable owner-scoped batches retain request, instrument snapshot, retrieval time, normalized bars and original six-field provider rows. Failed requests are recorded separately from empty successful responses. A global database advisory lock prevents concurrent backfills across API processes; attempts have a five-second minimum spacing and use the existing bounded broker retry client.
- Bars use provider opening timestamps in Asia/Kolkata, sorted and deduplicated. Conflicting duplicates, invalid OHLC/volume, timezone-free timestamps and out-of-range rows fail explicitly. Missing intervals remain gaps. OI is unavailable because this endpoint does not supply it. Closed/provisional means elapsed interval only, explicitly not provider confirmation of finality.
- Migration `d9c3efa54104` is applied locally. Downgrade refuses to discard nonempty history evidence. History batches are separate from executable snapshots and cannot create orders, fills or entry permission.

## Verification

The full Python suite passed 134 tests. Subsequent focused checks passed all six market-history tests, including the additional mock-transport client test and recorded authentication-failure/rate-limit checks. Ruff and mypy passed for the backend; migration/model comparison and contract regeneration passed. Frontend type checking and production build passed with the generated quote changes. The API and web services were restarted, with the worker in observation mode. All test market values were isolated fixture inputs, never production seed/history.

A real, bounded history request for a stored current contract was attempted through the handler. Angel One rejected it with `BROKER_AUTH_REJECTED`; the failure was recorded. This does not establish whether a fresh login or another provider/account correction is needed, and candle entitlement remains unverified. No successful real bars are claimed. The local account retained its cash, entries disabled, zero orders and zero fills.

## Remaining M3 acceptance

1. Resolve the broker authentication rejection and obtain actual supported contract candles. Compare timestamps and values with the provider's same-session data; document account/expired-option limitations.
2. Build observed live bars with session-aware alignment, cumulative-volume resets, late/duplicate/out-of-order updates and gaps. Snapshot LTP updates cannot reconstruct every exchange trade; label coverage accordingly.
3. Persist provisional live bars independently from provider history and reconcile overlap without double counting. Exercise reconnect, restart and backfill.
4. Add coherent instrument/range selection and delivery for chart consumers before M5. Index/reference instruments require their own contracts; current historical requests intentionally cover stored options only.

The full M3 acceptance gate is not passed. M4 visual design and M5 chart interactions remain subsequent work. M2 actual-market qualification and fee/depth evidence are also still outstanding; this change does not arm paper entries.

## Sources

- [SmartAPI historical API](https://smartapi.angelone.in/docs/ResponseStructure): candle endpoint, interval/range declarations and six-field OHLCV response. Public indexed documentation was readable; direct access can require authorization.
- [SmartAPI market data](https://smartapi.angelone.in/docs/Instruments): REST price-field meanings, including previous close.
- [Official SnapQuote decoder](https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartWebSocketV2.py): binary field offsets. Existing TLS and endpoint allowlists remain in force.

Provider declarations establish contracts, not this account's current entitlement or the accuracy of unobserved data.
