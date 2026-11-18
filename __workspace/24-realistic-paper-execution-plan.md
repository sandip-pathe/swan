# Realistic paper execution: accepted direction and implementation plan

Date: 17 November 2026, Asia/Kolkata.
Status: implementation is underway. Steps 1/2 and step 3A code evidence are linked below; autonomous sizing/protection routing, configuration and behavioral acceptance remain pending. This plan does not enable trading.

Latest implementation: [step 3A matching/fees/valuation](27-paper-step-three-matching-and-fees.md). Step 3B will integrate deterministic sizing and independent protective execution with the worker.

Implementation update: [step 2 storage/accounting delivered](26-paper-step-two-implementation.md), with local migration and static/schema verification on an empty trading database. Execution matching/fee application and behavioral acceptance remain pending; step 3 is next.

Earlier implementation update, 17 November 2026: step 1 contracts/configuration code delivered; [evidence and unresolved connected/configuration checks](25-paper-step-one-implementation.md). The implementation steps below remain unchecked until their full completion evidence exists.

## Accepted product decision

SWAN owns a persistent virtual-cash account and its paper orders, fills, positions and accounting. Angel One supplies actual market observations and instrument metadata. The existing agents propose trades; deterministic strategy, risk and execution components decide whether, when and how the paper order can execute. No external paper provider or paid virtual-credit subscription is required.

The user explicitly accepts simulated execution and virtual money. This does not reverse the previous exclusion of synthetic market quotes, generated news, fabricated agent responses, seeded trades, or the replay runner. Any execution parameter that is assumed rather than observed must be labeled and versioned.

Keep one owner and one Angel One data connection. Preserve the agreed scope: long NIFTY/SENSEX calls and puts, intraday scalping, listed expiries from today through seven calendar days, including same-day expiry. Close before the verified session ends; selecting a contract expiring later does not authorize overnight holding. Short options, spreads and overnight strategies are outside this increment.

Keep initial virtual capital at the existing INR 100,000 default, risk per trade at 0.5%, daily loss cutoff at 2%, and one active position. These remain configurable product defaults, not financial recommendations. Pending entries and partially filled positions consume that position slot and reserve cash/risk. Do not silently increase capital when a lot is unaffordable. Account resets require a recorded explicit action and start a new evaluation period; never silently refill losses.

Real-money Angel One execution remains future product scope through a separate adapter. Paper functionality must have no path that places an actual broker order. AI cannot alter balances, execution assumptions, charges or risk settings.

## What the code already provides

Inspection baseline, not a statement of connected acceptance:

- `services/paper/engine.py`: account locking, durable decision identities, fills, cash movements, positions, session baseline, monitoring, pending exits and reconciliation. Entries currently fill immediately and completely.
- `services/risk/engine.py`: whole-lot sizing, quote checks, spread/depth constraints and cost-aware planned risk. This must separate an executable price estimate from an actual paper fill event.
- `services/core/contracts.py`: instrument/quote/config contracts and a simplified cost model using flat-per-fill and turnover charges. This is insufficient for side-specific Indian option charges and per-order brokerage across partial fills.
- `services/core/models.py`: paper orders, fills and positions. Current reconciliation assumes one full entry fill and one full exit fill; schemas and queries need migration before partial fills.
- `services/market/stream.py`: parsing of multiple depth entries but normalization retains only the best bid/ask and associated size. Preserve the available depth and its provenance before using it for multi-level fills.
- `services/worker/runtime.py`: independent monitoring and REST recovery paths. Integrate order progression without letting agent/news calls block exits.

Do not delete or rewrite historical fills to match new accounting. Introduce explicit execution/cost versions; any needed balance correction is a separately explained ledger event. Existing records remain attributable to their original model.

## Realism contract

### Market evidence and time

Store instrument identity, exchange, expiry, strike, CE/PE, lot size and tick size from actual metadata. Preserve provider event time, local receive time, feed source and sequence when supplied. Record unknown fields as unavailable. Confirm quote quantity units before converting lots/units.

Normalize the available bid/ask depth without inventing missing levels. Reject crossed, invalid, stale, out-of-order or future-dated observations according to the verified feed semantics. A receipt timestamp does not prove an old quote is current. Deduplicate REST/stream observations where possible and mark provenance limitations.

An execution can use only evidence received after the order becomes eligible. Persist submitted/accepted/eligible/fill/cancel timestamps. Measured SWAN processing time and assumed broker/exchange latency are separate fields. Use deterministic, versioned latency assumptions until independently calibrated; do not claim measured exchange latency. Never fill an order retrospectively from the snapshot used to propose it.

### Orders and fills

Persist order states: submitted, accepted/open, partially filled, filled, cancel requested, cancelled, rejected and expired. Cancellation can race a fill; record the committed sequence and leave already filled units as exposure. Reject invalid tick/lot/price/contract/session inputs before acceptance. Recheck risk and reserve cash atomically at acceptance, then enforce limits at each fill.

Market buys consume eligible observed asks; sells consume bids. Fill price is a volume-weighted result of consumed displayed levels, rounded against the trader where required. Apply a configured conservative participation cap to displayed size. Do not assume hidden liquidity or fill unlimited volume at the best quote. Incomplete depth restricts executable size rather than triggering an optimistic fallback.

Partial fills are permitted, including a remainder smaller than one lot where actual exchange semantics allow it; submitted quantity must respect lot rules. Verify that behavior before activation. Reserve/release cash and risk for unfilled quantities and update position weighted-average cost for filled units. Track liquidity consumed per observation across SWAN orders and never reuse the same snapshot as fresh liquidity. Unknown queue turnover or refreshed displayed liquidity must not be presented as independent executable volume.

Marketable limit orders execute only at prices satisfying their limit. Passive limits do not fill merely because LTP or a candle touches their price: require a later eligible executable quote that crosses the limit, bounded by observed liquidity. Queue position is unknown; do not simulate a precise queue or claim actual queue priority.

Stops are triggers followed by execution under the selected order policy, never guaranteed fills at the stop price. Gap exits use the next eligible bid/depth. Define stop-market and stop-limit handling separately; availability in a future real adapter must be checked against broker/exchange rules. Targets use an explicit limit/trigger policy. Partial entry protection starts with the first fill, cancels any remainder when an exit starts, and prevents repeated sells from exceeding held units. Any bracket/OCO behavior is local paper-engine behavior and must be identified as such.

Specify time-in-force, pending-order lifetime and amendment priority in configuration. Pending entry orders expire at entry cutoff, decision expiry or strategy invalidation, whichever occurs first. End-of-session handling cancels entry remainders and requests exits. Data loss leaves positions unresolved with an incident; it never creates a closing fill or uses settlement as an intraday exit. Restart reconciles orders, fills, reservations and positions, resumes protection first, and leaves new entries paused.

### Costs, affordability and valuation

Replace the flat fee approximation with an effective-dated, versioned fee schedule for the selected exchange/product/account. Record source URL, date checked, effective period, side, calculation basis, rounding and account-specific brokerage settings. Verify current Angel One pricing plus NSE/BSE and applicable statutory schedules when implementing; no unverified rates are prescribed here.

Itemize brokerage, exchange transaction charges, STT, SEBI turnover fees, stamp duty, GST and any other verified applicable charges. Apply buy/sell bases correctly, handle order-level brokerage across multiple fills without charging the full order fee on every partial fill, and handle order splitting only under verified freeze/size rules. Reserve estimated costs, then reconcile booked actual model costs. Version any correction; never silently recalculate old reports.

For this long-option scope, reserve premium plus applicable costs and preserve settlement/available-funds distinctions where relevant. Do not invent a SPAN margin model for short options that SWAN does not support. Verify how sale proceeds are treated before allowing reuse; block unsupported assumptions. Size against affordable whole lots, stop risk including costs and conservative execution allowance, remaining daily-loss headroom and pending reservations. Gaps can exceed planned stop risk.

Mark liquidation value against fresh executable bid/depth less estimated exit costs, subject to visible liquidity. Insufficient depth or stale data means uncertain liquidation value, with last-known values labeled. Track cash, reserved cash, available cash, realized P&L, unrealized P&L, total charges and net liquidation equity separately. Show session loss and open risk; do not count reserved cash twice. Uncertain valuation blocks new entries but never disables exit attempts.

Spread and depth movement already affect fill prices. Any additional adverse execution allowance must be explicit and must not double-count those effects. Report spread cost, depth impact, latency movement, fees and assumed additional slippage separately where evidence permits; do not manufacture an exact attribution when it cannot be established.

## Five implementation steps

| Step | Work and primary locations | Completion evidence |
| --- | --- | --- |
| 1. Evidence and configuration contracts | Extend market/core contracts to retain depth, clocks and quality; verify quantity units, sessions, instrument coverage, feed limits and retention permissions. Create versioned execution and fee config with source provenance. Audit current configuration safely without printing secrets. | Actual NIFTY and SENSEX option observations mapped to verified contracts; missing capabilities recorded; explicit activation blockers; sourced fee configuration. |
| 2. Durable order engine and ledger | Migrate core models; implement state transitions, multiple fills, reservations, idempotent event identities, cancellation/amendment races and reconciliation in paper/risk modules. Preserve historical records and version identity. | Orders, fills, held units, reserved/available cash, fees and ledger reconcile; duplicates/restarts cannot create cash, fills or oversells. |
| 3. Conservative execution and protection | Integrate latency eligibility, depth consumption/participation, market and limit fills, stops, pending-entry expiry, partial-entry exits and independent monitoring. Add cash/cost estimation and session/expiry enforcement. | Each fill identifies real supporting observations, execution configuration and timestamps; liquidity is not reused; stale/missing data cannot create a fill; unresolved exits remain visible. |
| 4. Agents and product interface | Route existing structured agent decisions through the common risk/execution intent; keep deterministic controls authoritative. Extend authenticated API/dashboard/journal for pending/partial orders, reasons, fill history, costs, uncertainty, virtual cash and agent evidence/version traces. | One trace connects real inputs, agent proposal/review, risk decision, order lifecycle, ledger and displayed result. Pause blocks entries while protection continues. No invented empty-state output. |
| 5. Final QA and local observation | Per user direction, defer new automated tests and broad QA until this stage. Verify numerical accounting, order races, partial fills, data loss, duplicate events, restart, pre-close behavior and API/UI reconciliation. Then observe actual market sessions locally with controlled virtual capital. | Documented final-QA results, read-only broker-call boundary review, latency/freshness and reconciliation reports; only then enable autonomous paper observation. No deployment is included. |

Dependencies are sequential: contracts/configuration before migrations and matching, durable orders before partial fills, and reconciliation/connected QA before autonomy. Build UI and adapter contracts alongside backend work where independent. Implementation-first is not evidence that operational readiness has passed.

Keep existing isolated numerical tests. No synthetic market fixture, replay runner, seeded paper trade, or synthetic agent reply is introduced. Final QA may use controlled pure-domain checks without presenting manufactured market/provider output as real; connected acceptance and the observation record use actual provider inputs. Do not place an actual broker order as part of paper QA.

## Agent observation and reporting

Run for the user's requested one-to-two-week observation period only after readiness checks. Preserve all WAIT/rejected decisions as well as executed trades. Record model/prompt/strategy, cost and execution versions so changes start separate cohorts. Count sessions/trades and market-data gaps; do not combine changed versions into one headline performance claim.

Assess contract/expiry/lot correctness; evidence freshness; invalid proposals and rejection reasons; cash/risk violations; entry/exit delay; pending and partial orders; duplicate/missing actions; unresolved exposure at close; and reconciliation discrepancies. Report gross and net P&L, charges, drawdown, exposure time, fill rate and the effect of explicit execution assumptions. Include observation coverage and unavailable metrics alongside the results.

Do not optimize the simulator to make agent returns look better. Freeze configuration within each observation cohort. Investigate whether returns disappear after costs or under more conservative execution assumptions. One-to-two weeks is useful for operational defects and agent iteration; it does not establish strategy profitability or live readiness.

## Access, outstanding choices and next task

No new paper-provider key or payment is required. Reuse the existing local Angel One setup for read-only data, renewing sessions through the existing private workflow. Existing OpenAI/news/Firebase dependencies still need valid configuration for their own features; this decision does not certify those dependencies as ready. Never paste secrets into the plan or chat.

Before activation, verify fee schedules, feed semantics/limits, permitted evidence retention, exchange sessions, quote freshness/depth thresholds, execution latency/participation configuration, and account/funds rules. Label assumptions explicitly. Obtain actual latency observations before claiming scalping suitability. No secret values, new rates or external entitlement claims were researched in this planning-only change.

Current implementation follow-up: [increment 29](29-paper-worker-and-protection.md) connects admission, durable matching and independent protection after the quote/configuration, ledger and sizing increments. Next: authenticated lifecycle/uncertainty presentation, reviewed configuration/dependencies and final QA. Behavioral acceptance remains pending; no autonomous observation or deployment has started.

## Relationship to earlier documents

This accepted decision supersedes the external-provider-first recommendations in documents 22 and 23 and the immediate-complete-fill execution policy in document 05. The older foundation remains implementation history, not evidence that the enhanced engine is complete. The high-level build plan and roadmap remain applicable with this five-step plan governing paper-engine enhancements. The original PRD remains historical source material.
