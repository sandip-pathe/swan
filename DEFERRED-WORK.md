# Deferred-work ledger

Updated 21 November 2026. This is the end-of-build review list. An implemented
feature is not accepted evidence of live behavior. Keep IDs stable; close a row
only with a linked result, test or explicit scope decision. Every future slice
must add newly skipped/blocked work here and update resolved rows.

Statuses: **User-deferred** = explicitly skipped for now; **Evidence-blocked** =
required facts/acceptance missing; **Planned** = accepted scope not yet delivered;
**Partially delivered** = a verified subset exists, with remaining scope named;
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
| D16 | Agent evidence/news citation drill-down and explicit evaluation/output correlation (M7) | Partially delivered: model outputs now carry explicit context links; Evidence used shows cited historical quotes and analysis headlines. Older unlinked outputs remain unavailable; evaluation IDs now connect new outputs to their owned evaluation slot and outcome, with saved stage-check results for new runs; accepted strategies now link to owned risk decisions and entry orders; richer evidence remains planned | Complete richer source/age drill-down and remaining downstream evidence gaps; preserve legacy gaps and do not infer missing outcomes | [activity](./__workspace/64-recorded-agent-activity.md) |
| D17 | Model/strategy version and spending/budget visibility (M7) | Partially delivered: Account activity shows today's conservative reservations/remaining allowance, recorded usage coverage and reservation model names. New runs also record requested/reported model names and local strategy/prompt/schema fingerprints. Immutable provider revision guarantees, monetary cost and unavailable provider usage remain open; incomplete/invalid HTTP-200 response totals are now retained; historical day selection is implemented | Record/pin stable provider revisions where supported, resolve missing transport/error usage where defensible and review the reproducibility boundary; add defensible pricing/billing attribution and any needed historical configuration timeline. Existing missing usage stays unknown, never zero or inferred from reservations | [agent runtime](./services/agents/README.md), [M7 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D18 | News suitability, permission and delay acceptance | Evidence-blocked: attribution/reader exist; free feed is delayed by 12 hours and coverage acceptance is incomplete | Confirm rights/coverage and intended use; preserve publication/retrieval/delay fields and do not present delayed headlines as breaking news | [agent news](./services/agents/README.md) |
| D19 | Strategy research and performance validation (M7) | Planned: versioned hypotheses, option selection/invalidation rules and out-of-sample fee-aware research are not qualified performance | Research with permitted data and declared assumptions/sample size; candle history cannot establish depth fills; no new strategy is enabled by examples | [M7 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D20 | M8 integrated recovery/security/load and bounded actual-market acceptance | Planned/evidence-blocked: slice suites pass; milestone-wide acceptance is not complete | Execute the integrated matrix and retain findings/closures, including concurrency, restart, stale data, ownership, load and private PWA behavior | [master plan](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D21 | M9 supervised paper observation and handover | Planned: requires completed qualification and a real observation period | Run the declared one-to-two-week supervised period with reconciliation, incidents/stop conditions, operator handover and recovery guide | [finish path](./__workspace/51-quote-order-and-finish-path.md) |
| D22 | Extended tools and exports beyond the critical finish path | Review needed: drawings, additional studies, scanners, layouts, alerts, strategy builders, baskets/payoffs, tags, scheduled reports and export formats remain backlog | Explicit scope/dependency decision for each; unsupported controls must not appear usable | [backlog](./__workspace/37-complete-system-and-broker-workspace-plan.md) |

## Evidence visibility limits carried forward

D16 remains open. [Checkpoint 67](./__workspace/67-linked-agent-evidence.md) adds
future output-to-context links and an owned citation view. Older outputs are never
linked by timestamp. News article links and richer depth/age analysis are still pending. Strategy/risk
correlation is implemented in checkpoint 70.
Proposal/review records cite market observations; only analysis records directly
cite news. This view does not attribute analysis headlines to a later proposal.
Missing/invalid observations remain unavailable; historical evidence grants no
current trading permission. No broker/login/manual acceptance was attempted.

[Checkpoint 68](./__workspace/68-linked-evaluation-history.md) adds explicit new
output-to-evaluation IDs and an owned history showing recorded model stages plus
the current slot outcome. Existing evaluation events can show their slot outcome,
but legacy model outputs are not backfilled. Stage checks are now persisted as described in checkpoint 69; pre-context failures
and hard-process loss can still lack a stage result. History is capped
at the first 20 outputs and marks truncation; pagination/query indexing/load review
remain under D16/D20. Strategy/risk/order correlation is implemented in checkpoint 70.

[Checkpoint 69](./__workspace/69-recorded-stage-checks.md) records new analysis,
proposal, review and strategy-stage passed/failed/interrupted results. This logs
executed stage checks, not a separate result for every predicate. A valid WAIT or
rejected review can pass response checks without granting entry permission. Older
checks are not backfilled. Failures before saved context (configuration/news/evidence
selection), process death, and an unavailable audit database can still leave no
stage-check result; never infer success from that absence. Stage results and output lists now use independent 20-record cursor pages
(checkpoint 74); other bounded lists remain explicit.

[Checkpoint 70](./__workspace/70-strategy-risk-order-history.md) follows an owned
accepted evaluation envelope to risk records by exact strategy ID, then to entry
orders by decision ID. Recorded fill quantities come from actual fills; existing
order timelines provide events and related exits. No acceptance root, invalid roots
or duplicate outcome records are unavailable, never guessed. No decision/order
found is distinct from rejection or a fill. Risk decisions are capped at 20 and
orders at 100 with truncation; full pagination/index/load review stays D16/D20.
Pre-admission control denials that never persisted a DecisionRecord have no linked
risk result; richer risk evidence and explicit denial events remain under D16.

## Usage visibility limits carried forward

D17 remains open. Current-day allowance reads current settings, which may differ
from a running worker; past days use saved request limits. Calls are grouped by
the IST date of reservation. Reported
usage prefers a unique owner-linked usage receipt, falling back to a legacy saved
output only when no receipt exists. Duplicate, missing, invalid or conflicting
usage stays unknown.
Provider failures can consume tokens without a saved valid output; supplied
HTTP-200 usage is now retained before output validation. No monetary cost, provider billing reconciliation, immutable provider-weight
identity or full reproducible application/environment bundle is implemented. Historical day selection is implemented in checkpoint 72. New requested/reported model names and local-rule
fingerprints are recorded as described in checkpoint 71. This slice does not change the budget
guard or return reserved allowance after failures. See [checkpoint 66](./__workspace/66-analysis-allowance-and-recorded-usage.md).

## Daily-report limits carried forward

D15 also covers historical marked equity and available-cash/reservation snapshots,
immutable final reports and report exports. The current report reconstructs an IST
calendar day from dated records; today is provisional. It has no incident roll-up,
strategy-performance attribution or scheduled delivery (D14/D19/D22). Activity
counts above 2,000 source records are explicitly unavailable; only the newest 20
fills are listed while financial totals include all dated fills. Larger paginated
report drill-down remains under D15. Reconciliation failures or undated fills
suppress financial totals until the underlying records are resolved, not guessed.

[Checkpoint 71](./__workspace/71-recorded-model-and-rule-versions.md) binds new
reservations to evaluation/context IDs and records the requested model plus prompt
and response-schema SHA-256 fingerprints before HTTP. Valid completed outputs save
the provider-reported model when present; missing/duplicate/mismatched responses
remain unavailable. The context records the local strategy label and loaded
pipeline-source fingerprint. This is not a full dependency/build snapshot or proof
of immutable provider weights. Old runs are not backfilled from current settings.
The display is bounded to 20 requests; excess/ambiguous responses are marked
incomplete. Monetary cost, missing transport/error usage, pagination/index/load review
remain D17/D20; historical usage is implemented in checkpoint 72. No live API request was used for this slice.

[Checkpoint 72](./__workspace/72-historical-analysis-usage.md) adds IST-day selection
for reservations, recorded token totals, unknown-usage coverage and model counts.
Linked responses saved after midnight stay with the request day. New reservations
save the exact allowance used by the guard. Past-day allowance is shown only when
all selected requests record the same valid limit; missing/mixed limits remain
unavailable. Even a uniform recorded limit is not proof of final day-end settings.
Empty old days have zero recorded requests but unknown historical allowance.
Current settings are never read for past days. Missing transport/error usage, billing and any final-settings timeline remain D17; query indexing/load remains D20.

[Checkpoint 73](./__workspace/73-retained-response-usage.md) saves normalized
provider usage before completed-status, refusal and output validation checks.
Incomplete/invalid responses still fail and cannot authorize trading. Daily usage
counts each request once, preferring a unique receipt to its mirrored output;
legacy outputs remain supported. Duplicate/conflicting values stay unknown.
Non-200, oversized, malformed-JSON, timeout/cancelled transport and lost audit
writes can still lack usable usage; these are not zero and are not billing totals.
Token breakdowns remain supplied metadata, not a reconciled billing calculation.
No pricing or invoice reconciliation is implemented. D17 remains open for those
limits and provider/reproducibility guarantees. D16/D20 retain remaining bounded-list pagination and query/index/load qualification. No live API or market check was performed.

[Checkpoint 74](./__workspace/74-paginated-evaluation-history.md) adds independent
20-record newest-first cursor pages for evaluation outputs and stage checks.
Cursors are scoped to owner, evaluation and kind; equal timestamps use UUID ties.
Older pages append without duplicates; failures retain existing rows, and closing
or reopening ignores stale responses. Page reads are consistent individually,
not one frozen cross-page snapshot; reopening refreshes newer records. Versions,
risk decisions/orders and report fill lists keep their stated bounds. Their
pagination plus database index/load qualification remain D16/D20.

[Checkpoint 75](./__workspace/75-history-query-indexes.md) adds matching composite
expression indexes for evaluation links and nested model-request evaluation links.
A disposable 30,000-row synthetic audit dataset verifies first/older query plans
use ordered index scans with no full-table scan or sort; migration downgrade and
upgrade are tested in that schema. Local migration applied with bounded lock and
statement waits. This qualifies these query shapes only: wider history/usage/risk
queries, concurrency, cold-cache/production-sized load and integrated restart/
recovery remain D20. Remaining model-version pagination is next under D16/D17.
No broker or actual-market acceptance was attempted.

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
