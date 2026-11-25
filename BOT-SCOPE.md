## Build status: 25 November 2026

Conditional decision-assistant code is on `bot/read-only` and Oracle. The leading
RESUME.md checkpoint distinguishes implementation from observed source failures.
User deploys Vercel. D34 remains open for actual-market, model-quality, device and
outcome acceptance; no orders are placed by this bot.

Current target design: [AI trading decision assistant](./docs/designs/market-decision-assistant.md),
25 November CEO review proposal. It specifies how to deliver the direction below;
it does not describe currently deployed capability. See RESUME.md for actual state.

# Product correction: AI trading decision support

25 November 2026: user clarified that the objective is making better trading bets
using AI, real broker data, news, reports and analysis. An indicator-description
bot is insufficient. No execution means the USER places every order; it does not
exclude evidence-backed trade ideas, directional scenarios or suggested actions.
This section supersedes narrower observation-only product wording below. It is an
accepted product direction, NOT a claim that the following pipeline is implemented.

## Primary deliverable

A ranked, selective stream of actionable SENSEX long-option ideas for intraday use,
with a separate weekly swing horizon. Ideas can suggest watching, considering a
call or put purchase, waiting, avoiding an opportunity, or closing a user-reported
long position. No naked option selling, order routing or autonomous execution is
inferred. No live holdings access/monitoring is implemented. Existing Chat/Insights
UI, local archive, slim host and token limits remain useful infrastructure.

Each idea must identify:
- Horizon, underlying, actual option contract/expiry/lot size and source times.
- Thesis: price action, market participation/options evidence where available,
  relevant verified catalyst, and evidence against the thesis.
- Conditional action and entry trigger; whether it is watch-only or actually
  triggered, supported by sufficiently fresh executable bid/ask observations.
- Invalidation/exit condition, time expiry, targets/scenarios and why they are
  justified. User executes; no guaranteed fill or enforced stop is implied.
- Whole-lot premium required, costs/slippage estimate, net scenarios and the
  user's five-percent position-premium loss reference. If minimum lot, liquidity
  or plausible stop cannot fit, disclose incompatibility rather than force a setup.
- Strategy/version, evidence links and measured historical results when available.
  Unvalidated ideas must be labelled unvalidated. No invented win probabilities,
  confidence percentages or guaranteed daily returns.
- Lifecycle: watch -> trigger met -> invalidated/expired; update the same thesis
  with provenance rather than endlessly issue contradictory standalone signals.

## Intended reasoning pipeline

Verified market/contract data + source-linked announcements/news/reports
-> validation and timestamp alignment
-> deterministic market features and small strategy candidate set
-> AI synthesis of thesis, catalysts, counterarguments and scenarios
-> mechanical checks on identity, freshness, liquidity, costs and risk compatibility
-> rank/publish eligible ideas or an explained no-setup decision
-> track subsequent outcomes for evaluation (not automatic execution).

LLMs reason over concise relevant evidence on meaningful changes or explicit
research requests. They do not fabricate prices, compute authoritative fees/size,
substitute guessed news, or decide whether data passed validation. Mathematical
checks are necessary for credible recommendations; they are not the entire product.
News/report claims require accessible source content and publication/event times.
No full-news/minute model loop. Source outage means withhold affected claims.

## Actual gap and next build order

Current deployed bot has source validation, SENSEX/NIFTY range/SMA observations,
simple deterministic interpretation and optional tightly restricted explanation.
It does NOT yet deliver the recommendation pipeline above. Current model instructions
explicitly prohibit trade commands/entry-exit levels; this is a product mismatch.
Do not merely remove that restriction and emit unsupported recommendations.
First build option/contract quote evidence and conditional idea schema/lifecycle;
then a small explicit strategy set, sourced event/news synthesis, scenario/cost
checks and triggered AI reasoning. Weekly history and outcome evaluation need
separate pipelines and acceptance. Keep price suggestions unpublished until their
inputs exist, and do not mark simulated/fixture performance as market acceptance.

---

# Current bot priorities: 25 November 2026

This section supersedes the earlier proposal below. Product stays read-only with
Chat and Insights. Primary intended use is buying SENSEX options for intraday
sessions and, separately, weekly swing research. Total capital may be INR 25,000
or INR 100,000; INR 6,000 was an example position allocation, not confirmed capital.
User clarified that the 5% loss threshold applies to each position, not total
account capital per day. For a long option, use the position premium paid as the
analysis basis: an INR 6,000 position gives an INR 300 reference loss threshold.
This is an informational scenario, not an enforced maximum or an order instruction;
fees, spread, slippage and gaps can make realized loss larger. The bot does not
trade, place/modify/cancel orders, manage positions or execute stop-losses. The user
makes and executes every trading decision. No account-wide daily limit is inferred.

## What a useful insight must contain

- Instrument/contract identity and horizon; never substitute NIFTY context for a
  SENSEX or option-specific setup. Contract lot/expiry must come from current master.
- Source event time, source received time, publication time, rule version and
  reproducible evidence. A fresh HTTP response alone is not fresh market data.
- What materially changed, counterevidence, invalidation condition and expiry.
- Data health: coverage, age, ordering and gaps. Withhold unsupported conclusions.
- For any future option setup: executable bid/ask, spread/liquidity, expiry,
  premium budget, whole-lot sizing, all fees, estimated slippage and downside.
  An underlying move cannot establish the corresponding option profit.

## Insight catalogue and order

1. Source health and session state: authentication/collection/coverage failures,
   stale observations and recovery. Already displayed as status; durable event
   publication/recovery notifications are not implemented.
2. Intraday context changes: completed-bar opening-range break, return inside,
   trend confirmation/invalidation; publish state transitions, not every candle.
   Existing slice now implements SENSEX and NIFTY range/SMA observations, with separate
   venue calendar checks and bounded gap repair. Actual source continuity and
   confirmed multi-timeframe conditions still require acceptance/implementation.
3. A small watchlist of cost-aware SENSEX option opportunities or explicit no-setup
   explanations. Aim for selectivity compatible with one/two user decisions daily;
   do not suppress genuine invalidation/risk updates to satisfy an alert quota.
   Not implemented; requires contract data and acceptance before actionable claims.
4. Weekly swing context: confirmed daily/weekly structure, event calendar and
   invalidation, with a separately validated multi-session history pipeline.
   Not implemented. Do not reuse intraday freshness or assume weekly option expiry
   equals a safe week-long hold. Overnight gaps and premium decay matter.
5. Official exchange/company announcements through verified feeds. RSS is transport,
   not a reliability guarantee. Retain source links/event times, deduplicate, filter
   relevance and treat content as untrusted. Feed ingestion is not implemented.

## Timing and token contract

The bot does not scalp or execute trades. Current REST collector targets each
completed minute at second 03; it cannot know a completed candle before its close.
Requests may be delayed or fail. Foreground device sync runs every 15 seconds,
including while Chat is open; this reads SQLite and never calls OpenAI. These are
scheduling settings, not measured latency guarantees. Measure source-to-receipt,
receipt-to-publication and publication-to-device separately under open-session load.
Investigate observed missing candles before accepting continuous scans. Do not
increase request frequency to disguise an upstream delay.

Background maths, state-change detection, validation, deduplication and publication
use zero model tokens. Existing chat can request bounded interpretation using only
current structured evidence. No news dump or minute-by-minute model loop. Daily
conservative reservations and single-call concurrency remain enforced. Future feed
summaries should be on-demand or materially triggered, cached and bounded, never
required to publish time-sensitive deterministic facts.

INR 500 net is an evaluation example, not a daily quota or guaranteed result:
2% of INR 25,000, 0.5% of INR 100,000, or 8.33% of an INR 6,000 allocation.
For a long option, net result = (exit premium - entry premium) * quantity - all
charges - slippage. One entry plus one exit already incurs two executed-order
charges; additional exits add costs. Published Angel One pricing currently lists
INR 20 per F&O executed order plus statutory charges. Use versioned applicable
rates and actual contract quantity, not a fixed guessed total cost.
Reference: https://www.angelone.in/exchange-transaction-charges (read 25 Nov 2026).
Evaluate net expectancy, drawdown and skipped opportunities across multiple
sessions; never tune rules to force INR 500 every day.

## Local-first retention implemented in this branch

IndexedDB is scoped to the signed-in account. Initial restore is local; sync uses
a monotonic server cursor, paginates new records and idempotently inserts by ID.
Star changes synchronize across devices; unchanged starred bodies are not resent.
Only the newest 100 device entries render initially, with access to older entries.
Unstarred backend insights/evidence expire after seven days or 1,000 records;
starred records/evidence persist (up to 200 per account) until unstarred and eligible
for cleanup. The short-lived server buffer is necessary for offline catch-up.
Device history persists until sign-out or site-data deletion; browsers may evict it.
Evidence is fetched on demand and is not yet archived locally. Users offline longer
than backend retention may miss unstarred insights. No guarantee of delivery while
the PWA is suspended/closed: push and delivery acknowledgments are not implemented.
PWA caches the public shell/static files; private API responses never enter shared
service-worker cache. Offline fresh sign-in still requires a connection.

## Hosted reduction completed

Oracle now runs bot API, one collector and Caddy; old API/worker/PostgreSQL are
stopped, not destructively deleted. Existing automatic-login timer uses a bounded
one-shot container with --no-deps and does not restart PostgreSQL. Original ledger,
credentials, source and images remain available for rollback. Public API now serves
the bot; Vercel remains the user's deployment task. See BOT-RUNBOOK.md and D34.

---

# SWAN market bot — proposed scope

25 November 2026. Discussion draft, not approved implementation or a claim of
provider/data acceptance. For one or two users. Existing hosted services stay as
they are until a separate migration decision. Broker/live-market acceptance remains
paused. Preserve the existing trading project and its permission gates.

## Outcome

Help the user notice relevant market changes, understand the evidence and ask
follow-up questions. Deliver a small number of defensible observations rather
than constant commentary. No orders, positions, portfolio allocation or automatic
trade management in this new slice.

## First useful version

- NIFTY and SENSEX context, plus at most ten explicitly selected option contracts.
  These are proposed bounds; supported broker coverage must be accepted first.
- Market-hours collection of supported quotes and completed candles. Use one shared
  feed, bounded recovery and persistent snapshots; never fetch once per user.
- Deterministic scans: completed-bar range break/re-entry, trend/indicator change,
  and unusual volume relative to an explicit same-instrument baseline when enough
  valid history exists. Start with range and trend scans; enable volume only after
  source units, baseline coverage and comparability are established.
- On-demand explanations and bounded research using saved evidence. Research means
  comparing the current condition with valid recent history and explaining plausible
  interpretations, counterevidence and missing inputs. Arbitrary web research and
  strategy invention are outside the first version.
- In-app insight feed and chat. One opening context note when inputs are available,
  material-change insights during the session and a closing recap. No external
  messaging integration in the first version.
- News is optional context. Existing 12-hour-delayed feed is unsuitable for live
  catalysts; disclose the delay and omit causal claims unsupported by fresh sources.

## Small worker design

Three logical jobs in one background process, not three model agents or servers:

1. Collector/validator: own supported data subscriptions, normalize accepted records,
   check source identity, timestamps and coverage, save changes and expose health.
2. Calculator/scanner: consume new completed bars; update indicators incrementally;
   emit typed events with exact rule versions, evidence IDs and invalidation conditions.
3. Research/publisher: deduplicate events, select useful changes, optionally request
   one bounded model explanation, validate its claims/citations and save the insight.

API reads saved results; page refresh must not start collection or research. Chat
can enqueue one explicit fresh analysis with an honest queued/running/result status.
Use the existing database queue/claim primitives where suitable; no new Redis,
distributed agents, vector database or load balancer for this scope. One active
collector and one concurrent research task. A busy research job must not delay data
collection. Job keys include instrument/session/bar/rule version to prevent replay.

Collect accepted ticks without running scans/models for every tick. Run scans once
per newly completed one-minute bar and aggregate five-minute bars where valid.
Closed-market collection sleeps on the verified calendar; unavailable calendars
produce unknown status. Recovery has shared quotas and backoff, not one retry loop
per screen. Model work runs on material events or explicit questions, never heartbeat.

## Validation and sanity checks

- Validate instrument/venue/expiry/token mapping, schema, units and finite values.
- Record exchange observation, retrieval and processing times separately. Reject
  future times, ordering regressions and duplicates using source-appropriate rules.
- Check OHLC consistency, expected session/bar boundaries, gaps and completed-bar
  status; do not manufacture bars or assume absent volume is zero.
- Check price and spread consistency. Flag implausible jumps for corroboration;
  retain raw evidence and never silently smooth genuine moves away.
- Price ages and coverage are per dataset. A working heartbeat is not a fresh feed.
  Define numeric freshness limits per provider/data contract before enabling alerts.
- Missing/stale/gapped inputs suppress dependent current insights. Independent valid
  results can remain visible. Historical outputs retain their original as-of time.
- Code calculates all numerical claims. Validate model output shape, permitted IDs,
  instruments, numbers and timestamps against supplied evidence. Unverifiable prose
  falls back to a deterministic fact summary or explicit unavailable result.
- Model review is not independent source verification. No second reviewer model by
  default. Cross-source comparison is optional only when comparable licensed inputs
  exist; one provider passing checks does not prove market truth.

## Insight contract

Each insight contains: instrument and horizon; observed change; deterministic
trigger; source observation time and data age; supporting evidence; interpretation
clearly identified as interpretation; counterevidence/limitations; and when the
condition becomes invalid or needs reassessment. Store source/rule/model versions.
Do not assign uncalibrated probability/confidence scores or imply predictive accuracy.
Do not turn observations into buy/sell commands or personalized contract selection.

Deduplicate by event, suppress unchanged conditions and batch low-priority changes.
Data corrections supersede previous insights explicitly. On restart, resume pending
valid jobs once; expire old jobs and never replay a storm of historical alerts.
Feed states: current, historical, insufficient data, provider unavailable, processing
and failed. An unavailable model must not be shown as 'nothing interesting'.

## Compute and cost boundaries

Keep one copy of shared market inputs for both users. Persist changed snapshots and
completed bars in bounded batches. Bound history windows, retention, subscription
count and queue length. Keep user/chat retention separate from shared market data.
Begin with a proposed maximum six unsolicited model explanations per session across
both users; code-only facts can still publish, with deduplication. Explicit questions
share the existing daily token allowance, concurrency cap and finite deadline. At
the limit, show cached/structured facts and disclose that explanation is unavailable.
Measure tokens, model latency, job age, rejected inputs, duplicate alerts, CPU, memory
and DB time. Set final budgets after observing the first bounded session.

## Reuse and separation

Reuse reviewed market contracts, calendar, candle checks, indicators, source-time
fields, provider adapters, auth, durable jobs and usage accounting. Existing ORB
assessment can become a descriptive scan after removing execution coupling from
the new route. Existing generic trading worker must not simply be renamed: its
validation, qualification, paper ledger and exit watchdog are separate responsibilities.
New bot APIs/workers must have no route/tool that places, arms or manages orders.
Do not remove old protections from running services during this planning pass.

## Acceptance before expansion

1. Offline checks demonstrate rejection of stale/gapped/future/duplicate inputs,
   source-grounded numbers, deterministic event replay and bounded queue recovery.
2. When the user explicitly resumes provider acceptance, inspect one bounded real
   session: compare supported source observations and independent UI values where
   available, record data lag, gaps, failures and recovery. Fixtures cannot close it.
3. Review at least 20 saved outputs: every factual number/citation traces to evidence;
   separate factual correctness from whether the interpretation was useful. Record
   unsupported claims, missed/duplicate events and corrections rather than hiding them.
4. Verify ordinary saved-result API reads stay responsive while research runs on the
   actual host. Provisional target: p95 under two seconds for saved authenticated
   reads; measure request-to-queue acknowledgement separately from model completion.
5. User judges whether insights saved effort compared with looking at the same chart.
   No claims of profitability, predictive edge or research quality from infrastructure
   success. Stop expansion if the first slice is not useful.

## Open product decisions

Confirm universe (indices/options versus selected equities), preferred horizon
(intraday versus multi-day) and what counts as a useful observation. Proposed default
is existing NIFTY/SENSEX coverage, five-minute intraday context and in-app delivery.
Avoid adding notification channels, broad scanners, backtesting/optimization,
continuous multi-agent debate or new data purchases before the first slice passes.

## Sources inspected

- QuantConnect separates universe selection and alpha insights from portfolio,
  risk and execution modules. This bot retains the data/insight responsibilities:
  https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview
- Freqtrade documents the live loop's data/indicator/signal and order-management
  work and cautions against heavy calculations in frequent callbacks:
  https://www.freqtrade.io/en/2026.3/bot-basics/
  https://www.freqtrade.io/en/stable/strategy-callbacks/
- Local inventory: services/agents/README.md, services/worker/README.md,
  services/worker/strategy_watch.py and RESUME.md. Reuse candidates are implemented
  code, not evidence that current hosted data or model quality is accepted.
