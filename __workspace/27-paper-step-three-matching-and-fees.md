# Realistic paper execution - step 3A: fees, depth matching and valuation

Updated: 17 November 2026, Asia/Kolkata.

Step 3 is split into two implementation increments. This increment implements fee accrual, depth matching, trigger preparation, durable liquidity accounting and liquidation estimates. Step 3B will connect deterministic risk approval and independent protective execution to the worker. The full readiness gate in [the accepted plan](24-realistic-paper-execution-plan.md) remains open.

## Delivered components

- `services/paper/fees.py`: effective-dated schedule inputs, cumulative order charges, chronological session-level rounding allocation, caps, side-specific rules and dependency-based tax bases. Every fill pays the increase in the applicable rounded total, so a flat-per-order brokerage fee is not charged anew on each partial fill. Session rounding is allocated to the currently filled order; prior immutable allocations are preserved. Charge-based rules use actual cumulative upstream charges, including their declared rounding. This basis must match reviewed broker/statutory evidence before configuration is approved.
- Missing components in previously booked fee history are rejected rather than treated as zero. Amounts/rates come only from reviewed schedules. Negative incremental fees are rejected for explicit investigation/correction instead of silently rewriting old financial records. INR rounding increments must be whole paise.
- `services/paper/liquidity.py`: unit conversion based on verified metadata; side-specific adverse tick rounding; bounded displayed-size participation; and persistent level-capacity calculations. Additional adverse slippage is a declared assumption, separate from spread/depth effects.
- `services/paper/matching.py`: matching eligible actual best-five observations against stored orders, walking best executable prices first, respecting fixed price bounds, available capacity, whole-lot versus verified unit granularity, and remaining cash after fees. Fees/capacity are recomputed under the ledger's account lock before booking. Stale concurrent proposals fail rather than trusting the earlier read.
- `DurableOrderLedger.prepare_match`: real stop-trigger evidence, a fresh latency interval after the trigger, and a fixed bound for market-style paper orders. Stops wait for a later observation before execution and use its actual depth; stop-limit gaps can leave the order pending. They are not filled at an assumed trigger price.
- Market-style protection anchors once to the first eligible executable quote. Its percentage is configurable and mandatory for reviewed policy. The bound rounds inward; fill slippage rounds adversely. This is an explicit SWAN paper rule, not a claim that its anchor reproduces Angel One's exact market-price-protection implementation. Once set, the bound is not moved to chase the market.
- IOC processing cancels the unfilled remainder after the first eligible usable-observation matching attempt, including when a matching error occurs and persistence remains available. An outage that prevents acknowledgment still leaves a durable unresolved order. Waiting for an observable eligible book is a paper-model limitation, not a measured exchange IOC acknowledgment.
- `services/paper/valuation.py`: complete liquidation estimates from fresh bids/depth, remaining paper liquidity capacity, modeled adverse execution and estimated exit fees. Insufficient depth, unknown units/timestamps, unavailable budgets or invalid fee policy return an explicit unavailable value with covered quantity. A partial-depth subtotal is not presented as full account equity. The function does not book a fill.

## Persistent liquidity semantics

New `paper_liquidity_levels` rows scope capacity to account, session, instrument, consumption side and actual raw price. `paper_liquidity_uses` link each fill to consumed level quantity. Capacity, usage, fill, fees, cash, position and lifecycle evidence commit together in the ledger transaction.

The initial capacity is the rounded-down configured fraction of displayed units. Later evidence can add capacity only for a positive displayed-size increase in a newer observation from the same feed source. An identical observation, equal timestamp, reconnect or source change cannot replenish the budget. Switching feeds retains the more conservative displayed baseline; disappearing outside best-five does not reset it to zero. A changed execution/fee model cannot create a fresh budget for the same account session.

This is a disclosed conservative depth model. Displayed increases do not prove queue position or guaranteed liquidity, and partial quote feeds do not reveal hidden replenishment. The implementation makes no precise exchange-queue claim. During observation, track fill scarcity and coverage alongside performance so a conservative model is not mistaken for actual exchange behavior.

The ledger verifies raw depth price, available participation capacity, additional-slippage calculation, tick/limit constraints, fee increment, and matching observation identity before committing. Supporting evidence requires actual exchange-feed timestamps and declared depth provenance. Fee/execution configuration is frozen across the account session; legacy and new execution models cannot be mixed within that session. Reconciliation checks fill-to-liquidity usage, raw-price evidence and cumulative consumed totals.

Provider quantity units remain unknown at normalization until verified. The matcher can apply reviewed unit metadata by producing a separately identified metadata-enriched snapshot; prices, quantities, timestamps and market-event identity remain unchanged. This enrichment does not create a new liquidity budget.

## Source review and configuration

Sources reviewed on 17 November 2026:

- [NSE circular FA73061](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf), dated 27 February 2026, revises the exchange/IPFT split effective 1 March 2026 while preserving the combined member outflow. The source table was also requested as a PDF screenshot. This is why exchange and IPFT are separate configurable components rather than a historical flat turnover assumption.
- [NSE levies](https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies): reviewed the published side/product distinction for stamp duty, turnover fees and STT. Actual effective dates and charge bases remain schedule inputs.
- [Angel One published charges](https://www.angelone.in/exchange-transaction-charges): reviewed per-order brokerage, account offers and current exchange/statutory components. Account tariff/promotions, GST basis and rounding still require confirmation before approval; the public table is not a substitute for account evidence.
- [SmartAPI documentation](https://smartapi.angelone.in/docs): the indexed first-party material says market orders are converted to price-protected limits. Exact current account/venue behavior has not been exercised. SWAN's explicit paper protection bound must not be labeled an observed Angel One execution rule.

No guessed live fee rates or fabricated latency/liquidity settings were inserted. `config/paper-execution.json` remains unreviewed, with required choices explicitly absent. Added `market_protection_bps` as another unresolved policy parameter. Effective NFO/BFO schedules, source provenance, unit/partial-fill semantics and funds-reuse rules must be resolved before activation.

The fee engine can calculate a supplied reviewed schedule, including order/session rounding, but production rate configuration and parity against actual account charges are not validated. That distinction is visible in `market.cmd status`.

Resume is now enforced through readiness in the authenticated API and worker/store entry paths. A manual resume cannot route new entries into the older immediate-fill implementation while step 3B is pending. Existing-position monitoring still runs before the entry-readiness gate. This is an actual runtime gate, not just a status label.

## Local migration and verification evidence

Applied migration `95d7e32c10ab` after a private backup at `.local/backups/before-95d7e32c10ab-20261117T104040726973Z.dump`. The before/after financial fingerprint is unchanged. The actual database has zero accounts, orders, fills, positions and liquidity rows. No account or example trade was created to make verification appear complete.

The migration refuses pre-existing nonlegacy fills without a reviewed liquidity-evidence conversion. It cannot invent missing historical consumption records. Downgrade also refuses to discard existing liquidity-use history. The local upgrade helper now supports explicit supported revision targets and defaults to the current liquidity migration.

Verification completed: Python lint; type checking across 44 source files; shared schema regeneration and frontend TypeScript compatibility; successful local schema migration; Alembic reports no model/schema differences; read-only revision/row inspection; and actual local operator status. The database was stopped initially and was returned to that state after verification.

No test suite, synthetic market fixture, replay, fake agent response, provider market-data request or paper trading session was run. No broker orders, worker activation or deployment occurred. Static/schema checks do not establish numerical or operational acceptance of the new matching engine; final QA remains deferred by user instruction.

## Next increment - step 3B

Sizing component delivered in [increment 28](28-paper-depth-risk-sizing.md). The portfolio loader, transactional admission and protective worker routing below remain pending.

1. Replace legacy entry estimates with deterministic depth/fee-aware whole-lot sizing and typed `OrderRiskApproval`, including current account revision, pending reservations, net liquidation equity and daily headroom.
2. Route accepted entries and observed order updates through the new ledger/matcher. Add bounded, coalesced processing so quote bursts and fee work cannot starve protection.
3. Protect the first partially filled units immediately; cancel entry remainders, reconcile cancellation/fill races, create exits for actual held units, and prioritize stops, daily-loss protection, maximum holding time, invalidation and pre-close flattening independently of agents/news.
4. Integrate complete/uncertain liquidation estimates, outstanding-order recovery and unresolved-exposure incidents into account state. Define cancel/replace priority and verified funds-hold release without rewriting historical records.
5. Keep new entries blocked until calendar, session, execution/fee configuration, all dependent provider settings and final connected QA are ready. Use actual market sessions for the requested observation period.
