# Execution visibility milestone

18 November 2026. Implemented and locally verified. Fee/feed qualification and the final paper activation gate remain unresolved.

## Delivered

- Overview shows cash balance, pending-entry reservations, restricted proceeds, available cash and pending risk allocation. Missing funds remain unavailable, without substituting total cash for buying power.
- Pending orders show status, filled/total/remaining units, type, reason, price/trigger bounds, reservations, timing and policy evidence. Accepted orders are explicitly distinguished from fills.
- Position cards show entered, closed and remaining quantities, average entry, stop, target and realized P&L. Stored metadata supplies underlying/strike/type/expiry/venue/lot labels; absent metadata remains explicit.
- Exit status distinguishes recorded full-quantity exit orders, exit requests, incomplete coverage, stale data and disconnected workers. A recorded order does not imply executable depth or guaranteed protection.
- The Execution page shows recent orders, fills, itemized fees and frozen fee versions, proceeds holds and order events. Recent order cards are collapsed initially so they do not bury fills and holds.
- Risk inputs are disabled while orders exist or their count is unavailable. Resume remains disabled for observation-only workers even if a future execution gate reports ready.

## API contract

The authenticated workspace endpoint adds `active_orders`, `order_summary` and `instruments`. Recent history remains capped at 50 orders. Active orders are queried independently, oldest first, up to 200. The full owner-scoped count and explicit truncation flag prevent a truncated list from implying no additional exposure. Exit coverage is unavailable when this list is incomplete.

Fill rows include their actual order's side and instrument, even if that order is outside recent history. Metadata comes from stored instrument records. Unreleased holds sort before released history in the existing 100-record view; the funds summary includes all current restrictions.

## Verification

- **89 Python tests passed**. New isolated-schema cases cover old active orders beyond recent history, the 200-order cap, cross-owner exclusion, fill side/instrument/decimal fields and remaining quantities.
- Ruff, mypy (50 service files), frontend TypeScript and the production build passed.
- Playwright checked populated Overview, Execution and Journal at 1440, 735 and 390 pixels: partial quantities, restricted cash, fee details, contract labels and empty/missing/stale/offline/truncated states. It also checked the disabled observation-worker resume button with a simulated ready gate. No page overflow or browser runtime errors occurred.
- Browser checks used a clearly labeled temporary page, synthetic records and intercepted GET requests. Other API requests were blocked. The page was removed before the production build; only the real root, not-found and manifest routes remain.
- An initial build found stale generated types referencing the removed fixture. Restarting Next regenerated those types and the subsequent build passed. No generated checks were weakened.

Evidence and reproducible browser fixture: `.local/qa-execution-20261118`. Screenshots are `overview-{1440,735,390}.png` and `execution-{1440,735,390}.png`; backend XML is `backend-tests.xml`. The retained `page.tsx` is outside app source and must only be copied into a temporary route during isolated testing, then removed before building.

No broker orders, fee approvals, ledger changes or seeded production trades were introduced. Real Firebase sign-in and actual-market paper fills were not tested by these browser fixtures. Existing closed-position CSV is unchanged; detailed durable fill/fee exports remain follow-up work.

Fee rounding, explicit BFO IPFT treatment, depth quantity units and the bounded supervised validation/qualification lifecycle still block activation. The worker remains observation-only with entries disabled.
