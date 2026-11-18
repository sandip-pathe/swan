# Release quality and acceptance additions

The existing AC01–AC12 remain required. Add these checks for the agreed product scope:

| ID | Requirement | Required evidence |
| --- | --- | --- |
| AC13 | Only actual listed expiries 0–7 calendar days away qualify, including same-day expiry | Timezone/date-boundary, expired instrument and metadata-refresh tests |
| AC14 | No intentional overnight holding; special-session cutoffs are session-relative | Cutoff/flatten replay, unavailable exit incident, resume inhibition |
| AC15 | Streaming entry/exit checks do not wait for the model | Simulated tick/clock tests; measured quote-to-rule and rule-to-ledger latency |
| AC16 | No entry outside valid strategy envelope | Expiration, invalidation, contradictory rules and in-flight pause tests |
| AC17 | News is attributed, deduplicated and assessed for freshness | Provider contract tests, stale/missing required context rejection |
| AC18 | Firebase identity restriction applies to every protected endpoint | Emulator/verification tests, wrong project, expired/revoked token, wrong UID |
| AC19 | Accounting survives process failure and restore | Transaction fault injection, reconstruction, backup restore evidence |
| AC20 | Interface is usable on mobile and keyboard | Browser checks and manual accessibility/device review |
| AC21 | Agent/data dependency spending and quotas are bounded | Mocked quota exhaustion, timeout, retry/backoff and budget-limit checks |

## Performance and resilience

Benchmark with representative active subscriptions and instrument counts rather than an invented server size. Record hardware, fixture rate, p50/p95 processing latency, queue lag, database growth, quote drops and recovery time. The initial one-second monitor watchdog is an engineering target to verify, not a promise of provider latency. Block entries when lag exceeds permitted freshness.

Use bounded queues and retries, jittered backoff, per-provider rate limiting and circuit breakers. Streaming gaps invalidate entry readiness. Persist enough permitted market evidence to reconstruct each fill; retention and licensing govern raw tick storage. Reports must disclose quote gaps and simulation assumptions.

## Release checklist

- [ ] All AC01–AC21 have passing evidence or an explicitly unresolved release blocker.
- [ ] Exact strategy, risk, cost and data-quality versions are recorded.
- [ ] Secrets and dependency scans pass; no brokerage execution calls exist.
- [ ] Migration, rollback/forward recovery and database restore have been rehearsed.
- [ ] Android install, auth, pause and disconnected-state checks pass.
- [ ] Dashboard, journal, reports and ledger reconcile.
- [ ] Live read-only data checks establish both index coverage and fresh executable quotes.
- [ ] News coverage and failure policy are documented and tested.
- [ ] Session close, forced exits, worker death and pending-exit incidents are tested.
- [ ] Operator documentation identifies alerts, recovery steps and unresolved limitations.
