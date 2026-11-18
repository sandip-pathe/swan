# Architecture

16 November 2026 scope update: current implementation remains paper-only, with one owner. Future product scope includes autonomous real broker execution and multiple users; see [latest architecture direction](./21-autonomous-product-direction.md). The current market adapter has no order methods, and the hosted registration page is not a broker authorization/token-exchange implementation. Proposed technologies below are not evidence that all dependencies are installed.

## Proposed repository

```text
apps/web/                  Next.js, TypeScript, Tailwind, shadcn/ui, Serwist
services/api/              FastAPI routes, auth, application services
services/agents/           Typed Python analysis/proposal/review workflow and OpenAI adapter; LangGraph not installed
services/paper/            Orders, fills, ledger, reconciliation
services/risk/             Pure deterministic validation and sizing
services/market/           SmartAPI adapter, normalization, session calendar
services/worker/           APScheduler, ingestion, monitoring, reports
shared/schemas/            Versioned JSON Schema and generated TS contracts
tests/                     Existing isolated checks; no synthetic market fixture or replay runner
infra/                     Docker, deployment and migration configuration
__workspace/               Requirements and planning
```

Start as one Python codebase with API and worker processes, sharing PostgreSQL. Domain folders are modules, not independent microservices. This preserves the requested stack without unnecessary network boundaries. Resolve Python packaging/import conventions at scaffolding.

## Runtime flow

1. Worker verifies enabled state, exchange session, account configuration, and provider health.
2. Ingestion normalizes instrument identifiers and quotes into immutable snapshots.
3. A bounded AI cycle refreshes strategy context (initial default: three minutes). Between cycles, deterministic setup rules process streaming quotes and may propose entries only within an unexpired AI-approved strategy envelope. Every entry still requires current risk validation; the model is not called on every tick.
4. AI returns a typed proposal with referenced evidence. Invalid/late responses block approval with an explicit error; genuine WAIT is a model outcome, never a fabricated fallback opinion.
5. Deterministic risk validation checks the proposal against current state and executable quotes.
6. Within a database transaction, recheck trading state, risk, quote freshness, and available capital before committing the virtual fill and ledger entries.
7. A separate monitoring loop observes open positions and applies deterministic stop/target/session-exit rules. Do not rely on the three-minute LLM loop for exits.
8. At session end, reconcile ledger and positions, then create a deterministic report and optional AI narrative.

## Trust boundaries

- Browser: display and authenticated user commands only. No provider or OpenAI secrets.
- API: validates identity, allowlist, input and authorization on every protected route.
- Agent: read-only market/context tools and structured proposal output. No execution or settings mutation tool.
- User-facing chat agent: separate authenticated conversational interface over persisted workspace data. It can retrieve relevant agent findings, market/news evidence, positions, trades, risk, and system events on user request. Its command tools are a narrow allowlist (initially session-scoped stop-new-entries); it cannot submit/modify orders, alter risk/strategy, access provider/execution credentials, or bypass deterministic controls. Chat downtime has no effect on the worker.
- Risk and paper modules: sole authority for accepting and committing simulated orders.
- Provider adapter: market-data methods only; no brokerage order methods exposed.
- Database: durable source of truth for trading state, idempotency, balances, and events.
- Agent findings and tool commands are persisted with timestamps, source/evidence references, freshness, requester identity, outcome, and audit metadata. Routine findings remain queryable rather than being pushed into chat; critical system safety alerts use a distinct alert path.

## Scheduling and concurrency

- Run a single active scheduler initially, protected by a database lock/lease to prevent duplicate work after restarts or deployment overlap.
- Persist job/session keys; enforce uniqueness for evaluation slots and decisions.
- Serialize account-changing transactions with an account row lock. Treat retries as normal.
- Prevent overlapping evaluations; expire proposals after their allowed window and revalidate quotes at fill time.
- Use UTC for storage and Asia/Kolkata for exchange session interpretation and display.
- Define monitoring frequency after verifying provider rate limits; record it as a configured value with measured latency. Target a short monitoring cycle independent of AI latency.

## UI data delivery

Begin with authenticated polling for portfolio/activity and incremental event cursors. Adopt SSE only if measured UX or traffic needs justify it. Display stale/unavailable states explicitly. Service-worker caching covers public static assets; authenticated financial responses must bypass caches.
