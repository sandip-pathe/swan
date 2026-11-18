# Autonomous product direction

Accepted user clarification: 16 November 2026, Asia/Kolkata. This supersedes permanent paper-only and single-user limits in earlier planning. This change records scope; it does not implement or enable real-money execution.

## Product

SWAN is the AI decision and automation layer over supported existing trading/broker accounts. Users should not need to open a new demat account with SWAN. Broker account opening, custody and exchange execution remain with the supported broker unless a separate future business decision changes that relationship.

The intended flow is market/news observations → agent analysis → strategy proposal → independent review → deterministic risk/sizing → selected execution adapter → position monitoring and reconciliation. Agents initiate trades autonomously within approved session and account limits. Do not require a person to approve every individual trade once an account/session is explicitly armed. User controls include pause, emergency stop, capital/risk limits and mode authorization.

## Immediate priority: autonomous paper observation

Run a one-to-two-week observation period on actual quotes, using persistent virtual capital, cost/slippage assumptions and the existing paper ledger. The period starts when the configured workflow is actually activated, not when planning is written. Do not place real broker orders during this period.

Preserve ledger and positions across development restarts. Recover and reconcile first; new entries remain paused until explicitly resumed, with exits prioritized. Changes must record strategy/model/prompt/risk/code versions and iteration boundaries. Maintain daily/session summaries of net P&L, costs, drawdown, turnover, data gaps, rejected proposals, pending exits, model usage and latency. These reports support debugging and agent improvement; paper fills cannot establish actual broker execution quality.

No synthetic market data, replay runner or fabricated agent response is authorized. Real-time paper fill calculation from actual quotes is required functionality, distinct from synthetic market-data generation. Existing unit tests remain; additional test suites are deferred per user instruction. Connected read-only checks have been authorized and performed.

Current implementation has agents, risk, paper ledger, worker and dashboard code. Broker authentication and sampled NIFTY/SENSEX REST data are verified. Still needed for activation: backend Firebase service identity/owner binding, explicit account/risk/cost policy, reviewed session calendar, actual OpenAI model/budget, usable news integration/freshness policy, and streaming/worker connection. Do not describe the observation run as started while these remain unresolved.

Local operation requires the computer and API/worker/database processes to remain running during market sessions; broker authentication/renewal requirements still apply. Installation in Firebase Hosting of the registration page does not run the local trading worker.

## Future real execution

Reuse the strategy and risk pipeline, with a separate broker execution adapter and durable broker order state. Paper fills must never be recorded as broker fills. Real submission, broker acknowledgment, partial fills, rejection, cancellation, uncertain submission and exchange/position reconciliation need their own state transitions. A missing response must not cause an unverified duplicate order. Stops and forced exits need broker-supported order types, account-specific handling and an emergency control path.

Separate paper/live accounts, balances, positions, credentials, order identifiers and reports. Real mode is disabled by default and must require explicit account/session authorization; current paper records must not migrate into live positions. A mode change is not a simple switch to a different HTTP endpoint. Do not execute real trades as part of development verification.

Before live activation, verify current broker support, permitted algo/order types, account permissions, static outbound IP requirements and applicable release obligations. An AI proposal cannot bypass these or enlarge account limits. No successful/ profitable trading claim follows from implementation or a short paper run.

## Future multiple users and brokers

Firebase identifies the SWAN user. A separate Connect Broker workflow links that user to a supported broker account using the broker's approved authorization/onboarding flow. A universal login for every demat account is not assumed; each broker requires an adapter, approved access and capability verification. Session renewal and reconnect behavior may differ by broker. Evaluate broker app/vendor-key arrangements rather than assuming one user's key/session can be reused for other users.

Replace the current fixed UID/account binding and singleton broker session file with database-backed user, broker-connection and trading-account ownership. Store tokens encrypted on the server, scope every query/action/stream/worker lock by ownership and account/mode, and support revocation/disconnect. Each user gets independent virtual capital, live portfolio, risk budgets, usage budgets, permissions and audit. Do not share broker tokens or pool funds across users.

The deployed Firebase registration page currently discards tokens and does not establish this connection. A genuine multi-user authorization callback requires verified broker responses, login-correlation/state handling, token storage and a completed ownership link.

Public multi-user algo distribution is a later release with broker onboarding and an applicable regulatory review; it is not achieved by removing the UID allowlist. Exact permissions depend on the service and broker arrangement.

## Evidence and delivery order

1. Complete and operate persistent autonomous paper trading locally.
2. Use the observation records to improve reliability and versioned agent decisions.
3. Implement a separate real broker execution lifecycle; activate only after explicit authorization and appropriate verification.
4. Implement isolated broker connections for additional users/brokers and validate public-service requirements before onboarding other users.

Order execution requirements reviewed: [Angel One SmartAPI changes](https://www.angelone.in/news/market-updates/what-s-changing-in-angel-one-s-smartapi-access-from-april-1-2026). Multi-user provider obligations require verification against the current exchange framework and the broker's onboarding terms; this document does not establish approval.
