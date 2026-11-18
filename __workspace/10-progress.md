# Progress

Updated: 17 November 2026.

Authentication correction: [public-key Firebase verification and local enrollment](31-firebase-public-key-auth.md) replaces the mandatory Admin credential/manual binding requirement. The local setting enables transactional first-owner wallet initialization only after a genuine signed Firebase login. No wallet is seeded before sign-in. Immediate Admin revocation lookup is not performed; trading stays gated.

Local run: [startup and wiring](30-local-startup.md). PostgreSQL, API and frontend are running locally; app/health/CORS probes pass and unauthenticated workspace access is denied. A background `local.cmd start/status/stop` launcher is available. Firebase server credentials, owner binding and actual paper-account configuration are absent; trading worker remains stopped.

Latest increment: [durable worker routing and protection](29-paper-worker-and-protection.md) connects locked portfolio admission, typed approvals, ledger/matcher routing, full-budget partial-fill risk allocation, recovery and independent protective orders. Ruff, backend typing, schema exports and frontend typing pass. Configuration, connected dependencies and final QA still block activation; no worker or trading session was started. Next: authenticated lifecycle/uncertainty display and readiness inputs; evidence-backed funds release remains pending.

Previous increment: [depth-aware risk sizing](28-paper-depth-risk-sizing.md) implemented whole-lot admission sizing with conservative fees, durable liquidity-budget inputs, cash/daily-risk headroom and typed revision-bound approvals. Shared admission validation preserves legacy sizing.

Previous increment: [paper step 3A](27-paper-step-three-matching-and-fees.md) implements order/session fee accrual, depth matching, stop-trigger preparation, persistent capacity/consumption, price protection and liquidation estimates. Migration `95d7e32c10ab` is applied to the empty local trading database after backup. Static/schema checks pass; behavior and configured charge parity remain unverified.

Previous increment: [paper step 2](26-paper-step-two-implementation.md) delivered durable lifecycle/events, multiple fills, reservations, proceeds holds and shared reconciliation. Tests and behavioral acceptance remain deferred.

Previous increment: [realistic paper execution step 1](25-paper-step-one-implementation.md) added actual quote depth/time identities, versioned execution/fee contracts and readiness diagnostics. Current configuration and connected readiness remain incomplete.

## Completed

- [x] Product requirements, decisions, architecture and implementation plan.
- [x] Local Node/Python/PostgreSQL environment, dependency lockfiles and launch scripts.
- [x] Firebase Google and email/password login; user confirmed login works.
- [x] Step one: versioned backend contracts and JSON Schema/TypeScript exports.
- [x] Step one: PostgreSQL models and applied Alembic migration.
- [x] Step one: pure risk checks and whole-lot sizing with explicit costs/liquidity.
- [x] Step one: transactional paper fills, ledger, positions, audit and reconciliation.
- [x] Step one: duplicate/concurrent entry protection, pause/recovery and exits.
- [x] Removed replay runner and synthetic market-data file at user request.

## Current state

16 November 2026 coverage follow-up: current Tradetron docs list NIFTY/SENSEX in **Live Offline**, external signal integration and an Angel One live broker adapter. This is documented capability, not an account-tested integration or an Angel One virtual-money OMS. Readback/deduplication, actual mode semantics, fees and latency remain unverified. See [Angel One paper/live workflow assessment](./23-angelone-paper-live-workflow.md).

16 November 2026 paper-execution preference: evaluate an officially supported external paper backend before assuming SWAN's local simulator is the chosen observation environment. [Provider findings](./22-external-paper-execution-options.md) identify Tradetron/Algomojo as candidates; no external integration or subscription is selected, and no paper run has started.

16 November 2026 product clarification: autonomous paper operation is the immediate observation phase, not a permanent product limit. Real broker execution capability and isolated multiple-user connections are now accepted future scope. Requirements/decisions are updated in [autonomous product direction](./21-autonomous-product-direction.md). No real order functionality was added or enabled by this documentation update.

16 November 2026: [connected market-data check](./20-connected-market-data.md) verified broker authentication, fresh NIFTY/SENSEX index quotes and four actual option quotes with depth/volume/OI. Verified index tokens are configured locally. Backend Firebase project ID matches browser configuration, but service credentials and owner/account binding remain pending. Trading stays disabled.

Latest delivery: [authenticated workspace](./19-authenticated-workspace.md). Backend identity verification, account bindings, dashboard, controls, policy edits, CSV export and app manifest/icons are implemented. Credentials, tests and connected acceptance remain deferred. See the delivery note for the next work; earlier entries below describe prior milestones.

The trading foundation, Angel One adapter and market worker exist as internal Python modules. Database migrations through 31fa5ac4735a are applied, without seeded accounts, quotes or trades. The frontend remains the working sign-in interface. Broker access and calendar/account configuration are missing; no broker, news or OpenAI connection is active.

Existing verification completed before the implementation-first instruction: 45 domain/PostgreSQL tests passed, including concurrency, rollback, migration round-trip and accounting checks; Ruff and backend type checks passed. Further test development, CI and broader validation are deferred to final QA. Existing tests remain in place.

## Next step

Agent/news integration code is implemented; see [step-three delivery](./18-agents-and-news-implementation.md). All credentials and tests are deferred by user instruction. Structured outputs, durable token reservations, evidence validation, review and licensed RSS/Atom sources connect to the worker. Live behavior and provider-specific authenticated news API coverage remain pending. Next implementation: authenticated backend and dashboard.

Step two code is implemented; see [market runtime status](./17-market-runtime-implementation.md). Configure actual Angel One access and reviewed session/account settings when available. Next implementation: real agents and licensed news context. Further QA remains deferred; missing dependencies never generate placeholder market values or agent replies.

See [trading foundation](../services/README.md) and [implementation roadmap](./14-implementation-roadmap.md).
Step-two delivery includes private broker login, actual metadata, streaming, chain metrics, session loader, durable evaluation slots, singleton worker, independent exits, latest-quote publication and operator commands. Ruff and backend type checks pass; no new test suite was run.
# 17 November 2026: realistic paper step 1

Implemented quote depth/time/event evidence, cache rejection diagnostics, versioned execution/fee configuration contracts, exported shared schemas and local readiness reporting. See [implementation details](25-paper-step-one-implementation.md). The saved broker session is expired, calendar entries are absent and configuration choices/effective fee schedules remain pending. No tests, simulation, provider requests, database migration or deployment ran. Next: durable orders, partial-fill accounting and cash/risk reservations. Existing immediate fills are not evidence that the realistic execution plan is complete.

