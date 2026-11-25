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
