# Owned paper cancellation and position exit

Implemented 20 November 2026. This slice adds user controls to the durable paper
execution path. Live-market evidence remains deferred; no broker login or market
refresh is part of these commands.

## User behavior

Orders exposes Cancel remaining entry for active, owned durable BUY orders.
A focused inline confirmation explains that existing fills remain positions.
Protective SELL orders cannot be cancelled through this control. Open durable
positions expose Exit position. Confirmation persists a request for the actual
remaining held units, pauses new entries and disarms the current trading session.
It does not claim an immediate fill. Monitoring, verified sessions and fresh
market depth still govern execution; the request persists when they are absent.
The user sees pending exit status until actual fills close the position.

Manual and automated entry source labels appear in order/position details.
Workspace responses also include owned entry order, manual intent and decision
identifiers, resolved through bounded bulk queries rather than per-card queries.
Cancellation and exit remain requestable with stale workspace data because the
server checks current ownership, orders, holdings and reconciliation.

## Commands and recovery

POST /api/paper/orders/{order_id}/cancel and
POST /api/paper/positions/{position_id}/exit accept only request_id (UUID).
Authentication supplies the account. Immutable audit events bind the request ID
to its account, action and resource. Cancellation uses separate existing ledger
request/acknowledgment transactions, retains holds until acknowledgment, and
preserves partial or complete fills that win the race. Exit uses the existing
watchdog protection path and frozen execution policy, with USER_EXIT priority
below daily-loss/pre-close exits and above session invalidation. No new migration
is required. Replaying an accepted exit does not pause a later resumed account.

The mobile UI reviews before sending, locks other actions while a command is
uncertain, and retains the same identity on network/authentication failures.
Account-scoped sessionStorage restores pending commands without automatic POSTs.
A receipt survives disappearance of the order card and clearly distinguishes
cancelled remainder, a filled order, a pending exit and a closed position.
No credentials or tokens are stored by this flow.

## Verification

249 backend tests pass, including eight new integration cases for concurrent
cancellation, full/partial fill races, reservation reconciliation, exit lifecycle,
closed/unavailable-session persistence, ownership, strict input, source links,
priority preservation and replay side effects. Ruff, mypy (76 modules), ten
frontend tests, frontend type checking and production build pass.

Browser fixtures exercise deliberate confirmation, lost-response/remount recovery,
stable retry identity, pending exit controls and overflow at 360, 390, 430, 768,
844 landscape and 1440 pixels. These are isolated fixtures, not actual trades.
The local API was restarted and web/API/database are running. The mobile public
sign-in/PWA smoke check passes; only the offline fallback is cached. The actual
account still has zero orders and manual intents, no enabled entries, and its
worker remains OBSERVATION. Live broker checks and M3 manual evidence remain
skipped at the user's request.

## Next slice

Continue order lifecycle usability with amend/replace semantics for pending manual
entries, including fresh preview, current account revision and reservation changes.
Broader manual permission remains bounded by the existing HUMAN validation session.
M6 is not complete; M3 live evidence and the remaining milestone plan are unchanged.
