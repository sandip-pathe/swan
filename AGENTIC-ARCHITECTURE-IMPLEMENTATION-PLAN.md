# Agentic architecture spike: implementation plan

Prepared 22 November 2026. This plan is for a bounded, reasoning-only spike. It does not authorize model-provider spending, worker activation, broker access, live-market acceptance, orders, or changes to existing risk and permission gates.

## Current checkpoint

- `RESUME.md` is absent in the current workspace. The architecture and strategy handoffs are used as the checkpoint.
- NIFTY one-minute index snapshots and deterministic ORB assessments now have separate, provenance-preserving storage and bounded as-of readers.
- The existing `AgentPipeline` remains coupled to quote-based proposal/review and short-lived `StrategyEnvelope` output. It is not the right place to store a reviewed research draft.
- This spike adds a separate durable workflow over the index snapshot/assessment records. Missing input ends as an explicit unavailable outcome; it does not trigger alternative research.

## Milestones

### M1 — Durable assessment assignment and typed evidence tools

Create a durable explicit assessment assignment with a deadline, linked source snapshot, status and outcome. Assemble a bounded context through typed snapshot-read and deterministic-ORB-assessment operations. Persist assignment/artifact history separately from model context. If evidence is missing, expired, or the snapshot arrived after the requested as-of time, save that outcome without invoking a model.

**Exit:** an explicit request can be resumed/read after process exit; duplicate requests are idempotent; every context fact links to the exact snapshot, assessment and evidence IDs.

### M2 — Analyst, independent reviewer, and saved draft

Use the existing structured provider and budget/audit controls for a bounded analyst call followed by a reviewer call. Validate all cited IDs against the typed tool results. Save a reviewed draft or explicit abstention/rejection. Keep the draft non-executable and outside `StrategyEnvelope`, risk admission, and order flows. Provider credentials remain user-deferred; stubs establish software behavior only.

**Exit:** supported, rejected, abstained, unavailable, interrupted and expired outcomes are distinct durable records; late work cannot overwrite an expired assignment.

### M3 — Conditional bounded research branch and readback

When a valid assessment shows that the predefined setup does not fit, create one bounded research assignment that can save an alternative hypothesis, including its evidence, assumptions and proposed evaluation. Never branch on absent/stale/gapped evidence. Provide a bounded readback of assignment, result and evidence links for the future chat consumer; no chat UI is required here.

**Exit:** a saved result and its evidence can be read without the original process; a research hypothesis cannot activate or alter a production strategy.

### M4 — Learn from the path before expanding

Exercise the supported-setup, no-fit, missing-evidence, tool-failure and expired/interrupted cases with isolated providers/stubs. Compare supported decisions, abstention quality, tool utility, recovery, latency and reserved spend against the fixed pipeline where matched inputs and authorized access permit. Record fixture evidence separately from model quality and actual-market acceptance.

**Exit:** state which parts work, which are only software-verified, and the smallest next experiment. Do not claim economic improvement from fixtures.

## Implementation checkpoint

M1 implementation is in place; its initial verification was skipped at the user's direction and the missing/idempotency paths were subsequently exercised under M4. M2 has a bounded structured analyst call and separate reviewer call, exact strategy/assessment/evidence validation, durable analyst/review/final artifacts, and distinct completed, abstained, rejected, unavailable, failed, interrupted, and expired outcomes. Provider reservations, usage and outputs carry the assignment ID. Access/transport/budget unavailability is kept separate from model/contract failure. M3 gives the eligible research branch its own bounded durable assignment, links it to the parent assessment and snapshot, validates cited evidence, stores an inactive hypothesis, and exposes the child outcome through bounded parent readback. The service is callable from the application layer; read-only assessment, plan, and research-candidate endpoints are wired into the API. Drafts remain records only.

M4 software coverage exercises supported setup and reviewed draft, valid no-setup and linked research, missing snapshot, gapped evidence, deterministic tool failure, idempotent replay/key conflict, and a response arriving after expiry. Latest focused verification: 26 tests passed across the workflow, assessment-context, assessment/plan-store, watcher, ORB and index-store suites; Ruff passed for the touched workflow, API, strategy, market and test files; Alembic history resolves as one linear chain ending at `e5f6a7b8c9d0`; `git diff --check` reported no whitespace errors. The database's applied revision could not be inspected because the local environment lacks a usable PostgreSQL `libpq` driver (`alembic current` fails to import psycopg). This is fixture/stub evidence only. No live provider call or matched fixed-pipeline comparison was made under the existing provider-test deferral. Model quality, latency/spend comparison, actual-market acceptance and profitability remain open. Manual paper checks and human review remain intentionally skipped at the user's direction.

## Boundaries

The first slice is an explicit assessment path, not a market watcher. The existing market worker, account controls, paper engine and broker paths stay unchanged. No model output grants account eligibility, execution permission, or a live-market acceptance result. New skipped or blocked accepted scope must be recorded in `DEFERRED-WORK.md`; this spike handoff itself explicitly requests no such ledger update.
