# Durable paper entry sizing

Updated: 17 November 2026, Asia/Kolkata.

This increment delivers the deterministic sizing component of step 3B. It does not complete worker routing or enable trading.

Follow-up: [increment 29](29-paper-worker-and-protection.md) connects locked portfolio loading, admission and independent protection and adds whole-budget partial-entry risk allocation. The remaining-work descriptions below record the state at this increment's delivery.

## Implemented

`services/paper/risk.py` sizes whole lots using actual best-five ask observations, remaining persistent liquidity capacity, verified quantity units, configured participation, adverse tick rounding and the reviewed exchange fee schedule. Missing budgets are unavailable; an explicitly empty budget mapping means the caller verified that no capacity has been consumed. Loaded levels must match account, day, instrument, side, raw price and configuration version.

The calculator derives a fixed tick-aligned entry limit bounded by the strategy ceiling and configured price protection. It reserves cash at that limit for every unit, rather than assuming that the best ask will remain available. The later order router must submit a LIMIT order with this limit; a market order that chooses a new anchor later is outside this approval.

Sizing respects available cash, trade risk, daily-loss headroom and already reserved risk. The caller must supply reconciled net liquidation equity, cash excluding pending reserves and restricted proceeds, and the position/pending-order slot count. An unavailable valuation must set `valuation_fresh=False`; this component does not load or manufacture portfolio marks.

Fee allowances round each component upward and propagate those upper allowances into dependent taxes. This bounds session rounding without inventing fee history. Unit-level conservative premium rounding also covers fragmented-fill premium rounding. Booking continues to calculate actual incremental fees; the reservation allowance is not a booked fee or UI charge.

The result includes a typed `OrderRiskApproval` with quantity, cash/risk budgets, account revision, risk/execution configuration versions, evidence IDs and a bounded expiry. An approval whose remaining lifetime does not cover assumed latency is rejected. Returning this object does not save a decision, reserve funds or submit an order.

Shared strategy/session/evidence/liquidity admission checks now live in `services/risk/engine.py::entry_problem`. Historical immediate-fill sizing continues to call those checks and retains its old cost model. New sizing does not use that cost model.

## Limits and next implementation

Stop-based planned risk is an estimate, not a maximum loss guarantee. A later gap, disappeared bid or protected order that cannot execute can produce a larger loss. Protection must use subsequent real observations; the estimated stop price must never be booked as a fill.

Before connecting this calculator to order submission, implement the locked portfolio/valuation loader, persist real evidence and the approval, and check the account revision at admission. Reconcile partial-entry risk allocations: prorating a whole-order risk budget can understate the first partial fill's flat fees. The router must retain enough reserve through cancellation/fill races and protect the first held units independently of agent calls. These are outstanding work, not accepted behavior.

Next: connect the worker to admission, ledger and matcher; handle pending orders on recovery; implement bounded independent protection and exits; preserve unresolved-exposure incidents. Final QA, actual calendars, reviewed execution/fee inputs and provider readiness still gate activation.

## Verification

Ruff and backend type checking are run for this increment. No tests, fixtures, provider calls, paper fills, real broker orders, worker activation or deployment are part of this increment. Static checks do not establish behavioral or numerical acceptance. No database schema change is required.
