# Strategy MVP: the next small implementation

Prepared 22 November 2026, Asia/Kolkata. Status: implementation specification only. No code was changed or tests run to prepare this file.

## Decision

Build one pure, read-only NIFTY opening-range breakout evaluator with typed inputs and reasoned outputs. This is the first quantitative tool for the strategy agents. It identifies a setup; it cannot recommend an executable option order, create a strategy envelope, or authorize trading.

This is one bounded increment, not approval to implement the entire discussion. Finish and review this increment before choosing the next one. Do not replace the harness or build additional agents in this increment.

## Why this comes first

The agent coordination already exists. The missing capability is a mechanically checkable strategy assessment that agents can use as evidence.

| Observed code | What exists | Consequence |
| --- | --- | --- |
| `services/agents/pipeline.py`, `AgentPipeline.evaluate` | Sequential analysis, proposal, and independent review, with citation checks, audit context, stage outcomes, a deadline, and evidence-bound envelope expiry | Reuse this coordination later; no demonstrated need for a framework migration first |
| `services/agents/provider.py`, `StructuredProvider.generate` | Structured outputs, token reservations, usage records, bounded requests, and instructions that prohibit tool requests | This is a bounded model pipeline, not a general tool-calling agent runtime; future tool integration needs a deliberate change |
| `services/agents/contracts.py` | Generic outlook/proposal/review schemas | No predefined strategy ID, frozen eligibility rules, or strategy assessment contract |
| `services/worker/runtime.py` | Eligible option quotes passed into the pipeline in durable evaluation slots | Current model context has no underlying candle sequence or ORB calculations |
| `services/market/history.py`, `HistoryQuery.provider_body` | Bounded historical candle requests for NFO/BFO option instruments | This is not a NIFTY spot-history adapter |
| `services/market/references.py`, `save_reference`; `services/core/models.py`, `UnderlyingReference` | Replaceable latest index display reference | A latest index price cannot reconstruct the opening range |
| `services/market/live_candles.py`, `LiveCandles.observe` | Observed candle aggregation restricted to supported option instruments | Do not relabel these as index bars |

The recommendation follows the separate strategy discussion. [RESUME.md](./RESUME.md) and D23 in [DEFERRED-WORK.md](./DEFERRED-WORK.md) still identify chat as the active product priority. This spec proposes a separate strategy increment; it does not rewrite those plans or claim to complete chat. D19 describes the broader strategy gap.

## Product goal and boundary

The eventual goal is to evaluate predefined strategies first, then let agents develop alternatives when those strategies do not fit. Each decision needs inspectable evidence, costs, invalidation, and evaluation history. The first instrument scope is intraday NIFTY/SENSEX long-options paper trading for one user.

This increment implements only the NIFTY underlying setup assessment. It establishes a deterministic baseline for later agent comparison. SENSEX, option selection, sizing, exits, and generated strategies remain later increments.

Preserve the stopped worker, disabled entries, and all existing gates. Do not log into the broker, call providers, start a worker, change settings, or run actual-market acceptance. Synthetic inputs belong only in isolated unit tests. Do not add a replay service, seeded application data, demo strategy results, or a claim of profitability.

## Deliverable

Add a small `services/strategies` package with a versioned ORB definition and an `evaluate_orb` function. It accepts a caller-supplied, point-in-time snapshot and returns a serializable assessment. No database, clock, environment, network, model, or worker dependency is allowed in the evaluator.

### Inputs

- A verified `ExchangeSession`, restricted to a regular NSE session opening at 09:15 IST and extending past the signal window. Unsupported sessions produce an explicit result.
- An explicit timezone-aware `as_of`, used for every time comparison. Never call the wall clock internally.
- A snapshot identity, source identity, underlying identity, and a bounded collection of one-minute bars.
- Each bar includes a stable evidence ID, NIFTY/NSE identity, source, opening and closing timestamps, `available_at`, final/provisional state, and finite positive Decimal OHLC with valid ordering. `available_at` means when this record was available to the system, not when its exchange minute began.
- Enforce a maximum of 400 bars per call. Require unique evidence IDs, unique minute timestamps, the declared source, and one session. Reject malformed, conflicting, mixed-source, mixed-instrument, or cross-session inputs. Sort valid bars by time so caller ordering cannot change the result.

Only final bars with `closes_at <= as_of` and `available_at <= as_of` can contribute. Future or provisional bars may be present but must be excluded and reported by ID. A completed bar received late cannot be treated as known earlier. Do not accept option bars as NIFTY index evidence.

### Frozen research definition

Use strategy ID `S01-NIFTY-ORB`, version `0.1-setup`. This deliberately names the setup subset of the fuller research card in the discussion.

1. Freeze the opening range from all 15 bars opening in `[09:15, 09:30)` IST. Before 09:30, report `NOT_READY`. After that, missing eligible opening bars produce `UNAVAILABLE`.
2. Compute `H = max(high)`, `L = min(low)`, `W = H - L`, and `B = 0.05 * W`. A zero-width range produces `NOT_APPLICABLE`.
3. Inspect completed post-range bars closing after 09:30 and no later than 11:00 IST. Require continuous eligible minute coverage from the opening window through the assessment's last required closed minute, capped at 11:00. A missing or not-yet-received minute produces `UNAVAILABLE`, since the first trigger cannot otherwise be established.
4. The first close `C` satisfying `H + B < C <= H + 0.25 * W` produces `BULLISH_SETUP`. The first satisfying `L - 0.25 * W <= C < L - B` produces `BEARISH_SETUP`. Equality at a breakout threshold is not a break. An overextended close is a rejected candidate, not a trigger; continue looking for the first eligible close. Record rejection time and reason.
5. Report bullish invalidation `H - B` and target `C + W`, or bearish invalidation `L + B` and target `C - W`. These are index levels, never option premium stops or execution instructions.
6. The trigger opportunity expires at `trigger.closes_at + 60 seconds`. At or after that time, return `EXPIRED` and preserve the original trigger. Do not rediscover a later trigger to renew it. No trigger before the cutoff produces `NO_SETUP`; before the cutoff this means none yet, and at/after it means none in the window.

The 5% buffer, 25% extension boundary, opening interval, and cutoff are research choices. Keep them immutable for this version. Changing them requires a different definition/version. Do not add optimization or configurable strategy menus now.

Minute-based status does not prove that the setup remains valid between observations. A later integration must independently check fresh underlying state, option quotes, liquidity, risk, and execution permissions. This evaluator neither tracks account entry attempts nor applies the complete strategy's order/exit lifecycle.

### Output

Return strategy ID/version, definition fingerprint, snapshot identity, `as_of`, session identity, status, stable reason codes, and evidence IDs. Include missing intervals and excluded-bar IDs where applicable. Valid calculations include range boundaries, width, buffer, and any trigger, invalidation, target, and expiry.

Use statuses `NOT_READY`, `UNAVAILABLE`, `NOT_APPLICABLE`, `NO_SETUP`, `BULLISH_SETUP`, `BEARISH_SETUP`, and `EXPIRED`. Represent unknown values as null. Invalid schemas raise validation errors; well-formed but insufficient evidence produces an assessment. Schema and algorithm checks must not rely on model prose.

No `BUY`, quantity, option contract, probability-of-profit, estimated P&L, or `StrategyEnvelope` belongs in this result. A deterministic explanation may describe the computed predicate, but must not imply execution eligibility.

## File-level implementation checklist

| File | Change |
| --- | --- |
| `services/strategies/__init__.py` | Package marker and minimal public exports |
| `services/strategies/contracts.py` | Frozen input, definition, status/reason, and assessment schemas using existing Decimal/aware-time conventions |
| `services/strategies/orb.py` | One immutable definition and pure evaluator implementing the rules above |
| `tests/test_strategy_orb.py` | Focused schema, time, coverage, provenance, and calculation tests |

Reuse `ExchangeSession` and IST conventions from `services/core/contracts.py`. Reuse base contract and fingerprint conventions where their semantics fit. Keep new evidence identity distinct from existing option-quote UUID citations. Do not modify `AgentPipeline`, `StructuredProvider`, runtime scheduling, market adapters, risk, paper execution, UI, migrations, dependencies, configuration, or existing plans for this increment.

## Acceptance and checks

The increment is complete only when:

- Tests establish exact range and level calculations in both directions, strict threshold equality, extension-boundary behavior, the first eligible trigger, 11:00 inclusion, 60-second expiry, and no renewal from later bars.
- Tests cover before-open and before-range-close states, no setup, flat ranges, missing minutes, delayed availability, provisional/future observations, mixed identity/source, invalid OHLC, duplicate bars/IDs, unsupported sessions, and the collection bound.
- Equivalent timezone representations and reordered inputs produce the same assessment. Every used calculation points to supplied evidence. Modifying excluded future data cannot change the eligible historical result.
- The package performs no I/O and cannot produce an execution envelope. Unit fixtures never populate application tables.
- Targeted pytest, Ruff, and mypy pass using the existing project environment. Broaden checks only if implementation touches shared code or reveals a regression.

Suggested checks after implementation, not run during this planning task:

```powershell
python -m pytest -q tests/test_strategy_orb.py
python -m ruff check services/strategies tests/test_strategy_orb.py
python -m mypy services/strategies
```

Passing these checks establishes software behavior under isolated inputs. It establishes neither actual index-data availability nor a profitable strategy nor actual-market acceptance.

## Stop point and the next decision

After this evaluator passes review, stop and demonstrate its structured results using isolated tests. Do not automatically continue into agents or trading.

Then choose one next increment: obtain a provenance-preserving, read-only underlying-bar input path. Current inspected code does not establish this capability. Determine whether actual locally stored permitted evidence suffices before proposing any provider change. If no suitable data exists, report the gap; broker login and live checks remain paused.

Only after that input path exists should a later increment attach the assessment to the existing agent context and enforce its strategy/version/evidence linkage. Subsequent work can compare deterministic selection with agent reasoning, add other strategy cards, and save agent-originated research drafts. Harness changes need a concrete failure or missing requirement first.

Broader unresolved topics stay in [the discussion](./AUTONOMOUS-TRADING-DISCUSSION.md#strategy-system-design-22-november-2026). Do not update `DEFERRED-WORK.md` for this brainstorming thread, per the user's later instruction. This spec introduces no new numeric profitability or promotion threshold.

## Implementation handoff to another chat

This file is self-contained for the first increment. The discussion document explains the wider direction; its later ideas are not additional implementation requirements. The planning chat may continue exploring those ideas while the implementation chat works on this slice.

### Start here

1. Read the workspace `AGENTS.md`, `RESUME.md`, and this entire spec. Inspect the code references above to confirm they still match the checkout.
2. Record the initial `git status --short` and inspect any existing files at the four intended paths. The workspace already contains unrelated modifications and deletions. Preserve them. Do not reset, clean, stash, or include them in this slice.
3. Implement only the four files in the implementation checklist. If another chat has already created or changed those files, inspect that work before editing and avoid overwriting it. Coordinate if ownership overlaps.
4. Run the targeted checks with the installed project environment. Resolve failures attributable to this slice. Report environment blockers without installing or upgrading tools, changing application configuration, or starting services automatically.
5. Stop after this increment. Return a reviewable result and the report below. Do not integrate it into agents, providers, APIs, UI, or execution, and do not commit, push, or deploy unless separately requested.

The user's later request is to stop deferred-work updates in this thread. For this bounded handoff, leave `DEFERRED-WORK.md`, `RESUME.md`, existing plans, the discussion document, and this spec unchanged. Report remaining work in the completion message. Do not create additional planning or progress files.

### Implementation decisions clarified

- The evaluator is an ordinary synchronous Python function. Use the project's existing Pydantic and Decimal conventions; add no framework or dependency.
- Define minute boundaries by converting aware timestamps to IST. A bar spans exactly one minute, begins on a minute boundary, and belongs wholly to the declared session. Require `available_at >= closes_at` for final records. Reject impossible timestamp relationships.
- Before session open or opening-range completion, return `NOT_READY` with a stable reason. Use `UNAVAILABLE` for missing eligible data once it should be assessable. Use `NOT_APPLICABLE` for unsupported session/underlying scope or a zero-width range. Malformed records remain validation errors.
- For coverage, the last required minute is the latest minute closed by `as_of`, capped at 11:00. Scan chronologically and require uninterrupted eligible coverage only until the first qualifying trigger is established. If a required gap occurs before that trigger, return `UNAVAILABLE`. If no trigger is established, require coverage through the capped assessment time. Missing bars after an established trigger do not erase it or change its expiry. This clarification narrows rule 3 above to avoid demanding irrelevant later bars.
- At exactly 09:30, complete opening data can produce `NO_SETUP` with a `NO_TRIGGER_YET` reason. The first post-range signal bar can close at 09:31. At exactly 11:00, the bar opening at 10:59 is included; the bar opening at 11:00 is not.
- A qualifying trigger expires at its own close time plus 60 seconds, even if it arrives late. A late-received trigger can therefore first appear as `EXPIRED`. Do not renew validity from receipt or evaluation time.
- Version `0.1-setup` applies only the frozen predicates written here. It does not invalidate an already detected setup from subsequent bars, check current underlying price, track fills/attempts, or select an option. Those belong to later integration.
- Do not quantize index calculations to option tick sizes or money precision. Preserve Decimal arithmetic and serialize computed decimal values as strings. Hash a canonical representation of the immutable definition for a stable fingerprint; do not include wall time or random IDs.
- Result values depend on supplied snapshot identity and `as_of`. Excluded-bar IDs may change when excluded records change, but eligible calculations, trigger selection, and status must not change because of excluded future values. Keep this distinction explicit in tests.
- Use short stable reason codes with structured details; reason text must not be needed to interpret the status. Evidence lists must make the opening range and trigger calculations traceable. Do not treat these new IDs as persisted `Quote` citations.

If an ambiguity changes trading behavior, input provenance, or the allowed file scope, report it before widening implementation. Resolve routine naming and test organization locally. No model/provider request is needed to complete this increment.

### Required completion report

Return:

- What was implemented and the exact files changed.
- Targeted test/lint/type-check commands and actual outcomes, including failures or checks not run.
- One compact bullish, no-setup, and missing-data example from isolated unit tests, explicitly labelled as test inputs.
- Any remaining ambiguity or limitation, especially the missing production underlying-bar path.
- Confirmation that no provider calls, application data writes, service launches, permission changes, or unrelated edits occurred.

Do not claim profitability, actual-market qualification, full strategy completion, or agent integration. After reporting, wait for the next user instruction.

### Prompt to paste into the implementation chat

> Work in `D:\s\swan`. Implement only the first increment specified in `STRATEGY-MVP-SPEC.md`. Read its implementation handoff and the workspace instructions first. The task is a pure, typed, deterministic NIFTY opening-range setup evaluator and isolated tests, confined to the four listed files. Preserve existing unrelated work. Do not change agents, harness, providers, UI, trading permissions, existing docs, or DEFERRED-WORK.md. Do not log into the broker, call providers, start services, commit, or deploy. Run the specified local checks, report actual results and limitations, and stop after this slice.
