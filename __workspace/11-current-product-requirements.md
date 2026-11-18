# SWAN Trade — current product requirements

Authority: user decisions through 18 November 2026. This document and accepted decisions supersede conflicting historical requirements. SWAN is an AI trading layer connected to supported existing broker accounts. Deliver autonomous paper trading first, then separately implement real broker execution and multiple users. The initial single-owner setup is an implementation stage, not a permanent product limit. See 21-autonomous-product-direction.md for the latest scope and activation boundaries.

## Agreed behavior

- Immediate operation: autonomous paper trading of NIFTY and SENSEX long calls/puts for a one-to-two-week observation period while development continues. Use actual market data and a persistent virtual ledger; no real money during this period.
- Product capability to build subsequently: autonomous real broker execution after the user explicitly enables that mode and broker/account eligibility and execution controls are verified. No per-trade human approval is intended once an authorized session is armed within its limits. Real execution is not implemented or activated by this requirements change.
- Intraday scalping; no intentional overnight positions. Exit on stop, target, strategy invalidation, maximum holding time, daily-loss breach or pre-close flattening, whichever applies first.
- Select actual listed expiries within 0–7 calendar days in Asia/Kolkata, inclusive of same-day expiry. Expiry is contract eligibility, never permission to hold longer.
- Angel One is the intended market-data source. Resolve instruments, expiry, exchange, lot size and tick size from validated provider metadata; do not guess schedules.
- Current access: Firebase Auth for one verified allowlisted owner. Future access: separate user identities, supported broker connections, consent, isolated tokens, portfolios, risk policies and audit trails. PostgreSQL remains the accounting database.
- SWAN owns its paper balance, fills, ledger and risk state. TradingView is an optional human comparison tool, with no assumed automation integration.
- OpenAI-backed analysis, proposal and daily-review agents; deterministic risk, sizing, monitoring and execution.
- A separate user-facing chat agent is the primary point of contact. The user can ask questions across current market context, news, agent decisions, trades, positions, account state, risk, and historical activity. The chat agent is distinct from autonomous strategy/review agents; it does not participate in their trading loop, and their work continues all day without the user keeping chat open.
- Autonomous agents persist their findings and evidence for later retrieval. They do not send routine unsolicited reports into the user's chat. When asked, the chat agent gathers relevant current or historical results and presents a concise answer with source, timestamp, freshness, and missing-data context. News claims require attributed, licensed source evidence; unavailable news is reported as unavailable.
- The dashboard is secondary and on demand. Chat responses can include focused, expandable summaries or open the relevant detailed view (market/option chain, activity/evidence, positions, journal, risk, system health, or daily report) without making the user navigate a dashboard first.
- The chat agent may perform a narrow set of explicit user-requested account controls through authenticated, audited commands. Initial allowed action: stop new entries for the remainder of the current exchange session ("stop trading today"). This sets a durable session stop, prevents new entries, and leaves existing position monitoring and protective exits running. It does not imply an immediate position liquidation. The assistant must state the effect and resulting state. Resuming after a session stop requires a separate explicit user command and normal system preflight.
- Chat commands cannot place or alter orders, change risk limits, rewrite strategy, bypass deterministic risk checks, or grant the chat agent direct access to execution/provider credentials. Existing deterministic controls remain authoritative. Destructive or ambiguous actions require clarification/confirmation; command retries must be idempotent and every accepted/rejected command is auditable.
- Full dashboard, option chain, activity/evidence view, positions, journal, settings, daily reports, data health and connection status remain available as secondary, on-demand views.

## Chat experience and acceptance

- Opening the authenticated app lands in a ChatGPT-style conversation, with prior conversations and a clear prompt area. Suggested prompts may help the user ask about the market, news, decisions, trades, risk, or system health; they must not imply that unavailable data exists.
- The user-facing chat agent answers from persisted workspace evidence and invokes only the relevant read tools or explicitly allowed control actions. It separates observed facts, agent interpretation, and unavailable/stale inputs; summaries link back to the underlying decision, source, trade, or event.
- Autonomous trading and monitoring are independent of chat availability, chat history, or whether the user is present. Chat-agent failure cannot pause, enable, or otherwise change autonomous trading.
- Routine agent outputs stay in the activity/evidence store until the user asks. Critical operational safety state (for example, worker loss while positions are open or a daily loss block) remains visible as a system alert, separate from agent conversation output.
- "Stop trading today" means block new entries until the current verified exchange session ends; keep protecting and managing existing positions under the configured deterministic exit policy. Show the session stop as active and record who requested it, when, and the effective session. Never interpret it as permission to close positions immediately.
- Acceptance: an all-day autonomous session produces persisted, timestamped agent evidence without requiring chat interaction; a later user question retrieves the relevant results and their provenance; an unavailable news feed is disclosed rather than replaced with generated headlines.
- Acceptance: the chat agent can stop new entries for the current session through the authenticated control path; duplicate requests do not duplicate effects; the UI confirms the active stop; open positions remain monitored; a new session does not silently inherit the stop unless a separately specified policy says so.
- Acceptance: chat cannot submit/modify orders or mutate risk/strategy configuration, cannot bypass risk controls, and cannot interrupt the autonomous worker when chat is unavailable.
- Acceptance: routine agent reports do not appear unsolicited in chat, while critical operational alerts remain visible and distinguishable from analysis.

## Engineering defaults, versioned and visible

These implementable defaults are not claims about profitable strategy settings. User-confirmed scope above remains separate from tunable configuration.

| Setting | Default |
| --- | --- |
| Paper capital / per-trade risk / daily loss / positions | INR 100,000 / 0.5% / 2% / one |
| Entry cutoff / flatten request | Session close minus 20 / 10 minutes |
| AI context refresh / strategy envelope lifetime | 180 / 180 seconds; invalidate on material data/session changes |
| Position monitor | Tick-driven, with a one-second watchdog target; measure actual latency |
| Executable quote freshness | Two-second target for scalping; hard ceiling 10 seconds; block at configured threshold |
| Maximum holding time | Five minutes; configurable; exit still requires valid quotes |
| Restart | Reconcile and handle exits; new entries remain paused until explicit resume |
| Equity/risk basis | Positive equity capped at configured capital; planned costs included |

Liquidity thresholds, fee/slippage settings, strategy thresholds and model budget must be explicitly configured and verified before autonomous operation. Missing configuration blocks activation instead of silently guessing values.

## Strategy contract

An approved strategy envelope must specify instrument universe, eligible expiry/strike filters, deterministic entry predicates, stop/target method, maximum holding time, invalidation predicates, evidence timestamps, expiry and strategy version. AI prose alone cannot authorize an entry. Deterministic rules can narrow an envelope but cannot enlarge risk permissions. A single active envelope and one open position avoid conflicting concurrent strategies.

Do not claim a successful scalping strategy merely because the software works. Evaluate actual paper observations for net results, drawdown, turnover, fees, spread, slippage, rejection rates and data gaps. Record strategy/model/prompt/risk versions and explicit iteration boundaries so changes remain attributable. Do not add a replay runner or synthetic market/agent responses; these were explicitly rejected by the user.

## Quality bar

Use semantic responsive UI, keyboard access, visible focus, appropriate contrast, accessible control names and clear stale/pending/error states. No placeholder production metrics, fabricated evidence or decorative confidence scores. Include meaningful automated domain/integration/browser tests, security checks, reproducible builds, dependency/license review, migration handling, backup/restore rehearsal, release checklist and operator runbooks.

Complete delivery includes news/context integration through a licensed adapter, timestamped source attribution, deduplication, publication-versus-retrieval times, freshness rules and visible provider outages. Provider selection is a dependency, not an excuse to fabricate news or scrape without permission. Whether a strategy may operate without news must be explicit in its required-input contract.
