# SWAN strategy intelligence system

Product and architecture handoff, 22 November 2026, Asia/Kolkata.

## Direction

Build a personal strategy intelligence system for intraday NIFTY/SENSEX long-options paper trading, eventually supporting separately authorized broker execution. The objective is useful strategy selection and development that improves net trading outcomes after costs, within a tolerable drawdown. Fixed daily profits are not promised.

This handoff captures the planning conversation the implementation chat has not seen. It describes the larger behavior and design intent, not a prescribed file layout, agent framework, or implementation sequence. Use judgment to split it into small coherent increments grounded in the current code. Do not interpret the full scope as one giant change.

The current ORB increment in [STRATEGY-MVP-SPEC.md](./STRATEGY-MVP-SPEC.md) is one tool within this larger system. Check its current implementation state before duplicating work. Its original four-file boundary applies to that isolated slice, not to all future work described here. This new handoff does not enlarge another chat's already-running task automatically.

The detailed background is [AUTONOMOUS-TRADING-DISCUSSION.md](./AUTONOMOUS-TRADING-DISCUSSION.md). Its numerical strategy examples are research candidates. Existing implementation requirements and the separate discussion have differences in holding horizon and expiry eligibility. Reconcile them explicitly when an increment needs execution integration; the narrower research example does not silently replace account policy.

## What the user wants

- A single-user trading desk over an existing Angel One account, without multi-user product infrastructure or commercial packaging.
- Frontier-model agents using mathematical tools and evidence, not training a new predictive model.
- Predefined strategies first. The user has no proprietary library and wants to start from publicly described approaches.
- Agents that recognize when existing strategies do not fit, adapt suitable components, and develop their own strategies or missing tools.
- Clear strategy recommendations explaining conditions, instrument choice, entry, exits, sizing, evidence, uncertainty, and costs.
- A conversational agent distinct from the autonomous trading loop, with a detailed dashboard available when needed.
- Paper evaluation of strategies, agent versions, deterministic baselines, and eventually humans under comparable conditions.
- Practical profitability and execution quality as the focus. More agents, indicators, or model calls are not progress by themselves.

The user prefers flexible handoffs describing intent, scope, and decisions. Implementation details and reasonable engineering choices belong to the implementation chat. Do not update DEFERRED-WORK.md for this thread. Harness framework selection and detailed human-intervention behavior were held for later discussion; this document describes the event behavior required without choosing that framework.

## The operating model: continuous observation, selective reasoning

Models do not need to think every second. Separate the continuously running market and position services from bounded reasoning jobs.

```text
Market stream -> normalized market state -> incremental features
                                             |
                                deterministic strategy watchers
                                  /                       \
                         relevant change             eligible trigger
                              |                            |
                      bounded agent job          current execution checks
                              |                            |
                   versioned plan or research      order state management

Account/order events -> reconciliation and protection, independently of models
```

The watcher computes only relevant features and predicates as observations arrive. Closing a bar, crossing a level, or changing spread is inexpensive code work compared with model reasoning. Market-data ingestion can be continuous without a REST poll or model request per tick. Missing stream observations still limit what the system knows.

Agents prepare a bounded plan ahead of an opportunity. The plan states what conditions permit action and what invalidates it. When its conditions occur, code revalidates fresh evidence, risk, account authority, and execution feasibility. An agent need not be awake for every trigger. This only applies to a plan that has passed the required strategy and account gates.

Some events genuinely need a new model judgment. If that judgment does not finish before the opportunity expires, skip the opportunity. Never extend evidence or plan validity merely because a model was slow.

## Proposed trigger families

| Trigger | Immediate code response | When to wake an agent |
| --- | --- | --- |
| Session preparation or opening range complete | Check input coverage, calculate features and strategy eligibility | Prepare session context or compare eligible strategies |
| Relevant bar completion | Update affected evaluators | A meaningful eligibility/regime change or a new candidate needs judgment |
| Approach to or crossing of a watched level | Recheck the registered predicate and freshness | Ahead of a trigger if discretionary analysis is needed; no mandatory model call for an already prepared plan |
| Material volatility, liquidity, or trend change | Invalidate affected plans or suspend entries as defined | Reassess strategy suitability |
| Relevant new information | Attribute, timestamp, deduplicate, and assess relevance | Information can materially change a hypothesis; repeated syndicated headlines do not repeatedly wake models |
| Order acknowledgement, fill, rejection, or cancellation | Update order state, reconcile, and protect actual exposure | A later explanation or decision outside existing plan rules is needed |
| Stop, target, holding limit, loss limit, or session cutoff | Apply deterministic protection/exit behavior | Do not wait for a model to protect a position |
| Feed disconnect, stale data, provider failure, or restart | Invalidate stale work, block new entries, reconcile unresolved state | Optional incident diagnosis after immediate controls |
| No suitable strategy | Record why each failed or lacked data | Start bounded research if evidence and research budget allow |
| Session close or an accumulated batch of outcomes | Freeze session records and compute defensible results | Review performance, missed opportunities, and new hypotheses |

A modest scheduled reassessment can complement events, but must not become a second-by-second model loop. Timer frequency, significance thresholds, proximity buffers, and budgets are strategy-dependent choices to measure. There is no agreed universal cadence.

## Prevent repeated wakeups and stale decisions

Use event identity and strategy/input version to deduplicate work. Trigger on state transitions rather than continuously true conditions. Apply cooldowns, hysteresis, and bounded batching where they preserve the strategy semantics. A persistent condition should not repeatedly generate a fresh entry intent.

Give work a deadline, priority, and scope. Coalesce superseded research requests for the same situation. Validate results against the current market/session/account generation before accepting them. Do not let a late response replace a newer decision. Protect position-management capacity when research queues grow.

Maintain bounded reasoning context: current structured snapshot, changed features, strategy assessments, active plan, exposure, relevant attributed information, and linked prior findings. Persist observations and decisions outside the model conversation. Retrieve relevant history rather than append every tick or the entire day to a chat transcript. A replacement model job should be able to reconstruct its assignment from records.

Record each wakeup's reason and outcome so we can measure useful decisions per model call, wasted/superseded work, cost, latency, and missed opportunities. A model outage must not stop deterministic monitoring or exits.

## Strategy library and research

The initial research families are opening-range breakout, trend pullback, range breakout/retest, mean reversion, and failed-breakout reversal. These are hypotheses to formalize and test, not profitable systems inherited from their names.

Separate the underlying setup from its option expression. Direction, timing, IV, expiry, spread, depth, and contract selection all affect option economics. Do not infer an option fill or P&L from an underlying candle.

Each version needs a strategy card covering hypothesis, scope, inputs, eligibility, triggers, contract-selection policy, sizing, exits, invalidation, costs, adaptation bounds, evidence, and evaluation status. Each opportunity links that version to actual observed evidence and a validity deadline.

Assess predefined strategies using explicit fits/does-not-fit/insufficient-data/outside-scope outcomes. Missing data does not prove that a strategy fails. Choose among valid candidates using a declared selection policy and measured evidence where available.

Agent discretion has several levels:

- Selecting an existing evaluated strategy.
- Adapting parameters under an evaluated selection rule.
- Proposing changed rules or a new combination as a new version.
- Defining a missing calculation tool with formula, units, assumptions, and verification needs.
- Developing an original hypothesis and its evaluation method.

The last three create research candidates. They do not inherit execution eligibility from the agent's confidence or from the components they reuse. Generated tool code does not modify active execution or obtain credentials by itself.

Research should happen between opportunities and between sessions as well as when no strategy fits. An agent must not feel compelled to invent an immediately executable trade in a few seconds. It can save a draft, request missing evidence, or abstain.

## From strategy to bounded trading plan

A plan connects an eligible strategy to an instrument universe or selected contract, trigger predicate, evidence dependencies, validity, invalidation conditions, execution price/spread boundaries, sizing policy, exits, and holding limits. It remains separate from an order and from account permission.

The execution layer rechecks live conditions immediately before submission. Signal observed, plan eligible, order submitted, broker acknowledged, partially filled, and filled are distinct states. Pending cancellations and unknown outcomes must remain visible. One underlying event must not accidentally create multiple entry orders through repeated messages or retries.

Actual model output, reviews, deterministic assessments, risk decisions, and outcomes should remain linked so chat can later answer why a strategy was chosen, why it waited, or why execution failed. This larger scope does not authorize widening the current chat's limited command permissions.

## Broker limits are an execution constraint

The SmartAPI reference checked on 22 November 2026 states that place, modify, and cancel requests share a combined maximum of 9 requests per second. Its table lists 500 requests/minute and 1,000/hour for each of these endpoints. Do not assume the minute/hour scope is cumulative or independent without confirmation. An older official forum announcement says 10 requests/second, so there is a published discrepancy. Preserve the source and recheck effective account limits before eventual broker integration.

Sources: [SmartAPI rate-limit reference](https://smartapi.angelone.in/docs/ResponseStructure), [order documentation](https://smartapi.angelone.in/docs/Orders), and [older announcement](https://smartapi.angelone.in/smartapi/forum/topic/5254/important-updates-to-smartapi-in-compliance-with-sebi-guidelines/1?lang=en-GB). These are published limits, not observed account capacity or promised throughput.

Design an account-wide order-request budget, not a limiter per agent. All entry, amendment, cancellation, and exit producers must pass through it. Respect every applicable time window and read-endpoint limit. Start below the documented ceiling with headroom, and make the effective policy explicit rather than hardcode the largest published number.

Reserve capacity for exits and cancellations. Drop or defer research-driven entries before protection work. A priority queue cannot create capacity once a broker quota is exhausted, so conservative admission matters before an entry is placed. Record deferred and unresolved actions honestly.

Do not reprice orders on every tick. Define meaningful price-change thresholds, minimum amendment intervals, finite retries, and opportunity deadlines. Revalidate queued entries at dispatch and discard expired ones. Do not flood the broker with delayed entry requests after recovery.

Use streamed order updates where supported, with bounded reconciliation for gaps. A timeout is an unknown outcome until reconciled, not permission to resubmit blindly. Distinguish provider throttling from authentication/authorization failures. Continuous quote processing, model-call budgets, and broker order quotas are separate resource limits.

Current SWAN is paper-oriented; no live order routing is requested here. Paper planning can expose the same request-budget assumptions for evaluation, but does not establish actual broker throughput or market acceptance.

## Evaluation and learning

Compare deterministic strategy behavior with agent-assisted selection under matched information and cost assumptions. Separate correctness of setup detection, agent decision quality, execution realism, operational reliability, and economic outcomes.

Track net outcomes, drawdown, exposure, fees, fill rate, execution shortfall where defensible, invalid proposals, abstentions, data gaps, model cost, latency, and missed opportunities. Preserve strategy/prompt/tool versions and all failed experiments. Use chronological evaluation with declared criteria and untouched evidence where appropriate.

Historical agent research can be contaminated by a frontier model's knowledge of later events. Be explicit about this limitation and distinguish it from prospective paper evidence. Inadequate option history cannot support fabricated option returns. Existing restrictions on adding a replay service remain in effect unless separately reconsidered.

Post-session learning generates evidence-linked hypotheses and candidate changes. It does not rewrite active rules invisibly. Numerical promotion thresholds, uncertainty treatment, acceptable drawdown, and observation duration still need decisions before evaluation results can justify eligibility. Strategy eligibility never bypasses existing account qualification and arming.

## What a trading day should feel like

Before or early in the session, SWAN checks what it actually knows, prepares context, and registers watchers for eligible strategies. As relevant events arrive, it updates calculations cheaply. Agents compare opportunities when judgment is useful and prepare bounded plans. Code handles eligible triggers and existing protective rules without waiting for repeated model calls.

When nothing fits, SWAN explains why and may research alternatives. When evidence or providers fail, it states the limitation. After the session, it reconciles results and proposes specific experiments. When the user asks, chat retrieves the recorded story and opens the relevant dashboard details rather than inventing a retrospective explanation.

## Starting point for implementation planning

The inspected code already has analysis/proposal/review coordination, structured outputs, audit evidence, token budgets, timeouts, worker evaluation slots, risk controls, and a paper ledger. It lacks a complete strategy intelligence lifecycle and, in the inspected paths, underlying candle history passed to agents. The ORB evaluator is the first isolated strategy tool, not completion of the whole system.

Use the current code to decide the next vertical slice after ORB: a truthful underlying-data path, persisted strategy assessment, and a meaningful event-driven agent invocation are likely prerequisites. The exact order depends on what the other chat has implemented and what genuine stored evidence exists. Identify those dependencies before adding frameworks or many agents.

Current operating boundaries persist: keep worker operation and entries disabled as directed by the checkpoint; do not resume broker login, provider acceptance, or real-money execution. New planning and local implementation do not remove those boundaries. Future broader discussion here should inform subsequent increments without silently expanding work already underway elsewhere.

## Implementation closeout — 22 November 2026

This handoff's current implementation pass is closed. The ORB foundation now
has a local index-history contract and store, deterministic assessments and
watcher records, bounded agent evidence, immutable non-executable plan drafts,
a fail-closed paper preflight, inactive research candidates, authenticated
as-of APIs, and a read-only Strategy intelligence dashboard.

Verification completed: 375 backend tests passed; Ruff and targeted mypy passed;
frontend typecheck, 13 tests, and production build passed. The Alembic revision
`e5f6a7b8c9d0` is the sole head and was applied to the local development
database. PostgreSQL was stopped after checks. No provider or broker call was
made, and no worker or order path was started.

This closes the implementation pass, not the broader strategy lifecycle.
Remaining policy review, economic evaluation, UI/browser acceptance, additional
strategy families, conversational record retrieval, and user-deferred live
market acceptance are recorded under D19 in
[DEFERRED-WORK.md](./DEFERRED-WORK.md). Keep the worker and trading permissions
as currently configured until separately authorized.
