# Verification strategy

## Required test layers

| Layer | Coverage |
| --- | --- |
| Domain unit tests | Money precision, costs, lot sizing, risk boundaries, stop/target ordering, daily baseline |
| Database integration | Atomic fill/ledger updates, unique keys, concurrent orders, retries, rollback, position reconstruction |
| Provider contract tests | Recorded/synthetic payload normalization, missing metrics, stale/crossed quotes, instrument changes |
| Agent tests | Valid decisions, WAIT, invalid JSON, timeout, conflicting fields, unavailable evidence, attempted instruction injection |
| Session integration | Open/closed market, holidays, cutoff, restart, disconnect, loss limit, pending exits, end-of-day reports |
| API/browser tests | Auth, allowlist, protected routes, settings conflicts, pause race, dashboard/journal consistency |
| Manual device check | Android installation, launch, responsive controls, stale/offline indication and safe caching |

## Golden fixture scenarios

1. Valid call entry → target exit → ledger and report reconcile after costs.
2. Valid put entry → gapped stop exit → actual simulated loss may exceed planned risk.
3. Small risk budget cannot afford one lot → no fill.
4. Quote older than 10 seconds, missing bid/ask, missing required metrics or crossed market → no new entry.
5. Duplicate/concurrent evaluation → one accepted entry maximum.
6. Pause between AI proposal and transaction commit → no entry; existing position monitoring continues.
7. LLM timeout or invalid output → auditable WAIT with no order.
8. Daily loss breach → entries disabled; flatten when valid quotes return.
9. Restart during open position → reconcile once, preserve daily baseline, remain paused for entries.
10. Market close with unavailable exit quotes → unresolved position and incident, no invented fill.
11. Unauthorized identity or expired token → no portfolio or mutation access.
12. Account and report arithmetic → every cash movement maps to a ledger entry.

## Evidence and commands

Choose concrete commands when scaffolding establishes package tooling. Expected categories: frontend lint/type/build, backend lint/type/unit tests, PostgreSQL integration tests, fixture session tests and browser tests. Do not claim they have run before code exists.

Keep synthetic fixtures in version control; use recorded provider data only when permitted and sanitized. Each fixture records origin, timestamp conventions, expected output and simulation settings. CI must run with provider/API credentials absent and outbound model/provider calls mocked.

Store milestone evidence as concise dated records linked to acceptance IDs. Validate live data separately from fixture correctness; neither establishes real-world profitability.
