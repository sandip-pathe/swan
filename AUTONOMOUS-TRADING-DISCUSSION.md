# SWAN autonomous trading: a separate line of thinking

Discussion captured on 20 November 2026, Asia/Kolkata.

This is a working brainstorming document. It preserves the product discussion and open questions so we can develop them further. It does not replace existing plans, approve implementation, change operating permissions, or authorize trading. Existing documentation and configuration remain unchanged.

## Product intent

SWAN began as an autonomous trading system. The original idea was a bot that tells people when and where to invest. The next step was to let agents act on that information within user-defined permissions, instead of relying on a person to interpret and manually execute every recommendation.

Charts, candles, indicators, and manual trading extend that core idea. They let users inspect the market and trade from SWAN when they choose.

The intended platform has these parts:

- A connection to Angel One, through which humans and agents can eventually trade in the connected broker account.
- An agent system that uses context, news, research, strategies, and mathematical tools to make and manage trading decisions.
- A familiar trading workspace for humans, including charts and relevant instrument and account details.
- A paper environment for testing agents and comparing humans, agent versions, and strategies under controlled conditions.
- A conversational agent that answers questions and invokes permitted research and trading workflows. This agent is distinct from the autonomous trading system.
- A dashboard that users can open when they want detailed evidence, market data, account information, and controls.

The product direction is an autonomous trading system with chat as its main interface and a detailed trading workspace available alongside it.

## Why the priority needs clarification

Recent work has emphasized candles, indicators, contract search, watchlists, and option chains. These are useful supporting capabilities. They do not by themselves establish that the autonomous system makes sound decisions or operates reliably.

The existing workspace plan emphasizes a paper-trading workspace with optional autonomy. This discussion explores giving the autonomous system first priority, with manual trading and charts supporting it. This distinction is recorded here without editing that plan.

Angel One already provides candlestick charts, other chart styles, and TradingView integration with indicators. Familiar broker workflows are useful references, but feature parity is not the main measure of SWAN's progress. A broker app's features also do not prove that identical data or functionality is available through its API.

Source: [Angel One app features](https://www.angelone.in/share-market-app).

## Three approaches discussed

| Approach | Benefit | Tradeoff |
| --- | --- | --- |
| Finish the broker workspace first | Gives humans a familiar manual trading experience | Delays testing the autonomy thesis |
| Add chat over the current pipeline | Makes existing capabilities accessible through conversation | Can make an immature trading system appear more capable than it is |
| Prioritize the trading harness and paper evaluation, with focused chat and dashboard support | Develops and measures the core autonomous capability | Requires backend reliability and evaluation work before a complete polished experience |

We chose to discuss the third approach further. Its architecture and delivery sequence remain proposals, not an approved implementation specification.

## The first complete capability

Proposed milestone:

> SWAN can run a bounded paper-trading session, explain every decision, manage its positions through interruptions, and produce a trustworthy account of the result.

This includes a session with no trades. Abstention can be a valid result. Provider failures, missing evidence, and exhausted budgets must remain distinguishable from a deliberate decision to wait.

## A mandate defines the agent's assignment

Before a session starts, a mandate defines:

- Permitted instruments and venues.
- Trading horizon and session window.
- Capital allocation and risk limits.
- Allowed strategies and available information sources.
- Authority to enter, modify, and exit positions.
- Conditions for pausing, stopping, and handling unresolved positions.

An agent can exercise judgment within that mandate. Changing the mandate is a separate operation with its own permissions.

The first mandate is unresolved. The repository currently targets intraday NIFTY and SENSEX options paper trading. The broader idea also includes investment recommendations. A slower investment horizon would need different context, evaluation, position management, and latency targets.

## Proposed session lifecycle

| Stage | Responsibility |
| --- | --- |
| Prepare | Check market data, account state, dependencies, permissions, and the mandate |
| Observe | Maintain normalized market state and calculate relevant features |
| Research | Retrieve context and assess candidate opportunities |
| Propose | Produce a structured trade hypothesis or an explicit abstention |
| Validate | Check evidence, strategy conditions, freshness, exposure, and risk |
| Execute | Submit an eligible paper order and track its actual outcome |
| Manage | Monitor positions, exits, and changes that invalidate assumptions |
| Reconcile | Verify that orders, fills, positions, and funds agree |
| Review | Explain decisions and evaluate session behavior and results |

This is not a single sequential model conversation. Observation and position management continue while research runs. Research repeats when relevant events justify it. Protective exits and reconciliation must continue when research or chat is unavailable.

## The harness runs the agents reliably

The harness is the software that supplies context, controls tools, saves workflow state, handles failures, and measures results.

Proposed responsibilities include:

- Durable workflow state, interruption handling, and recovery.
- Timestamped evidence with expiry and invalidation rules.
- Typed tool inputs and outputs with explicit units and error states.
- Bounded permissions, execution time, model spending, and tool usage.
- Versioned prompts, skills, strategy definitions, and tool contracts.
- Duplicate prevention and controlled retry behavior.
- A trace connecting evidence, proposal, review, risk checks, orders, fills, and outcomes.
- Evaluations of decision quality, operational behavior, latency, and cost.

The system must distinguish a genuine WAIT decision from stale evidence, a rejected proposal, a provider error, an unresolved order, and a workflow that never completed.

## Proposed agent responsibilities, skills, and tools

Start by testing a small set of bounded responsibilities:

1. Research assembles attributed evidence, relevant context, and uncertainty.
2. Strategy proposal applies a defined strategy and proposes a trade or abstention.
3. Independent review challenges the evidence and proposal.

These are responsibilities to evaluate, not a requirement to create three separate model calls for every opportunity. A review agent must demonstrate enough value to justify its latency and cost.

Skills describe repeatable procedures, such as how to research a market event, assess a strategy, or review a proposal. Tools perform verifiable operations, such as retrieving exposure, calculating indicators, checking spreads, and obtaining account state.

Code enforces calculations, accounting, sizing, permissions, execution state, and risk limits. Models reason over evidence and structured tool results. Agent confidence does not override execution checks.

The current agent documentation already describes analysis, proposal, and independent review producing a short-lived strategy envelope. Deterministic checks govern paper execution. This is a foundation to examine and reuse rather than a reason to rebuild everything.

## Chat and dashboard access the same system

The conversational agent understands user intent, invokes permitted operations, and explains recorded outcomes. The autonomous worker continues independently of an open chat window.

Example requests include:

- "Run today's paper session using my saved mandate."
- "Why haven't you traded today?"
- "Research this contract."
- "Show the evidence behind that decision."
- "Why did you skip that breakout?"
- "Stop opening new positions."

Chat must distinguish stopping new entries from closing existing positions. It must report actual workflow and order state, including pending or failed operations.

Chat responses should link to the relevant session, decision, chart, order, or position in the dashboard. Both interfaces use the same authoritative records. Order status comes from execution records and reconciliation.

## Market speed and agent latency

Real-time market data does not require a model call for every tick. Proposed separation:

```text
Market feed -> normalized state -> calculated signals -> execution checks
                    ^                    ^
             research context     approved strategy rules
                    ^
              research agents

Chat -> permitted commands and queries -> the same underlying services
```

Research can prepare context and bounded proposals ahead of execution. Code evaluates immediate conditions and rechecks current prices, liquidity, exposure, and proposal validity before acting.

Measure research latency separately from execution latency. Track the age of evidence when a proposal is created and when an order becomes eligible. Report tail latency and missed or expired opportunities, not only average model response time.

The existing agent documentation specifies a pipeline deadline of up to 100 seconds. Whether that is acceptable depends on the strategy's opportunity lifetime. No latency target is agreed yet.

## News: freshness is relative to the decision

The user's position is that news always arrives after events and that useful free feeds, libraries, or APIs may already solve enough of the retrieval problem. Investigate existing options before building a custom news service or assuming a paid source is required.

Separate four times where available:

- When the underlying event occurred.
- When the publisher published the information.
- When SWAN first received it.
- When an agent used it to decide.

A provider-imposed delay is separate from publication and collection delays. Old information may still provide useful context. Its suitability depends on the strategy and horizon. Receiving an old article now does not make its contents new evidence.

The current agent README records a 12-hour delay for the configured NewsData free plan. That is an existing configuration constraint, not a claim that all news sources impose the same delay. Provider offerings can change and must be checked before replacement.

### Free sources and libraries to evaluate

The following shortlist came from documentation research on 20 November 2026. No package was installed, feed polled, integration tested, or provider replaced during this discussion.

| Candidate | Proposed use | What remains to verify |
| --- | --- | --- |
| Direct publisher RSS, including Economic Times feeds | Collect Indian business and market headlines without an aggregator layer | Relevant feeds, actual publication-to-receipt lag, completeness, availability, and permitted use |
| RBI official RSS | Obtain policy and central-bank announcements from the primary source | Which feeds match the mandate and how quickly they update |
| Python `feedparser` | Parse RSS and Atom using an existing library | Integration behavior, malformed feeds, timestamps, and conditional retrieval; the library supplies no news coverage itself |
| Open-source `ranahaani/GNews` | Discover Google News RSS results through a Python wrapper | Coverage, indexing delay, redirect handling, reliability, and permitted use; this is distinct from the commercial GNews API service |
| GDELT DOC API | Broader news discovery and topic context | Current service behavior, India relevance, discovery latency, and operational limits; no assumption of tick-level freshness |
| Alpha Vantage news sentiment endpoint | Optional supplementary research | Endpoint entitlement, Indian instrument coverage, freshness, and quota; its general free allowance is 25 requests per day |

Proposed starting experiment: use direct publisher feeds and official RBI updates through a small RSS adapter, with Google News discovery or GDELT as a supplementary candidate. Reuse the existing RSS capability where it fits. Keep sources replaceable and measure them before selecting a replacement.

Normalize titles, publisher URLs, source identity, publication times, receipt times, and known delays. Preserve unknown timestamps as unknown. Deduplicate syndicated stories and repeated headlines so repetition does not become false corroboration.

Source failures should remain visible. Whether partial coverage blocks a particular strategy is an open policy decision. A strategy that requires fresh event coverage needs a different rule from one that uses news only as background context.

Free software and publicly readable feeds do not by themselves establish permission to store full articles or redistribute content. Determine the metadata and content each source permits us to use as part of choosing the adapter.

### News references

- [Economic Times RSS directory and terms](https://economictimes.indiatimes.com/rss.cms).
- [RBI official RSS information](https://www.rbi.org.in/Scripts/rss.aspx).
- [`feedparser` documentation](https://feedparser.readthedocs.io/en/latest/).
- [`ranahaani/GNews` source and README](https://github.com/ranahaani/GNews).
- [GDELT DOC 2.0 API description](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/). This is an older API description, not evidence of current availability or measured latency.
- [Alpha Vantage API documentation](https://www.alphavantage.co/documentation/) and [general free usage limit](https://www.alphavantage.co/support/api-key/).
- [NewsData documentation](https://newsdata.io/documentation). The 12-hour statement above describes the recorded SWAN configuration.

## Human trading and shared account coordination

For eventual trading in one connected broker account, human and agent actions affect the same funds and exposure. A manual purchase changes agent capacity. A manual close invalidates any assumption that the position remains open.

Orders need actor attribution and a defined owner for subsequent position management. Account changes made through the broker app must also be reconciled. The policy for human intervention, agent resumption, and conflicting instructions remains unresolved.

The current implementation is paper-oriented. The intended broker-connected product and its eventual real-money execution path are broader than what this discussion establishes as working today.

## Paper evaluation and fair comparisons

Build evaluation into the first complete session. Compare the agent system with a simple deterministic strategy baseline to determine what agent judgment adds.

Human-versus-agent experiments use separate paper portfolios so participants do not consume each other's capital or alter each other's positions. Match starting capital, instrument universe, decision windows, available information, and execution assumptions. Explicitly record differences in tools and information access.

Equal starting money alone does not make the comparison fair. Include fees, spread, slippage, liquidity, rejected orders, and unresolved exits consistently. Never infer an executable fill merely from a displayed candle price.

Measure:

- Net P&L, drawdown, exposure, turnover, and costs.
- Evidence quality and whether information was available at decision time.
- Strategy adherence, invalid proposals, and risk rejections.
- Review effectiveness and missed mistakes.
- Decision latency, expired opportunities, and model spending.
- Operational failures, recovery, and reconciliation correctness.
- Abstention behavior, including its recorded reasons.

Use repeated sessions and report sample size. Separate software reliability from trading performance. For replay experiments, preserve what was actually knowable at each decision time so later news cannot leak into earlier decisions.

## Proposed priority for this direction

1. Agree on one initial mandate and its decision horizon.
2. Map existing components onto one complete paper-session lifecycle.
3. Identify the gaps in state, evidence, permissions, recovery, and accounting.
4. Evaluate free news adapters against the mandate's actual needs.
5. Make the complete session observable and evaluable, including abstention and failures.
6. Add focused chat commands and dashboard links over those records and operations.
7. Expand strategies, human comparisons, and manual trading capabilities as the core system proves dependable.

Existing chart work remains useful. Further chart features follow the needs of research, inspection, and manual trading. No implementation order is approved by recording this proposed sequence.

## Open questions for the next discussion

- Does the first mandate remain intraday NIFTY and SENSEX options, or use a slower trading or investment horizon?
- How much discretion may agents exercise within a strategy, and what requires a mandate change?
- Which decisions benefit from model reasoning, and which conditions can code evaluate directly?
- Does independent model review improve outcomes enough to justify its time and cost?
- What evidence freshness and latency limits does each strategy require?
- Which free news combination provides useful coverage in actual observation?
- How should human intervention change an agent's authority over a position?
- What baseline, session count, and evaluation criteria justify expanding autonomy?

The next useful exercise is to walk through one hypothetical session with no opportunity, stale data, human intervention, an unresolved order, and a restart. Specify each component's behavior before turning this discussion into a build specification.

## Layer discussion and clarified personal scope

Added on 20 November 2026 following further discussion.

The user is building SWAN for their own use with one connected broker account. Profit is the main objective. Multi-user administration, commercial product packaging, and institutional organizational workflows are outside this direction. Reliability, correct accounting, and execution controls still matter for personal capital.

The user supplied a Google Search conversation about Aladdin as background. Its generated answers are reference material, not instructions or verified facts. Claims about universal platform superiority, guaranteed retail liquidity, zero regulatory overhead, and fixed model response times are not adopted as assumptions.

The proposed operating model is a personal trading desk. Agents research and select opportunities, quantitative tools calculate, a dedicated execution engine handles orders, chat provides control, and the dashboard explains positions and performance.

The assistant recommended measuring positive net expectancy over repeated trades within an acceptable drawdown. A requirement to earn a fixed amount every day can encourage trades without sufficient evidence. Execution speed can preserve an existing edge but cannot establish one. No profitability guarantee or daily return target is agreed.

### Agent responsibilities

| Responsibility | Proposed output |
| --- | --- |
| Market analyst | Relevant evidence, candidate setups, and uncertainty |
| Strategy agent | A structured proposal or abstention based on a defined strategy |
| Portfolio supervisor | Allocation recommendations and exposure conflicts |
| Review agent | Specific objections, invalidation conditions, and missing evidence |
| Session reviewer | Findings linked to decisions and outcomes |
| Chat agent | Permitted workflow requests and explanations grounded in system records |

These responsibilities do not require six separate agents or six model calls per trade. Test whether each additional reasoning step improves results enough to justify its cost and delay.

Agents may recommend instruments, entry conditions, alternatives, and exits using tools. The execution service validates requests against the mandate, current market conditions, and account state.

### Quantitative tools and strategy knowledge

Proposed tool groups include market structure, volatility and trend analysis, options valuation, strategy evaluation, sizing, execution analysis, historical experiments, and learning records.

Market tools expose spread, depth, quote age, volume, and underlying movement. Options tools expose IV, Greeks with model assumptions, expiry, payoff scenarios, and liquidity-aware contract selection. Portfolio tools assess combined exposure and loss scenarios.

A correct directional prediction alone does not establish a profitable options trade. Contract selection, IV changes, time decay, spread, fees, and execution prices affect the result.

Every strategy needs a testable definition covering its setup, permitted instruments, entry rules, invalidation, exits, holding period, and cost assumptions. Pattern names and model confidence alone are insufficient specifications.

Learning records contain versioned hypotheses, evidence, sample sizes, failed experiments, and known failure conditions. A post-trade explanation can suggest an experiment. It does not automatically justify changing the active strategy.

### Harness and deployment candidates

The assistant proposed comparing the existing durable worker with LangGraph for stateful agent workflows. Temporal is a further candidate if long-running workflow recovery becomes difficult to maintain. No framework selection or migration is approved.

LangGraph provides persistence and workflow control. Temporal provides durable orchestration. Neither establishes trading quality or correct broker execution. A small deployment with a few defined processes and PostgreSQL may meet the single-user requirement.

The harness must track task state, evidence and strategy versions, restart behavior, retry eligibility, external effects, invalidation, and provider failures. If an order request times out, reconcile its broker status before retrying. A workflow checkpoint alone does not prevent duplicate external orders.

References: [LangGraph](https://reference.langchain.com/python/langgraph/) and [Temporal durable execution](https://docs.temporal.io/durable-execution).

### Latency, order timing, and slippage

Separate research from immediate execution. Research produces a bounded plan with eligible instruments, trigger conditions, a spread limit, a price boundary, validity period, sizing constraints, and invalidation conditions. Code checks the live trigger and current execution conditions. New evidence may revise or cancel the plan.

For opportunities that remain useful for minutes, model reasoning may fit before entry. For opportunities whose edge expires within seconds, immediate triggers and execution need a code path with agents preparing and supervising the strategy. These are hypotheses to measure against actual strategy behavior, not promised latency figures.

Measure market-data delay where timestamps permit it, calculation delay, proposal and review time, trigger-to-submission time, broker acknowledgement time, time to fills, and decision-price-to-fill shortfall. An acknowledged order is not necessarily filled.

SmartAPI documents shared rate limits across placement, modification, and cancellation, plus order-status updates. Repricing and retry policies must account for those constraints. Source: [SmartAPI documentation](https://smartapi.angelone.in/docs/ResponseStructure).

Paper evaluation must model spreads, available depth, partial fills, adverse movement, fees, and unfilled orders consistently. Limit orders may miss opportunities. More aggressive execution may fill at worse prices. Define and evaluate that tradeoff rather than assuming either order style is always better.

Reference: [QuantConnect slippage models](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/supported-models).

### Platform ideas worth borrowing

- Aladdin provides a reference for a consistent view of positions, exposure, performance, and scenario risk. Its capabilities do not establish that copying its interface or architecture produces intraday alpha. [Aladdin Risk](https://www.blackrock.com/aladdin/platforms/products/aladdin-risk).
- QuantConnect provides a reference for separating signals, allocation, risk, and execution, with explicit simulation assumptions. [Algorithm framework](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview).
- Composer provides a reference for turning a stated strategy into an inspectable, backtestable definition. [Backtesting](https://help.composer.trade/article/67-backtest-basics).

Other referenced portfolio managers, analytics products, and AI copilots serve different jobs. Select individual capabilities that improve this personal trading process rather than combining their feature lists.

### Dashboard priorities

The main view should show net P&L, exposure, remaining risk capacity, positions, unresolved orders, watched opportunities, and conditions for action. Users should be able to inspect why a trade happened or was skipped and which strategies contribute after trading and model costs.

Charts open against the relevant opportunity or position. Decision timelines connect evidence, proposals, checks, orders, and fills. Pausing entries, cancelling orders, and closing positions remain separate operations.

## Confirmed strategy direction: predefined and agent-originated

The user explicitly wants both predefined strategies and strategies developed by agents. AI-generated strategy recommendations and supporting trading details are a core product capability, continuing the original trading-bot idea.

The requested priority is:

1. Assess predefined strategies first against current conditions and available evidence.
2. If none is helpful, let agents research and propose their own strategies.
3. Explain the strategy and supporting details so the user can understand and inspect the recommendation.

This confirms research and proposal capability for agent-originated strategies. The conditions for promoting a new proposal into executable paper trading or eventual live trading remain open. A lack of suitable predefined setups does not itself prove that a newly generated strategy has an edge. Abstention remains a possible outcome.

The user wants this capability to work dependably. Translate that goal into measurable acceptance criteria for coherent strategy definitions, correct tool use, evidence quality, realistic evaluation, and complete explanations. No AI system can guarantee perfect trading outcomes.

### Recommended next discussion: the strategy lifecycle

Define how strategies move from an idea to an evaluated and executable version:

- What belongs in the initial predefined strategy catalog?
- What does "nothing helpful" mean, and when does that trigger new research?
- What structured strategy definition and supporting details must the AI produce?
- What tools and data can it use to test the idea?
- What evaluation distinguishes a plausible proposal from a strategy eligible for paper execution?
- What approval and evidence permit later promotion, and what causes retirement?

This lifecycle determines agent authority, tool requirements, harness state, and the dashboard records. Start by specifying the strategy proposal contract and walking through one predefined setup and one agent-originated idea.

## Strategy system design, 22 November 2026

This section delivers the requested initial catalog, strategy card, adaptation rules, and worked example. It is a research design. No backtest, provider request, broker login, paper session, generated tool execution, or live-market acceptance was performed. Existing permission gates remain unchanged. The current implementation checkpoint requires the worker to remain stopped and entries disabled.

### Confirmed scope and boundaries

The initial focus is intraday NIFTY and SENSEX options. The user has no proprietary strategy library and wants to start with publicly described methods. Agents assess predefined strategies first, then develop alternatives when the available strategies do not suit the situation.

Other short-horizon methods used by experienced traders are research candidates, not an agreed expansion into more asset classes or execution types. Harness selection and human-intervention design are explicitly held for a later discussion. The numerical parameters below are proposed experimental choices, not user-approved settings or profitable recommendations.

The current accepted implementation scope is long-options paper trading. Short options, spreads requiring short legs, and multi-leg execution require separate scope and execution design. Their payoff diagrams do not establish that the current system can execute them.

### Initial research catalog

All five entries start as documented hypotheses, with no SWAN performance evidence. The rules below are our proposed formalizations of publicly described concepts. The references explain concepts, not these exact rules or profitable NIFTY/SENSEX implementations.

| ID | Strategy family | Proposed measurable setup | Invalidation and exit concept | Main failure mode |
| --- | --- | --- | --- | --- |
| S01 | Opening-range breakout | Freeze an opening interval's high and low; require a later completed bar to close outside the range plus a declared buffer | Return through the breakout boundary, protective premium exit, time limit, or target | Whipsaws, chasing an extended move, and costs |
| S02 | Trend pullback continuation | Define direction using completed-bar trend features; require a bounded retracement and a completed-bar resumption trigger | Break of the defined pullback extreme, time limit, or target | A reversal misclassified as a pullback |
| S03 | Range breakout and retest | Freeze a range from an earlier fixed window; require breakout followed by a retest inside a declared tolerance and a confirming close | Failure back inside the range beyond the tolerance, time limit, or target | Repeated retests, subjective ranges, and late confirmation |
| S04 | Mean reversion | Require a non-trending regime and an unusually large deviation from a declared reference, followed by re-entry confirmation | Continued extension beyond a fixed boundary, time limit, or return to reference | Fading a strong directional move |
| S05 | Failed-breakout reversal | Record a prior boundary break, return inside, and confirmation toward the opposite direction | A renewed break beyond the failure extreme, time limit, or an internal range target | A temporary pause misclassified as failure |

For S02-S05, thresholds, reference windows, and precise bar predicates remain to be frozen in individual cards before implementation. S01 is specified below as the first experiment. These families overlap. Do not count closely related variants as independent diversification or corroboration.

VWAP is optional and requires actual traded volume. Identify the precise futures or other traded instrument used as a proxy. Do not calculate a purported spot-index VWAP from missing or fabricated index volume. For S04, a price-only reference is a separate version, not an invisible fallback.

Research references:

- [Zerodha's opening-range discussion](https://inthemoneybyzerodha.substack.com/p/all-about-opening-range-breakout) and [NIFTY-options follow-up](https://www.youtube.com/watch?v=erjnU13EYjk). These motivate examination of ORB and its option expression, not a claim that our experiment has an edge.
- [Zerodha support and resistance](https://zerodha.com/varsity/chapter/support-and-resistance/) for price-level concepts used in breakout, retest, and failure hypotheses.
- [Zerodha indicator notes](https://zerodha.com/varsity/chapter/supplementary-notes-1/) for trend and VWAP concepts.
- [Zerodha delta explanation](https://support.zerodha.com/category/account-opening/glossary/futures-and-options/articles/what-is-delta) for sensitivity and the limits of using delta alone.

### Standard strategy card

Every strategy version, including an agent-originated one, must answer these questions. Unknown evidence remains unknown, rather than receiving a fabricated score.

| Field | Required content |
| --- | --- |
| Identity | Stable strategy ID, immutable version, author, parent version, creation time, and change rationale |
| Provenance | Public references or agent hypothesis; distinguish borrowed concepts from our rules |
| Hypothesis | Why the setup might have an advantage, the mechanism assumed, and observations that would disprove it |
| Scope | Underlying, venue, instrument type, direction, permitted session, and expiry restrictions |
| Inputs | Exact data series, units, timestamp semantics, lookback, freshness limits, and unavailable-input behavior |
| Eligibility | Mechanical regime and session predicates, required history, and no-trade conditions |
| Entry | Observable trigger, completed-bar versus tick semantics, earliest action time, and expiry of the opportunity |
| Option selection | Expiry and strike policy, metadata checks, executable quote/depth requirements, selection tie-breaks, and fallback policy |
| Orders | Supported order type, limit-price boundary, lifetime, partial-fill policy, cancellation rules, and unresolved-order behavior |
| Sizing | Whole-lot calculation, capital and exposure constraints, planned loss assumptions, and applicable policy version |
| Exits | Protective price, market-setup invalidation, target, time stop, end-of-session cutoff, and exit priority |
| Economics | Gross payoff assumptions, fee version, spread and slippage treatment, and cost sensitivity |
| Adaptation | Parameters that may vary, permitted ranges and selection rule, and changes that require a new strategy version |
| Evaluation | Data coverage, chronological splits, all trials, baseline, sample size, metrics, uncertainty, and failure scenarios |
| Lifecycle | Draft, specified, under evaluation, paper-eligible, suspended, or retired; link the evidence for each transition |
| Explanation | Plain-language account of why this version fits now, competing choices, uncertainty, and reasons to abstain |

Separate the strategy definition from a particular opportunity. An opportunity links the strategy version to captured input IDs, observed conditions, selected contract, current sizing result, validity deadline, and subsequent outcome.

### Agent selection, adaptation, and invention

For each assessment, first check whether the data needed to judge the strategy pool exists. Missing inputs are a data limitation, not evidence that all known strategies fail or that invention is justified.

Evaluate each available strategy with explicit results: fits, does not fit, insufficient data, or outside permitted scope. Keep the failed predicates. Selection among fitting candidates uses a declared rule and measured evidence where available. Model confidence is not a calibrated probability of profit.

| Agent action | Example | Treatment |
| --- | --- | --- |
| Select | Choose S01 because its frozen conditions hold | Use the existing evaluated version and a new opportunity record |
| Adapt inside an evaluated policy | Select a declared buffer from a previously tested regime-to-buffer rule | Record the selected value and policy version; do not invent a new value after seeing the outcome |
| Change a rule or untested parameter | Add a VWAP filter or change the opening window | Create a new draft version and evaluate it |
| Combine existing components | Combine a failed breakout with a volatility filter | Treat the combination as a new hypothesis; component evidence does not automatically transfer |
| Create a calculation tool | Define a missing normalized range metric | Specify formula, units, inputs, deterministic checks, and isolated verification before use |
| Create a new strategy | Propose a setup absent from the catalog | Produce a full card, a falsifiable hypothesis, and a research plan |

Agents may draft calculations or code for later isolated verification. This design does not permit generated code to modify the running execution service, install dependencies, retrieve secrets, or grant itself execution authority. Exact sandbox and harness design is deferred.

"No strategy fits" can trigger bounded research. It does not require the agent to produce a trade before the opportunity disappears. Continue observing or abstain while the alternative remains unevaluated.

### Worked example: S01-NIFTY-ORB-LONG-v0.1

This is a frozen candidate for a first research experiment, not an active strategy. Its short parameters make behavior inspectable. They have no established performance advantage. SENSEX requires a separately evaluated venue-specific version.

#### Inputs and opening range

- Use genuine NIFTY spot-index one-minute OHLC for the market setup, with explicit exchange-time timestamps and IST session boundaries.
- Require the exchange calendar to confirm a regular session. This example uses the regular opening interval from 09:15 inclusive to 09:30 exclusive IST. Nonstandard sessions are ineligible for this version.
- Require all 15 completed opening bars. Missing bars make the session ineligible; do not fill gaps with invented bars.
- Freeze H as the highest high and L as the lowest low of those bars. Let W = H - L. Require W > 0.
- Set breakout buffer B = 0.05 * W. The 5% fraction is a research choice.
- Do not use volume, VWAP, news, or hindsight-based trend labels in this minimal baseline. Such additions require separate versions.

#### Entry eligibility and signal

After 09:30, examine completed one-minute bars. A bullish trigger is the first eligible close C above H + B. A bearish trigger is the first eligible close C below L - B. A bar is known only after it completes.

Require the close to be no farther than 0.25 * W beyond the relevant breakout boundary, to make a proposed anti-chasing rule explicit. The exact fraction needs testing. The latest trigger-bar completion is 11:00 IST.

For bullish entry, the underlying invalidation boundary is H - B and the setup target is C + W. For bearish entry, invalidation is L + B and the setup target is C - W. These are research rules, not calibrated reward or probability estimates.

Permit one entry submission attempt per session, across both directions. Unfilled, rejected, and cancelled attempts do not permit another attempt in this version. A signal rejected before submission consumes no attempt, but its one-minute opportunity expires and cannot be revived with a later quote.

The opportunity expires 60 seconds after the trigger bar completes. Recheck fresh underlying observations before submission. The price must remain outside the breakout threshold, within the anti-chasing boundary, and short of the target. A stale or missing observation blocks entry. Historical bar-only research cannot claim to have checked an unrecorded tick path.

#### Option selection and order behavior

Use a long NIFTY call for bullish signals and a long NIFTY put for bearish signals. For this experiment, choose the nearest listed expiry strictly after the current trading date, excluding same-day expiry. Require an actual permitted contract from current metadata.

Choose the strike closest to the underlying observation at selection time. Break an exact strike-distance tie by choosing the lower strike. If that exact contract lacks qualifying executable quotes/depth or fails liquidity, spread, or risk checks, skip it. Do not silently walk to another strike or expiry. Expiry and strike alternatives are separate experiments.

The selected contract is frozen for the opportunity. Use its actual lot size and tick size. Submit a BUY LIMIT at the qualifying observed ask, rounded as required by instrument metadata. The maximum limit is that captured price; do not chase. Cancel an unfilled remainder at the opportunity deadline. If partially filled, cancel the remainder and protect actual filled exposure. An unresolved cancellation or fill remains unresolved until reconciled.

These order semantics are design requirements to check against the paper engine, not a claim that every behavior is implemented. No real broker order is part of this design.

#### Sizing and exits

Use current policy-derived capital and risk headroom, with no new rupee budget invented here. For the research version, a protective premium threshold is 20% below average entry fill, with the target rounded upward to a valid tick to avoid increasing intended loss through rounding. The percentage is an experimental parameter.

Sizing must allow for fees and declared adverse-execution assumptions in addition to the planned premium loss. If one valid lot does not fit policy, abstain. A stop threshold does not cap realized loss during gaps, missing quotes, or poor liquidity. Also record the long option's full-premium-loss scenario.

Exit actual exposure on the first observed applicable condition:

- A qualifying executable bid reaches or falls below the protective premium threshold.
- A fresh underlying observation reaches the invalidation boundary.
- A fresh underlying observation reaches the setup target.
- Thirty minutes have elapsed since the first entry fill.
- The configured mandatory session-exit cutoff is reached.

Stop, invalidation, and mandatory exits take priority over a target if observations do not establish an ordering. Never fill from an index target or option candle merely because a line was touched. Missing executable bids create a pending exit, not an invented fill. No new model response is needed to apply these predefined exits.

#### Illustrative walkthrough, not market evidence

Suppose a fabricated research example has H = 25,000, L = 24,900, W = 100, and B = 5 index points. At 09:36 a completed bar closes at 25,010. The bullish threshold is 25,005 and the maximum allowed close is 25,025. The proposed invalidation is 24,995 and target is 25,110.

This produces a candidate opportunity, not a fill. Contract metadata, actual option quotes, depth, fees, permissions, and sizing are still required. This document supplies none of them and claims no option premium, lot count, return, or actual trade. The hypothetical values belong only to this explanation and must never populate application data.

If the selected call has no qualifying quote, the outcome is insufficient execution data. If the breakout has already extended beyond the allowed boundary, the outcome is an expired or unsuitable opportunity. A bullish index view does not override either outcome.

### Worked agent-originated alternative

Suppose S01 fails because price breaks above H + B and then returns inside the range. The agent first checks S05, since failed breakouts already belong to the catalog. It must not relabel a known strategy as an invention.

If S05 is not fully specified or evaluated, the agent may propose version S05-NIFTY-v0.1: record a completed close above H + B, require a subsequent close below H - B within a declared number of bars, consider a long put, invalidate beyond the recorded failure high, and test a range-based target and time stop. Exact windows, execution rules, and sizing must be frozen in its card before evaluation.

If the agent adds a newly developed cross-index divergence metric, that creates both a tool-verification task and a new strategy-version evaluation. NIFTY and SENSEX observations must be aligned by what was available at decision time. Correlation does not prove that divergence predicts reversal.

The agent's output explains the mechanism it suspects, the predefined candidates it rejected, the new elements, required data, tests, and reasons the proposal could fail. Until that evidence exists, the outcome is a research proposal with no entry authority.

### Evaluation and promotion rules

Use this proposed lifecycle: draft -> specified -> under evaluation -> paper-eligible -> suspended or retired. "Paper-eligible" is an evaluation label and does not bypass account qualification, explicit arming, or other current gates. Real-money promotion is outside this design.

Before evaluation, freeze the card, parameter trials, baseline, data split, and decision criteria. Log every tested variant, including failures. Use chronological development, validation, and untouched holdout periods. Repeated inspection or tuning on the holdout makes it development data and requires a new untouched period.

Where trades overlap, split by session and avoid leaking information across boundaries. Agents performing historical research must receive only information available then. A frontier model may already know later historical events, so describe historical LLM replay as potentially contaminated. Prospective paper observation is required to assess the combined agent process without that particular hindsight problem.

Evaluate signal behavior separately from options economics. Underlying candles may test whether breakout conditions occur. They cannot establish option P&L, executable depth, slippage, or fill ordering. Without historical contract metadata and suitable option observations, mark those results unavailable. When a bar crosses competing exit levels and the path is unknown, report conservative assumptions or bounds rather than choose the favorable exit.

Report net P&L, session returns, drawdown, exposure, turnover, fill rate, execution shortfall where reference observations exist, cost sensitivity, model spending, invalid proposals, failure rates, and abstention reasons. Report sample size, uncertainty, expiry proximity, and venue coverage. Examine sensitivity to nearby parameters and worse execution assumptions. Compare the frozen code baseline with agent selection and any new-strategy branch under matched information and costs.

Proposed paper-eligibility checklist:

1. The card and tool formulas are complete, versioned, and mechanically checkable.
2. Data provenance, timestamp coverage, fees, and execution assumptions support the claims made.
3. Chronological evaluation and holdout results satisfy criteria declared before that holdout was inspected.
4. Results do not depend only on one session, one tuned parameter, or optimistic fills; uncertainty and failed regimes are reported.
5. Recovery, invalidation, partial-fill, stale-data, and unresolved-exit behavior have an implementation verification plan.
6. The decision explicitly states the permitted scope and remaining market evidence. Account operation remains subject to separate existing gates.

Numerical minimum sample size, acceptable drawdown, uncertainty method, economic hurdle, and prospective observation duration remain undecided. No strategy can pass an unspecified threshold. These are the next decisions before an evaluation run, not values an agent may choose after seeing performance.

Retirement or suspension follows evidence of broken assumptions, unreliable data, unacceptable execution deterioration, or failure against preregistered monitoring criteria. Do not retune a failing strategy in place and preserve its old performance identity.

References: [QuantConnect research guide](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/research-guide), [overfitting and walk-forward discussion](https://www.quantconnect.com/announcements/15502/making-models-that-fit-the-signal-not-the-noise/), and [slippage models](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/supported-models). The promotion checklist above is our design proposal, not a guarantee derived from those sources.

### Result and remaining decisions

Delivered here: an initial sourced catalog, a common strategy card, selection/adaptation/invention rules, a detailed S01 research candidate, an alternative-research walkthrough, and proposed evaluation stages.

Still required before implementation or experiments: inventory actual historical input coverage, finalize the other strategy cards, choose evaluation thresholds and capital policy, and review the S01 experimental parameters. Harness and human intervention remain held for later at the user's request. Implementation, live acceptance, and execution authorization remain distinct. D19 and D24 in DEFERRED-WORK.md track those boundaries.
