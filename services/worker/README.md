# Market worker

18 November 2026: `local.cmd start` now manages a hidden **observation-only** worker for
the enrolled local owner. It reports `OBSERVATION_ONLY` and a genuine heartbeat while
keeping entries and agent generation disabled. It continues existing-position protection
when usable data is available; a heartbeat does not prove feed health or executable exits.
`local.cmd stop` stops this managed process. Check `.local/run/worker.stderr.log` if no
owner is enrolled or a different worker already holds the account lock.

The CLI equivalent is `market.cmd worker --local-owner --observe-only`. Provider tests
are explicit: `market.cmd diagnose broker --local-owner` (also `catalog`, `stream`, `ai`,
`ai_schema`, `news`). Tests for one account serialize; no provider tests run during normal
workspace polling. `ai_schema` makes one bounded real model call and uses the account budget.

The local owner's observation worker is connected to actual broker market data. Paper entry activation still requires the remaining configuration and connected execution qualification. There are no demo accounts or fake agent decisions.

## Operator commands

From the project root, prepare your risk settings in an ignored local file matching `shared/schemas/RiskConfig.json`. Costs and liquidity limits must be explicit; no fabricated fee schedule is provided. Then:

```powershell
.\market.cmd create-account --risk-file .local\risk-config.json
.\market.cmd worker --account YOUR_ACCOUNT_UUID
```

Use the actual printed account UUID. In another terminal:

```powershell
.\market.cmd status --account YOUR_ACCOUNT_UUID
.\market.cmd resume --account YOUR_ACCOUNT_UUID
.\market.cmd pause --account YOUR_ACCOUNT_UUID
```

General Resume now directs the owner to explicit **Paper controls** and cannot arm entries. A real approved strategy and current qualified paper permission are required before autonomous entries run. Pause clears both permission and strategy intent; monitoring continues while the worker runs. The implemented Firebase API authorizes the owner's web controls separately from local commands.

Bounded validation uses `local.cmd worker-stop` followed by `market.cmd worker --local-owner --validation-only`; the owner then explicitly starts a session in Paper validation. Worker preparation does not start entries. See [the lifecycle and operator flow](../../__workspace/36-controlled-paper-validation.md). Evaluations are bound to their original validation session, so a late result cannot arm a replacement session or observer.

## Runtime behavior

- A dedicated PostgreSQL advisory lock allows one worker per account. Connection loss stops it. Startup reconciles and pauses entries.
- Streaming updates coalesce in a bounded quote cache. Tick events or a one-second watchdog drive position monitoring independently of agents.
- A separate bounded task publishes latest observed quotes for future API consumers. Immutable evaluation/fill evidence is stored separately; raw ticks are not retained indefinitely.
- APScheduler refreshes subscriptions, available Greeks and three-minute evaluation slots. Unique database keys deduplicate slots; missed runs coalesce without inventing past evaluations.
- The agent pipeline is connected in validation/autonomous workers but remains idle without a valid explicit session/arm. Observation-only mode never invokes it. Missing dependencies produce explicit failures, not fabricated WAIT/trade decisions.
- A valid approved envelope can authorize a deterministic rule trigger from real quotes. Attempts are idempotent per envelope and risk is rechecked inside the paper transaction.
- Data gaps, changed subscriptions and provider failures pause entries and invalidate old envelopes. Exits resume with valid quotes; missing executable data leaves exits pending.
- Risk configuration supplies entry/flatten offsets and holding time. The actual entry session is persisted for recovery. If it is unavailable, the engine requests an unresolved-session exit using real quotes without inventing calendar times.
- A verified open session rolls a flat, reconciled account to its new daily baseline before entry-readiness and prior-day loss checks, including in observation mode. This leaves entries paused and clears prior strategy/resume intent. Unknown dates, pre-open times, unresolved orders/holdings and reconciliation failures do not reset the daily block. Repeated same-day cycles do not reset the baseline.

`RuntimeStore.approve_envelope` is the internal step-three handoff and requires persisted evidence and a current typed strategy. It does not grant broker execution or risk-setting permissions.

Native isolated-schema tests now cover durable admission/matching/protection/exit accounting, partial entries, pause, service reconstruction with duplicate observations, and safe daily rollover. These fixture results do not qualify live fees, depth units or activation. No replay product was added. Live execution coverage, remaining races and measured latency remain final-QA work. The watchdog frequency is an engineering target, not a guarantee of provider latency.
