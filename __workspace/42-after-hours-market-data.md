# After-hours market-data delivery

19 November 2026, Asia/Kolkata. This milestone extends M3; it does not complete M3 or qualify execution.

## Delivered

`POST /api/market/quotes/refresh` retrieves actual listed contracts and the last available FULL quotes for NIFTY or SENSEX. It works outside an open session. It uses the configured index token and a returned reference price to select the nearest listed expiry within seven days and up to five strikes, capped at ten call/put contracts. It does not guess index tokens or manufacture prices.

The request requires an authenticated existing account. A database advisory lock serializes refreshes across API processes; a global 30-second cooldown covers successes and failures. Provider work has an 80-second bound. Unexpected or duplicate contract responses, malformed quotes, future timestamps, missing references, and stale catalog dates are rejected. An older observation cannot overwrite a newer stored quote.

The Markets screen exposes an explicit Refresh prices action. Routine polling still reads the database without provider calls. Selection coverage and exchange timestamps remain visible. Retrieval does not relabel an old observation as live. The worker's existing open-session and executable-depth checks are unchanged.

These reads update instrument metadata and latest market observations, plus an account-scoped refresh audit. They do not enter the execution cache, create execution snapshots, generate strategies, qualify an account, arm entries, or place orders.

## Connected observations

On the fresh local account, after the owner renewed Angel One login:

- The read-only profile check passed.
- The official instrument master returned current eligible NFO and BFO contracts.
- A deliberate NIFTY refresh stored ten actual option quotes.
- A separate SENSEX refresh stored ten actual option quotes.
- The existing bounded history handler stored 376 actual one-minute OHLCV rows for one current NFO contract, requested from 09:15 through 15:30 IST on 19 November. The endpoint includes the requested ending timestamp when the provider returns it.
- A separate BFO history request returned 16 one-minute OHLCV rows from 09:15 through 09:30 IST for one listed SENSEX option.

This resolves the earlier `BROKER_AUTH_REJECTED` for that NFO request with the renewed session and demonstrates one BFO candle request. It does not establish all instruments' history entitlement, expired-option coverage, or a numerical comparison against a provider chart. Last available quotes are not proof of a current live feed.

## Verification

All 143 backend tests passed. Ruff and mypy passed. Frontend type checking and production build passed. Eight new test cases cover bounded contract selection, stale references/catalogs, provider-response identity, malformed/future data, timestamp preservation, overwrite ordering, ownership, failure auditing, cooldowns, and separation from execution. Test data stays in disposable schemas or isolated browser fixtures.

Browser fixtures passed all five primary screens at 360, 390, 430, 768, and 1440 pixels and 844-by-390 landscape. The new button makes one deliberate refresh request; navigation introduces no provider refresh. No page overflow or runtime errors were observed. Existing PWA offline checks still cache only the public offline notice.

## Remaining M3 work

1. Verify historical values/alignment against same-provider data and test broader instrument/range coverage.
2. Aggregate observed live updates into provisional session-aligned bars, with explicit coverage limitations, volume resets, late/duplicate events, and gaps.
3. Persist those observations independently and reconcile overlap with provider history through reconnect and restart.
4. Deliver coherent instrument/range selection to the chart proof of concept.

Historical bars should come from the provider. Locally observed bars describe only the stream SWAN received and must not claim complete exchange-trade coverage. Fee/depth evidence and actual-market execution qualification remain separate prerequisites.

## Provider references

- [SmartAPI FAQ](https://smartapi.angelone.in/faq): published API pricing and historical/live-data availability.
- [SmartAPI documentation](https://smartapi.angelone.in/docs): FULL quotes, instrument metadata, historical OHLCV/OI, intervals, and Greeks limitations.
