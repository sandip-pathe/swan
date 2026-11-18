# Risk and paper execution

17 November 2026 update: the user accepted SWAN-owned realistic paper execution with Angel One real market data. [The current enhancement plan](24-realistic-paper-execution-plan.md) supersedes the immediate-complete-fill policy below and specifies persistent orders, partial fills, depth/time evidence, reservations, versioned itemized charges and recovery. The following describes the earlier baseline; those enhancements are not yet implemented.

## Defaults from the PRD

- Initial paper capital: INR 100,000.
- Maximum planned risk per trade: 0.5%.
- Daily loss cutoff: 2%.
- Maximum simultaneous positions: one.
- New-entry quotes older than 10 seconds: reject.
- Actions: buy a call, buy a put, or wait; no short option positions.

## Proposed deterministic entry checks

Require enabled trading, open session, pre-cutoff time, healthy dependencies, reconciled account, valid decision, matching instrument/action, valid expiry and instrument metadata, complete required metrics, fresh quotes, non-crossed positive bid/ask, acceptable spread/liquidity, valid stop/target, available capital, remaining daily risk capacity, and position limit.

Liquidity thresholds, proposal lifetime, cutoff times and exchange calendars must be configured and verified before live-data operation. Never silently select guessed thresholds or lot sizes.

## Position sizing

Proposed base: current positive account equity, capped at configured paper capital. Trade risk budget = base × configured maximum trade risk. Further cap by remaining daily loss allowance after accounting for current losses and reserved open-position risk.

For each whole-lot candidate, compute loss at stop using the conservative entry/exit price model plus round-trip fees and slippage. Select the largest quantity satisfying both risk and premium affordability. Recompute costs for each candidate because fees may be nonlinear. If one lot does not fit, return WAIT/rejection; never round up.

Example without costs: INR 100,000 × 0.5% = INR 500 planned risk budget. The executable size may be zero once lot size, stop distance, fees and capital constraints are included. Planned stop risk does not guarantee a maximum realized loss during gaps or missing quotes.

## Fill and marking model

- Long entry fills at current ask plus adverse configured slippage, rounded against the trader to the instrument tick.
- Long exit fills at current bid minus adverse configured slippage, subject to a valid nonnegative price and tick rules.
- Reject invalid/crossed/missing quotes; do not fill at a stale last-traded price.
- product uses complete immediate fills for a constrained paper size; no simulated queue priority or unsupported depth claims. Reject sizes beyond the configured liquidity model.
- Mark long positions at an executable bid when fresh. If unavailable, show last known valuation as stale and flag equity uncertainty.
- Costs are an itemized, versioned simulation configuration verified against current applicable official schedules before use; reports disclose assumptions.

## Exits and daily loss

Evaluate stop and target against executable bid quotes, independent of the LLM. Gaps fill at the available quote under the model, not automatically at the configured stop. If data cannot establish trigger order, use a documented conservative rule and flag ambiguity.

Proposed daily-loss basis: session-opening equity minus current net liquidation equity, inclusive of realized/unrealized results and booked costs. Persist the session baseline; restarting must not reset it. At the limit, block entries immediately and request flattening at the next valid executable quote. Missing quotes leave an exit pending and generate a visible incident; never fabricate an exit.

Accepted: select listed contracts expiring in 0–7 calendar days, including same-day expiry, using verified Angel One metadata. Default to blocking entries 20 minutes before verified session close and requesting flattening 10 minutes before close. These configurable offsets are engineering defaults, not exchange rules. Never intentionally hold overnight or wait for expiry. Unresolved exits remain visible, raise an incident, and block new entries.

## Pause and recovery

Pause blocks new entries, including in-flight proposals at commit time. It does not stop position monitoring or cancel necessary exits. Distinguish pause from a future explicit close-position command.

On restart/network recovery, load ledger, positions, session baseline and risk state; reconcile; obtain fresh quotes; resume exits first. Proposed default is paused after restart, requiring explicit user resume. Duplicates, failed retries, and exit races must not mutate the ledger twice.
