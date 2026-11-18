# SWAN Trade workspace

Current authentication: [Firebase public-key verification](31-firebase-public-key-auth.md). Admin credentials/manual UID mapping are no longer local prerequisites; the first verified user enrolls as the sole owner of a paused virtual wallet. Trading readiness remains separate.

Local application: [startup and wiring](30-local-startup.md). Open http://localhost:3000. Database/API/frontend startup was verified; protected account access and trading still need the documented configuration inputs.

Latest increment: [durable worker routing and protection](29-paper-worker-and-protection.md), 17 November 2026. Locked portfolio admission, ledger/matcher routing, conservative partial-fill risk allocation and independent protective monitoring are connected. Configuration and final QA still block activation.

Previous increment: [durable depth-aware risk sizing](28-paper-depth-risk-sizing.md). Whole-lot sizing, conservative fee/cash allowances and typed revision-bound approvals are implemented.

Previous increment: [paper step 3A - matching and fees](27-paper-step-three-matching-and-fees.md). Fee accrual, conservative depth matching, stop-trigger preparation, liquidity budgets and liquidation estimates are implemented.

Previous increment: [realistic paper step 2](26-paper-step-two-implementation.md), 17 November 2026. Durable order lifecycle, multiple-fill accounting, reservations, proceeds holds and local migration are implemented. Protection orchestration remains pending; no autonomy has been enabled.

Previous increment, 17 November 2026: [realistic paper step 1](25-paper-step-one-implementation.md) added full depth/time identities and versioned execution/fee configuration contracts. Applied fees and depth matching remain pending; no new autonomy or deployment was enabled.

Latest accepted direction, 17 November 2026: [realistic internal paper execution plan](24-realistic-paper-execution-plan.md). SWAN owns virtual capital/orders/accounting, Angel One supplies real observations, and no external paper provider is required. That five-step plan governs the next local implementation increment; no new engine capability is claimed by this documentation update.

Planning baseline: 15 November 2026. Status: steps one and two implemented; live market access/configuration pending; agents/news are next.

SWAN Trade is an AI trading layer for supported existing broker accounts. Immediate delivery is autonomous **paper trading** of NIFTY and SENSEX options for one owner; future scope includes autonomous real execution and isolated broker connections for multiple users. Performance is assessed after costs; software acceptance does not imply profitable strategies.

## Read in this order

1. [Original PRD](./01-source-prd.md) — supplied requirements, preserved verbatim.
2. [Scope and acceptance](./02-scope-and-acceptance.md) — deliverables and definition of done.
3. [Architecture](./03-architecture.md) — components, trust boundaries, runtime flow.
4. [Data and API contracts](./04-data-and-api.md) — entities, invariants, endpoint plan.
5. [Risk and paper execution](./05-risk-and-execution.md) — sizing, ledger, fills, and exits.
6. [Build plan](./06-build-plan.md) — ordered tasks and milestone gates.
7. [Verification plan](./07-verification.md) — tests and acceptance evidence.
8. [Operations and security](./08-operations-and-security.md) — deployment, authentication, recovery.
9. [Decisions and dependencies](./09-decisions-and-dependencies.md) — assumptions requiring verification.
10. [Progress](./10-progress.md) — current state and next executable tasks.

The source PRD is an immutable historical input. Current product requirements and accepted decisions supersede it where user instructions changed scope. Proposed defaults and external verification tasks remain explicitly labeled. External API capabilities, fees, exchange rules, library versions, and hosting details have not been verified in this planning pass. Verify them against official sources before implementing dependent features.

## Working rules

Current execution plan: [complete system and broker workspace](./37-complete-system-and-broker-workspace-plan.md). Current baseline: [M1 audit](./38-m1-baseline-and-evidence-audit.md) and [feature/data inventory](./39-broker-feature-data-inventory.md). Earlier milestone descriptions below are historical; current user instructions and these reconciled records take precedence.

Latest lifecycle implementation: [M2 qualification, worker controls and paper arming](./40-m2-qualification-worker-controls.md). The implementation is available; the local account remains unqualified and unarmed.

Latest market-data implementation: [M3 foundation](./41-m3-market-data-foundation.md). Quote price retention and historical backfill/cache APIs are implemented. Real history access was rejected by the broker; live candle aggregation and connected acceptance remain pending.

Latest implementation: [agents/news](./18-agents-and-news-implementation.md) and [authenticated workspace](./19-authenticated-workspace.md). Provider credentials and final QA remain deferred by user instruction.

Latest user steering overrides earlier fixture/replay and milestone-verification suggestions: no replay runner or synthetic market-data fixture; prioritize implementation and defer further test expansion and broader checks to final QA. Keep existing isolated tests. See [progress](./10-progress.md).

For the short execution sequence and when to provide account access, use the [implementation roadmap](./14-implementation-roadmap.md).

- Keep current operation paper-only. Future real execution is authorized product scope, but requires a separate implementation and explicit activation; this document change does not enable live orders.
- Never invent market values or replace missing values with zero.
- Keep risk enforcement and execution deterministic; AI proposes decisions only.
- Complete final QA and connected acceptance before enabling autonomy; no synthetic fixtures or replay runner.
- Record changes to scope and consequential decisions in the decisions file.
- Keep secrets, tokens, production data, and personal information out of this folder and version control.

## Current agreed baseline

Read [current product requirements](./11-current-product-requirements.md) first, then [integrations and setup](./12-integrations-and-setup.md) and [release quality](./13-release-quality.md). These incorporate the subsequent user decisions: Firebase Auth, autonomous intraday options scalping, listed expiries within seven calendar days including expiry day, and no intentional overnight holding. Historical wording in the original source is retained only for provenance.
