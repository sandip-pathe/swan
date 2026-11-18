# Angel One paper/live workflow assessment

17 November 2026 accepted decision: use actual Angel One observations with SWAN's own persistent virtual-cash account and realistic paper execution. External paper-provider selection below is historical and superseded. Keep common agent/risk logic and a distinct future real-order adapter. Implementation details and readiness gates: [24-realistic-paper-execution-plan.md](24-realistic-paper-execution-plan.md).

## Provider decision update - 16 November 2026

The earlier AlgoTest-first suggestion is superseded by the user's free-only requirement. MegaBull is the first free external paper API candidate to verify, but its API's free options access after seven days, contract mapping, quote cadence, and execution behavior are unresolved. Do not pay for AlgoTest. thepapertrade is manual-only: its current Terms prohibit bots, scripts, automated simulated orders and data extraction, and its About page describes a read-only market-data connection with no order-routing path. See the current fact-check and acceptance gate in [22-external-paper-execution-options.md](22-external-paper-execution-options.md).

No provider has passed account-level validation. Keep the Angel One paper/live adapter distinction and never treat a provider's paper fill as an Angel One fill.

Reviewed: 16 November 2026, Asia/Kolkata. User's target remains one account: autonomous agents with paper observation first, followed by a separately authorized real-money Angel One execution mode. No live order, provider account, subscription or external strategy deployment was created during this research.

## Tradetron developer key status (16 November 2026)

The local ignored backend `.env` now contains `TRADETRON_API_KEY`; its value was not displayed or sent. The variable is not currently consumed by SWAN code, and its authentication against Tradetron has not been verified. The supplied `https://tradetron.tech/creator/developer-api` page redirects to Tradetron sign-in when accessed without the user's browser session, so its endpoint, scopes, account requirements, and paper-mode support could not be confirmed. Tradetron's public strategy API describes a separate per-strategy OAuth token for sending signals; do not assume the developer key is interchangeable with that token. No request was made with the key and no provider action was triggered.

## Evidence: documented versus exercised

| Capability | Evidence / status |
| --- | --- |
| Angel One authentication and actual NIFTY/SENSEX REST observations | Exercised in the user's account; sampled calls/puts returned depth, volume and OI. Streaming and broker order behavior are not established by this. |
| AlgoTest paper/forward-test API for NIFTY and SENSEX options | Official API docs define a paper start endpoint, weekly expiry options for both primary tickers, position ID, square-off endpoint and execution-update WebSocket. Not exercised in an account. |
| AlgoTest forward-test market/execution model | Product docs say simulated trades on live market data; pricing docs say slightly delayed live data, and the executions dashboard says trade display may lag up to a minute while orders themselves are not delayed. Exact signal/fill feed timing is unclear. Fee toggles and editable brokerage exist, but provider-specific slippage/partial-fill/margin equivalence remains unverified. |
| AlgoTest API plan/price | Pricing docs list a Signals plan at ₹1,599 + GST/month and a paper Execution plan at 50 credits per strategy per 28 days. Whether the API-started paper endpoint requires either or both is unclear; verify before purchase. |
| Tradetron India NIFTY and SENSEX live-price observation | Documented in Live Offline's instrument list. Not exercised in a Tradetron account. |
| SWAN-generated external entry/exit signals | Tradetron API and Signal Bridge document custom code/URL signals controlling a configured strategy. This is not a confirmed arbitrary-order/position-query REST contract. |
| Options contracts | Signal Bridge documents NSE/BSE options, call/put, strike and expiry selection. Runtime changes to arbitrary strike/expiry, token mapping and maximum basket size require integration assessment. |
| Angel One real execution through Tradetron | Documented SmartAPI broker integration, daily authentication and Tradetron server/IP setup. Not configured or exercised for this user. |
| Hosted test mode with virtual credits, real broker-like fills, fees, partial fills or margin checks | AlgoTest documents a virtual-money Forward Test endpoint; detailed simulation realism and costs remain unverified. Tradetron Live Offline is documented but its virtual-money API behavior is not confirmed. |
| Continuous external order/position readback and reconciliation | AlgoTest documents an authenticated execution-update WebSocket carrying strategy, legs, trade prices/timestamps and status; account-level paper delivery, replay/reconnect, paper square-off and scalping latency remain unverified. The API start response itself is only a position ID, not a fill acknowledgment. |

## Proposed separation

Keep Angel One's actual market-data adapter as SWAN's input. Keep agent analysis/proposal/review, deterministic risk/sizing, session rules and strategy versions common to both modes. Produce a normalized execution intent with underlying, venue, expiry, strike, option side, quantity, entry constraint, exit/risk rules and an idempotency identity.

- Observation mode: AlgoTest is the leading candidate. SWAN's paper adapter would use only its documented paper endpoint, with no broker ID and no broker connection. Consume its execution updates as provider-reported paper state, retain the actual Angel One quote and timestamp alongside every intent, and label provider P&L/fills clearly. Verify its slightly delayed live data and fill/cost behavior against Angel One observations. The same agents, strategy review, session rules and SWAN risk checks remain in control; the external service handles paper position execution and reporting.
- Real-money mode later: a distinct Angel One execution adapter sends permitted broker orders and reconciles actual order/trade/position records. No local or provider simulated fill may be substituted for an Angel One acknowledgment/fill. User authorization and mode/account isolation are required before activation.

Alternative: route both observation and eventual live execution through Tradetron, which documents an Angel One live adapter. That would make Tradetron a runtime dependency for real execution and require its own broker app/IP/session setup. It is not needed for the current paper phase. AlgoTest also documents both paper and live endpoints; SWAN's initial adapter must make the live route unreachable so an API/configuration mistake cannot switch a paper intent into broker trading.

The user's desired equation maps to common observations/agents/risk with mode-specific execution. A verified Angel One virtual-credit OMS has not been found. AlgoTest's API is the best documented external candidate, pending account-level checks. External paper operation cannot establish Angel One order permissions, rejects, margin, partial fills or settlement behavior. One-to-two-week observation can improve operational reliability; it cannot establish a best/profitable strategy or complete equivalence to real execution.

## Next account-level check

Create an AlgoTest account and ask which plan covers API-started paper positions (the public docs list separate Signals and paper Execution plans). Before paying, verify one NIFTY and one SENSEX paper position, paper square-off, timestamped execution updates, duplicate/retry behavior, feed timing, costs and account/history persistence. Keep broker setup empty and never select its live route. No paper position request has been sent.

The remaining gating contract is whether an external signal can be safely deduplicated and reconciled to authoritative provider position state at a cadence suitable for the existing scalping risk rules. A successful HTTP signal response alone is not a fill or position acknowledgment. If that contract is unavailable, do not pretend that SWAN's existing direct paper/position-monitor workflow can be replaced by a fire-and-forget webhook.

## Official sources checked

- India Live Offline mode and NIFTY/SENSEX coverage: https://tradetron.tech/live-offline
- External signals and strategy control: https://tradetron.tech/api
- NSE/BSE option selection and signal interface: https://tradetron.tech/signal-bridge
- Angel One integration: https://tradetron.tech/broker/angel-one
- Provider's limits of offline execution: https://tradetron.tech/blog/before-you-go-live-why-paper-trading-can-save-your-algo-strategy
- AlgoTest paper-start/exit API, instruments and configuration: https://algo-test.github.io/api-docs/components/signals-api-overview/
- AlgoTest webhook endpoints including paper-start: https://algo-test.github.io/api-docs/rest/webhooks-api-docs/
- AlgoTest execution updates and reported leg/trade timestamps: https://algo-test.github.io/api-docs/rest/execution-updates/
- AlgoTest forward-test data model: https://docs.algotest.in/getting-started/pricing-breakdown/
- AlgoTest Signals plan and current pricing: https://docs.algotest.in/Signals-AI/Pricing/
- AlgoTest paper executions dashboard: https://docs.algotest.in/Signals-AI/Going-Live/Executions/
- AlgoTest forward-test mode details: https://docs.algotest.in/Signals-AI/Going-Live/Forward-Test/
- AlgoMojo options and paper-mode documentation: https://docs.algomojo.com/algomojo/my-strategies/create/options and https://docs.algomojo.com/algomojo/my-strategies

Old search snippets describe Paper Trading/TT-PaperTrading. Current fetched pages describe Live Offline and must take precedence. No unsupported sandbox, virtual-credit or execution-accuracy claim is made.
