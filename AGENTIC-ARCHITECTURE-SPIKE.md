# SWAN agentic architecture spike

Handoff, 22 November 2026, Asia/Kolkata.

## Start building, then learn

Use [ROUGH-AGENTIC-ARCHITECTURE.md](./ROUGH-AGENTIC-ARCHITECTURE.md) as a working hypothesis. Build a small but complete agent workflow that makes the proposed separation real. We want to find out whether it produces better supported decisions, useful research, and more recoverable operation than the existing fixed pipeline. Do not spend this spike perfecting contracts or designing a universal platform.

The implementation chat has the code and can choose modules, storage, framework, and increments. This handoff supplies the conversation's direction rather than a file allowlist or a prescribed engineering checklist. Begin with a short practical plan, then implement the first coherent path. Keep the remaining architecture flexible.

## Product context

SWAN is a personal, single-user trading desk, initially for intraday NIFTY/SENSEX long-options paper trading. The user wants frontier-model agents that use mathematical tools, assess predefined strategies first, and develop alternatives when those strategies are unsuitable. AI explanations and strategy recommendations are core capabilities. Profit after costs is the eventual objective; activity, confident language, and more agents are not evidence of an edge.

Market observation is continuous code. Model reasoning is bounded and event-driven. Execution and position protection remain deterministic services, independent of model availability. The chat agent is separate from autonomous trading and retrieves the same evidence and artifacts when asked.

## What this spike should make real

Implement one path through:

```text
Relevant event or explicit assessment request
    -> durable assignment
    -> bounded context assembled from actual available records
    -> strategy analyst using typed tools
    -> reviewer
    -> saved reviewed draft, abstention, or unavailable outcome
    -> optional bounded research assignment when appropriate
    -> read back the result and its evidence
```

The output is a reviewed research/trading-plan draft, not an executable order or account permission. Missing evidence is a valid and important outcome. An unavailable draft must not be converted into a StrategyEnvelope or treated as trading eligibility.

Start with the analyst and reviewer. Add a focused research run that can save an alternative hypothesis when the predefined pool is genuinely unsuitable. Do not force a research branch merely because the data is absent. Chat is a consumer of the saved records; a new full chat UI is not needed to demonstrate this architecture.

The wider proposed roles remain strategy analyst, research agent, reviewer, and chat agent. These are bounded assignments, not four permanently active conversations. Reuse the existing analysis/proposal/review behavior where useful, and avoid duplicating its accounting and provider controls.

## Boundaries to preserve without overengineering

- Keep durable assignment history outside the model context. A fresh run should understand its objective, input references, progress, and outcome without the original Python process.
- Let the orchestrator own task routing, deadlines, deduplication, and cancellation. Let the harness own one bounded model/tool loop. They may initially be simple modules in one deployment.
- Give agents task-relevant tools with typed results, evidence identity, timestamps, and explicit unavailable states. Implement a small useful tool surface, not every tool in the long-term architecture.
- Build compact context from records and changes. Do not append all ticks or the entire trading day to a conversation.
- Save shared artifacts such as assessments, hypotheses, drafts, reviews, and findings. Agents communicate through those records rather than an unstructured group chat.
- Separate model failure, deliberate abstention, missing evidence, rejection, expiration, and superseded work. Late responses cannot revive expired opportunities or overwrite newer decisions.
- Keep generated experiments isolated from production credentials and active execution. A research draft can describe a proposed tool; a general code-execution sandbox need not be built unless it is necessary for this slice.

The architecture should tolerate interrupted reasoning. Recover or explicitly terminate work according to its deadline and current evidence rather than blindly retrying every operation. Do not confuse rerunning a model with reproducing the same answer.

## What the code already provides

The inspected AgentPipeline coordinates analysis, proposal, and independent review. StructuredProvider provides schema-constrained output, budget reservations, usage records, and bounded provider requests. Worker evaluation slots, audit records, paper accounting, and risk controls already exist. The existing provider prompt prohibits tool requests; real tool use needs an explicit supported loop or an equally clear tool-assisted workflow, not a prompt claiming tools were called.

The isolated ORB evaluator exists in `services/strategies`. Inspect its current implementation and [STRATEGY-IMPLEMENTATION-PLAN.md](./STRATEGY-IMPLEMENTATION-PLAN.md) before duplicating another chat's work.

The latest inventory in that plan reports no usable underlying index-bar path: latest-reference and market-snapshot tables were empty, and stored history/observed candles were option instruments. Do not assume ORB can run against genuine local index bars. This finding does not prevent implementing the runtime and truthful missing-data path.

RESUME.md was absent during the latest architecture review. Use current code and available handoffs; do not reconstruct a checkpoint from stale conversation context.

## Events and triggers

For the first path, support an explicit assessment request and a clear strategy-relevant event shape. Use actual available observations if there are any. Unit events can exercise orchestration in isolated tests but must not become fake production opportunities.

Later watchers can emit session/range completion, relevant bar close, eligibility transition, level proximity, or material context change. Model invocation should follow a meaningful state transition, with deduplication and bounded work, rather than every market update. Scheduling and provider choices can evolve after the first path works.

Order fills, stops, session cutoffs, and feed failures belong to deterministic operational handling. The spike must not move that handling into a model loop. Broker request quotas and model budgets are different constraints. Existing future broker-limit considerations remain in [STRATEGY-INTELLIGENCE-HANDOFF.md](./STRATEGY-INTELLIGENCE-HANDOFF.md); no live order scheduler is required for this reasoning-only spike.

## Find out whether this is better

Compare with the current fixed pipeline where matched inputs and authorized provider access permit a meaningful comparison. Focus first on supported decisions, truthful missing-data handling, useful tool use, clarity of reasoning, recovery, latency, and spending. Test whether reviewer objections and the research branch add value rather than assume they do.

Use a few representative situations: evidence supports a known setup, no setup fits, necessary evidence is missing, a tool fails, and a run expires or is interrupted. These are evaluation situations, not a requirement to build a replay product or fabricate production records.

Use isolated tests or provider stubs to establish software behavior. They cannot demonstrate actual model quality or economic improvement. Actual model comparison needs separately available and authorized access plus suitable evidence. Existing provider-test deferrals remain in force; do not silently spend model budget. If real comparison cannot run, deliver the implementation with that limitation stated rather than claim better results.

Profitability remains a later empirical question requiring realistic option data and execution assumptions. This spike can establish a more useful architecture before it can establish better P&L.

## Working boundaries and finish point

No broker login, live-market acceptance, worker activation, real-money execution, or permission-gate changes are authorized. Preserve existing unrelated work and coordinate with any implementation already underway. Do not update DEFERRED-WORK.md for this thread. This handoff supersedes the earlier request to postpone all harness exploration, but only for this bounded non-trading spike.

Finish when one complete, inspectable path through durable work, agent/tool interaction, review, and saved outcome exists, with a bounded research branch and honest behavior for missing evidence. Explain what worked, what remains conjecture, and the smallest next experiment. Do not build the entire architecture before returning something useful.

If a framework reduces effort, use it deliberately. If the current Python and PostgreSQL foundations suffice, use them. The success condition is a working end-to-end path we can learn from, not a particular framework or agent count.

## Prompt for the implementation chat

> Implement the spike described in `AGENTIC-ARCHITECTURE-SPIKE.md`, using `ROUGH-AGENTIC-ARCHITECTURE.md` as direction. Inspect current code and the strategy implementation plan, choose a practical sequence, and build one end-to-end path before expanding. Keep architecture choices flexible. Preserve the existing operating boundaries and unrelated work. We want working behavior and evidence about whether this improves on the fixed pipeline, not another comprehensive architecture exercise.
