# Realistic paper execution - step 2 implementation

Updated: 17 November 2026, Asia/Kolkata.

Delivered the durable order/accounting layer of [the accepted plan](24-realistic-paper-execution-plan.md). Depth matching, current fee calculation, protective-order orchestration and autonomous runtime routing remain step 3. These are code and schema changes, not a claim of connected or behavioral acceptance.

## Durable state and accounting

- Extended `paper_orders` with lifecycle status, filled quantity, execution version, order type/time-in-force, limit/trigger prices, acceptance/eligibility/expiry/cancellation/completion times, frozen request/configuration, exit-position linkage and cash/risk reservations.
- Removed the one-fill-per-order uniqueness constraint. Fills now carry an event identity, actual observation identity, booking timestamp and execution version. `(order_id, event_key)` is unique; historical identities are backfilled without changing prices, quantities, charges or ledger amounts.
- Added `paper_order_events` with account-scoped event idempotency. Request identities reused with changed contents raise conflicts; retries do not book another fill or release a reservation twice. Per-account database locks serialize submit/fill/cancel/expiry actions. Account revisions invalidate stale risk approvals.
- Added position `closed_quantity`. Existing `quantity` retains total purchased units; remaining units equal quantity minus closed quantity. Multiple entry fills produce a weighted average; partial exits allocate booked entry cost/fees cumulatively to realized P&L. Multiple exit orders can close one position without overwriting fill history.
- Added `paper_funds_holds` for positive net sale proceeds where reuse is unverified. These reduce available cash without changing cash/equity or pretending the money disappeared. No automatic release or assumed settlement date is implemented. Release requires a later reviewed funds-policy operation with evidence; current runtime does not create holds or trades automatically.

`services/paper/orders.py` provides an internal ledger boundary for upstream approved order submission, matched-fill booking, cancellation request/acknowledgment, expiry, unfilled-order rejection and paused recovery. It has no broker client or HTTP route. It is not a market matcher, and callers must not fabricate matches to exercise it.

## Controls implemented

- New entries require reviewed versioned policy/fees, a current verified session, eligible instrument metadata, correct lot/tick inputs, an approved persisted decision/strategy, and a typed deterministic risk approval. Approval quantity, budgets, account revision and config versions must match the request. The existing legacy risk function does not emit this new approval yet; step 3 must integrate it.
- Entry budgets reserve cash and planned risk without posting fictional ledger movements. Pending entries consume position slots. Partial fills transfer risk allocation from the order to held units; terminal states release only the unfilled reservation. Actual premium/fees affect cash only when a fill is committed.
- Cancellation is a request followed by acknowledgment. The request alone retains reservations and can race a committed fill. A completed order cannot be converted to cancelled. Partially filled orders are cancelled for their remainder rather than rejected as if no exposure existed.
- Exits reserve held units against other pending exits. Entry remainders must be terminal before an exit is accepted; further buys cannot resume after protection/exit begins. Exits must preserve the durable entry execution configuration. Historical positions remain on their legacy path; no unreviewed conversion to the new fill model is performed.
- Fill booking requires a persisted matching instrument observation, matching event identity, verified depth/unit metadata, a later eligible event/receipt, freshness, valid quantity/tick/limit and the frozen fee version. Stops require an upstream persisted trigger event. Matching depth/participation, trigger generation, liquidity consumption across feeds and actual fee calculation are not supplied by this ledger layer.
- Entry fills recheck pause/daily-block state and cannot exceed the approved cash budget or consume other reservations. Exit fills cannot oversell. Fill, order, position, cash, fees, holds and lifecycle event changes commit together or roll back.
- Shared reconciliation now supports pending orders and multiple fills. It checks cash, fill-ledger pairs, fee breakdowns, position quantities/averages/P&L, lifecycle evidence, reservation/risk allocation, exit over-reservation and sale-proceeds holds. Evidence/financial checks batch account records instead of issuing a query per historical fill.
- Recovery pauses entries and returns discrepancies. Session rollover refuses unresolved orders as well as open positions. Risk-setting updates refuse pending orders. The legacy monitor explicitly leaves new durable positions to the pending matcher rather than instantly filling them under the old model. Legacy valuation marks durable positions unavailable pending step 3's depth/fee-aware valuation.
- The ledger re-reads its clock after acquiring the account lock and rechecks order/quote lifetime before fill writes, so time spent waiting for a competing transaction cannot authorize a stale fill. The injected clock follows the existing engine's clock-boundary pattern; no fake market input or replay is introduced.

## API and contracts

The authenticated workspace read response includes funds (cash, reserved cash, pending risk, restricted proceeds and available cash), order lifecycle events and funds holds. Position rows include remaining quantity; fills sort by their own booking time. Existing account isolation applies. There is no new endpoint for externally supplying fills or approving risk.

Exported JSON Schema/TypeScript for `OrderRequest`, `FillBooking` and `OrderRiskApproval`. Step 4 will build full UI treatment for pending/partial orders and funds. Merely returning new fields is not completion of that UI.

`market.cmd status` now distinguishes available durable-ledger code from the pending matching/cost engine. Syntactically completing policy JSON will not automatically enable the realistic engine.

## Migration and local evidence

Applied local migration `84c6d21b09fa`, after `31fa5ac4735a`. Backup: `.local/backups/before-84c6d21b09fa-20261117T100042234470Z.dump`, ignored by version control. The migration helper is `python -m scripts.upgrade_paper_ledger` from the activated workspace environment; it refuses remote databases, unexpected revisions and active accounts/workers, takes a private pg_dump backup, and checks a before/after fingerprint of historical financial fields within the migration transaction.

The actual database contained zero accounts, orders, fills, positions, order events and funds holds. No seeded records or paper account were created. The migration updated schema only in this database; metadata backfill behavior on a populated historical database remains final-QA work. Downgrade refuses to discard durable/multiple-fill history silently.

Verification completed:

- Python lint passes for changed modules and migration/helper.
- Backend/migration/helper type checks pass across 40 source files.
- Shared schemas regenerated; frontend TypeScript compatibility check passes.
- Local migration succeeds; historical-field fingerprint is unchanged.
- Alembic reports no pending model/schema differences.
- Read-only schema inspection confirms the fill event uniqueness pair and absence of one-fill-per-order uniqueness.

No test suite, synthetic market fixture, replay, example fill or simulated trading session ran. No provider request, broker order, autonomous worker or deployment was performed. The database was initially stopped; it was started for backup/migration/inspection and returned to its stopped state afterward.

## Next task and remaining gates

Implement step 3: deterministic current-fee estimation/accrual, depth/time-based market/limit matching, persisted stop triggers, conservative liquidity-consumption budgets, pending-entry/IOC expiry and amendment policy, independent protection of partial entries, and depth/fee-aware liquidation value. Integrate the worker with the new deterministic approval and ledger interfaces; do not feed the new ledger from legacy optimistic fills.

Before autonomous paper observation: resolve actual quantity units/partial-fill semantics, execution parameters, current sourced fee schedules/account pricing and permitted funds reuse; renew the expired broker data session; populate reviewed exchange sessions; verify data/feed behavior; and complete final QA. Those operational conditions remain unmet. There is no change to the no-real-money instruction.
