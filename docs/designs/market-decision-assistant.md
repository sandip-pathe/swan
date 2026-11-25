# SWAN: AI trading decision assistant

Date: 25 November 2026 | Workspace: D:\s\swan-bot | Branch: bot/read-only
Status: DESIGN PROPOSAL; not implemented or market accepted.
Review: plan-ceo-review, HOLD SCOPE using the user's existing constraints.

## 1. Product decision and premise challenge

Help the user choose better SENSEX call/put opportunities, understand why they may
work, know when the thesis no longer holds, and skip weak opportunities. The user
places every order. Chat and Insights are the only screens. Intraday and weekly
research remain distinct horizons in scope. This is not an execution system.

The wrong success metric is fluent answers, indicator count, number of AI agents,
alerts/day or hitting INR 500 every day. The outcome is timely, useful decisions
whose net results, downside and failures can be evaluated without hindsight.
Without this change the existing service remains an indicator-description tool
with no demonstrated trading advantage. A different model alone will not fix it.

User constraints already settled: one/two occasional users; Oracle 1 GiB; existing
Vercel/Firebase/Angel One/OpenAI setup; low token spending; local-first history;
important starred backend retention; 5% position-premium loss reference. The exact
active capital is not chosen between INR 25k and INR 1 lakh. Do not infer sizing.

Three alternatives considered (design coverage, not profitability scores):

| Approach | Coverage | Effort human / AI-assisted | Benefits | Costs/risks |
|---|---|---|---|---|
| A. On-demand analyst over existing polling | 5/10 | S / S | Fewest files; reuses current chat/store | Cannot reliably watch triggers; preserves repeated history work; weak lifecycle |
| B. Event-driven research and conditional ideas | 10/10 intended scope | L / M | Reuses infra; selective model use; supports timing, costs and evidence | Needs verified streaming/depth, event sources and prospective evaluation |
| C. Multi-agent trading research platform | 10/10 plus unrelated breadth | XL / L | Flexible experiments and many strategies | More orchestration, token spend and operational burden; no demonstrated need |

Recommendation: B. Keep the market event loop and bounded research jobs inside
one collector process, API separate. No Redis, Kafka, distributed workers or
locally trained prediction model. Estimates describe build complexity, not market
acceptance duration. Live observation cannot be compressed by faster coding.

Landscape synthesis: established tools separate explicit alerts/strategy rules
from research and evaluation. TrendSpider describes AI strategy development and
backtesting; TradingView documents bar-close alerts to avoid intrabar repainting.
Those are product/mechanics references, not evidence that our strategies work.
First-principles choice: for this personal tool, combining a small event engine
with evidence-linked AI reasoning is more useful than copying a large platform.
Sources: [TrendSpider](https://trendspider.com/product/sidekick-ai-trading-assistant/),
[TradingView alert mechanics](https://www.tradingview.com/pine-script-docs/faq/alerts/).

The user's instruction to stop repeated questions takes precedence over the
skill's per-finding approval ceremony. These are review recommendations, not
claims of individual user approvals. No implementation/deployment changes occur
in this review. Optional telemetry/setup prompts are skipped; telemetry stays off.

## 2. What the user receives

Insights has three sections inside the existing screen: current decision context,
ranked active ideas, and archived/saved ideas. Chat explains or challenges the same
idea records. It must not invent a separate recommendation disconnected from them.

Each idea answers:
1. Action: watch, consider buying a call/put, wait, avoid, or reassess a user-reported position.
2. Thesis and horizon: what changed and why the opportunity could exist.
3. Evidence and opposition: price structure, participation/options observations,
   verified catalyst if relevant, plus the strongest contrary evidence.
4. Conditions: exact entry trigger, invalidation, scenario targets and time expiry.
5. Actual contract: strike, expiry, lot, current bid/ask, spread and observation age.
6. Economics: premium required, whole lots, charges/slippage assumptions, net upside
   and downside scenarios, and compatibility with the 5% position reference.
7. Status: what has happened versus what is still conditional, validation/strategy
   version, source times and historical evaluation status.

Do not fabricate calibrated win probabilities. Separate data completeness,
agreement of evidence and measured strategy performance; none is a confidence
percentage by itself. A watch idea must never look like a triggered opportunity.

Example shape, deliberately without invented market prices:
"SENSEX call candidate: wait for a completed break and successful retest of the
session range. The trend supports continuation; weak participation argues against
it. No entry yet. Contract feasibility and fresh spread must pass at trigger time.
Invalidate on the specified failed-retest condition; expire at the recorded time."

One/two trades is the user's preferred decision frequency, not a forced signal
quota. Invalidation updates must not be suppressed to meet an alert quota. No
eligible idea is an explained result, not permission to lower the requirements.

## 3. What already exists and what changes

| Existing code | Reuse / change |
|---|---|
| services/bot/app.py, store.py | Reuse auth, SQLite WAL, cursor sync/stars; add versioned idea/events/jobs |
| services/bot/worker.py | Replace repeated session polling with stateful event scheduling and bounded recovery |
| services/bot/analysis.py | Split dependency windows; opening range and rolling calculations validate independently |
| services/market/stream.py | Audit/reuse decoder, reference identity, bounded cache and reconnect invalidation; no legacy worker startup |
| services/market/catalog.py | Reuse metadata validation; bound download/parse memory and persist only selected contracts |
| services/market/index_history.py | Reuse validation for bootstrap/repair; add separate multi-session daily-history path |
| services/agents/news.py | Reuse attribution/parsing only after source review; existing NewsData branch declares 43,200s delay |
| services/agents/contracts.py, checks.py | Inspect reusable typed validation; do not revive the trading pipeline/DB |
| services/bot/chat.py | Replace recommendation prohibition alongside grounded idea tools, not as a standalone prompt edit |
| apps/web/src/app/bot-home.tsx, chat.tsx | Reuse two screens, archive and Firebase; add idea state/detail/explanation |
| Oracle compose, auto-login, PWA | Keep current small deployment; old services remain stopped |

Critical observations from the audit: the current gap check invalidates a whole
session; changing available_at regenerates evidence IDs; catalog parsing loads a
complete JSON master; worker catches all unexpected exceptions with generic logs;
chat's digit rejection limits useful analysis; source config currently has no feeds.
Refactor these at their relevant boundary, not through a rewrite of unrelated code.
Old passing test counts predate these changes. No current acceptance is inferred.

## 4. Architecture and data ownership

```text
 Angel One stream ----> normalized, timestamped observations ----+
 verified history ---> bootstrap / targeted repair --------------+--> rolling state
 contract master ----> selected SENSEX contracts ----------------+       |
 source feeds -------> attributed, deduplicated event records ----+       v
                                                                strategy candidates
                                                                      |
                                                 compact evidence --> bounded AI job
                                                                      |
                                           deterministic feasibility + freshness check
                                                                      |
                                                               idea + revisions
                                                                      |
                            SQLite <---- authenticated API ----------> PWA archive
                                                                      |
                                                               user decides/orders
```

Keep one market collector singleton and one API process behind Caddy. Inside the
collector, asynchronous stream, feed scheduling and one research job are tasks,
not separate always-running services. SQLite is the shared durable boundary;
bounded in-memory rolling state is rebuilt from a checkpoint after restart.
No order methods/tools are registered in the bot. Login secrets stay in the
existing separate one-shot job, not available to the model or browser.

Durable records: instrument metadata/version; observations/checkpoints; source
events; candidates; research jobs; idea revisions; per-owner stars/reported entries;
usage reservations; minimal prospective evaluation records. Use additive tables,
explicit schemas and indexes on instrument/time, job state, idea revision/cursor.

Raw histories remain short-lived/bounded. Keep existing 7-day/1,000 transient
insight buffer and 200 stars/account. User-reported entries are important private
records explicitly saved by the user, not inferred holdings. Proposed evaluation
retention is compact event/outcome metadata, not permanent full raw insights;
make its retention visible rather than silently changing the local-first contract.

## 5. Event processing and algorithms

Receiving a price does not mean rescanning the universe. Use a small adaptive
watchlist: SENSEX, NIFTY for corroboration, and initially at most eight selected
SENSEX option contracts. Contract selection follows current master metadata,
expiry, premium feasibility and liquidity; it is not a hardcoded strike list.

| Event | Work | AI? |
|---|---|---|
| Startup | Load checkpoint; verify session/master; bootstrap required windows | No |
| Quote/depth update | Identity/time check, update bounded latest state; evaluate armed price conditions | No |
| Completed 1-minute bar | Update rolling sums/ranges; aggregate confirmed 5/15-minute bars | No |
| Confirmed setup transition | Re-evaluate only dependent strategy; save candidate | Once if useful and budget allows |
| Relevant new verified announcement | Deduplicate, establish event time/relevance, reconsider affected ideas | Only material evidence changes |
| Reconnect/gap | Invalidate affected windows; bounded targeted repair, not full-session polling | No |
| End of session | Daily-history reconciliation and active idea expiry | Optional compact recap |
| Weekly scheduled/explicit research | Verified multi-session daily/weekly context; separate expiry policy | Bounded job |

Start with two explicit, unvalidated strategy families: confirmed breakout/retest
continuation and failed-breakout reversal. Regime context uses trend/range/volatility
and verified participation where available. No volume-derived index VWAP: indices
do not provide traded index volume. Futures/options participation must identify
the actual instrument used. Optional variables cannot silently become mandatory
or be represented as observed when unavailable.

Precise strategy thresholds, lookback windows, retest semantics, expiry rules and
required evidence must be written as versioned strategy definitions before coding
candidate publication. They are engineering/research decisions still to specify,
not a claim of an established edge. Avoid searching hundreds of variants and
selecting the best in-sample curve. Weekly research uses its own daily histories
and rules, not an intraday signal relabelled as a weekly prediction.

AI may also surface a new evidence-linked scenario outside the two seed families
from a material event or explicit research question. Save it as a labelled research
hypothesis, with counterarguments and a way to evaluate it. It is not silently
promoted to an evaluated strategy or an eligible trade because the prose sounds
convincing. This preserves AI discovery without making every price update a model job.

### Dependency-aware missing data

```text
 missing 15:16 minute
   +--> opening range 09:15-09:30: unaffected if its own evidence is complete
   +--> rolling 20 bars spanning 15:16: unavailable until repaired/window rolls on
   +--> today's high/low or complete-day statistics: incomplete
   +--> fresh quote/depth: independently usable for a price observation
   +--> strategy requiring the missing window: cannot become eligible
```

Stream-built candles are a separate source from broker historical candles. Tick
loss or a reconnect means affected bars are incomplete even if some ticks arrived.
Do not fill missing minutes with prior close or mix sources without provenance.
Completed-bar decisions cannot use later candles. Retain original revisions when
the provider corrects a bar; recompute and supersede affected ideas visibly.

## 6. AI research and mechanical verification

The model receives a compact packet: candidate, strategy definition, relevant
confirmed features, selected contract snapshots, attributed event excerpts,
counterevidence and known gaps. It may propose a conditional thesis or abstain.
It cannot browse arbitrary URLs, place orders, authorize data completeness or
calculate authoritative position size/fees. News/report text is untrusted data.

Output schema: thesis, evidence IDs, counterarguments, proposed direction/horizon,
structured trigger/invalidation/scenario expressions referencing allowed features,
missing inputs and abstention reason. Render all market numbers from the validated
packet/calculation layer. Replace the current blanket ban on digits with validation
of each quoted numeric claim; do not trust arbitrary model prices or probability.

Code checks contract identity, horizon, source age, rule consistency, executable
bid/ask/spread, whole-lot affordability, cost assumptions, and downside compatibility.
A 5% premium reference does not force a strategy stop inside ordinary noise. If a
credible invalidation needs more downside, say incompatible/skip, not fabricate a
tighter stop. Overnight gaps and option decay remain explicit scenario limitations.

After any model wait, recheck trigger and fresh pricing before marking an idea
eligible. A promising candidate that expired while AI was reasoning is not ready.
No valid model result means analysis-only/watch status with an explicit reason.

Reuse the existing global conservative 30k-token daily reservation ceiling (or the
lower configured allowance), single concurrent call, no automatic model retries.
Chat and proactive research share the budget. Bound queue to 16 pending jobs;
deduplicate by candidate/evidence/strategy/model versions, replace superseded jobs,
discard expired jobs before spending. Cache by those versions and relevant context.
Budget exhaustion pauses new AI work, not market collection or invalidation alerts.

## 7. State machines and user interaction

```text
Idea: candidate -> watch -> trigger_pending -> eligible
          |         |              |             |
          +---------+--------------+-------------+--> invalidated / expired
          +-------> rejected (data/risk/liquidity/cost conflict)
active + source loss -> suspended -> revalidated revision OR invalidated/expired
eligible + new opposing evidence -> updated revision OR invalidated

Research job: queued -> reserved -> running -> validated -> applied
               |          |           +--> unavailable / rejected / superseded
               +---------> expired
crash after reservation -> mark unknown usage, do not refund/retry blindly

User: Insights -> idea detail -> Chat about this idea -> back to same revision
                         +--> star / unstar
                         +--> optional "I entered" with manual premium/time/quantity
                              (reported, never broker-confirmed or automatically exited)
```

Immutable revisions plus compare-and-swap expected version prevent double clicks,
old background jobs or old clients from making stale ideas eligible. Terminal
ideas never silently resurrect; a new thesis gets a new ID. A user-reported entry
does not convert hypothetical targets into realized profit. Opposing call/put
candidates show the conflict; mutually incompatible active ideas cannot both be
ranked as the same preferred decision without explanation.

UI states: loading restores local records first; empty means no eligible setup
with reasons; partial means named missing dependencies; errors retain old records
as historical; eligible shows age and conditions; expired/suspended disables
current-action styling. Mobile prioritizes action/state, reason, downside, then
sources. Keyboard focus, 44px controls, text state labels and accessible live-region
updates are required. No third dashboard screen or decorative confidence gauges.

## 8. Error/rescue and failure-mode registry

All rows below are REQUIRED IMPLEMENTATION, not claims of existing tests/rescues.
User-visible state plus structured reason/event ID are required for each failure.
Never log tokens, login secrets, full private chats or raw authentication headers.

| Path / exception or named reason | Rescue / user impact | Verification |
|---|---|---|
| Stream / WebSocketException, TimeoutError | Backoff+jitter; generation invalidation; mark affected data unavailable | disconnect/reconnect replay |
| Auth / AuthenticationRequired | Await separate login; no busy retry or trade fallback | expired session; next scheduled login |
| Decoder / ValueError, ValidationError | Reject packet; bounded anomaly counter; identify dependency loss | wrong identity, malformed/future/out-of-order packets |
| History / ProviderError, timeout, 429 | Rate-budgeted targeted repair; preserve incomplete state | persistent four-minute SENSEX gap; exhausted retry |
| Catalog / HTTPError, invalid schema, empty master | Keep timestamped prior master for display; block new unverified contracts | stale master, lot/expiry revision, memory cap |
| Events / HTTPError, parse error, empty feed | Mark source unavailable or genuinely empty distinctly; no invented catalyst | outage vs zero items; missing/old publication time |
| Strategy / missing dependency, conflicting correction | Mark unavailable, recompute/supersede affected idea | unrelated gap preserves opening range; used gap blocks rule |
| Model / timeout, HTTP error, refusal, empty/malformed output | Separate safe reason; charged reservation retained; no automatic retry | one case per distinct outcome |
| Model verification / unsupported claim, unknown evidence ID | Reject output; show watch/unavailable reason | malicious report; invented price/probability |
| Budget / limit reached, concurrent reservation | Atomic reservation; queue/skip; collection continues | concurrent chat/job and midnight rollover |
| SQLite / OperationalError, IntegrityError | Bounded busy handling; no cursor/eligibility acknowledgement before commit | lock, disk full, crash between state/event writes |
| API / 401,403,409,404 | Reauthenticate, deny, refresh revision, or explain expiry respectively | wrong owner, stale revision, expired unstarred record |
| Device / DOMException, eviction, offline | Warn archive failure; cursor atomicity; resync on reconnect | quota failure, account switch, long offline period |
| Delivery / subscriber disconnect, duplicate event | Idempotent cursor catch-up; timestamps expire locally | hide/reopen, deploy disconnect, duplicate revision |

Every implementation row needs rescued status, test evidence, user-visible reason
and safe logs before release. A catch-all supervisor may preserve process health
but must emit a sanitized exception type/correlation ID; generic silence is a
critical defect. Source/model failures do not restart PostgreSQL or old workers.

Security review, additional to the failure registry:

| Threat | Likelihood / impact | Required design mitigation |
|---|---|---|
| News/report prompt injection | High / high | Treat source content as quoted evidence; no source instructions become tools, credentials or validation authority |
| Arbitrary report URL / SSRF | Medium / high | Fetch only configured HTTPS source hosts; block private/link-local addresses and revalidate redirects/DNS; bounded content/time |
| Cross-owner reported entry/star access | Medium / high | Reuse verified Firebase binding; owner scope every private lookup/write; reject forged owner fields |
| Model token abuse | Medium / medium | Shared atomic reservations, per-user request limits, one model call, bounded queue/context/output |
| Accidental trading authority | Low / high | Bot tool/API allowlist contains no order methods; inspect dependencies and keep retired runtime stopped |
| Injection or executable model output | Medium / high | Parameterized SQL, no shell evaluation, typed expressions over an allowlisted feature/operator set, safe text rendering |
| Secret leakage in traces/cache | Medium / high | Redact credentials; private chat/evidence access scoped; no secrets in model packet, event URL or public service-worker cache |

No source/library capability or licensing is inferred from the old adapter merely
existing. No new dependency is selected until the engineering review evaluates it.

Four paths per new flow:
```text
market: valid -> state | missing -> unavailable | empty -> no observation | error -> backoff
events: valid -> source event | missing -> no catalyst claim | empty -> checked/no new event | error -> degraded feed
AI: valid -> verifier | missing -> watch only | empty/refusal -> unavailable | error -> no retry/budget retained
publish: committed -> cursor | missing idea -> 404 | no delta -> unchanged | storage error -> no success acknowledgement
```

## 9. Test and evaluation design

This review proposes tests; no test suite or broker/model call runs in this pass.

```text
Unit: packet identity/time -> rolling dependency windows -> strategy transitions
      -> cost/lot math -> model schema/citations -> ranking/expiry
Integration: replay + checkpoint/restart + corrections -> idea revisions + outbox
             -> owner auth + delta cursor/stars + daily budget/cache
System: mobile PWA -> idea detail/chat -> offline/reconnect -> latest revision
Live acceptance: supported SENSEX feed/depth/history and timing, then shadow ideas
Evaluation: frozen rules + point-in-time inputs -> forward net scenarios/outcomes
```

Must cover happy/nil/empty/error paths from the registry, duplicate delivery,
same-timestamp conflicts, DST-independent IST boundaries, lot changes, insufficient
capital, spread wider than risk allowance, close-before-trigger, delayed AI output,
budget/date rollover, concurrent claims and crash between commit/notification.
Use injected clocks/replays for deterministic tests; do not make unit tests depend
on live providers. Chaos acceptance: kill collector during an active idea, disconnect
feed, fill the pending job queue and restart without duplicate/late recommendations.

Prompt evaluation baseline: existing deterministic context. Cases include aligned
and conflicting evidence, missing options, stale news, missing candles, a malicious
report, impossible 5% downside fit, unknown horizon and a genuinely empty market.
Score claim support, calculation accuracy, useful decision specificity and correct
abstention separately. Model prose quality is not profitability validation.

Track all eligible candidates prospectively, not just starred winners. Freeze
strategy version and separate validation periods from parameter selection. Use
timestamped bid/ask-aware hypothetical entries/exits and conservative cost/slippage
assumptions, not hindsight last prices. Track target/invalidation/expiry order,
adverse/favourable excursion, net expectancy, drawdown and missing-data exclusions.
Actual realized P&L needs user-reported fills; do not label simulated fills actual.
No win-rate/profitability claim before adequate out-of-sample evidence and explicit
review of sample size, exclusions and stability. Sample sufficiency is unresolved.

## 10. Performance, operations and delivery

Keep compute bounded: 2 index states, <=8 option quote states, fixed rolling
buffers, 16 pending research jobs, 1 model call, bounded feed/item sizes, paged DB
reads and indexed cursors. Defer bulk master parsing/research/backups from the
latency-sensitive loop; asynchronous I/O does not make CPU parsing nonblocking.
One HTTP client per provider, small connection limits and centralized rate budgets.

Proposed acceptance targets, NOT measured guarantees: healthy in-session option
quotes used for eligibility <=5s old; receipt-to-local feature update p95 <100ms;
deterministic event-to-API publication p95 <1s; connected foreground publication-to-
display p95 <2s via authenticated event notification with existing delta catch-up.
Bar-close strategies necessarily wait for close; model reasoning adds latency.
Expire slow jobs rather than use an old packet. Verify actual provider source
timestamps and host CPU steal before accepting these targets; relax no checks to
make a latency chart look good. Existing 15s polling remains a degraded fallback.

Use an authenticated fetch event stream (not a token-bearing URL), small outbox
notifications and SQLite delta reads; websocket market input is independent of
browser delivery. Closed-app push is a separate delivery acceptance task, not
guaranteed by installable PWA status. Browser/network suspension always displays
last received time and historical state. Push permissions must be user initiated.

Metrics: source age/gaps and stream generation, event/feature lag, strategy reject
reasons, research queue age, reserved/reported tokens, model failure/validation
rates, publication/delivery lag, SQLite size/busy time, process memory and CPU steal.
Expose a compact authenticated status read within Insights, not a new dashboard.
Alert on sustained source loss, no worker heartbeat, disk pressure or publication
stalls. Runbooks specify recovery/reconciliation, source disable and rollback.

At 10x symbols the full master parse/SQLite writes/streaming decode break before
LLM math; bound scope rather than add workers. At 100x users this personal design
needs a new capacity review. Oracle and the provider are single points of failure;
feature validation cannot promise VM availability. Daily consistent SQLite backup,
bounded retention, off-host encrypted copy and an actual restore exercise are
required for important saved records. Never copy runtime secrets into artifacts.

## 11. Rollout, reversibility and engineering sequence

```text
versioned additive schema + backup/restore proof
  -> stream/dependency engine in shadow mode (current UI/API continue)
  -> contract/cost feasibility + strategy replay
  -> conditional idea records (experimental, no performance claim)
  -> triggered AI/news with schema/evidence validation
  -> foreground delivery + PWA lifecycle states
  -> open-session acceptance + prospective results review
  -> separately accepted weekly history/rules on same idea contract
```

Every stage includes its error paths, recovery and tests. Intraday first is build
ordering, not silent cancellation of weekly research. News and option feasibility
cannot be claimed delivered by an intraday indicator release. Feature flags:
new collector, idea publication, proactive research and source-specific feeds.
Old clients see version/capability metadata and safe historical observations;
do not make a partially deployed frontend render experimental ideas as actionable.

```text
bad deploy -> disable idea publication/research -> retain existing records
          -> stop new collector before starting old bot collector
          -> previous bot image + compatible SQLite schema -> health/auth checks
          -> reconcile pending jobs/outbox; keep rejected revisions for audit
```

Rollback restores the previous BOT, not the retired trading stack. Do not remove
columns or rewrite old records during initial rollout. Reversibility: 4/5 with
additive schemas; provider contracts and delayed-source limitations remain debt.
First five minutes: identity/auth/route boundaries, singleton and DB compatibility.
First hour/open session: source age, replay parity, job expiries, bounded resources,
no duplicate publication and zero order calls. Vercel remains user deployed.

## Dream state delta and deferred work

```text
CURRENT: range/SMA descriptions + restricted optional explanation
PLAN: event-driven evidence -> conditional SENSEX ideas -> lifecycle/evaluation
12 MONTH IDEAL: proven useful strategies across horizons, calibrated uncertainty,
               trustworthy event research and measured fast delivery, still manual execution
```

NOT in scope: autonomous orders (explicitly excluded); naked selling/complex
multi-leg execution (not requested); all-market scanning (resource/value mismatch);
local model training/self-optimizing agents (no measured need); reviving old trading
services (unnecessary overhead); invented news, interpolation or backtest claims.
Weekly research, sourced news/reports, closed-app delivery and backups are retained
scope requiring staged acceptance, not excluded features. D34 remains the backlog
authority; D26 tracks calendar/provider operation. No competing TODOS.md is created.

## Implementation tasks

All effort labels are rough engineering size, not guarantees or market-validation
time. AI assistance compresses code writing, not source permissions or observation.

- [ ] T1 (P1, human L / AI M): Define versioned idea/evidence/rule contracts and atomic revisions/outbox. Files: services/bot/contracts.py (new), store.py, app.py. Verify: ownership, stale-version, restart and idempotency integration cases.
- [ ] T2 (P1, human L / AI M): Audit/reuse bounded stream adapter and dependency-local rolling state; bootstrap/repair only needed windows. Files: services/market/stream.py, services/bot/worker.py, analysis.py. Verify: raw packet replay, gaps/corrections, reconnect and source continuity.
- [ ] T3 (P1, human M / AI S): Add bounded contract selection and executable pricing/cost/downside checks. Files: services/market/catalog.py, services/bot/feasibility.py (new). Verify: real contract identity, whole-lot limits, bid/ask age and cost sensitivity.
- [ ] T4 (P1, human L / AI M): Specify and implement the two strategy families, conflict/ranking logic and prospective outcome recording. Files: services/bot/strategies.py (new), analysis.py, store.py. Verify: frozen versioned replays and no look-ahead; experimental status until acceptance.
- [ ] T5 (P1, human L / AI M): Configure eligible verified event/report sources and bounded research/verifier/cache/budget flow. Files: services/agents/news.py, config/news-sources.json, services/bot/chat.py, worker.py. Verify: delayed/empty/outage sources and adversarial output evaluation.
- [ ] T6 (P1, human L / AI M): Add idea lifecycle to the existing two screens, event notification/catch-up and offline expiry. Files: apps/web/src/app/bot-home.tsx, chat.tsx, src/lib/bot-archive.ts, services/bot/app.py. Verify: signed-in mobile/desktop, offline, stale revision and account isolation.
- [ ] T7 (P1, human M / AI S): Add metrics, source-specific runbooks, consistent backups/restore and guarded rollout. Files: services/bot/worker.py, store.py, hosting/oracle, BOT-RUNBOOK.md. Verify: host resource envelope, injected failures, restore and rollback; never restart old trading services.
- [ ] T8 (P1 for weekly capability, human L / AI M): Add verified multi-session daily/weekly histories and horizon-specific strategy/expiry semantics. Files: services/market history adapter, services/bot strategy/contracts. Verify: holiday boundaries, adjusted/corrected history and point-in-time weekly replay; keep capability unavailable until accepted.

## Review summary

All 11 inline skill sections were evaluated: architecture, errors, security,
data/interaction edge cases, code quality, tests, performance, observability,
deployment, long-term trajectory and UI. Recommendations are incorporated in the
proposal, not represented as deployed fixes. Reusable patterns: explicit identity
validation, atomic cursor/record persistence and retained source snapshots. Avoid
whole-session invalidation, generic supervisor errors and importing old DB workflows.
No new implementation, live-provider call, test run or deployment in this review.
The installed skill references sections/review-sections.md and jargon-list.json,
but those auxiliary files are absent; the inline eleven-section definitions were
used. No independent review was run, and no engineering clearance is claimed.
The jq helper is absent in this environment, so the autoplan JSONL task
export is not written; the eight build tasks above are the complete task artifact.
Install jq if automatic cross-review task aggregation is desired. This does not
affect the saved design or review of its contents.

Stale-diagram audit: this proposal supersedes the full-history observation workflow
in older BOT-SCOPE sections and the retired agentic/execution diagrams. Historical
documents remain reference only; this design is the target, current RESUME is fact.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| CEO Review | plan-ceo-review | Product scope and architecture | 1 | DONE_WITH_CONCERNS | Recommended B; all 11 areas evaluated; source/edge acceptance unresolved |
| Independent Review | Not run | Second opinion | 0 | NOT RUN | No outside findings incorporated |
| Eng Review | Not run | Implementation and verification | 0 | REQUIRED | Thresholds, source contracts, lifecycle and capacity need concrete specification |
| Design Review | Not run | Two-screen lifecycle UX | 0 | PENDING | Detailed interaction/accessibility review before rollout |
| DX Review | Not applicable | Personal app, no public developer product | 0 | NOT RUN | Operational runbook remains required |

VERDICT: Product design proposal complete with concerns; implementation not cleared; engineering review required.

**UNRESOLVED DECISIONS:**
- Provider capability and resource acceptance for supported SENSEX streaming/depth, historical correction and source permissions/delay.
- Exact versioned strategy thresholds, costs/slippage assumptions and evidence required to claim an evaluated edge.
- Prospective sample sufficiency and compact evaluation-retention policy; no daily profit or calibrated probability claim approved.
- Closed-app delivery and off-host backup implementation/acceptance remain under D34.
