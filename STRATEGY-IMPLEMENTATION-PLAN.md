# Strategy Intelligence: step-by-step implementation plan

Prepared 22 November 2026. This plan translates [STRATEGY-INTELLIGENCE-HANDOFF.md](./STRATEGY-INTELLIGENCE-HANDOFF.md) into small, reviewable increments grounded in the current SWAN code. It is a plan, not authorization to start providers, enable the worker, perform broker/live acceptance, or route real orders.

## How this plan was derived

I treated the handoff as product direction, not as a file-level design. I checked the existing ORB slice and referenced market and agent paths, then sequenced work by prerequisite:

1. Establish what permitted underlying evidence SWAN actually has.
2. Make that evidence available with provenance and as-of semantics.
3. Store and inspect deterministic assessments before asking models to use them.
4. Connect assessments to the existing agent pipeline through bounded, auditable work.
5. Evaluate strategy selection and execution separately, then add learning and conversational access over the same records.

This order keeps a missing-data problem from being mistaken for strategy failure, and keeps a model proposal distinct from a deterministic signal, an eligible paper plan, an order, and an execution result.

## Current checkpoint

- The `S01-NIFTY-ORB` version `0.1-setup` evaluator and isolated tests exist in `services/strategies`. The targeted pytest, Ruff, and mypy checks passed in the prior implementation slice.
- `services/market/references.py` and `UnderlyingReference` keep a replaceable latest index display quote. That is not a historical bar series.
- `services/market/history.py` only accepts NFO/BFO option instruments. `LiveCandles.observe` also rejects instruments outside NFO/BFO, so observed candles must not be relabeled as index evidence.
- `MarketHistoryBatch` and `LiveCandleSegment` are account/instrument scoped; the latter records observed option snapshots. Their suitability for index history is not established.
- `AgentPipeline.evaluate` receives option instruments and quotes, then runs analysis, proposal, independent review, and creates the existing short-lived `StrategyEnvelope`. It does not currently accept ORB assessments or index bars.
- The worker has durable evaluation slots and independent paper risk/execution controls. These are integration points to examine later, not permission to start it or loosen entry gates.

## Sequenced increments

### SI-0 — Preserve the operating boundary

**Purpose:** keep implementation and acceptance status honest throughout the program.

**Work:**

- Keep the worker stopped and entries disabled while building read-only data, assessment, and research slices.
- Keep broker login, live-market checks, and real-money execution outside the active work until explicitly resumed and separately planned.
- Distinguish software checks, prospective paper evidence, actual-market acceptance, and any later execution authorization.
- Do not change risk controls, qualification, or account arming as a side effect of strategy work.

**Exit check:** each later slice states which evidence level it actually reached and confirms that operating controls were not altered.

### SI-1 — Inventory permitted underlying-bar evidence

**Purpose:** settle whether an input source already exists before building an adapter or migration.

**Work:**

- Inspect local schema, stored market records, supported instrument metadata, and existing code paths for NIFTY and SENSEX index bars.
- For each candidate, verify identity, venue, interval, source, exchange timestamp, receipt/availability timestamp, final/provisional state, coverage, gaps, retention, and permitted use.
- Keep option history and option-derived observed candles separate from index evidence. A latest index reference cannot reconstruct an opening range.
- Do not query a provider, refresh market data, log in, or start a service during this inventory.

**Deliverable:** a concise evidence inventory: usable as-is, usable after a bounded read-only adapter, or unavailable, with provenance and coverage gaps.

**Exit check:** a reviewer can trace a candidate bar to its source and determine when SWAN could have used it. If none exists, report the data-source gap and stop; do not present fixtures as production coverage.

### SI-2 — Choose and implement one read-only underlying-bar path

**Dependency:** SI-1 establishes what data exists and what rights/source are available. Any external/provider path is a separate decision after that result.

**Source feasibility found during SI-1 follow-up:** Angel One's official
SmartAPI historical-data documentation says `getCandleData` provides past
data for indices and instruments, lists NSE as “NSE Stocks and Indices,” and
documents `ONE_MINUTE` candles. SWAN already has `ANGELONE_NIFTY_INDEX_TOKEN`
configuration for index references. This makes a dedicated NIFTY/NSE history
adapter a plausible next development slice; it does not verify the configured
token, account entitlement, returned history, timestamp quality, or actual
market access. See the [official candle API documentation](https://smartapi.angelone.in/docs/ResponseStructure).

Do not broaden the existing `HistoryQuery` silently: it currently validates
NFO/BFO option `Instrument` records and the persisted history table is keyed to
those records. SI-2 should use a separate typed index query/normalizer and an
appropriate provenance-preserving record shape. Use configured tokens rather
than guessed token values; record response receipt/availability separately
from the candle timestamp and label finality as elapsed-interval-based unless
the provider confirms finality.

**Purpose:** supply index evidence to evaluators without coupling them to storage, wall time, network, or model code.

**Work:**

- Define a source-neutral typed read contract returning bounded bars with stable evidence IDs, NIFTY/SENSEX identity, exchange, source, open/close time, availability time, finality, and Decimal OHLC.
- Preserve conflicting observations and gaps explicitly; never silently overwrite evidence needed to reproduce an earlier assessment.
- Adapt only the verified source found in SI-1. Keep index-bar storage separate from option-market records unless reviewed schema semantics prove reuse is safe.
- Keep ingestion/read access separate from paper execution. Do not create synthetic application rows or mark provisional observations final.
- Make historical reads as-of aware: a bar received later cannot appear in an earlier snapshot.

**Exit check:** isolated contract/adapter tests cover identity, source, availability, session, gaps, duplicates, and as-of behavior. Production-source availability remains separately labeled until actually observed and accepted.

**SI-2a status:** the NIFTY/NSE one-minute query and in-memory normalizer are
implemented in `services/market/index_history.py`, behind
`AngelOneClient.index_candles`. The returned batch carries a response hash,
receipt time, request identity, and stable bar evidence IDs. It is not persisted
or connected to the ORB evaluator or agents, and the provider method has not
been called. The next sub-slice is immutable local persistence and a bounded
read path; real source acceptance remains separate.

**SI-2b status:** added `index_history_batches`, a separate immutable table for
NIFTY/NSE response provenance, plus `services/market/index_history_store.py`
for idempotent persistence and interval-bounded reads that exclude responses
received after `as_of`. A later provider response remains a distinct snapshot;
the existing record is never overwritten. SQLite fixture coverage exercises
round-trip persistence and as-of exclusion. Focused strategy tests passed (17),
Ruff passed after import sorting, mypy passed, and Alembic reports the new
revision as the sole head. No database migration was applied, provider was
called, or source availability accepted. Next is a deliberate contract review
and wiring read-only consumers to snapshots before assessments; live source
verification remains paused.

**SI-3 status:** added `strategy_assessments`, linked by foreign key to the
exact index-history snapshot and uniquely keyed by snapshot/strategy/version.
`services/strategies/assessment_store.py` validates that the source snapshot
was available by assessment time and that every used or excluded bar ID belongs
to that snapshot. It stores the deterministic payload, deduplicates an
identical rerun, rejects a conflicting rerun for the same snapshot/version,
and provides a bounded as-of audit read. Focused tests passed (18), Ruff and
mypy passed, and Alembic reports one head. The migration was not applied; the
assessment store is not connected to a worker, agent, API, or execution path.
Next is SI-4's ORB session/bar-close watcher and stable event identity, still
offline and unconnected to model scheduling.

**SI-4 status:** added `services/strategies/orb_watcher.py` and durable
`strategy_watcher_events`. Event identity includes session, strategy/version,
source snapshot, and event kind. Exact redelivery returns the stored decision;
unchanged setup state does not emit another candidate, while gap/unavailable
assessments remain recorded with a no-candidate reason. The watcher records
assessments and transitions only; it does not schedule agents or orders.
Focused tests passed (19), Ruff and mypy passed, and Alembic reports one head.
The migration was not applied.

**SI-5 status:** extended the explicit strategy assessment workflow with a
bounded canonical assessment context: assessment ID, exact strategy/version
and definition fingerprint, snapshot, status, cited evidence, as-of, and a
fixed expiry capped by the assignment deadline. Analyst outputs now have
structured `SELECT`, `ABSTAIN`, `RESEARCH`, and `INSUFFICIENT_DATA`
dispositions. Validation binds selections to an eligible setup and exact
version, restricts analyst/reviewer/research citations to assessment evidence,
and rejects unknown assessments or expired context. Missing and unavailable
inputs are returned as `INSUFFICIENT_DATA` in the workflow outcome; they are
not treated as strategy failure. Existing deadline, review, budget, and audit
paths remain in place. Offline checks passed (22 focused tests, Ruff, mypy).
Agent DB integration tests could not initialize: the local psycopg install has
no `pq` wrapper and libpq is unavailable. No model call or provider request was
made. Next is SI-6's mandate and paper-plan boundary; its instrument, horizon,
expiry, and policy conflicts need an explicit product decision before code
can define eligibility.

**SI-6 status:** added a persisted `StrategyPlanDraft` derived from each
assessment. It maps deterministic outcomes to `FIT`, `DOES_NOT_FIT`,
`INSUFFICIENT_DATA`, or `OUT_OF_SCOPE`, carries exact assessment/snapshot and
evidence links, and for a setup records only the underlying trigger predicate,
invalidation, target, and opportunity expiry. For this first NIFTY-only ORB
research draft, contract expression is NIFTY NFO call/put by direction, the
nearest listed expiry strictly after the session and within the existing
seven-day policy, closest-to-underlying strike with lower-strike tie break,
one entry attempt per session, observed-ask limit with no chase, and a
300-second strategy holding ceiling. Future execution must also enforce the
then-current account risk configuration, so a stricter account limit wins.
The 30-minute hold and other experimental exit parameters from the worked
example do not override that ceiling. These are reviewable plan constraints,
not approval to trade: drafts are immutable, as-of-readable,
`execution_eligible=false`, and `PENDING_REVIEW`; current account risk review,
live option contract/quote evidence, premium exits, and fees remain absent.
The assessment workflow persists and exposes the draft. Checks passed (24
focused tests, Ruff, mypy; Alembic one head). No migration was applied and no
order/contract was produced. The non-executable SI-6 software slice is complete;
actual paper admission remains a separate reviewed step.

**SI-7 status:** added a fail-closed paper preflight contract. It rejects every
current plan because the contract fixes it at `execution_eligible=false` and
`PENDING_REVIEW`; it does not create an intent, envelope, or order. This records
the boundary while the first mandate and paper lifecycle remain unreviewed.
Existing account qualification and risk controls are unchanged. A true paper
admission integration cannot be completed until that review defines an
authorized mapping into the existing manual-intent/risk path.

**SI-8 status:** not implemented. Evaluation policy still needs review for
cost/fill assumptions, drawdown tolerance, uncertainty, sample construction,
and promotion criteria. No economic or comparative report can be defended
without those choices and linked realized paper outcomes; fixtures are not
market evidence.

**SI-9 status:** added immutable, deterministic-ID research candidate records.
Candidates are explicitly `INACTIVE_RESEARCH`, carry their own evidence,
assumptions, scope, and evaluation method, and cannot alter an active strategy.
Promotion remains absent pending SI-8 policy review and explicit authorization.
The focused strategy suite passed (26 tests), Ruff passed, mypy passed for the
strategy package and new strategy-record API, and Alembic reports one head.
The schema migration remains unapplied.

**SI-10 status:** added authenticated, bounded, read-only API access to
assessments, plan drafts, and research candidates with explicit as-of filtering.
Added a read-only Strategy intelligence dashboard in the existing workspace.
The dashboard displays deterministic assessments, non-executable plan drafts,
and inactive research candidates with evidence IDs. Conversational explanations
over linked market/agent/risk/order/outcome records remain future work because
those cross-lifecycle links and read tools are not yet present.

### SI-3 — Persist deterministic strategy assessments

**Dependency:** SI-2 provides provenance-preserving snapshots.

**Purpose:** make each assessment reproducible and inspectable before agents consume it.

**Work:**

- Define an immutable assessment record with strategy ID/version and definition fingerprint, snapshot ID/as-of, status/reason codes, used and excluded evidence IDs, missing intervals, and computed levels.
- Store assessments independently from `StrategyEnvelope`, model proposals, and orders. Add a migration only if the existing schema cannot preserve the required immutable links.
- Make duplicate evaluation of the same snapshot/version deterministic and safely deduplicated. A new snapshot/version creates a new assessment rather than rewriting prior evidence.
- Add a bounded read path for audit and later UI use; do not add execution behavior.

**Exit check:** a saved assessment can be verified from its exact input snapshot and strategy definition, including unavailable states.

### SI-4 — Add a deterministic watcher and event identity

**Dependency:** SI-2 and SI-3.

**Purpose:** update strategy state cheaply as observations arrive without waking models on every tick.

**Work:**

- Start with session-preparation and bar-close events for ORB. Do not add a generalized event framework without a concrete need.
- Derive a stable event key from session, strategy/version, source snapshot or bar identity, and relevant transition.
- Recompute on meaningful state changes; deduplicate repeated delivery and represent stale, gapped, or superseded work explicitly.
- Record why a watcher did or did not emit a candidate. Do not enqueue an agent task merely because a condition remains continuously true.

**Exit check:** replaying the same event cannot produce duplicate assessments or entry intents; a gap or stale input blocks a fresh signal.

After the ORB watcher is stable, extend trigger handling in bounded groups rather
than building a universal event bus up front:

- **Market-state changes:** completed bars, watched-level approach/crossing, and
  material volatility/liquidity/regime changes. Code updates features and
  invalidates affected plans; wake an agent only for a meaningful new judgment.
- **Information changes:** timestamp, attribute, deduplicate, and assess
  relevance of news. Reuse an accepted source only after confirming its actual
  coverage, delay, and permitted use. Repeated or syndicated headlines must
  not repeatedly wake a model.
- **Account/execution changes:** acknowledgement, fill, reject, cancel, and
  unresolved outcomes update durable state and protection first. Agent review is
  optional and cannot delay reconciliation or exits.
- **Operations/session changes:** feed disconnect, stale state, restart,
  session close, or accumulated outcomes invalidate stale work and preserve
  gaps. Optional diagnosis/research happens after immediate controls.

Each group needs its own event identity, deduplication, freshness, and tests
before being connected to model scheduling. No universal reassessment cadence
or significance threshold is assumed.

### SI-5 — Attach strategy evidence to bounded agent reasoning

**Dependency:** SI-3 and SI-4.

**Purpose:** let existing agents use deterministic evidence while preserving bounded, auditable behavior.

**Work:**

- Add assessment context to the existing agent evaluation contract: strategy ID/version, status, fingerprint, evidence links, assessment time, and expiry. Keep raw market context bounded.
- Update structured schemas/instructions so agents can select an eligible predefined strategy, abstain with a reason, or submit a research candidate. Missing data must remain `INSUFFICIENT_DATA`, not a strategy failure.
- Validate every referenced assessment/evidence ID in code. Model prose cannot establish eligibility or evidence linkage.
- Preserve review, budget, timeout, audit, and expiry controls. Measure whether independent review adds value before increasing model calls.
- Keep tool-calling/framework replacement out unless a demonstrated failure requires it.

**Exit check:** an offline/paper-context test proves output cannot cite an unknown assessment, change its version, turn unavailable data into a signal, or extend an expired opportunity.

### SI-6 — Separate strategy selection from bounded paper plans

**Dependency:** SI-5 and a reviewed first mandate.

**Purpose:** connect a selected strategy to an explicit paper hypothesis without turning an assessment into an order.

**Work:**

- Define the first mandate: personal account, intraday NIFTY/SENSEX long-options paper trading, permitted sessions, horizon, risk, and information boundaries. Resolve conflicts with existing account policy before supporting them in code.
- Define candidate outcomes `FIT`, `DOES_NOT_FIT`, `INSUFFICIENT_DATA`, and `OUT_OF_SCOPE`, with structured reasons.
- Specify option expression separately from underlying setup: contract eligibility, freshness, spread/liquidity, entry boundary, invalidation, target, sizing, and expiry rules need their own evidence and acceptance.
- Persist a bounded paper plan with strategy/evidence links, trigger predicate, validity deadline, invalidation, and risk constraints. Keep it separate from the existing executable envelope until mapping and gates are reviewed.
- Never infer option fills, premium stops, or P&L from index candles.

**Exit check:** plan validation rejects stale evidence, missing option data, unsupported expiry, mismatched strategy versions, and unreviewed mandate changes. No plan alone grants account permission.

### SI-7 — Integrate only with existing paper controls

**Dependency:** SI-6 and explicit review of the paper lifecycle integration.

**Purpose:** exercise the strategy path in the paper system while keeping deterministic controls authoritative.

**Work:**

- Map plan eligibility into existing validation, risk, account, and paper-order admission. Do not bypass or weaken existing gates.
- Enforce one intent per event/plan, freshness at dispatch, bounded retries, and explicit pending, rejected, canceled, partial, and unresolved outcomes.
- Keep position monitoring, exits, reconciliation, and loss controls independent from model availability.
- Keep the worker stopped and entries disabled unless the user separately directs a specific controlled paper run and required local controls are reviewed. This plan does not authorize a run.

**Exit check:** isolated tests cover duplicate events, stale plans, risk denial, worker/model interruption, and paper-order recovery without activating a live worker.

### SI-8 — Establish fair strategy and agent evaluation

**Dependency:** trustworthy snapshots, assessments, plan/order links, and reviewed evaluation policy.

**Purpose:** measure setup correctness, agent contribution, execution realism, and economic outcomes separately.

**Work:**

- Freeze evaluation methodology before examining results: outcome measures, costs, spread/fill assumptions, drawdown, sample construction, uncertainty, and promotion criteria. Numeric thresholds remain an explicit product decision.
- Compare deterministic baseline with agent-assisted selection under matched information and declared cost assumptions. Track abstentions, missed opportunities, data gaps, risk rejections, latency, cost, and failures as well as net outcomes and drawdown.
- Preserve chronological evidence availability and model/tool/strategy versions. Address frontier-model hindsight contamination in historical research.
- Prefer prospective paper evidence when historical option/fill evidence is insufficient. Do not add a replay service unless separately reconsidered.

**Exit check:** reports disclose sample size, evidence limits, assumptions, and software-versus-market acceptance. No profitability or promotion claim rests on fixtures alone.

### SI-9 — Add controlled strategy research and post-session learning

**Dependency:** SI-8 defines how candidates are evaluated.

**Purpose:** let agents develop adaptations and tools without silently changing the active library.

**Work:**

- Add versioned research drafts for adaptations, new combinations, and missing calculations, each with hypothesis, scope, formula/units, evidence needs, assumptions, and proposed evaluation method.
- Keep candidates inactive until review and evaluation. Generated code cannot modify active execution, access credentials, or inherit eligibility from reused components or model confidence.
- Record failed experiments and keep prior versions immutable.
- Decide promotion, uncertainty, drawdown, and observation-duration criteria before a candidate can become eligible; require explicit authorization for any move toward autonomy.

**Exit check:** post-session learning can propose but cannot activate or rewrite an active strategy.

### SI-10 — Surface the recorded story through chat and dashboard

**Dependency:** durable assessment, agent, plan, risk, order, and outcome links.

**Purpose:** explain decisions and abstentions from authoritative records.

**Work:**

- Reuse the existing chat-first product direction for questions such as “why no setup?”, “why was this rejected?”, and “what evidence supported the selected strategy?”
- Link answers to the exact session, assessment, evidence, evaluation, plan, order, and position, including timestamps and unavailable data.
- Keep chat separate from the autonomous worker. Add only separately reviewed commands with explicit authorization; this plan grants no new chat order or risk-setting capability.

**Exit check:** answers come from linked records and distinguish recorded facts from explanation or inference.

## Decisions to resolve before dependent slices

1. **Data source:** what locally stored, permitted NIFTY/SENSEX index evidence exists, and is its provenance adequate?
2. **First mandate:** confirm instruments, horizon, session, expiry eligibility, and allowed information. The handoff and existing account policy differ in places; reconcile before execution integration.
3. **Evaluation policy:** define costs/fill realism, drawdown tolerance, uncertainty, minimum evidence, and promotion criteria before measuring candidates.
4. **Human position ownership:** define before combining shared-account manual and agent position management. This plan intentionally does not settle that policy.
5. **Broker execution:** treat as a separate future authorization and qualification program. Recheck published limits and actual account behavior then; this plan assumes no broker order routing.

## Implementation closeout

**SI-1 status: complete; no suitable local index bars found.** The inspected
application paths show that `UnderlyingReference` is a replaceable latest
index quote, while history and observed-candle paths are scoped to NFO/BFO
option instruments. No index-bar table or read path exists.

The local database initially was stopped. I started the existing PostgreSQL
instance for this inventory and queried it through the bundled `psql` client
using `BEGIN READ ONLY` transactions. The Python query route remains unavailable
because psycopg has no `pq` wrapper/libpq. Results:

- `underlying_references`: 0 rows; `market_snapshots`: 0 rows.
- `market_history_batches`: 5 batches, 4 available and 1 unavailable. All
  referenced option instruments (NIFTY/NFO CALL or SENSEX/BFO CALL), from
  `angelone-historical:getCandleData`; none are index spot bars.
- `live_candle_segments`: 61 records, all NIFTY/NFO or SENSEX/BFO CALL/PUT
  option contracts. Their source is `observed_ltp_snapshots`, with coverage
  explicitly limited to observed snapshots rather than all exchange trades.
- Schema inspection found only the existing underlying-reference, market
  snapshot, option-history, and observed-option-candle paths; no separate
  underlying-bar store exists.

The local database was stopped after the read. Its startup/shutdown may have
updated its own PostgreSQL control/WAL files; no application records were
written by the inventory query. This establishes that the current local SWAN
records do not provide a provenance-preserving NIFTY/SENSEX index-bar path.

**Implementation pass closed 22 November:** SI-1 through SI-6 software
foundations are implemented, SI-7 ends at a fail-closed preflight, SI-9 stores
inactive research candidates, and SI-10 has authenticated API reads plus a
read-only dashboard. SI-8 economic evaluation and executable paper admission
remain pending policy review. The dashboard has not had a manual browser
acceptance pass. Full backend tests passed (375); Ruff, targeted mypy, frontend
typecheck/tests/build passed; Alembic reports one head and its migration is
applied to the local development database. The remaining work and the formal
review limitation are tracked in D19 of [DEFERRED-WORK.md](./DEFERRED-WORK.md).
Actual provider/market acceptance remains user-deferred. This closes the
implementation pass, not the strategy lifecycle or market acceptance.

## Non-goals

- Fixed daily-profit promises or assumptions that strategy names imply profitability.
- New predictive-model training, a generalized agent framework, or many-agent expansion without measured need.
- Treating option history, option-derived candles, fixtures, or the latest index quote as underlying index-bar evidence.
- Broker login/live-market acceptance, real-money order routing, or relaxing permission, risk, qualification, or arming gates.
- Automatically promoting a strategy based on evaluation results.
