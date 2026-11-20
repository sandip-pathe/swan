# Usable depth in manual previews

Implemented 20 November 2026. This completes a deterministic sizing prerequisite
for manual entries. Manual order admission, fill revalidation and protection
integration remain unfinished; the Place order action is still unavailable.

## Behavior

The Order preview shows usable lots at the entered BUY limit. Capacity includes
only depth whose modeled execution price fits that limit. It applies verified
quantity units, reviewed participation limits, whole-lot fill granularity and
account/session/instrument/side-scoped durable consumption. Higher displayed
quantity does not automatically restore previously consumed liquidity. Slippage
is applied before the limit comparison. A separate planning check flags requests
above the configured maximum order quantity.

A verified zero appears as zero lots with an explanation. Missing, stale,
future-dated or unverified quotes produce Unavailable, as do liquidity budgets
newer than the quote or bound to another execution configuration. The server
returns available_depth_quantity and available_depth_lots, both nullable.
Saved plans retain these values in their recalculated preview snapshots; loading
inputs still requires a fresh preview.

## Shared implementation

The existing AI depth-capacity loop moved to paper.liquidity.buy_capacity without
changing its whole-lot, scope, consumption or price behavior. AI sizing and manual
previews now call this helper. Its callers validate quote freshness, provenance
and execution policy. It does not reserve cash, consume depth, create evidence,
persist approvals or change account permissions. Preview remains a coherent
PostgreSQL read-only transaction; no provider call is introduced.

## Verification

All 208 backend tests pass, including seven new cases for consumed capacity,
limit boundaries, unknown versus zero, future/stale timestamps, unknown source,
newer/mismatched budgets, lot-unit conversion, slippage and quantity limits.
The preview integration case verifies trading records and durable consumption
remain unchanged. Existing durable fill/protection cases pass after extraction.
Ruff and mypy pass. Ten frontend tests and the production build pass. Six browser
layouts pass without overflow or runtime errors; the 390px case checks unavailable,
zero and positive depth states. Actual localhost sign-in/PWA smoke passes. The
390px screenshot was visually inspected. Fixture data stays in isolated schemas
or the ignored browser harness. The managed API was restarted; the observer was
left running. No real broker or paper order was placed.

## Next implementation

Complete the manual source contract and permission model, then wire admission,
fill-time revalidation and protection to human intent. Preserve the session,
fee/depth, reconciliation, exclusive entry ownership and qualification gates.
Exercise pause/restart, duplicates and protective exits before exposing placement.
M3 manual/live evidence remains explicitly deferred.
