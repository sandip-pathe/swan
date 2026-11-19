# Contract search

Implemented 20 November 2026. One reviewable M5 slice; watchlists remain next.

Open **Markets → Search**. Search by strike, index, call/put or expiry text; use
market, expiry and option-type filters to narrow results. Results sort by expiry,
numeric strike and side, with 30 per page. Each result shows actual listing
metadata and opens the existing chart. Back returns to the preserved filters.
Chart links can resolve saved contracts independently of the quoted option chain.

**Refresh contracts** explicitly retrieves Angel One's public supported-option
master. Typing, filtering, paging and chart resolution read only the database.
This action does not retrieve prices, change subscriptions or require a broker
price request. Historical candles remain a separate explicit action in the chart.

The `listed_instruments` cache is separate from the instrument identities retained
by the execution ledger. Atomic refreshes publish a current catalog generation;
removed listings from older generations do not appear. Expired contracts are
excluded. A listing from a previous IST date is visibly stale and must be
refreshed before selection. Selection persists verified chart metadata without
creating quotes, executable snapshots, orders or permissions. Existing instrument
identity conflicts are rejected rather than overwriting a retained contract.

All endpoints require an authorized local account. Catalog refresh has a shared
advisory lock and a one-minute cooldown covering successes and failures. Failures
leave the previous cache intact and expose a sanitized error. Search terms use
bound parameters and literal wildcard escaping; query length and paging are
bounded. Listing metadata is global public discovery data, not private account
data. The existing no-store response and offline-cache rules apply.

Migration `f1e5abc76306` is applied locally. Its table is a rebuildable discovery
cache, not trading evidence. No broker credentials or account settings changed.

## Verification

Four isolated integration tests cover search filters, numeric ordering, paging,
literal wildcards, removed/expired/stale contracts, refresh failure/cooldown/lock,
ownership checks, idempotent selection and changed broker identities. Selection
preserves account cash and entry state and produces no orders.

The browser fixture checks search at 360, 390, 430, 768 and 1440 pixels, plus
landscape; no horizontal overflow or runtime errors were observed. It exercises
explicit refresh, filters, chart selection and browser-back filter preservation,
alongside the existing chart, offline and navigation checks. Fixture contracts
remain outside the application database.

A genuine public-master refresh cached 6,272 normalized supported contracts just
after midnight IST on 20 November. Both NIFTY and SENSEX returned paged call
results and 18 expiry choices, without provider calls during search. The actual
account still has zero orders/fills and entries disabled. Listing presence does
not establish price/history coverage or execution eligibility for every contract.

The full backend suite, frontend calculation tests, type checking and production
build are checked before commit. Live market/reconnect acceptance remains open.
Saved watchlists and richer option-chain/instrument details are later slices.
