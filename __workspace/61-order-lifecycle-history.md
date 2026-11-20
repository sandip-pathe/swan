# Order lifecycle history

Implemented 20 November 2026. Orders now exposes Order timeline on pending and
recent order cards. Position cards expose Entry and exit history when a durable
entry link is available. Opening a timeline is deliberate and read-only; normal
workspace polling does not fetch histories or call providers.

## User experience

The timeline shows current order status/source, actual filled units, average
fill price, total fees and net cash movement for this order. Cash movement does
not imply that restricted sale proceeds are spendable. A linked position shows
remaining units, stop/target, pending exit and realized P&L. Related entry/exit
orders open within the same timeline with a way back to the original order.
The UI distinguishes pending/replaced/cancelled exits from executed exits.

Activity is newest first and includes recorded acceptance, amendments, fills,
cancellation request/acknowledgement, expiry, triggers and price bounds.
Amendments compare old/revised prices and reservations. Fill rows use actual
ledger fills and offer itemized fees. A cancellation acknowledgement does not
claim that a fill did not occur. Missing fill evidence and earlier orders with
no lifecycle records are explicit rather than reconstructed as synthetic events.

History shows its snapshot time and has explicit refresh and older-activity
controls. Loading, retry and empty states are accessible. Collapsing, switching
orders and unmounting abort obsolete requests; response generations prevent
late responses replacing the selected order. History uses the signed-in request
boundary and is not cached by the PWA service worker.

## API and consistency

GET /api/paper/orders/{order_id}/history authenticates ownership before reading
order evidence. A repeatable-read snapshot keeps order, events, fills and position
consistent within each response. Events page by (timestamp, UUID), newest first,
with a cursor bound to that owned order. Default page size is 30, maximum 100.
Equal timestamps have a deterministic UUID tie-break. Fee/fill aggregates cover
all fills, independently of the event page. Only fill records referenced by the
current event page are fetched for itemized details. Related orders are bounded
to 50 with an explicit truncation flag.

Event payloads are projected through field allowlists. Raw accepted configuration,
request payloads, internal market identifiers and arbitrary event detail are not
returned. The endpoint performs no mutation, broker request, refresh or login.
No migration is required. Existing unknown/foreign orders return the same 404;
foreign/unknown/cross-order cursors cannot read another history.

## Verification

263 backend tests pass, including four new integration cases covering real
amend/fill/fee/protection and closed-position histories, cash movement signs,
read-only account state, equal-timestamp pagination, no duplicate/missing events,
field filtering, owner/cursor isolation, input bounds and cancellation after a
fill. Ruff and mypy (78 modules), ten frontend tests, type checking and production
build pass. Browser fixtures cover deliberate loading, error/retry, itemized fees,
older pages, related-order navigation, close and horizontal overflow at 360, 390,
430, 768, 1440 and 844 landscape pixels. Existing workspace flows remain green.
The local API was restarted, and the mobile public sign-in/PWA smoke check
passes. The actual account still has zero orders and manual intents, no enabled
entries, and an OBSERVATION worker. Live-market acceptance and broker login
remain skipped at the user's request.

## Next slice

Expose reconciled portfolio value and P&L with honest fresh/stale/unavailable
valuation states. Continue M6 without presenting bounded manual validation as
unrestricted trading or marking M3 live evidence complete.
