# Durable manual paper plans

Implemented 20 November 2026. This is the user-intent foundation of manual paper
orders, not completion of submission. Inspection showed that BUY admission,
later fill revalidation, position protection and qualification evidence currently
rely on AI DecisionRecord/StrategyRecord data. Those paths were not bypassed or
fed invented AI approvals to make manual placement appear functional.

## Delivered user flow

Contract / Order can save a fresh preview as a paper plan. Saved plans belong to
the authenticated account, survive reload/restart and retain immutable input,
instrument and preview snapshots. Loading a plan restores inputs, clears the old
estimate and asks for a new preview. Archive removes it from the active list but
preserves the record. Neither save, load nor archive places an order or reserves
funds. The UI uses Save paper plan rather than an unsupported Place order button.

The selected contract's saved list loads only while its Order tab is visible,
with bounded 25-row pagination. Saving is disabled for expired previews. Failed
save retries retain the request key while inputs remain unchanged.

## Backend contract and concurrency

POST /api/paper/plans accepts the existing strict ManualPreview fields plus a
UUID idempotency key and expected account revision. Prices are canonicalized to
two decimal places for retry comparison. Under the account lock, a matching
existing request returns the same saved/archived plan before revision or capacity
checks. Different inputs with the same owner/key fail. The database enforces the
owner/key uniqueness as well.

New saves require the expected current revision and recalculate the preview using
the shared read-only calculation helper under that lock. They snapshot current
checks rather than trust a client-provided approval or cost. Fifty active plans
per account are allowed. Archiving is owned and idempotent; retrying an archived
save never reactivates it. Saved/archive audit events are emitted once. GET list
and archive operations scope all access to the authenticated account.

ManualPaperPlan is a separate table without a decision/order-approval role. API
responses explicitly report human source, order_id null and submission_ready false.
No plan is consumed automatically by the worker. Saving changes neither account
revision nor trading permissions. Preview remains PostgreSQL REPEATABLE READ,
READ ONLY; its calculation body was extracted for reuse without changing logic.

Migration d5c9efa10710 is applied locally. Downgrade refuses to drop populated
plans. The managed API was restarted; the observer was left running.

## Verification

All 201 backend tests pass, including all twelve preview cases after refactoring.
Four new integration cases cover canonical retry identity, concurrent duplicate
requests, conflicting reuse, owner isolation, account revision changes, rejected
client approval/source overrides, cap/archive behavior and exactly-once audit
creation. Orders/fills/ledger/strategies/decisions/snapshots remain unchanged.
Ten frontend tests, production build/type checks, Ruff and mypy (72 modules) pass.
Six browser layouts cover save, list, load, archive, fresh re-preview, input
retention, existing chart/depth/market flows and offline fallback without overflow
or browser exceptions. Visual review inspected the 390px order screenshot. Actual
localhost mobile sign-in/PWA smoke passes. Fixture plans/prices never seed the
production account. Local environment/setup changes and the separate autonomous
brainstorming document were excluded from the commit.

## Next execution slice

Introduce an explicit manual intent reference in the order contract and ledger;
provide deterministic manual admission, exclusive entry ownership, current
permission/evidence binding, idempotent order creation and later fill revalidation.
Update position protection/exit derivation to read human stop/target/holding inputs
without assuming an AI decision exists. Exercise the full eligible fixture flow,
rejections, pause/restart, duplicate admission and protective exits before exposing
Place paper order. Preserve existing fee/depth/session/qualification gates.
