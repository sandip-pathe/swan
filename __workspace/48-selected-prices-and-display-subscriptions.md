# Selected prices and bounded display subscriptions

Implemented 20 November 2026. M3 remains incomplete pending actual open-market
feed/reconnect verification with a valid daily broker session.

## Behavior

Chart Refresh price and Watchlist Refresh prices request exact contract IDs,
not the nearest-strike selection used by the option-chain refresh. The selected
endpoint validates today's cached listing, expiry and retained identity before
one bounded FULL quote request (1?50 unique contracts, grouped by venue).
Both quote endpoints share the advisory lock and 30-second global cooldown,
including provider failures. Returned venue/token identity, duplicates and future
timestamps are checked; missing contracts are reported, not fabricated. Existing
newer observations cannot be overwritten by older broker quotes. Display refresh
writes no order or execution evidence.

One selected-chart lease per account expires after 90 seconds; the visible chart
renews it every 30 seconds without provider REST calls. Hidden/background pages
stop renewing. Across tabs the latest selection wins. The worker checks display
interest every 15 seconds during an open verified session. The protected base
universe and open exposure remain first, then the selected chart, then up to 50
saved watchlist contracts. Additions require matching fresh catalog identity and
unexpired contracts. The configured subscription cap is never exceeded; contracts
without a remaining slot can still use explicit REST refresh. Actual set changes
use the existing stream invalidation/disarm path. Execution authorization remains
scoped to the existing validation or autonomous permission.

## Yesterday's prices

The saved broker session expired at 00:00 IST on 20 November. A safe local session
check returned DAILY_BROKER_LOGIN_REQUIRED before any network request. The 20
November refresh audit recorded unavailable; latest saved quotes were dated 19
November. Authentication failures now return BROKER_LOGIN_REQUIRED and the UI
explains that saved quotes remain visible. Login was deliberately skipped as the
user requested. Live price delivery has not been claimed or verified this turn.

## Validation

Disposable-schema and provider-fixture tests cover request bounds, missing quotes,
identity/venue/duplicate/future rejection, exchange timestamp retention, login
failure, shared cooldown, owner isolation, lease replacement/expiry, fresh catalog
identity, capacity bounds and preservation of protected exposure. The full backend
suite passed 177 tests; five frontend calculation tests, production build, type
checking, Ruff lint and mypy (69 source files) passed. Changed Python files pass
format checking. A repository-wide format check reports a pre-existing formatting
issue in tests/test_readiness.py; that unrelated file was left unchanged. Six browser
sizes (360, 390, 430, 768, 1440 and landscape 844) cover navigation, exact selected
refresh, chart/details, search/watchlist, touch chart interactions, offline fallback
and overflow; only the public offline document is service-worker cached.

The migration b3a7cde98508 is applied locally; API/database health and the actual
mobile sign-in/PWA smoke check pass. The managed worker remains in observation
mode, with zero orders/fills.

Next: renew broker login manually when ready, verify actual selected-contract
stream quotes and candle recovery through reconnect, then close M3 against its
remaining acceptance checklist. No real broker orders were placed.
