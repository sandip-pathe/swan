# Reconciled portfolio value and P&L

Implemented 20 November 2026. Home now separates portfolio valuation and P&L
from spendable paper funds. No broker login, provider refresh or trading
activation is involved in calculating or displaying this information.

## Calculations

GET /api/paper/portfolio reads an authenticated account in a repeatable-read
snapshot. It reuses portfolio_snapshot and liquidation_estimate, including
account reconciliation, frozen execution/fee settings, executable bid depth,
quantity mapping, adverse slippage, liquidity budgets and estimated exit fees.
This display never grants risk approval or creates fills. Admission still uses
its existing account lock and permission checks.

Portfolio value is recorded cash plus estimated net sale value of all held units.
Pending entry reservations and restricted proceeds reduce available cash, not
portfolio value. Total P&L compares portfolio value with recorded CAPITAL ledger
entries, not mutable configured capital. Realized P&L sums reconciled position
results, which include allocated entry costs and actual exit fees. Estimated
open P&L is total less realized P&L and includes remaining entry costs plus
estimated exit fees. Session P&L requires an opening-equity baseline for the
current IST session date. Fees are actual recorded fill fees across all orders.

Aggregation covers all owned positions/fills rather than the workspace's bounded
recent-history page. A flat account needs no market prices: equity equals cash
and open-position value is zero. Closed trades remain in realized results.

## Unavailable and stale data

The response distinguishes FLAT, FRESH, STALE, UNAVAILABLE and UNRECONCILED.
An estimate is returned only when all open positions can be valued and the
account reconciles. Missing prices, incomplete depth, unknown units, insufficient
liquidity, invalid configuration or expired quotes cannot turn the risk model's
internal zero placeholder into a displayed account value. There is no partial
portfolio subtotal. Reconciliation failures suppress all financial totals.
Recorded realized P&L and fees remain available when only valuation is blocked.
Raw parsing errors, configuration contents and quote payloads are not returned.

The UI shows snapshot and oldest quote times in calculation details. It polls
retained records every five seconds while Home is visible, pauses requests for
hidden pages and aborts obsolete requests. Expired quote validity hides estimates
locally without waiting for the next poll. Account snapshots expire locally after
15 seconds; fetch failures hide financial values and offer retry. No PWA cache
or persistent browser storage is added for private portfolio data.

## Verification

272 backend tests pass, including nine new cases for flat/pending reservations,
actual bid-depth equity, P&L identities, fee accounting, closed positions and
restricted proceeds, stale/missing/malformed/incomplete quotes, reconciliation,
current session baseline, read-only state and account isolation. Ruff and mypy
(79 modules), ten frontend tests, type checking and production build pass.

Browser fixtures exercise fresh, flat, stale, unavailable, reconciliation failure,
fetch error/retry and local quote-expiry states at 360, 390, 430, 768, 1440 and
844 landscape pixels. Recorded realized P&L remains separate from unavailable
estimates. Layouts have no horizontal overflow. Existing workspace flows pass.
The managed API was restarted. The local public mobile sign-in/PWA smoke check
passes and only the offline fallback is cached. A read-only check against the
actual local account returns FLAT, reconciled, with equity available without
broker data. The account still has zero orders/manual intents, no enabled entries
and an OBSERVATION worker. Live-market acceptance remains deferred at the user's
request.

## Next slice

Add owned fill and open-position stop/target overlays to the contract chart,
using recorded evidence and clear pending/closed states. Keep M3 live acceptance,
source fee/depth evidence and broader manual permission constraints explicit.
