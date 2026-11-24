# Paper execution

The current reviewed paper model uses up to 100% of observed depth, with durable
consumption budgets and modeled slippage. This does not guarantee real fills.
An unavailable portfolio valuation pauses new entries without closing an existing
manual holding. Protection checks the holding's bounded validation lease instead
of treating the entry-enable flag as a liquidation command. Explicit session
termination, user exits, stops, targets, maximum hold and feed/loss protection
remain active. See the [23 November audit](../../EXECUTION-AND-AGENT-AUDIT-2026-11-23.md).

## Estimated fee schedules

Fee schedules distinguish `calculation_basis: documented` (the default) from
`estimated`. Both require complete formulas/components and explicit review.
Estimated schedules must disclose `assumed` evidence; they cannot contain
unresolved `unverified` sources. A documented reviewed schedule rejects assumed
inputs. Assumptions cannot verify depth-unit mappings or reusable sale proceeds.

Each order retains the full execution configuration, including fee basis and
assumptions. Portfolio `fee_basis` is derived from filled orders for their actual
venue, rather than today's configuration or an unused venue's schedule. It is
`no_fills`, `documented`, `estimated`, `mixed`, or `legacy`; the UI labels modeled
fees. These labels describe simulation inputs, not actual broker debits.

The 23 November paper configuration uses published standard rates with explicit
cumulative-order paise rounding assumptions. BFO IPFT has an INR 1 per executed
order modeling allowance, including its GST dependency. This is an estimate,
neither an established tariff nor a guaranteed conservative upper bound. Exact
broker-statement reconciliation remains separate from paper simulation testing.
The reviewed 23 November configuration maps depth to absolute option units using
exchange protocol semantics, the raw SDK decoder and live corroboration. This is
a documented inference, not explicit SmartAPI confirmation. See the
[source review](../../SMARTAPI-DEPTH-UNITS-QUESTION.md). Two actual-data manual
paper round trips closed and reconciled. Autonomous qualification remains open.
Older increment notes below describe implementation history.

Current integration: [worker routing and protection](../../__workspace/29-paper-worker-and-protection.md). `coordinator.py` connects locked portfolio/risk admission to the ledger and matcher. Its separate worker watchdog handles real-observation fills, first-partial cancellation/protection, protective stops, prioritized exits and unresolved exposure. `portfolio.py` provides complete net liquidation snapshots. New orders retain their entire risk budget while any units remain; historical allocation is preserved by request evidence. Configuration and final QA keep activation blocked.

Latest sizing increment: [depth-aware risk sizing](../../__workspace/28-paper-depth-risk-sizing.md). `risk.py::size_entry` consumes reconciled portfolio state and actual depth budgets and returns a typed approval with a fixed entry limit. It is read-only and not yet connected to worker admission. Partial-entry flat-fee risk allocation and independent protection must be completed before routing; readiness remains false.

Latest increment: [step 3A](../../__workspace/27-paper-step-three-matching-and-fees.md). `fees.py` calculates incremental order/session charges from reviewed schedules; `matching.py` and `liquidity.py` match actual later depth using persistent consumption budgets; `valuation.py` estimates complete liquidation value or returns an explicit unavailable reason. The worker and deterministic sizing/protection integration remain step 3B. No new engine is activated automatically.

Market-style paper orders acquire one fixed protection bound from the first eligible executable quote. Stop preparation requires real trigger evidence and a later observation after latency. A price touch/LTP alone cannot fill a passive limit. Liquidity claim, per-order/session fee increment and cash/position changes commit together. Repeated receipts and feed transitions do not reset consumed budgets. Treat displayed-size increases as a disclosed model assumption, not proof of queue position.

The local upgrade helper defaults to migration `95d7e32c10ab`; `--target 84c6d21b09fa` retains explicit support for the earlier schema when applicable. Run it only from the activated environment with the local database running and the worker stopped. It takes a private backup and checks historical financial fields before committing the upgrade.

17 November 2026: [step 2](../../__workspace/26-paper-step-two-implementation.md) adds `DurableOrderLedger` in `orders.py`, typed internal requests in `contracts.py` and shared reconciliation in `accounting.py`. The local schema migration is applied. Matching and actual fee calculation remain step 3; the worker does not yet route new trades through the durable ledger.

The ledger accepts only persisted deterministic approval evidence. `DecisionRecord.result` must contain `status: APPROVED` and an `approval` matching `OrderRiskApproval`; it is not an AI reply schema. Fill bookings are internal outputs of the future matcher/fee calculator, not public user/agent inputs. Do not call them with invented market evidence.

Cash reservations remain part of account cash; subtract them and active funds holds to obtain available cash. `PaperPosition.quantity` is cumulative bought quantity and `closed_quantity` is cumulative sold quantity. Stop/limit matching, fee computation and funds-release policy are not supplied by the ledger. Historical fills retain `legacy-immediate-v1`; new positions cannot use the legacy monitor's full-fill shortcut.

SWAN owns virtual capital and uses actual Angel One observations. The current engine is the earlier immediate-complete-fill foundation. The realistic order/depth execution upgrade is in progress; its [plan](../../__workspace/24-realistic-paper-execution-plan.md) and [step 1 evidence](../../__workspace/25-paper-step-one-implementation.md) distinguish delivered code from pending behavior.

`config/paper-execution.json` defines the new versioned policy. Unset assumptions are null, quantity units are unknown, and fees are absent until sourced. Validate presence/readiness without accessing providers:

```powershell
.\market.cmd status
```

`paper_execution` reports configuration validation, effective fee versions, unresolved inputs and the pending engine. It never enables trading. Legacy account `RiskConfig.costs` still controls the old engine; do not mistake that flat approximation for the new fee rules.

Fee definitions use explicit BUY/SELL applicability and decimal rates as fractions, flat currency amounts, optional per-order caps, source evidence and rounding scope. Charge-rate rules refer to previously declared fee codes. Schedule dates are inclusive and cannot overlap within one exchange. A reviewed schedule must cover every required component (including explicit sourced zero charges where appropriate), verify account pricing and avoid unverified source claims. Calculation, per-fill accrual and settlement reconciliation will be implemented in subsequent steps.

No guessed latency or liquidity parameters activate automatically. Future readiness requires verified quote units/semantics, effective fees, session/calendar coverage, final QA and the upgraded durable engine. Paper execution must never call broker order endpoints.
