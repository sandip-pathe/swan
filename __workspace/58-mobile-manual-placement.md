# Mobile manual paper placement

Implemented 20 November 2026. This slice exposes the bounded human execution
lifecycle through an authenticated API and the mobile contract ticket. It does
not complete unrestricted manual permission or all M6 order management.

## User flow

Manual paper trading shows the selected contract's current session availability.
Closed/unknown sessions and the entry cutoff keep starting/placing disabled while
previewing and saving plans remain available. An observation monitor explains
where to prepare trading in Account; the ticket never silently switches modes.
Starting explicitly requests a HUMAN, five-minute, one-entry, one-lot validation
session through the existing guarded endpoint. Existing shared readiness and
connection requirements remain in force. No broker login is initiated by the UI.

Once the monitor confirms readiness, the user previews and saves current inputs,
reviews contract/quantity/limit/stop/target/costs, then explicitly selects Place
paper order. A focused inline review keeps mobile navigation and touch targets
accessible. Missing costs, blocked checks, account changes, expired estimates,
wrong contract/session ownership and quantities above the lease disable review.
The backend remains authoritative if state changes after review.

Acceptance replaces the old estimate/save message with an order receipt. The
receipt labels its last confirmed state and directs users to Orders for current
fills/protection. Saved plans now link to their latest owned order instead of
always saying that no order was placed. A single ranked query resolves order links
for the bounded plan page. Stop manual session uses the existing draining path.

## API and retries

GET /api/paper/manual/status reads the current owned session, permission, account
revision and owned entry without provider calls or mutation. It distinguishes
market/cutoff, preparation, source/scope, waiting, stopping and consumed-entry
states. POST /api/paper/plans/{plan_id}/submit accepts only a request UUID and
expected account revision. Account identity comes from authentication; plan
inputs, quotes, local calendar and approvals come from server-owned records.
The route calls ManualPaperService, which repeats deterministic admission.
Business failures return controlled codes; configuration paths/contents and raw
exceptions are not sent to the client. Client errors retain status/code metadata
for retry handling.

The service can load retained observations when called by the API, but resolves
existing intent/order identity before loading market data or configuration.
Retries can therefore recover an accepted result after close, missing quotes,
account revision changes or configuration loss. No refresh or login is hidden
inside submission.

The ticket locks editable inputs while an outcome is uncertain. It preserves the
same plan/request/revision across retries, including authentication failures.
A definite server rejection clears the command and requires a fresh review.
Pending identifiers are stored in sessionStorage under the authenticated account
and instrument when available; no tokens, credentials or prices are stored.
Remount restores the pending command without submitting automatically. Matching
owned status receipts can reconcile it; success removes pending storage. If
storage is unavailable, recovery remains in memory and server one-entry limits
still apply. Chart state is keyed by signed-in user and contract.

## Verification

All 241 backend tests pass. Five new API integration cases cover concurrent
identity, owner isolation, strict command fields, archived/unknown plans,
read-only status, closed/cutoff/source/pause states, retries without current
market/configuration, linked plan orders and current-risk rejection. The existing
28 manual lifecycle cases still pass. Ruff and mypy (74 modules), ten frontend
tests, type checking and production build pass.

Six browser sizes cover closed planning, explicit session start, fresh preview,
save/review/placement, receipt and stop. Mobile tests cover lost responses,
authentication failure, unchanged retry identity, account-scoped pending storage,
remount recovery without automatic submission and definite server rejection.
Layouts have no overflow or runtime errors; public-only offline caching remains
unchanged. The 390px review and receipt were visually inspected. Browser data is
in the ignored fixture harness; backend records live in disposable schemas.

Per the user's instruction, broker login, live price refresh and open-market
acceptance were skipped. No session or order was started in the actual account.
The local API was restarted; the existing observation worker stayed running.
No migration is required. M3 live evidence remains deferred.

## Next slice

Add owned order cancellation and position-exit actions with clear pending,
partial-fill and unresolved-exit states. Preserve the ledger's race/idempotency
rules and protective sell path. Surface human source and linked intent alongside
actual orders/positions. Broader permission outside bounded validation, M7
reports, M8 release/PWA integration and M9 operational evidence remain separate.
