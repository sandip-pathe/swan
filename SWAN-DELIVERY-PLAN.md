# SWAN delivery plan

## Agent, chat and watcher checkpoint: 23 November 2026, afternoon

### Verification for this checkpoint

427 backend tests passed (one existing Starlette/httpx deprecation warning),
15 frontend tests passed, Ruff passed across services/tests, targeted mypy passed
on 12 changed source modules, frontend typecheck/production build passed, and
`git diff --check` passed. API/web listeners and managed observation worker are
running. These checks do not close actual-market autonomous paper acceptance.

This checkpoint supersedes earlier statements that index acquisition is API-only,
chat is limited to canned actions, or ORB qualification accepts generic records only.

- A deterministic worker job checks NIFTY index evidence every 30 seconds during
  the verified ORB window. Shared history acquisition, completed-bar assessment,
  watcher deduplication and durable assignments drive bounded model work. Generic
  snapshot reasoning no longer competes for automatic execution ownership.
- Free-text chat selects up to four named read-only tools for market, account,
  strategy and indicator records. Answers retain context/source IDs and timestamps;
  chat cannot create orders or change risk. The separate audited stop-new-entries
  control remains. An authenticated UI test at 15:15 IST returned actual NIFTY
  observations and correctly described the expired ORB trigger. Browser-local
  history is bounded and is not cross-device storage.
- Fixed daily AI allowance settlement: one valid provider usage receipt replaces
  its conservative reservation; absent, inconsistent or duplicate receipts retain
  the reservation. Actual usage above the estimate counts in full. No limit was
  raised. The failing UI request had 240,290 estimated tokens reserved versus
  58,323 settled tokens. A subsequent real UI answer passed after the fix.
- Session HLC3 VWAP and SMA-seeded DEMA 9 are available on charts and through
  read-only tools. Completed candles only; gaps/warmup and unavailable volume are
  explicit. Chart inspection showed DEMA and unavailable VWAP for incomplete
  history. These are context, not new strategy cards or automatic exit rules.
- ORB admission now applies the reviewed depth-unit mapping before executable
  quote checks. Qualification verifies the original ORB candidate, source bars and
  owned analyst/reviewer provider records; it does not fabricate generic reviews
  or grant qualification. Negative provenance tests remain fail-closed.
- Stream index references now publish to the database regularly; missing previous
  close in an LTP packet preserves the same-session previously observed close.
- Real option-history refresh returned provider rate limiting. Current VWAP parity
  and complete history acceptance remain open. No retry loop or fabricated volume.
- No new paper order was placed. Nine total orders, flat account, no active
  validation, qualification or arm; cash INR 99,766.55. Earlier round trips remain
  manual. Today?s ORB window ended at 11:00 IST. Next actual acceptance requires a
  fresh eligible setup and the existing bounded validation/qualification controls.
- Private runtime evidence: `.local/run/chat-watcher-checkpoint-2026-11-23.json`,
  `.local/run/indicator-history-check-2026-11-23.json` and the earlier paper ledger.


## Later execution and agent audit: 23 November 2026

The [execution and agent audit](./EXECUTION-AND-AGENT-AUDIT-2026-11-23.md)
supersedes earlier descriptions of the 10% paper participation configuration.
The audited model now permits up to 100% of observed depth, with existing
consumption, freshness and risk checks. Entry-only valuation pauses and chat
session stops no longer force manual liquidation. Explicit lease termination and
position protection remain enforced.

D19/D25: the ORB index-history producer is still an explicit API operation, not a
scheduled worker task. Generic option-snapshot reasoning and predefined ORB work
also need explicit ownership and fallback priority. These are confirmed integration
gaps, not missing broker depth. Close with automatic completed-bar acquisition,
durable assessment/agent work and an eligible strategy-to-paper session through
existing controls. No eligible current ORB opportunity or qualification was
invented during this audit.

D07/D20/D21: both earlier round trips were manual. A new real-provider, read-only
agent run passed analysis and proposal validation and returned WAIT for missing
directional evidence. Review was skipped after WAIT and order count stayed nine.
This does not qualify autonomous trading. The first trial rejected an invalid
citation; prompt/context corrections retained that rejection guard. Actual holding
acceptance after the entry-pause fix remains open until a bounded market session
exercises it. No new paper or broker trade was submitted in this audit.

## Latest checkpoint: real-data paper round trips, 23 November 2026

This checkpoint supersedes the older status sections below. Two one-lot NFO
paper positions completed a buy and a sell against actual Angel One observations.
No real-money broker order was submitted.

| Contract | Units | Buy | Sell | Estimated fees | Net P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| NFO:64458 | 65 | INR 183.10 | INR 182.40 | INR 75.54 | INR -121.04 |
| NFO:64490 | 65 | INR 295.15 | INR 294.85 | INR 92.91 | INR -112.41 |

Final cash and equity were INR 99,766.55 from INR 100,000. Total realized P&L
was INR -233.45, including INR 168.45 in estimated fees. Both positions were
closed, all orders were terminal, all validation leases stopped, and ledger
reconciliation returned no problems. Available cash was INR 68,852.54 because
the configured sale-proceeds holds remain in force. This is not reserved entry
cash or an open position.

Both exits followed `ENTRIES_PAUSED_UNAVAILABLE_VALUATION` with
`INSUFFICIENT_EXECUTABLE_DEPTH`, then `MANUAL_SESSION_STOPPED`. The watchdog
cancelled the protective stop before filling the replacement exit. The first
entry used WebSocket evidence and its exit used FULL REST evidence. The second
round trip used WebSocket evidence on both sides and held for about 13 seconds.
These are manual execution tests, not profitable strategy signals or accepted
AI-directed trading. Three other accepted entries expired unfilled; an additional
manual intent was rejected for insufficient executable depth. No fill was forced.

Private local evidence is in `.local/run/paper-round-trip-final-2026-11-23.json`,
including order IDs, immutable snapshot IDs, provider event IDs, fills and totals.
First entry order: `41d5b095-395e-4ccf-8ecb-af0c4ca2494c`.
Second entry order: `aeeb19b3-f99b-49bc-bee0-1085ca4d164c`.

Runtime fixes address observed PostgreSQL deadlocks and concurrent clock reads.
Quote and candle publishers lock instrument metadata in a stable order and do
not regress its verification time. Heartbeat publication follows account-to-control
lock order. Validation and manual protection read the clock after account locking;
manual quote checks read it after awaited scope work. Freshness, depth and risk
limits were not increased. Regression tests cover concurrent publications, packets
arriving during scope reads, and heartbeat changes during account-lock waits.
The two actual exits above were caused by insufficient depth, not proven clock
failures. The clock regressions are separate implementation findings.

All six refreshed provider diagnostics passed: broker, catalog, stream, AI,
structured AI output and news. The project OpenAI key works after removing the
expired override from launched processes. Real NIFTY history produced 137 complete
bars without gaps in the captured range. Its ORB signal had expired before these
tests, so it was not executed. Recognized provider history throttles remain visible.

Depth mapping now uses absolute option units, supported by exchange quantity
semantics, the official SDK's raw decoder and 80 sampled depth levels across both
venues and transports. This is a documented inference, not explicit SmartAPI
support confirmation. See [the source review](./SMARTAPI-DEPTH-UNITS-QUESTION.md).
The NFO REST corroboration sample was stale and was not used as fresh admission
evidence. Paper fees disclose rounding assumptions and the unresolved BFO IPFT
modeling allowance. Exact broker contract-note parity is still unverified.

Verification after the runtime fixes: 404 backend tests passed, Ruff passed for
the changed runtime modules and regressions, and targeted mypy passed for seven
source modules. The only test warning concerned Starlette's deprecated httpx
integration. Frontend checks from the preceding increment passed; no frontend
code changed in this runtime continuation.

The worker was returned to OBSERVATION after confirming the account was flat.
Entries remain paused. The API was restarted to load the fixes. Qualification,
autonomous arming, AI-directed paper-session acceptance, target/stop/max-hold
acceptance against actual market data, broader reconnect checks and dashboard/chat
visual acceptance remain open. No qualification or arm was fabricated from these
manual tests. R1 is not fully accepted.

Consolidated 22 November 2026, Asia/Kolkata.

## The outcome

Finish a personal trading system that observes actual markets, evaluates strategies with AI and quantitative tools, manages authorized paper trades, and explains what happened through chat and a useful dashboard.

Build a functioning narrow version first. Improve strategy quality and profitability through measured operation afterward. A profitable strategy is an empirical outcome, not a prerequisite for finishing the software or a promise this plan makes.

This is the consolidated forward plan for this conversation. Older discussion and slice plans remain useful evidence and implementation detail. This file does not change existing permissions or declare unverified work accepted. On 22 November 2026 the user explicitly resumed verification, provider checks, broker login, live-market acceptance, qualification and supervised paper-session acceptance. No real-money orders are authorized. Deferred items below retain their stable D IDs and closure conditions; DEFERRED-WORK.md remains the source ledger.

Implementation should proceed in small, complete increments with flexible engineering choices. Do not stop for another architecture exercise unless a concrete implementation problem requires a decision. Do not interpret the full future scope as work that must be completed before the first release.

## Three finish lines

| Release | Definition of finished | What does not block it |
| --- | --- | --- |
| R1: first running paper version | One NIFTY strategy goes from genuine observations through agent assessment and gated paper execution to reconciled exits, with visible evidence and working recovery | Full chat, SENSEX, a large strategy pool, autonomous tool creation, human competitions, proof of profitability |
| R2: complete personal paper product | R1 plus primary chat, SENSEX coverage, complementary predefined strategies, a usable research/evaluation loop, and basic personal-operation documentation | Real-money routing, institutional analytics, many specialists, multi-user infrastructure, all optional trading-workspace features |
| R3: optional expansion | Separately selected improvements and, if explicitly pursued, actual broker execution | No automatic commitment to every future idea |

R1 is a substantial delivery, not a demo seeded with invented prices or trades. R2 closes the personal paper-product scope described here. R3 is a future program, not a reason to keep R2 unfinished.

## What we already have

The following baseline combines source inspection and implementation reports. Reported checks were not rerun while writing this plan.

| Capability | Current evidence | Remaining boundary |
| --- | --- | --- |
| Single-owner app and paper workspace | Authentication, market views, charts, options chain, positions, journal, risk, reports, and paper lifecycle exist | Not evidence that the new strategy path operates end to end |
| ORB tool | Isolated deterministic NIFTY setup evaluator and tests | Setup identification is not a complete option trade |
| Index evidence foundation | Dedicated query/normalizer, immutable index snapshots, bounded as-of reads | Actual configured-source coverage and ongoing ingestion remain unaccepted |
| Strategy records | Persisted assessments, watcher events, non-executable plan drafts, inactive research candidates | No executable admission from those drafts |
| Agent spike | Durable assignments, bounded analyst/reviewer calls, conditional research, evidence validation, audit and usage links | Real model quality and matched baseline comparison remain untested; do not assume a general autonomous tool loop exists |
| Read access | Authenticated assessment/plan/research endpoints and read-only Strategy Intelligence dashboard | Manual dashboard acceptance and primary chat remain open |
| Paper preflight | Explicitly rejects current research-only, pending-review drafts | This is an intentional boundary, not completed trading integration |
| Database and checks | Local DB migrated through `f8c1d2e3a4b5`; 376 backend tests, Ruff, targeted mypy, 13 frontend tests, frontend typecheck and production build pass | Offline verification is complete for this implementation pass; live/session/UI acceptance remains incomplete |

The latest [strategy implementation closeout](./STRATEGY-IMPLEMENTATION-PLAN.md) supersedes the older spike report's unresolved local driver/migration status. Do not automatically repeat a driver repair or migration application. The older [architecture spike checkpoint](./AGENTIC-ARCHITECTURE-IMPLEMENTATION-PLAN.md) remains useful for the workflow details.

RESUME.md is absent in the current checkout. Do not reconstruct it from stale conversation text. Existing unrelated edits and work in another chat must be preserved.

## Architecture we will use

Use [the rough architecture](./ROUGH-AGENTIC-ARCHITECTURE.md) as the working design, not a framework-selection project:

```text
Market observations -> normalized state -> features and strategy watchers
                                               |
                                    durable bounded assignments
                                               |
                              analyst + tools -> review
                                               |
                                 reviewed draft or abstention
                                               |
                            deterministic plan/account admission
                                               |
                           paper orders -> fills -> protection -> ledger

Saved evidence and outcomes -> evaluation/research -> candidate versions
Saved records and allowed controls <-> separate chat and dashboard
```

Durable sessions, orchestration, bounded agent harnesses, context retrieval, tools, and research execution have separate responsibilities. They need not be separate microservices. Keep model/research work from blocking position management.

Retain four conceptual agent roles: strategy analyst, research agent, reviewer, and user-facing chat. Use deterministic services for risk, calculations, scheduling, accounting, request limits, and exits. Add specialists only when a distinct need or measured benefit appears. No mandatory LangGraph/Temporal migration, multi-model debate, or agent-per-indicator design is required.

## R1: first running paper version

### P1. Freeze one practical mandate and the draft-to-plan boundary

**Current implementation milestone.** Resolve the remaining execution choices together with the code that consumes them. Produce one concise, versioned mandate and a complete candidate paper-plan representation rather than another broad policy document. The frozen candidate is recorded in [PAPER-ORB-MANDATE.md](./PAPER-ORB-MANDATE.md).

Use the current research draft as the starting point: NIFTY/NFO long call or put, ORB, at most one entry attempt per session, closest-to-underlying strike with the recorded tie-break rule, next listed expiry after the session within seven days, ask-based limit entry without chasing, and a maximum 300-second hold. Current account policy can be stricter. These are candidate implementation constraints; they are not approval of trading quality or permission to operate.

Settle premium protection, underlying invalidation, target and time exits, order lifetime, partial-fill treatment, fees, and the capital/risk policy reference. Do not turn index points into option-premium prices by assumption. Keep discretionary agent opinions separate from deterministic exit rules. Use existing reviewed account settings; do not invent or widen balances, risk, expiry scope, or permission.

Keep immutable research drafts intact. An admitted paper plan should be a distinct versioned record linked to its review and current evidence, not a boolean flipped on an old draft. Autonomous orders need honest actor attribution; do not impersonate a HUMAN manual intent to reuse its permissions.

**Finished when:** the mapping from draft to candidate plan is explicit, unresolved inputs block it with precise reasons, and existing risk/permission controls remain authoritative. Activation still requires P6.

**Implementation checkpoint:** added the versioned ORB paper mandate, immutable candidate record linked to the exact source draft and approved reviewer artifact, post-review workflow persistence, and an authenticated as-of read endpoint. Candidates remain blocked with explicit current account, qualification, contract, executable quote/depth, fee-schedule, and revalidation/exit-monitor blockers. The prior research-draft schema and records remain intact. The candidate-plan and merged exit-policy migrations are applied locally; backend tests pass. Candidate admission still blocks pending mandate review and candidate-to-envelope/exit mapping.

### P2. Wire the real data-to-assessment path

Reuse the existing index adapter, storage, evaluator, and watcher. Connect deliberate acquisition and subsequent updates to bounded snapshots and assessments, with source/receipt times, gaps, corrections, finality, and as-of semantics intact. Inspect current code first so parallel work is not duplicated.

For ongoing operation, choose an actually supported stream or bounded refresh strategy. A historical endpoint's existence does not establish suitable update latency. Market-data polling has its own quotas. Plan and model deadlines must reflect measured data age and the opportunity's remaining lifetime. Capture observations incrementally where possible instead of fetching and re-reasoning over a whole day repeatedly.

Build and verify offline wiring separately from provider checks. Actual source checks belong in P6 after explicit resumption. Never substitute option bars, the latest index quote, or fixture records for missing index history.

**Finished when:** actual permitted observations can travel through the path once source verification is resumed, and unavailable/stale evidence produces a visible honest outcome. Software completion and connected verification are labelled separately.

**Implementation checkpoint:** added an authenticated, explicit current-session NIFTY/NSE refresh route and bounded cached as-of read route. Refresh acquires the complete ORB prefix through the latest completed minute (capped at 11:00), preserves immutable provider batches, and stores a deterministic ORB assessment tied to the exact batch. Gaps remain explicit; cached reads do not contact the provider; refreshes are rate-limited. Changed eligible setups persist watcher events and durable deduplicated assignments. The data path and tests are verified offline. The authenticated provider checks completed later: broker/account match and catalog passed; the WebSocket authenticated and decoded an option quote packet. Since the exchange was closed, that packet does not establish freshness; actual index-candle comparison, open-session freshness, both-venue depth and reconnect acceptance remain open. The NIFTY path uses the imported NFO calendar and is not yet market-accepted.

### P3. Complete event-to-agent orchestration

Connect meaningful watcher events to the durable assessment workflow. Start with session/range completion and relevant bar/eligibility transitions. Deduplicate, coalesce superseded work, enforce deadlines, and reject late results. Expensive reasoning should not run every second.

Prepare bounded plans ahead of immediate triggers where the strategy permits it. If a fresh model decision cannot finish before an opportunity expires, abstain. Code rechecks live conditions before admission; an agent response cannot renew stale evidence.

Keep missing data, no setup, deliberate abstention, reviewer rejection, provider failure, expiry, and interruption distinct. Ensure a valid no-fit case can save a bounded research hypothesis, while a missing-data case does not invent an alternative strategy.

**Finished when:** an event produces one durable decision path without manual invocation of internal functions, and restart/duplicate/late-event behavior is understandable. Real model behavior is separately exercised in P6.

**Implementation checkpoint:** eligible changed watcher events create one account-scoped `WATCHER_STRATEGY_ASSESSMENT` assignment keyed to the event, with a deadline capped by assessment expiry. Newer events expire superseded queued work. The background consumer claims queued work atomically and invokes the bounded workflow; duplicate claims do not run twice, queued work survives restart, expired work is not replayed, and late results are rejected. Offline tests pass. Connected model behavior remains unverified: the OpenAI model-list probe returned HTTP 401, so no analyst/reviewer call or budgeted generation was attempted.

### P4. Connect complete plans to paper execution

Use existing paper risk, order, fill, reservation, protection, and ledger services. Add the authorized strategy-admission bridge rather than a second paper engine. Bind the plan to current contract metadata, executable option evidence, account policy, review, session, and validity.

Recheck permissions, spread/liquidity, sizing, and freshness at submission. Track working orders, actual filled quantity, partial fills, cancellation races, rejection, and unknown outcomes. Monitor premium and underlying exits as specified by P1. Stop/target/time/session protection must work without model calls.

Preserve idempotency, durable actor/strategy/evidence links, restart reconciliation, and the rule that unresolved exits cannot become fictional fills. Fixture-driven tests can exercise the bridge without enabling it in the user's account.

**Finished when:** one valid admitted plan can traverse the existing paper engine in isolated verification, invalid plans cannot, and state/ledger projections reconcile. This does not arm a session.

**Implementation checkpoint:** added an authenticated, read-only candidate preflight that rechecks current account risk configuration, qualification, active paper arm, and effective execution configuration, plus mandate/candidate fingerprints and source-plan, reviewer, approval, assessment and evidence provenance. A generic dual-exit policy persists on paper positions; the worker subscribes to configured index tokens in LTP mode; the coordinator checks identity-matched underlying observations alongside option-premium protection and fails closed when required underlying data is unavailable. Migration `f8c1d2e3a4b5` is applied locally, and offline checks pass. This infrastructure is not connected from the ORB candidate/admission path. ORB candidates remain blocked pending mandate review and mapping of deterministic ORB levels into candidate/envelope/exit fields, plus verified current index-token/source behavior. P4 paper execution integration remains incomplete.

### P5. Make the complete loop visible and operable

Extend the existing UI rather than build a new dashboard. Show feed freshness, worker/session state, strategy assessment, model outcome, admission blockers, orders, actual fills, protection status, and reconciled results. Link the complete decision timeline.

Give the owner a deliberate session setup/start path through existing controls, pause-new-entry behavior, and clear visibility of unresolved positions. Distinguish stopping entries from liquidation. Preserve deliberate arming and qualification; a cosmetic start button is insufficient.

**Finished when:** the owner can understand and operate the bounded paper session through the app, without calling internal functions or inferring status from logs. Full chat is not required yet.

**Implementation checkpoint:** expanded the existing Strategy Intelligence screen with readiness, session, worker heartbeat/status, account pause/loss block, active orders, open exposure, recent fills, watcher assignments, bounded analyst/reviewer/research summaries and paper-candidate blockers. Added authenticated bounded reads and navigation to existing permission/execution controls, without adding or weakening trading actions. Automated checks pass. Manual visual review remains blocked: browser access is unavailable and the Comet window did not render the local SWAN page. P4 remains incomplete and candidate submissions remain blocked.

### P6. Resume connected verification and qualify the narrow path

The user explicitly resumed this milestone on 22 November 2026. Current broker/account match, catalog, and authenticated stream quote decoding passed through account-scoped diagnostics. The market was closed, so live freshness and actual paper qualification could not be accepted. The OpenAI model-list check returned HTTP 401 and news returned `NEWS_HTTP_ERROR`. The account has no validation sessions, no qualification and no arm; all 17 qualification checks lack evidence. No structured model-generation request was made.

Verify configured NIFTY source access, current session/calendar, option metadata, executable depth quantity semantics, effective fees/rounding, provider behavior, and the actual analyst/reviewer request path. Test the integrated app and bounded paper entry/exit workflow under the existing qualification matrix. Do not weaken a gate because it is inconvenient or because fixture tests pass.

Calendar coverage was previously recorded only through 30 November 2026. Check and extend it from official sources before any later trading date. Source freshness and credential validity must be current, not inherited from November setup evidence.

Model comparison need not prove better P&L to finish R1. It must establish that real requests, citations, outcome validation, budgets, and timeouts work. Do not infer model quality from stubs. If the strategy yields no trade, record it; that session does not establish entry/fill/exit behavior. Obtain bounded separate execution evidence through the existing permitted validation route rather than force a strategy signal.

**Finished when:** current evidence satisfies the narrow qualification and the owner separately arms the supported paper scope. Current status: not qualified or armed. Repeat the day-scoped broker login on the next trading day; complete open-market source/depth/fee checks and genuine validation evidence first. If checks remain blocked, label R1 implementation-ready, not operating or accepted.

### P7. Run, reconcile, and close R1

Observe a bounded actual session. Record legitimate trades or abstention, actual failures and gaps, and the model/strategy/risk versions. Verify recovery and protective behavior using appropriate controlled evidence. Resolve material accounting, duplicate-order, ownership, and exposure-management defects before expanding.

**R1 completion:** genuine data reaches the strategy/agent path automatically; an eligible plan can produce and manage actual paper exposure through the permitted route; the account reconciles; the UI explains outcomes; existing controls and recovery work. Qualification evidence covers the execution path even if a particular strategy session abstains. This remains open: no plan has entered the paper engine and no actual validation or paper-acceptance session has run.

Profitability remains measured and unknown until enough observations exist. Successful operation with losses is not a profitable strategy; it is still useful evidence about a completed software loop.

## R2: complete the personal paper product

### P8. Deliver primary chat over the same records

Add the conversation surface/history and bounded read tools for market context, news, strategy assessments, agent work, orders, positions, risk, and reports. Answers identify source, time, freshness, uncertainty, and missing evidence, and open relevant dashboard details.

**Implementation checkpoint:** added a read-only Chat tab with bounded prompt actions for paper status, saved NIFTY/SENSEX references, open positions and active orders, risk/exposure, strategy assessments and watcher outcomes, and daily reports. Answers identify API source/as-of time; unavailable records return explicit errors; saved market reads do not refresh prices. Up to 50 answers persist in browser-local storage, without cross-device sync. Backend and frontend checks pass. Visual/manual review remains blocked by browser access. The audited session-stop command remains outstanding.

Keep chat independent of autonomous operation. Initial control is the explicitly requested and audited stop-new-entries-for-today command, leaving protection running. General trade-by-chat, changing risk, resuming sessions, and liquidation are not implicitly authorized. Define any expanded commands separately.

**Finished when:** the app opens into useful conversation, prior decisions are retrievable, the permitted stop command is idempotent, and chat failure does not change trading operation.

### P9. Add complementary strategies and SENSEX

First add trend pullback and failed-breakout reversal with mechanical cards and evaluator versions. Complete range breakout/retest and mean-reversion cards to round out the original five-family catalog. Stage implementation by actual data support and usefulness; do not invent performance claims for a named pattern.

Introduce a declared selection policy and preserve why candidates fit, fail, or lack data. Adaptation is allowed only within an evaluated rule; new thresholds or combinations become new versions. Separate setup, contract expression, and execution assumptions.

Add SENSEX with its own actual underlying-data path, BFO metadata/depth/fees, calendar, and venue-specific qualification. NIFTY evidence does not qualify SENSEX. Resolve BFO IPFT and any charge/unit uncertainty before relying on that venue's results.

**Finished when:** the intended catalog is represented honestly, complementary strategies can be evaluated and selected, SENSEX follows the same proven lifecycle, and unsupported candidates remain research-only rather than advertised as executable.

### P10. Complete evaluated research and learning

Extend the existing inactive hypothesis store into a useful research workspace. Agents can select, adapt, combine, or propose strategies, explain what is new, and save experiments with versions and evidence. Research occurs between sessions and opportunities; it need not create an immediately executable trade when nothing fits.

Provide the small tool set the work actually needs: evidence retrieval, strategy cards and assessments, features, options sensitivity/scenarios, contract comparison, exposure, cost/sizing scenarios, prior decisions, and bounded research operations. Generated calculations require explicit formulas, units, and verification. Code experiments run isolated from secrets and active execution; promote tools and strategies deliberately.

Define economic evaluation criteria before judging results: costs/fill assumptions, sample construction, uncertainty, drawdown tolerance, sensitivity, and promotion/retirement rules. Preserve failed trials and untouched evidence. Compare deterministic and agent-assisted behavior fairly. Historical frontier-model knowledge can contaminate replay reasoning; prospective paper evidence remains distinct. Do not introduce the previously excluded replay service without a separate decision.

Post-session findings become hypotheses, not automatic rule edits. Research candidates can be useful without being profitable or executable.

**Finished when:** the user can inspect a proposed strategy/tool, its experiment/evidence and limitations, and its lifecycle state. A candidate cannot activate itself; no fabricated backtest or success score is required to fill an empty screen.

### P11. Finish personal operations and evidence-linked reporting

Provide a coherent session summary and longitudinal view: net/gross results, realized/open exposure, drawdown, costs, turnover, rejected opportunities, outages, and missing valuations. Add defensible model-cost attribution where pricing/usage supports it. Token reservations are not billed currency, and unknown usage is not zero.

Keep source/prompt/tool/strategy/risk versions, exact evidence links, useful pagination, and existing exports. Add historical marked-equity capture if needed for drawdown; do not reconstruct invented marks. Make restart, local startup/shutdown, session renewal, backup/restore, and unresolved-exit procedures usable. Remove broken navigation and misleading controls when encountered.

Run an integrated regression and application acceptance pass appropriate to the combined change. Automated regression is now green. Manual/browser review has been resumed but remains blocked until the browser can display the local app; it is not marked complete. A formal review can be useful without requiring a new skill/framework installation.

**R2 completion:** chat, dashboard, autonomous paper operation, supported strategies/venues, and research records form one coherent personal product with a reproducible local operating path. Record remaining optional items below; do not hold the release for them.

## Sequence and overlap

```text
P1 mandate and plan boundary
   -> P2 data wiring -> P3 event/agent integration
   -> P4 paper bridge -> P5 operator UI
   -> P6 explicitly resumed qualification -> P7 first running release
   -> P8 chat -> P9 strategy/venue expansion -> P10 research -> P11 product closeout
```

P2 and P3 can develop alongside P1 where they do not require its execution choices. P8's read-only chat can proceed once record APIs are stable. Strategy-card research and evaluation design can run alongside integration. SENSEX implementation waits for a proven NIFTY path. Avoid multiple chats editing the same runtime/contracts without coordination.

Do not assign fixed calendar completion dates before the next slices reveal remaining integration effort. Market sessions, user-deferred checks, and prospective observation are real scheduling dependencies. Code can be completed faster than evidence can be collected.

After each increment, use actual outcomes to select the next unfinished prerequisite. Do not restart planning, rebuild accepted foundations, or broaden a narrow fix into an architecture migration. Tests should address changed behavior and material risks, not repeat the whole project after every documentation change.

## Deferred work carried into this sequence

The D IDs below are copied from `DEFERRED-WORK.md` so their status and closure requirements are visible beside the delivery milestones. The ledger remains authoritative; this table does not close, reopen, or renumber an item. “R1 gate” means evidence is required before calling R1 operating/accepted, not before implementing software. User-deferred checks stay deferred until explicitly resumed.

| Ledger IDs | Plan placement | Current state and milestone treatment |
| --- | --- | --- |
| D19 | P1-P4, P9-P10 | P1-P3 source implementation and offline tests are present. P4 dual-exit infrastructure is present, but ORB candidate-to-paper-engine mapping is missing and candidates remain blocked. Full offline regression passes; connected model behavior, UI review, actual-market lifecycle and economic evaluation remain open. Resolve mandate/cost/fill/drawdown assumptions, link prospective outcomes, and review other strategy cards before closing D19. |
| D01-D04, D06, D08 | P2, P6-P7 | Source/reconnect, broker diagnostics, depth semantics, fees, calendar extension, and historical coverage are not proven by fixtures. Build offline in P2; resume only needed current-source, venue and fee checks at P6. D03/D04 are R1 execution gates where depth/fees affect safe sizing and reconciliation. Check reviewed calendar coverage before any session beyond 30 Nov 2026. |
| D05 | P9 | BFO IPFT evidence is a SENSEX/BFO dependency. Resolve effective fee and date before relying on BFO estimates; NIFTY acceptance does not close it. |
| D07, D20-D21 | P6-P7 | Explicitly resumed 22 November. Broker/account match, catalog and stream quote decode pass; qualification has no evidence for all 17 checks, no arm exists, and no supervised paper session ran. Preserve the current gates. |
| D09 | Optional; no R1/R2 blocker | Physical-phone PWA check is parked unless a concrete device-specific defect appears. |
| D10 | P9 or F02 | Add missing analytics only when a strategy decision needs them and reliable inputs exist. Preserve source/method/time and unavailable states; they do not block first ORB release. |
| D11 | P5 | Pending-order markers are partially delivered. Check marker/order/fill lifecycle in UI acceptance and add paging only if actual volume needs it. Never merge working orders with fills. |
| D12-D13 | F05/F07 | Broader manual permissions/order types, bulk exits, and wider amendments are not part of narrow R1. Keep bounded manual controls and gates; design separately before adding these capabilities. |
| D14-D15 | P11, otherwise F11 | Exposure/headroom and paged journal work is partly delivered. Historical equity, defensible slippage references, richer filters, and audited funding/reset work remain open; include in R2 only where useful for daily operation. |
| D16-D17 | P10-P11 | Evidence drill-down and model/version/budget visibility are partly delivered. Preserve unknown legacy links and unknown usage; improve reproducibility, provider usage and monetary cost attribution only where reliable evidence exists. Do not infer costs or completeness from reservations. |
| D18 | P8/P11 if news is surfaced | Feed integration exists, but rights, attribution/storage suitability and India coverage remain evidence-blocked; free feed is delayed 12 hours. Label timing honestly and verify rights/coverage before broader use. Breaking-news strategy is not required for R1. |
| D22 | Future scope F02/F07/F10/F11 | Extended tools, charting, exports and workspace features are backlog. Select each by need; do not make the catalog a hidden release requirement. |
| D23 | P8 | Source-linked read-only chat and browser-local history are implemented and automated checks pass; visual review is blocked. Broader reads and audited idempotent stop-new-entries-today control remain. Keep chat read-only for trading decisions; no order placement, risk changes, resume, or liquidation authority is implied. |
| D24 | F03/F05 | Harness selection was narrowed by the implemented spike; detailed human-intervention, position ownership, recovery, and generated-tool isolation design remains deferred. Reopen when that capability is proposed. |

### Step-by-step milestone order

1. **P1 — Lock the first mandate and plan boundary.** Resolve ORB-to-candidate-plan fields and blockers; retain stricter existing account policy.
2. **P2 — Wire observations to assessments.** Connect supported acquisition, provenance, freshness, gaps and as-of evaluation; unavailable evidence stays visible and honest.
3. **P3 — Connect watcher events to the durable agent path.** Add bounded triggering, deduplication, deadlines, late-result rejection and restart behavior.
4. **P4 — Bridge admitted plans into the existing paper engine.** Generic dual-exit monitoring/persistence and preflight provenance checks exist. Complete reviewed ORB mandate-to-candidate/envelope/exit mapping, deterministic admission into current risk/order/fill/protection/reconciliation services, then test the bridge without weakening gates.
5. **P5 — Make the R1 loop operable in the app.** Show freshness through outcomes, controls, blockers, working orders, fills, exits and recovery state.
6. **P6 — Resume only explicitly selected qualification checks.** Reconfirm current source/calendar, provider, option metadata/depth and costs needed for the chosen NIFTY scope. This is user-controlled and does not follow automatically from reaching this milestone.
7. **P7 — Run and reconcile the narrow paper release.** With qualification and deliberate arm separately in place, capture bounded genuine operation and recovery evidence. Otherwise call it implementation-ready, not accepted/operating.
8. **P8 — Add primary chat.** Provide saved conversation and bounded evidence reads; add only the permitted audited stop command.
9. **P9 — Expand strategies and SENSEX selectively.** Add mechanically defined cards and venue-specific data/fee qualification; do not claim performance from names or fixtures.
10. **P10 — Build an evaluated research and learning loop.** Freeze sample, costs, uncertainty and promotion criteria before economic conclusions; link prospective outcomes and keep candidates inactive until separately admitted.
11. **P11 — Close daily operations and evidence-linked reporting.** Fill personal-product gaps that matter, preserve source/version/accounting links, and distinguish implemented, automated-tested, manually reviewed and market-accepted states.

Finish each milestone's code and automated checks independently of skipped human or market acceptance. Do not claim release acceptance merely because the next milestone's implementation has started.

## Future scope: preserved, not required to finish R1

| ID | Future capability from the discussion | When it makes sense |
| --- | --- | --- |
| F01 | Better real-time information: direct publisher/RBI RSS, feedparser, Google News discovery/GNews, GDELT, supplementary APIs | Evaluate coverage, lag, rights, deduplication, and operational cost; replace the delayed feed when useful. Strategy-required information must be truthful now, but no breaking-news strategy is required for R1 |
| F02 | Broader quantitative/options tools: valid-volume VWAP, change-in-OI, IV/Greeks, volatility regimes, correlations, PCR/max-pain with coverage | Implement tools tied to a decision and supported data. No spot-index volume fiction or decorative metrics |
| F03 | Richer strategy selection, more specialist agents, multi-model review, alternative harnesses | Add only for distinct work or measured quality/recovery benefits. Do not assume more reasoning calls improve trades |
| F04 | More capable generated tools and experiment sandbox | After bounded research is useful; isolate code, credentials, network and resources, and preserve verification/promotion |
| F05 | Human manual trading alongside agents | Define permissions, action/position ownership, intervention behavior, shared capital and external-account reconciliation before expanding current bounded manual mode |
| F06 | Human-versus-agent comparisons | Separate portfolios with matched starting capital, information windows, costs, and execution assumptions; repeated sessions and net outcomes, not a single P&L leaderboard |
| F07 | Expanded order management: bulk exits, richer amendments, order types, baskets | After exact semantics for fill races, reservations, cancellation and partial execution are defined; do not bypass risk or make unsupported buttons appear usable |
| F08 | Advanced portfolio/risk analytics inspired by Aladdin | Scenarios, combined exposures, correlations, factor views, stress tests, and appropriate VaR methodology when they help this account; no institutional infrastructure for its own sake |
| F09 | More short-horizon methods used by experienced traders | Research scalping, event, volatility and other hypotheses with data/cost/latency requirements. No promise of fast daily cash or unbounded short-option exposure |
| F10 | Richer charting and workspace | Drawings, additional studies, scanners, layouts, alerts, chain analytics, markers/paging, preferences, tags, and exports when usage calls for them |
| F11 | Deeper reporting and personal analytics | Historical equity, execution shortfall with defensible references, richer filters/exports, monetary model cost, and contribution analysis |
| F12 | Expanded conversational actions | Explicitly design authority for trade requests, resume, risk changes or liquidation; current chat command limits remain until then |
| F13 | Actual Angel One broker execution | Separate explicit release: current eligibility/terms, account routing, credentials/static IP, exact order semantics, quota handling, reconciliation and bounded real-money introduction. Paper completion does not authorize it |
| F14 | Holdings and broader investment horizons/assets | Separate mandates, data and accounting for longer-horizon investing, other derivatives or delivery holdings. Do not quietly generalize the intraday long-options engine |
| F15 | Funding/reset, broker holdings, demat/banking/settlement workflows | Only if a concrete personal need appears; resets preserve audit history and are not a way to erase losses |
| F16 | Multi-user/commercial platform | Explicitly outside this personal-project direction. Retained only as an older idea, not an accepted future deliverable |

Human workflows remain preparation, setup identification, instrument selection, sizing, execution, protection, close/reconciliation, and review. Agentic workflows automate parts of that same sequence. Tool development should improve those decisions rather than create an agent for each human activity.

## Open decisions that matter, and when to make them

| Decision | Needed by | Handling |
| --- | --- | --- |
| Complete first mandate and premium/underlying exit semantics | P1/P4 | Resolve together with admission implementation; do not change the account's policy implicitly |
| Evidence freshness and opportunity lifetime | P2/P3/P4 | Measure actual source/model delay and skip expired opportunities; never stretch validity to hide latency |
| Which deferred provider/manual/market checks resume | P6 | Explicit user direction is required; elapsed time and this plan are not resumption |
| Economic sample/uncertainty and strategy promotion criteria | P10, before economic conclusions | Freeze before inspecting promotion evidence; not a blocker for implementing an unevaluated research workspace |
| Human intervention and expanded chat authority | F05/F12 | Later design; preserve current permissions now |
| Framework/service decomposition | Only when needed | Start with the existing foundations. Pick one owner for retries/task state rather than overlapping frameworks |
| Broker quotas and eventual real order semantics | F13 | Recheck effective documentation/account behavior; account-wide pacing, exit headroom, finite repricing, and reconciliation are required |

Broker references previously showed a 9-request/second combined place/modify/cancel limit and an older 10/second announcement. Treat [the handoff's dated findings](./STRATEGY-INTELLIGENCE-HANDOFF.md#broker-limits-are-an-execution-constraint) as research, not a permanently verified runtime setting. Market-data, model, and order budgets are independent.

## How we will know the project is closed

R1 closes the narrow running loop. R2 closes the intended personal paper product. For each, distinguish source implementation, automated verification, current-environment operation, provider/model evidence, and actual-market acceptance. Do not collapse them into one word such as done.

The final demonstration should show the user starting a deliberately permitted session, viewing real data and strategy/agent outcomes, following any actual paper orders and exits, receiving reconciled results, and later asking chat to explain them. A no-trade session is valid, but execution acceptance needs separate bounded evidence. Recovery and missing-data behavior are part of the demonstration.

If profitability is poor, investigate strategies and execution using recorded evidence. That does not automatically justify rebuilding the harness or adding agents. If operation is unreliable, fix the reproduced failure before expanding the strategy catalog.

The future-scope table is not a hidden second finish line. Select optional work deliberately after the releases rather than accumulating it as mandatory completion criteria.

## Immediate handoff

> Continue SWAN using `SWAN-DELIVERY-PLAN.md` as the consolidated direction. The user explicitly resumed tests, verification, manual review, broker/provider/live-market checks, qualification, arming and paper-session acceptance. Offline tests and type/lint/build checks pass. Broker/account, catalog and stream checks pass after private login; AI and news checks fail; market acceptance remains blocked by session timing, and no qualification/arm/session exists. Manual UI review is still blocked by browser access. Finish the ORB candidate-to-paper-engine bridge only after mandate review and dual-exit mapping; keep admission fail-closed and preserve all permission gates.

## Acceptance pass — 22 November 2026

- Backend: `376 passed`; Ruff passed; targeted mypy passed for eight market/exit/worker modules. The local database is migrated to `f8c1d2e3a4b5`.
- Frontend: 13 tests passed, TypeScript typecheck passed, and production build passed. One existing Starlette/httpx deprecation warning remains in the backend suite.
- Provider checks after the user completed secure CLI login: broker authentication/account match passed; catalog retrieval passed (316 NFO and 528 BFO contracts expiring within seven days); stream authenticated and decoded an actual quote packet. Since the exchange was closed, quote freshness, both-venue depth, and subscription acceptance remain open. OpenAI model-list returned HTTP 401; NewsData check failed with `NEWS_HTTP_ERROR`. No broker orders were placed, and no credentials were printed. The broker session is day-scoped and must be renewed on the next trading day.
- Manual browser review: attempted against local app, but the browser automation host was unavailable; Comet did not navigate to the local app. UI acceptance remains open.
- Market and paper acceptance: local database contains zero qualifications, zero arms, and zero validation sessions. The qualification matrix has zero evidence for its 8 NFO criteria, 8 BFO criteria, and session rollover. 22 November 2026 is Sunday; no open-market evidence could be accepted. No qualification was fabricated, no arm issued, and no paper order/session started. Resume on an open session with a renewed broker login and current preflight.
- Still needed before admission: review the mandate and map deterministic ORB levels into the saved underlying-exit policy. Candidate preflight remains fail-closed pending this work.

## Source map

### Open-market continuation: 23 November 2026

Latest underlying fixes: introduced explicit estimated fee schedules with disclosed
assumptions and per-order provenance; saved through audited setup. Portfolio now
labels the basis from filled orders, independently of later configuration. Fixed
inclusive provider history boundaries and persisted 137 completed real NIFTY bars
with an honestly EXPIRED ORB assessment. All 400 backend tests, 13 frontend tests,
frontend typecheck/build, Ruff, targeted mypy and diff checks pass. Current execution
configuration is still blocked by depth quantity-unit verification. No owner paper
orders/fills/arms or accepted round trip exist. See the dated correction record.

Paper-flow follow-up: owner-approved risk limits are now saved/audited (capital
100,000; trade risk 0.5%; daily loss 2%; one position; hold 300s; cap 65 units;
quote age 2s; spread 100bps). 101 focused flow/accounting tests pass. The real
owner portfolio endpoint reconciles a flat INR 100,000 account with zero fees/P&L.
No owner paper orders/fills have occurred. Actual-market round-trip acceptance
remains blocked by execution evidence; history also produced a validation error
whose precise cause is unconfirmed. See the dated paper-flow follow-up.

Follow-up: the OpenAI key in `.env` was valid. An inherited environment override
caused the 401. Local services now run without that override; account-scoped AI
authentication and strict structured-output diagnostics pass. This supersedes
the AI failure below, without claiming trading-model quality acceptance.

The owner renewed broker login and resumed connected acceptance. Broker/account,
catalog, fresh NIFTY/SENSEX references, and sampled five-level REST/WebSocket depth
for calls/puts on both venues passed. Fixed the unsupported news request filter;
the news diagnostic now retrieves 10 attributed delayed headlines. Historical
candles are throttled with HTTP 403, previously misclassified as authentication;
recognized throttling now reports `PROVIDER_RATE_LIMITED`. AI still returns 401.
The worker runs in OBSERVATION mode only, with entries paused. Nineteen focused
tests, Ruff and targeted mypy pass. No paper orders, validations, qualifications or
arms exist. Execution-unit/fee evidence, history, model and full UI/qualification
acceptance remain open. See [the dated evidence and closure requirements](./MARKET-ACCEPTANCE-2026-11-23.md).

### Continuation checkpoint: underlying-target bridge and session-stop control

On 22 November the owner explicitly chose underlying target + 20% actual-average-
fill premium stop + maximum five-minute hold. Added a pure ORB mapping path,
provenance/authority-checked staging and worker integration into existing paper
admission. Existing research candidates remain blocked/immutable; staging cannot
qualify, arm or enable an account. The new envelope permits no premium target,
with a required underlying exit policy. The ledger derives stop prices from
actual fills. Entry expiry is distinct from filled-position lifetime, and late
generic evaluations cannot replace the active ORB policy.

Applied migration `f9d2e3a4b5c6` locally. The first full backend run after the
exit-contract change passed 385 tests. Subsequent expanded verification caught
and fixed an idle-validation scheduling regression introduced by the ORB owner
check. Final full backend verification passed 390 tests; a subsequent focused
19-test run covering final runtime changes also passed. Ruff and targeted mypy
passed (19 source files), and `git diff --check` passed. The existing
Starlette/httpx deprecation warning remains. Targeted paper-ledger and
provenance/staging checks pass. Qualification boundaries were
isolated in staging unit tests; no actual qualification evidence was created.

Added authenticated `/api/chat/stop-trading-today` and its chat button. Its audited,
idempotent session stop blocks future entry permission without setting a daily
loss flag, clearing the protection policy, or stopping monitoring. Unit tests
cover duplicate requests, actor/session scope, next-day behavior, and authentication.
Frontend typecheck, all 13 frontend tests, and production build pass.

The local web and API are running for review; web returned HTTP 200 and API
health reported the database connected. No market/trading worker was started.
The API's existing bounded assignment consumer runs with the application.
The local database still has zero qualifications, zero arms, zero validation
sessions and zero application paper orders. Do not call this a running accepted
paper-trading session.

Browser access through the browser host is unavailable, but native Comet control
successfully opened the actual local app. The sign-in screen was visually inspected;
authenticated dashboard/chat review still needs the owner to sign in. No credentials
were requested in chat. The existing OpenAI 401 and news provider failure were not
retested or represented as resolved. Sunday/open-market freshness, qualification,
arming and accepted paper-session evidence remain outstanding. R1 is not closed.

DEFERRED-WORK.md is unchanged by this continuation, following the owner's instruction
for this thread. No broker login, provider/model request, worker start, account arm,
or application paper order was performed. Disposable test schemas contain isolated
test orders only.

- [Product discussion and strategy research design](./AUTONOMOUS-TRADING-DISCUSSION.md).
- [Rough agentic architecture and trading workflows](./ROUGH-AGENTIC-ARCHITECTURE.md).
- [Strategy intelligence direction, events, tools, and broker considerations](./STRATEGY-INTELLIGENCE-HANDOFF.md).
- [Original bounded ORB spec](./STRATEGY-MVP-SPEC.md).
- [Strategy implementation plan and latest closeout](./STRATEGY-IMPLEMENTATION-PLAN.md).
- [Versioned first paper mandate and candidate rules](./PAPER-ORB-MANDATE.md).
- [Agentic spike handoff](./AGENTIC-ARCHITECTURE-SPIKE.md).
- [Agentic implementation checkpoint](./AGENTIC-ARCHITECTURE-IMPLEMENTATION-PLAN.md).
- [Existing project ledger, read only for this consolidation](./DEFERRED-WORK.md). D01-D08 and D20-D21 map primarily to P6/P7; D10-D18 and D22 to P9-P11/future scope; D19 to P1-P4/P9/P10; D23 to P8. D09 is optional physical-device evidence. D24's earlier harness deferral was subsequently narrowed by the authorized spike, while detailed human-intervention design remains future scope. Stable ledger IDs are not changed here.

This plan and [DEFERRED-WORK.md](./DEFERRED-WORK.md) record the explicit resumption and current acceptance evidence. They distinguish offline verification from live-market, qualification, and paper-session acceptance.
