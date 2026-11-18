# Agents and news implementation

Updated: 15 November 2026.

User decision: defer all API credentials, continue implementation and skip tests until final QA. This supersedes earlier access-before-implementation timing. No keys were created, reused or written, and no live requests were made.

Implemented analysis/proposal/review schemas, Responses API client, durable conservative token reservations, evidence checks, licensed RSS/Atom reader, context/output audit and worker integration. Strategies retain deterministic paper execution/risk checks. Missing dependencies produce no synthetic opinions or market values.

Before activation: actual Angel One setup and session calendar, explicit paper account/risk policy, OpenAI project/key/model and token budget, and reviewed licensed news sources. Currency billing controls, coverage approval and a provider-specific authenticated news API adapter remain pending provider selection. Licensed RSS/Atom is implemented now.

Validation: Ruff and mypy passed for agents/workers. No tests, simulations or connected checks were run. Existing tests remain for final QA.

Next: authenticated backend endpoints, Firebase token verification/identity allowlist and a dashboard backed by persisted real observations and paper account state.

See [implementation details](../services/agents/README.md).
