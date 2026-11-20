# Saved watchlist

Implemented 20 November 2026. This M5 slice adds one account-owned watchlist,
limited to 50 contracts. Multiple named lists and reordering remain outside this
slice.

## User flow

In **Markets → Search**, tap the star beside a contract to save it. The star shows
the saved state and can remove the contract. **Markets → Watchlist** shows saved
contracts, opens their charts and provides an explicit remove button. Chart Back
returns to the originating market view. Entries survive navigation, reload and
sign-in on another browser because the database stores them for the account.

The list shows the actual saved LTP only when available, with exchange date/time.
It never substitutes a bid/ask midpoint or zero. Recent/last quote describes the
observation age, not execution readiness. Expired and no-longer-listed contracts
remain visible with labels so existing saved history can still be reviewed.
Changed listing identity is also labeled unavailable rather than silently moving
the saved item to a different broker contract.

Saving does not subscribe the contract, call the broker, refresh its price, enable
entries or place an order. Quotes appear only if the existing ingestion/explicit
refresh paths already saved them. Visible watchlist polling reads the database;
other market views load saved membership without a recurring watchlist poll.

## Persistence and boundaries

Migration `a2f6bcd87407` adds `watchlist_items`, keyed by account and retained
instrument identity with a server-generated save timestamp. Saving a new item
reuses the search selection checks for current metadata and unchanged identity.
Duplicate saves and removes are idempotent. Existing saved items can be removed
after expiry or catalog aging. A per-owner advisory lock serializes capacity
checks without taking the execution account lock. A downgrade refuses to discard
a nonempty list.

Authenticated endpoints are `GET /api/watchlist`, `POST /api/watchlist/save` and
`POST /api/watchlist/remove`. Every query/mutation binds the owner to the verified
account. The API's no-store headers and public-offline-page-only service worker
remain unchanged; no credentials or account data are stored in browser storage.
Client mutation controls report completion only after the server responds, and
older list responses cannot overwrite a newer mutation result.

## Verification

Four isolated integration tests cover owner isolation, durable/idempotent saves
and removes, expired/removed/reused listings, unchanged quote timestamps, stale
metadata rejection and concurrent saves at capacity. They also establish that
cash, entry state, quotes, executable snapshots and orders are not manufactured
by saving a contract. Existing instrument-search tests verify the reused guards.

Browser fixtures exercise star save, chart opening, correct Back destination,
restoration after leaving Markets, removal and empty state at six viewport sizes,
including 360/390/430-pixel phones and landscape. The existing chart, gesture,
offline and navigation checks also pass with no overflow or runtime errors.
Fixture contracts never enter the actual account database.

The local database was stopped at the start of verification and recovered normally
when restarted. Migration/model comparison passed. Broker login was not attempted;
the user's instruction was to skip authentication if needed and keep building.
Actual-market/reconnect qualification remains unverified, independently of this
watchlist implementation.

Next slice: richer instrument details and the option-chain workflow. Subscription
prioritization for saved/selected contracts needs its own bounded market-data
policy; saving is deliberately not an implicit subscription request.
