# Pending manual order amendments

Implemented 20 November 2026. Orders now supports Change order for wholly
unfilled durable manual BUY LIMIT entries. Quantity, contract, session scope
and maximum expiry cannot increase. Partial fills, cancellation requests,
terminal/expired orders and automated entries cannot use this operation.

## User flow

Change order opens a mobile form for entry limit, stop loss and target. Invalid
price ordering disables preview. Preview is read-only and repeats permission,
current account revision, verified session, metadata, executable depth, fees,
liquidity budgets and portfolio risk checks. Review compares old/revised prices,
reserved cash and reserved risk. Edit prices returns to the form. Explicit
confirmation repeats all checks; a preview never authorizes a later stale change.

The existing global action controller retains the exact amendment command after
an uncertain response or authentication failure, including across reload. It
restores a locked review without automatically submitting. A retry uses the same
UUID, prices and account revision. Definite rejections require a new review.
No hidden login, refresh, broker order or entry activation is performed.

## Persistence and execution

POST /api/paper/orders/{order_id}/amend/preview accepts expected_account_revision,
entry, stop_loss and target. POST /api/paper/orders/{order_id}/amend additionally
requires request_id. Extra fields, including quantity, are rejected. Ownership
comes from authentication. Controlled errors do not expose private configuration.

The service locks the account and only re-prices this order's old reservation in
the risk snapshot. All other exposure remains included. Successful confirmation
atomically appends an immutable manual intent and AMENDED event, switches the
order to the revised intent and budgets, updates reservations, resets execution
latency, caps expiry at the old expiry, increments revision and reconciles.
The original accepted request/event and previous intents remain unchanged.
The same order ID and validation slot remain in use; no second entry is created.
The frozen execution configuration must still match current reviewed settings.

Fill-time checks and protection use the latest approved intent. A fill/cancel
winning the account lock prevents a fresh amendment; a stale fill proposal must
satisfy the revised limit, eligibility, intent and protection checks. Accepted
amendment retries return the current order even after fills, expiry or loss of
current market data. Original placement retries still resolve the same order
through its original idempotency key. Saved plan links remain intact.

No schema migration is needed. Workspace reads expose only the latest manual
terms and an amendment-availability flag through an account-scoped bulk query.

## Verification

259 backend tests pass, including ten new integration cases for read-only
preview, concurrent retry identity, one-entry preservation, reservation/risk
reconciliation, original placement retry, revised fill protection and latency,
strict fields, owner isolation, changed request identity, revision conflicts,
off-tick/risk failures, terminal/fill/cancel/pause/closed/stale/configuration
conditions and current workspace/plan links. Ruff and mypy (77 modules) pass.
Ten frontend tests, type checking and production build pass.

Isolated browser fixtures cover editing without losing input focus, invalid price
ordering, preview before mutation, deliberate confirmation, lost-response/reload
recovery, locked pending fields, exact retry payloads and no horizontal overflow
at 360, 390, 430, 768, 1440 and 844 landscape pixels. Existing cancellation/exit
and workspace checks remain green. The local API was restarted and the public
mobile sign-in/PWA smoke check passes, with only the offline fallback cached.
The actual account still has zero paper orders and manual intents, no enabled
entries, and an OBSERVATION worker. Broker login/live-market checks remain
skipped at the user's request. These fixtures place no actual trades.

## Next slice

Add a per-order history view that joins actual lifecycle events, amendments,
fills and fees, with clear links to current position/protection. Keep the broader
M6 manual permission limits visible and preserve deferred M3 live acceptance.
