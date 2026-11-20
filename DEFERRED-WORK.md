# Deferred-work ledger

Updated 20 November 2026. This is the end-of-build review list. An implemented
feature is not accepted evidence of live behavior. Keep IDs stable; close a row
only with a linked result, test or explicit scope decision. Every future slice
must add newly skipped/blocked work here and update resolved rows.

Statuses: **User-deferred** = explicitly skipped for now; **Evidence-blocked** =
required facts/acceptance missing; **Planned** = accepted scope not yet delivered;
**Review needed** = the remaining scope needs a concrete acceptance decision.
Do not interpret these statuses as permission to log in, arm trading or weaken gates.

| ID | Work / milestone | Status and reason | What closes it | Source |
| --- | --- | --- | --- | --- |
| D01 | M3 live candle, quote and reconnect acceptance (both supported venues) | User-deferred: user asked to skip manual/live evidence and continue building; market/session access unavailable during recent slices | Bounded open-market provisional-bar/value comparison, stream gap/reconnect and history overlap results, with actual timestamps and honest gaps | [M3](./__workspace/41-m3-market-data-foundation.md), [finish path](./__workspace/51-quote-order-and-finish-path.md) |
| D02 | Fresh broker login / connected diagnostics for acceptance | User-deferred: do not request login or perform live refresh for current implementation; session may be expired | When acceptance resumes, user renews sign-in if needed and deliberate read-only diagnostics establish current access; earlier successful login/refresh remains historical evidence | [resume](./RESUME.md) |
| D03 | Depth quantity semantics for NFO/BFO REST and WebSocket | Evidence-blocked: units/mapping not fully verified | Authoritative provider evidence and bounded observed checks for each transport/venue; record mapping provenance and invalidate affected qualification | [master plan](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D04 | Effective execution fees, tax dependencies, caps, rounding/allocation | Evidence-blocked: source/rounding review incomplete | Reviewed authoritative effective schedules and representative calculations for both venues; distinguish conservative assumptions from measured facts | [master plan](./__workspace/37-complete-system-and-broker-workspace-plan.md), [resume](./RESUME.md) |
| D05 | BFO IPFT component/evidence | Evidence-blocked: component/source evidence unresolved | Resolve applicable fee and effective-date evidence; update reviewed configuration and tests without inventing a zero fee | [resume](./RESUME.md) |
| D06 | Calendar coverage after 30 November 2026 | Evidence-blocked for later dates: current reviewed coverage ends then | Extend from official exchange calendars and verify normal/closed/special sessions before testing later dates | [resume](./RESUME.md) |
| D07 | Actual-market qualification matrix and explicit autonomous arm acceptance (M2/M8) | Evidence-blocked: code exists, actual account has no qualification/arm; connected matrix incomplete | Record permitted scoped round trips, stop/target, pause/cancel, feed gap, restart/recovery, expiry and rollover evidence; qualification and a separate explicit arm must pass existing gates | [M2](./__workspace/40-m2-qualification-worker-controls.md), [finish path](./__workspace/51-quote-order-and-finish-path.md) |
| D08 | Broader historical candle coverage / venue comparison | Evidence-blocked: bounded history reads exist; broad coverage/value parity not established | Verify supported instruments/dates/venues and provider limits; document remaining gaps rather than backfilling synthetic values | [after-hours history](./__workspace/42-after-hours-market-data.md), [live chart](./__workspace/43-live-candles-and-mobile-chart.md) |
| D09 | Real phone PWA installation, touch and background/resume acceptance (M4/M8) | Planned: six-size automated browser/PWA checks pass; physical-device acceptance not recorded | Install/use on target phone, check navigation, keyboard, zoom, offline notice, resume freshness and private-cache behavior | [master plan](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D10 | Remaining market/option analytics and studies (M5) | Planned: EMA/SMA/RSI, depth, reference and fills/levels exist; VWAP where valid, sourced change-in-OI, expanded IV/Greeks methodology and coverage-aware PCR/max-pain are not all delivered | Feature inventory and implementations with real inputs, source/method/time and unavailable states; never manufacture missing metrics | [M5 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D11 | Pending-order chart markers distinct from actual fills | Planned: fills/current position levels and pending-exit details exist; all pending entry/exit chart markers are not delivered | Scoped order-marker design, lifecycle semantics and race/stale tests; maintain distinction from execution | [chart overlays](./__workspace/63-owned-chart-trade-overlays.md) |
| D12 | Broader manual paper permission and order types (M6) | Planned: currently a bounded HUMAN five-minute/one-entry/one-lot session with BUY LIMIT; unrestricted manual mode is not implemented | Specify separate explicit permission lifecycle, supported types, mutual exclusion, recovery and deterministic admission; keep current gates until accepted | [manual placement](./__workspace/58-mobile-manual-placement.md), [amendments](./__workspace/60-manual-order-amendments.md) |
| D13 | Bulk protected exits and broader modification scope (M6) | Planned: individual exit and wholly-unfilled manual price amendments exist; no bulk exit, quantity increase, expiry extension or filled-position amendment | Specify/review semantics and implement reservation/fill-race/unresolved outcomes; do not add cosmetic actions | [M6 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md), [owned controls](./__workspace/59-owned-paper-cancel-and-exit.md) |
| D14 | Remaining risk/exposure metrics and trade statistics (M6) | Planned: portfolio/P&L and ledger funds exist; full daily loss/headroom, exposure analytics, win/loss/expectancy/profit factor/drawdown/slippage/holding-time reporting remains | Define all-time/session/sample/net-gross boundaries; reconcile to fills; undefined ratios stay unavailable | [portfolio](./__workspace/62-reconciled-portfolio-value-and-pnl.md), [M6 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D15 | Historical equity/P&L snapshots, richer journal filters/exports and funding/reset decisions | Planned: cash ledger/closed-position CSV exist; no complete historical marked-equity series or reviewed funding/reset workflow | Persist/reconstruct only defensible snapshots, add scoped filters/exports; funding/reset must preserve ledger history | [M6 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D16 | Agent evidence/news citation drill-down and explicit evaluation/output correlation (M7) | Planned: stages/explanations exist, older records lack durable correlation | Add future IDs and evidence-age/source/news drill-down; leave older WAIT-or-reject outcomes unspecified; never time-join unrelated outputs | [activity](./__workspace/64-recorded-agent-activity.md) |
| D17 | Model/strategy version and spending/budget visibility (M7) | Planned: server budget reservations exist; user-facing usage/remaining allowance/cost boundaries incomplete | Expose recorded/estimated usage distinctly, model/version binding and budget limits without secrets or fabricated billing cost | [agent runtime](./services/agents/README.md), [M7 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D18 | News suitability, permission and delay acceptance | Evidence-blocked: attribution/reader exist; free feed is delayed by 12 hours and coverage acceptance is incomplete | Confirm rights/coverage and intended use; preserve publication/retrieval/delay fields and do not present delayed headlines as breaking news | [agent news](./services/agents/README.md) |
| D19 | Strategy research and performance validation (M7) | Planned: versioned hypotheses, option selection/invalidation rules and out-of-sample fee-aware research are not qualified performance | Research with permitted data and declared assumptions/sample size; candle history cannot establish depth fills; no new strategy is enabled by examples | [M7 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D20 | M8 integrated recovery/security/load and bounded actual-market acceptance | Planned/evidence-blocked: slice suites pass; milestone-wide acceptance is not complete | Execute the integrated matrix and retain findings/closures, including concurrency, restart, stale data, ownership, load and private PWA behavior | [master plan](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D21 | M9 supervised paper observation and handover | Planned: requires completed qualification and a real observation period | Run the declared one-to-two-week supervised period with reconciliation, incidents/stop conditions, operator handover and recovery guide | [finish path](./__workspace/51-quote-order-and-finish-path.md) |
| D22 | Extended tools and exports beyond the critical finish path | Review needed: drawings, additional studies, scanners, layouts, alerts, strategy builders, baskets/payoffs, tags, scheduled reports and export formats remain backlog | Explicit scope/dependency decision for each; unsupported controls must not appear usable | [backlog](./__workspace/37-complete-system-and-broker-workspace-plan.md) |

## Daily-report limits carried forward

D15 also covers historical marked equity and available-cash/reservation snapshots,
immutable final reports and report exports. The current report reconstructs an IST
calendar day from dated records; today is provisional. It has no incident roll-up,
strategy-performance attribution or scheduled delivery (D14/D19/D22). Activity
counts above 2,000 source records are explicitly unavailable; only the newest 20
fills are listed while financial totals include all dated fills. Larger paginated
report drill-down remains under D15. Reconciliation failures or undated fills
suppress financial totals until the underlying records are resolved, not guessed.

## Current exclusions, not delayed promises

Real-money broker orders, public multi-user launch, broader asset classes,
margin-aware short selling/multi-leg execution, live broker holdings, banking,
funding/settlement and demat features remain outside the accepted single-owner,
long-options paper scope. Re-scope them explicitly before implementation.

## End review

Review every open ID with the final checkpoint. Preserve source evidence and note
what was built, what was actually verified, and what still needs a person, market
session, source evidence or a scope decision. Passing a fixture never closes an
actual-market or longitudinal acceptance item.
