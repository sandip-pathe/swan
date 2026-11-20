# Manual paper-order preview

Implemented 20 November 2026. M3 manual evidence remains deferred. This M6 slice
implements planning, not order submission or autonomous activation.

## User flow

Open a contract's Order tab. Enter 1-1000 whole lots, a positive limit price,
a lower positive stop and a higher target. Prices must align with the contract's
actual tick size. Use saved ask explicitly copies the observed ask; no stop or
target is invented. Inputs and results survive switching Chart/Depth/Details tabs.
Changing an input clears the old result. Server previews expire after ten seconds;
expiry asks for recalculation and never grants an execution permission.

The view shows premium at the limit, gross stop/target scenarios, entry and stop
exit fee allowances, cash required/available and planned stop loss including
modeled costs where available. Missing reviewed fee or execution inputs leave
those estimates unavailable. Gross scenarios remain distinct from net estimates.
Planning checks explain metadata, quote, session, account, capacity, entry-mode,
execution/depth, fee, cash and risk dependencies in user-facing text.

## Read-only contract

POST /api/paper/orders/preview accepts instrument_id, strict integer lots, entry,
stop_loss and target only. It is a manual BUY LIMIT plan for the retained option;
there is no account override, SELL/market-order field, AI strategy ID or submission
operation. Prices are finite Decimal values, at most two fractional digits, with
strict stop < limit < target. Off-tick prices fail rather than being silently
rounded. Retained contract metadata is checked against today's cached listing.

The endpoint runs in a PostgreSQL REPEATABLE READ, READ ONLY transaction. It
creates no order, funds reservation, strategy, decision, audit approval or quote
snapshot. The same portfolio_snapshot helper supplies reconciled available cash,
net valuation and existing reserved risk. The remaining risk budget follows the
existing capital/equity ceiling and daily loss headroom; absent current-session
baseline or valuations remains unavailable, never a made-up balance.

Fee allowances use the reviewed effective venue schedule and shared fee_ceiling.
Planned stop price uses existing adverse-slippage/tick logic; planned stop loss
includes entry and stop exit fee allowances. It is an estimate, not a guaranteed
stop fill. No provider call is made by previewing.

submission_ready is always false. Planning checks are partial diagnostics, not
size_entry approval: full liquidity-consumption budgets, order admission races,
manual/automatic ownership, permission scope and revalidation belong to the next
submission slice. No fake TradeDecision or StrategyEnvelope bridges the existing
AI-only admission contract. Execution/fee versions and account revision are
reported for traceability; the preview is not a reusable approval token. Future
manual admission must independently bind current input digests/evidence and
recheck under the account lock, rather than trust these frontend values.

## Verification

All 197 backend tests pass. Twelve new cases cover whole-lot/cost arithmetic,
missing configuration, account ownership, unknown instruments, invalid/fractional/
boolean quantities, nonfinite and overprecision prices, reversed stop/target,
off-tick prices and extra account fields. Before/after counts verify no changes
to orders, fills, ledger, strategies, decisions, snapshots or audit records.
Read-only transaction mode also prevents accidental writes by shared helpers.

Ten frontend tests, type checking, production build, Ruff and mypy (71 modules)
pass. Six browser layouts cover planning inputs/results, actual request lots,
tab retention, invalidating estimates after edits, existing chart/market/depth
flows and offline fallback. No overflow or browser exceptions. Visual review
used the 390px screenshot. Actual mobile sign-in/PWA smoke passes.

PostgreSQL was stopped at initial test setup; the first run failed to connect.
After starting it, focused and full suites passed. The managed full application
was started locally in observation mode; no login, price-refresh exercise or
real broker order was performed. User environment/setup changes and the separate
AUTONOMOUS-TRADING-DISCUSSION.md file are excluded from this commit.

Next: explicit manual intent/admission and idempotent submission through the
existing durable ledger. Preserve qualification, fee/depth and session gates;
manual actions must never acquire invented AI approval.
