# Sequenced build plan

17 November 2026: use [the realistic paper execution plan](24-realistic-paper-execution-plan.md) for the next implementation increment. SWAN owns virtual capital/execution with actual Angel One inputs. External paper providers are not dependencies. Existing engine completion below refers to the original immediate-fill foundation, not completion of the new order/partial-fill/cost model. Local iterations precede deployment; no deployment is authorized by this plan.

Tasks are ordered by dependency. Check a task only after its evidence exists. No calendar estimates are asserted before data access and deployment constraints are known.

## M0 — Resolve feasibility and contracts

- [ ] Verify Angel One access to both requested indices/exchanges, instrument master, streaming/polling quotes, bid/ask, OI, volume, IV and Greeks.
- [ ] Record official capability references, entitlement requirements, rate limits, session/auth lifecycle, and permitted fixture retention.
- [ ] Establish approved derivations or explicit unavailable states for unsupported metrics; block affected strategies.
- [ ] Verify session/holiday source, expiry/lot metadata, fee inputs and hosting connectivity.
- [ ] Resolve provider-specific blockers in the decisions register; use accepted defaults from current requirements.
- [ ] Freeze decision schema, risk conventions, fill rules and real-data evidence specification; no synthetic fixture or replay runner.

Gate for provider-dependent work: a documented capability matrix supports the required workflow, or missing capabilities are recorded as blockers. Credential-free domain work may proceed while these are resolved. Do not substitute another provider without a scope decision.

## M1 — Repository and deterministic domain core

- [x] Scaffold web/Python modules, native PostgreSQL, migrations and lint/type tooling. CI deferred to final QA by user instruction.
- [x] Define instrument, snapshot, decision, risk and ledger schemas with versioning.
- [x] Implement pure risk checks and whole-lot sizing.
- [x] Implement paper fills, fees, ledger, positions and reconciliation.
- [x] Add transaction/idempotency boundaries and concurrent-entry protection.
- Removed from scope by user: replay runner and synthetic market-data fixture. Ordinary isolated numerical tests are retained.

Status: implemented. Existing 45 checks passed without provider credentials; migration applied. Further test development and wider validation are deferred to final QA at the user's request.

## M2 — Market adapters and runtime safety

- [x] Implement read-only SmartAPI adapter and actual instrument normalization; fixture adapter removed by user instruction.
- [x] Add freshness/availability, metric provenance and selected-contract chain computations.
- [x] Implement explicit calendar loader, durable evaluation slots, singleton worker and coalesced scheduling. Actual calendar entries still required.
- [x] Wire independent position monitor, exit recovery, pause, cutoff and daily-loss state.
- [x] Implement paused recovery and provider failure handling. Connected behavior remains unverified.

Status: code and migrations implemented; basic lint/type checks pass. Replay is excluded by user instruction. Live access, connected behavior and broader QA remain pending; see [step-two status](./17-market-runtime-implementation.md).

## M3 — AI workflow

- [ ] Configure API access securely before live API work; choose a current supported model after documentation/cost verification.
- [ ] Build read-only market-analysis, proposal and review workflow with LangGraph.
- [ ] Validate schema/evidence, enforce timeout and token budget, convert errors to WAIT.
- [ ] Store model/prompt versions and sanitized traces; reject expired proposals.
- [ ] At final QA verify schema/error handling and adversarial-context boundaries without adding synthetic agent replies to the application.

Gate: AI cannot bypass execution checks or change risk settings; all malformed/error paths fail to WAIT.

## M4 — Authenticated PWA

- [ ] Configure Firebase Auth and backend token/allowlist validation.
- [ ] Build dashboard, market view, activity, journal, risk settings and reports.
- [ ] Add responsive loading, unavailable, stale, unauthorized and error states.
- [ ] Wire pause/resume and versioned settings updates; show confirmed server state.
- [ ] Add manifest, icons, install support and safe static-asset caching with Serwist.
- [ ] Use Lightweight Charts only for useful portfolio/price history views.

Gate: full browser workflow works against actual configured services and explicit unavailable states; Android install and authorization checks pass at final QA.

## M5 — End-to-end validation and reporting

- [ ] Run controlled autonomous paper sessions using real provider inputs, with costs, entries, exits, audit trails and daily reports, after final-QA readiness.
- [ ] Complete acceptance matrix AC01–AC12 and capture evidence.
- [ ] Review source and outbound adapter calls for absence of brokerage execution.
- [ ] Reconcile dashboard, journal and reports against actual recorded paper ledger events.

Gate: isolated accounting checks and connected read-only market/paper acceptance pass; no real broker orders.

## M6 — Deployment and controlled paper observation

- [ ] Deploy frontend to Vercel and API/worker to Lightsail; provision private-access PostgreSQL and HTTPS.
- [ ] Apply migrations, secret configuration, backups, health checks and operational alerts.
- [ ] Exercise restart, failed migration recovery and database restore in a nonproduction environment.
- [ ] Perform authenticated read-only market-data smoke test with entries disabled.
- [ ] Enable paper trading only after freshness, session, cost, risk and monitoring configuration pass preflight.
- [ ] Observe several complete sessions and record reliability and simulated performance separately.

Gate: operational evidence and reports disclose sample size, data gaps, simulation assumptions and costs. Profitability is evaluated, not promised.

## Scope additions required before release

- [ ] Implement the strategy-envelope schema, deterministic tick-driven entry predicates, expiration/invalidation and maximum holding-time exit.
- [ ] Implement 0–7-day expiry eligibility and session-relative cutoffs, including expiry-day and special-session tests.
- [ ] Integrate a licensed news/context provider with attribution, freshness, deduplication and required-input failure rules.
- [ ] Add Firebase emulator tests, UID authorization, sensitive-action revocation handling and connection setup UX.
- [ ] Add actual-session strategy evaluation with frozen strategy/cost/execution versions and net-performance reporting; replay runner remains excluded.
- [ ] Complete latency/load measurements, bounded retries/queues, quota controls, dependency/license review and accessibility checks.
- [ ] Complete AC13–AC21 and the release checklist; include these in M5/M6 gates.

API-backed implementation begins after the applicable secure credential-choice workflow. Planning files require no API credentials. Consult integration setup for account requirements before asking the user for information.
