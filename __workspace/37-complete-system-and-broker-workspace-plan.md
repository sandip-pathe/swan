# SWAN: complete paper system and broker-style workspace

Prepared 18 November 2026, Asia/Kolkata. This is the detailed feature and
acceptance blueprint, not a live status tracker. Current status is maintained in
the root [project work list](../DEFERRED-WORK.md). The accepted [current product
requirements](./11-current-product-requirements.md) and [decisions](./09-decisions-and-dependencies.md)
supersede older scope details. They make source-grounded chat the primary user
surface; that is the next product build item (D23).

Implementation evidence from milestones 38–87 remains in the linked checkpoint
notes. Configuration clearance and actual-market acceptance are separate from
software implementation; consult the work list for the user's current holds.

## Target and scope

Deliver a reliable, understandable paper-trading workspace for a person, with optional autonomous operation after qualification. Users should be able to inspect markets, study candles and option data, understand account performance, and manage supported paper orders without copying contract IDs or using a terminal for normal tasks.

Reproduce useful broker workflows and information, with an original SWAN interface. Do not promise every feature of every broker or assume that a broker website's data is available through our account's API. Maintain an explicit feature/entitlement matrix. Initial execution scope remains NIFTY and SENSEX options, the existing single-owner account, and virtual execution. Real-money orders, public multi-user launch, equity delivery, derivatives outside the supported universe, banking and settlement are separate projects.

New human paper-order workflows are a proposed expansion: specify their approval and risk path before implementing them. They must not masquerade as AI-approved decisions or bypass the durable ledger.

## Current position

The app, identity, data adapter, connection diagnostics, account policy, durable virtual orders/fills, independent protection, accounting and bounded validation lifecycle are implemented. The last full test run passed 106 tests; a final 24-test focused run covered additional worker/session regressions. This establishes isolated correctness, not actual-market qualification.

Remaining known blockers: depth quantity units are unverified; NFO/BFO fee review and rounding evidence are incomplete; BFO IPFT evidence/component is missing; actual-market execution validation has not occurred. The final autonomous engine flag remains permanently false today. A genuine qualification and explicit arming path still needs implementation; passing configuration alone cannot enable it. The managed launcher deliberately starts an observer.

The existing plan's baseline findings are historical. Re-audit their completion against milestones 33–36; do not rebuild completed work or treat old README statements as live facts. Recheck authentication, diagnostics, calendar coverage and dependencies at implementation time.

## Product principles

- Market data, derived analytics, paper account numbers and agent opinions must be distinguishable. Show source, exchange timestamp, retrieval time, units and freshness where relevant.
- Missing is not zero. Closed market is not offline. Worker online is not feed fresh. An accepted order is not a fill. Pause entries is not close positions.
- Existing prices/history cannot be replaced by hardcoded examples. Test fixtures remain isolated from production. Provider-supplied historical bars are acceptable; invented market history is not.
- Chart prices are for analysis. Paper fills continue to require qualifying executable bid/ask depth; never execute at a candle close or last-traded price merely because it appears on a chart.
- Every metric needs a documented formula, scope, units, source and treatment of unavailable inputs. Avoid redundant, unexplained numbers.

## Delivery sequence and acceptance

### M1 — Reconcile the baseline and close configuration evidence

Create one issue inventory: reproduced defect or unverified requirement, owner/module, impact, remediation, proof and dependency. Categorize findings as resolved, reproducible, market-dependent or outside scope.

Verify Angel One depth semantics separately for REST and WebSocket and for both venues. Verify standard published pricing, effective dates, every charge component, tax dependencies, caps and rounding/allocation rules. Use authoritative documentation and actual account evidence where available; conflicting sources remain named blockers. A contract note may help but must not be assumed available. Separate chosen conservative simulation assumptions from measured provider facts.

Review calendar maintenance beyond the currently imported range, session renewal, reference metadata, AI budget and news delay/permissions. Identify missing configuration UI rather than silently adding defaults. Refresh safe read-only diagnostics only when implementation is authorized.

Acceptance: every currently known blocker has authoritative evidence or an explicit unresolved dependency; reviewed files and account policy agree. No guessed charge, depth multiplier or success flag.

### M2 — Finish qualification, modes and operator recovery

Define a server-owned state machine: observer → eligible for bounded validation → validation active/draining/completed → qualified for a declared scope → explicitly armed autonomous paper operation. Qualification is a separate persisted record, not a manually editable boolean. Declare the required evidence matrix before evaluating results: entry admission/fill, protection, exits, fees, reservations, reconciliation, stale/disconnected data, pause/restart and session boundaries; distinguish venue-specific evidence from shared correctness tests.

Bind qualification to account, supported venues/contracts, code/build, execution/fee/risk policy, relevant provider semantics and strategy/model versions. Define which changes invalidate each part. Authentication, current quotes and daily risk checks remain dynamic even after qualification. Replace the permanently false gate with checks against valid evidence and explicit arming; do not simply flip it.

Add authenticated worker-mode preparation and supervision through a local supervisor with a fixed command allowlist, singleton ownership and audited intent. A mode change never arms trading. If a reliable supervisor cannot be provided yet, retain a precise documented operator action and show that limitation. Stop, restart and session expiry must leave entries disabled; protection and unresolved incidents remain visible.

Acceptance: all modes have truthful UI states; bounded validation is possible without unrestricted autonomy; qualification cannot be forged by a frontend switch; a restart cannot rearm entries; normal users have clear recovery instructions.

### M3 — Establish the market-data and historical-candle foundation

Inventory each field and endpoint against official documentation and the actual account's permissions, retention terms, interval coverage, expired-contract availability, quotas and costs. Do not introduce another broker integration merely because its documentation is a useful reference.

Define normalized instruments, quotes, depth, candle bars and observation lineage. Use stable internal instrument identities and expiry-aware provider-token mapping. Add bounded historical fetching, paging, caching, deduplication, backfill and reconnect gap recovery. Prioritize visible/selected instruments; share subscriptions across charts, chain and agents rather than opening competing streams.

For candles, store interval, exchange-aligned opening time, OHLC, volume and available OI, source and final/provisional state. Keep historical-provider bars distinguishable from bars built from observed live updates. Handle cumulative-volume resets, late/duplicate/out-of-order updates, missing intervals and session boundaries explicitly. Missing intervals remain gaps; no synthetic price continuity. Index volume/VWAP must be unavailable where volume has no valid meaning. Reconcile overlapping historical and live intervals without double counting.

Acceptance: a real supported instrument loads actual historical bars, updates its provisional bar, survives reconnect, shows gaps honestly and respects quotas. Validate bar alignment and values against the same provider/session, documenting legitimate differences from broker screens.

### M4 — Design the human trading workspace

Create wireframes and a feature/field inventory before frontend implementation. Desktop layout: watchlist/search at left, selected instrument and chart in the center, details/depth/order panel at right, orders/positions/activity below. Mobile: selected instrument and chart first, dedicated tabs/drawers for depth and orders. Persist layout and watchlists without storing credentials in the browser.

Use compact, readable hierarchy and meaningful empty states. Replace generic readiness warnings with a small overall status and actionable dependency details. Keep worker, feed, market, entry permission and protection separate. Make delayed news and stale data obvious. Use accessible contrast, keyboard navigation and non-color status labels.

Acceptance: mockups cover desktop/mobile, loading, empty, closed-market, stale, offline, partially filled and unresolved-exposure states; a person can identify the contract, market freshness, actual exposure and next action without reading implementation details.

### M5 — Broker-style market tools and charts

First release:

| Surface | Planned information and actions |
| --- | --- |
| Search/watchlists | Search eligible instruments, expiry/type/strike filters, saved lists, selected instrument synchronized across panels |
| Market overview | NIFTY/SENSEX reference value, absolute/% change against the documented previous close, current session/range and freshness |
| Instrument detail | LTP, previous close, session OHLC, bid/ask, spread in price/bps, actual lot/tick size, expiry, volume/OI where provided |
| Depth | Best-five price/quantity levels, verified units, observation time and stale state; never imply complete exchange order-book visibility |
| Candle chart | Supported intervals, candle/line view, volume where valid, crosshair, OHLC tooltip, zoom/pan, range selection, auto-scale and reset |
| Chart analysis | Configurable SMA/EMA, RSI and VWAP where inputs support it; later MACD/Bollinger bands, drawings and saved layouts |
| Paper overlays | Entry/exit fills, open position, stop/target and order markers with links to ledger events; markers distinguish requested orders from fills |
| Option chain | Call/put sides around strikes, expiries, ATM marker, bid/ask/LTP, volume/OI/change in OI where sourced, spread and liquidity; direct chart/order selection |
| Option analytics | IV and Greeks with source/calculation method, timestamps and assumptions; PCR/max-pain only with declared chain coverage and methodology |
| News/context | Attributed permitted headlines, publication/retrieval time, provider delay, instrument/context links and agent citations |

Select a chart library through a small proof of concept: required interactions, performance, accessibility, license/attribution, bundling and maintenance. Confirm requirements for embedded broker-branded chart products before choosing them. Do not assume a complete broker charting package is freely embeddable.

Acceptance: numbers trace to actual or explicitly derived inputs; chart switching cannot mix instruments or intervals; indicators have sufficient-history rules; unavailable analytics show why. Loading a chart does not trigger agent generation or paper entry.

### M6 — Human paper orders and account metrics

Design a paper-only order ticket showing actual lot quantity, supported order type, limit/trigger, stop/target, estimated fees, cash/risk use and rejection reasons. Quantity selection uses actual lots. Estimate labels stay distinct from booked results. Introduce an explicit manual intent type with its own evidence and approval contract; retain deterministic risk checks, account locks, idempotency, freshness, session controls and the existing ledger. Manual and autonomous entry ownership must be explicit; default to mutually exclusive entry modes.

Deliver supported place/cancel/exit actions first. Order modification is a separately specified replacement workflow with reservation and fill-race handling; do not add a cosmetic edit button. Bulk exit submits protected exit intents and reports unresolved outcomes; it never promises an immediate fill.

Metric definitions:

- Cash, reserved cash, restricted proceeds and available cash use the existing ledger/reservation policy.
- Gross realized P&L, booked fees and net realized P&L have explicit boundaries and partial-close allocation.
- Unrealized liquidation value uses fresh executable-side prices and estimated exit costs; unavailable valuation must not become zero or silently fall back to LTP.
- Net equity, daily opening equity, daily loss use and remaining risk headroom reconcile under documented session rules.
- Exposure, open/pending units, position count, average fill, planned risk and protection state reflect actual remaining quantities.
- Trade statistics include trade count, win rate, average win/loss, expectancy, profit factor, drawdown, slippage and holding time with declared sample size and net/gross basis. Undefined ratios remain unavailable; avoid annualized claims from tiny intraday samples.

Add order/fill timelines, fee drilldowns, daily equity/P&L history, journal filters and exports. Paper funding/reset, if provided, is an explicitly reviewed ledger operation preserving history; it cannot erase losses through settings.

Acceptance: every displayed account total reconciles to authoritative ledger records; concurrent clicks/retries cannot duplicate orders; partial fills and exits update all views consistently; manual orders never acquire false AI approval.

### M7 — Agent transparency, strategy evaluation and reports

Expose actual evaluation inputs, evidence age, permitted news context, model/strategy version, review outcome, typed proposal, deterministic risk result and execution outcome as a linked timeline. Distinguish legitimate WAIT/rejection from provider failure, exhausted budget or absent data. Implement/verify end-of-session summaries with reconciled figures, incidents and unresolved checks.

The accepted current product requirements also make a source-grounded user chat
the primary app surface. Persist conversations and let chat retrieve relevant
workspace records through scoped read tools, preserving source, timestamp,
freshness and unavailable states. The only initial control is an audited,
idempotent “stop trading today” command. Chat cannot place/alter orders, change
risk or strategy, access provider credentials, or affect worker monitoring.

Strategy research track: define the existing predefined strategies and their
versioned evidence, option-selection rule, entry predicate, invalidation, holding
limit and exits. When none fit, agents may research and propose a new versioned
strategy with supporting evidence and evaluation; proposal alone cannot promote
it to execution. Do not enable a strategy merely because it is newly generated.
Continue to require liquidity, spread, freshness, risk and session eligibility;
no forced trade to satisfy a demo.

Separate research from execution qualification. Evaluate strategies on permitted historical data with fees, spread/slippage assumptions and out-of-sample splits where appropriate. Candle-only history cannot validate depth-based fills, and insufficient expired-option history limits conclusions. Any deterministic historical research harness is isolated from production; it is proposed new scope requiring its own specification. Compare paper outcomes against a baseline and report uncertainty/sample size. AI may propose and explain; it cannot override risk gates or declare itself profitable.

Acceptance: every executed strategy has traceable genuine evidence and approvals; spending is bounded and visible; reports distinguish software correctness from trading performance.

### M8 — Integrated QA and controlled market qualification

Test the combined system with isolated fixtures and actual permitted observations. Cover provider throttling/session renewal, chart backfill/gaps/time zones, ownership, stale responses after instrument switches, duplicates/order races, partial fills, fee rounding, daily rollover, restart/reconnect, expired strategies, loss limits, flattening and unresolved exits. Include dependency/security review, realistic subscription load, browser responsiveness/accessibility, backup/restore and recovery drills.

During verified open sessions, collect the preregistered bounded validation evidence for both venues through the same durable execution path. Record unobserved scenarios as unobserved; do not manufacture fills or agent decisions. Qualify only the supported scope whose criteria passed, and require explicit paper arming afterward.

Acceptance: no unresolved critical execution/accounting/ownership defect, actual-market evidence meets the declared matrix, screens and reports reconcile, and recovery instructions have been exercised. No real broker orders.

### M9 — Supervised paper observation and handover

Run the agreed one-to-two-week paper observation period after qualification, with daily reconciliation, dependency/budget checks, incident review and strategy-performance reporting. Define stop conditions and escalation before starting. Fix findings and repeat affected qualification checks when inputs change.

Acceptance: sustained operational evidence, documented limitations, reproducible startup/recovery and a usable daily workflow. Profitability is evaluated separately and is not guaranteed by readiness.

## Extended broker feature backlog

Inventory price/indicator alerts, additional drawing tools, multi-chart layouts, scanners, strategy builders, baskets, payoff scenarios, trade tagging, scheduled reports and additional export formats. Each gets explicit data, licensing, execution and usability dependencies before scheduling. Basket/multi-leg execution and margin-aware selling require materially new risk/accounting semantics; they are not simple UI additions. Broader asset classes, corporate actions, demat holdings, live broker positions, funding and real execution remain separately scoped. Unsupported features must not appear as working buttons.

## Engineering strategy

Reuse and extend the current adapters, coordinator, ledger, risk engine, identity and dashboard. Keep ingestion, historical storage, derived analytics, chart delivery, paper execution, agent analysis and supervision as clear responsibilities. Send normalized backend data to the browser; broker credentials and fee/risk decisions stay server-side. Share one instrument selection and coherent snapshots across views. Use push/coalesced updates for visible market data and bounded REST backfill; setup diagnostics remain deliberate actions, not provider calls from ordinary polling.

Deliver a small end-to-end slice before broadening: search one actual contract → load history → show fresh depth → inspect risk → submit a permitted paper intent → observe fills/protection → reconcile and report. Expand to the complete chain and additional analytics only after this path is correct.

## Scheduling and completion tracking

The active product build is D23: make source-grounded chat the primary mobile
surface over the existing market, account and agent records. Then specify and
deliver the accepted strategy lifecycle as a separate increment. Additional
analytics and order types stay behind that path. Market access, provider evidence,
qualification and supervised observation remain separately held work; consult
the root [status ledger](../DEFERRED-WORK.md) before attempting them. Do not use
this historical milestone sequence as a claim of current completion.

## Reference sources

- Angel One SmartAPI market-data documentation: https://smartapi.angelone.in/docs/MarketData
- Angel One SmartAPI FAQ: https://smartapi.angelone.in/faq
- Kite Connect quotes/instruments, as a reference for field/workflow inventory only: https://kite.trade/docs/connect/v3/market-quotes/
- Kite Connect historical candles, as a reference for bar contracts only: https://www.kite.trade/docs/connect/v3/historical/

These sources motivate the feature/data audit. They do not establish entitlement, full feature parity, current pricing or the availability of every requested field through the existing Angel One account.
