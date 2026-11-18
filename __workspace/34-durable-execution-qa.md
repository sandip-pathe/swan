# Durable execution and worker session QA

18 November 2026. Status: **DONE_WITH_CONCERNS** for the scoped native functional checks; complete paper readiness is still blocked.

## Target and isolation

Target: durable coordinator → deterministic risk → order ledger → depth matcher → protective exit → cash/fee reconciliation, plus worker daily-session rollover. Existing pytest fixtures create a UUID-named PostgreSQL schema, migrate it, and remove only that schema. Fee rates, quotes and strategy evidence are explicitly synthetic test inputs. They never populate the owner's trading views. Production activation is not exercised: the coordinator's deliberately closed configuration gate is replaced only inside the disposable test fixture to reach downstream contracts. No production bypass or qualification flag was added.

Native commands use the workspace's existing pytest, Ruff and mypy. The gstack QA Bash launcher/evidence wrappers could not run because Bash was unavailable in the workspace shell; their prescribed capture/telemetry workflow is not claimed complete. Native pytest XML captures are retained instead. No browser changes or browser QA were needed for this backend change. This folder is not a Git checkout, so no commits were created.

## Reproduced defect and repair

**ISSUE-001: previous-day daily-loss block cannot roll over in the worker.**

Before repair, `TradingRuntime.cycle()` returned at observation/entry-readiness checks and then rejected `daily_blocked` before the only later `start_session()` call. That prevented the legitimate new session from clearing yesterday's block. The engine already rejects unresolved orders, holdings and reconciliation failures; no weaker reset was needed.

The regression ran twice before repair with the same isolated starting state: account session November 13, daily block true, no exposure/orders, a verified open November 14 test session. Expected session November 14; actual remained November 13. Same-day retention already passed. Preserved failure evidence: `.local/qa-durable-20261118/rollover-before.xml`.

The worker now reads the persisted account session key and starts a verified open new session before entry gating, using the existing guarded engine method. It then clears prior strategy/resume intent and leaves entries paused. Existing-position monitoring still runs first; the independent execution watchdog is unchanged. A rollover failure reports `SESSION_ROLLOVER_BLOCKED`, without resetting risk.

Value: protects=verified flat-account rollover; fails_when=prior-day loss check precedes rollover; why_new=earlier tests covered same-session retries, not worker rollover; seam=none; no_claim=real exchange/provider qualification (isolated calendar and clock).

## Contracts exercised

| Contract | Result | Evidence |
|---|---|---|
| Risk-approved durable entry remains unfilled during simulated latency | Pass | `tests/test_durable.py` |
| Eligible later observation fills entry; protective stop installed | Pass | same |
| Target escalation exits; cash reconciles to premiums less fees | Pass | same |
| Sale proceeds remain restricted | Pass | same |
| First partial entry cancels remainder, releases reservations, protects held quantity | Pass | same |
| Pausing cancels unfilled entry with no exposure or cash change | Pass | same |
| Reconstructed service and repeated quote do not duplicate fills | Pass | same |
| Stop exit continues while entries are paused after reconstruction | Pass | same |
| Unresolved orders or positions prevent daily-baseline reset | Pass, both cases | same |
| Verified open new day resets old daily loss, without arming | Pass after repair | `tests/test_session_rollover.py` |
| Same-day retry retains daily loss and baseline | Pass | same |
| Pre-open or missing calendar coverage cannot reset baseline | Pass, both cases | same |

These are bounded contract checks, not exhaustive testing of every input field, race, database outage or process-kill boundary. No claims of live fills, actual broker fee allocation, provider depth-unit semantics or strategy quality follow from fixture success.

## Commands and retained reports

Run in PowerShell after activating workspace tools:

```powershell
. ./scripts/activate.ps1
python -m pytest tests/test_session_rollover.py -q
python -m pytest tests/test_durable.py tests/test_session_rollover.py -q
ruff check services tests
mypy services
python -m pytest -q --junitxml=.local/qa-durable-20261118/full-suite-final.xml
```

The pre-repair regression failed on the new-day case; the repaired targeted run passed all eight cases then present. The final run adds pre-open/unknown-calendar negative cases and passes **86 tests**. Ruff and mypy (50 source files) pass. Reports under `.local/qa-durable-20261118` preserve before, targeted after and full-suite results. Existing Starlette/httpx TestClient deprecation warning remains unrelated.

## Remaining blockers and next work

- Verify Angel One fee rounding/allocation and explicit BFO IPFT treatment. The owner has been asked whether an existing options contract note is available privately; no fresh trade is needed or authorized to obtain one.
- Verify best-five depth quantity units for both venues. Order-quantity documentation and lot-size metadata do not by themselves prove depth units.
- Implement the bounded supervised validation/qualification lifecycle from the accepted completion plan. The current hardcoded final activation gate remains closed; downstream fixture tests are not a substitute for removing that circular gate through a properly scoped lifecycle.
- Actual-market fill/protection evidence, broader cancellation/concurrency/failure recovery, UI durable order visibility and journal reconciliation remain later work.

Durable learning: readiness and previous-day loss checks must not precede a guarded legitimate session transition; otherwise yesterday's block prevents its own reset. Keep rollover independent of entry permission while preserving the flat/reconciled-account guard and same-day idempotency.
