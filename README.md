# SWAN Trade

History now includes a date-selectable IST daily report of recorded fills, net
realized P&L, fees, cash movement and decision stages. Today is provisional; cash
movement is separate from profit and no historical marked equity is inferred.

Account activity includes today's analysis allowance: conservative reservations,
remaining allowance, recorded token-usage coverage and historical reservation model
names. Missing usage stays unknown. This view does not estimate monetary billing.

Implementation continuity: [RESUME.md](./RESUME.md). All skipped, held and remaining
accepted work is tracked in [DEFERRED-WORK.md](./DEFERRED-WORK.md), with reasons and
closure requirements for the final review.

Use **Markets → Search** to find listed NIFTY/SENSEX contracts by strike, expiry
and call/put, then open a chart. **Refresh contracts** updates the listing cache;
prices and candle history load separately.
Star a search result to save it under **Markets → Watchlist**. Saved contracts
belong to your account and join the worker feed when capacity is available.
Saving a contract does not enable trading. Open-contract and Watchlist **Refresh
price(s)** request those exact contracts, up to 50 per request; the shared refresh
cooldown is 30 seconds. Viewed contracts receive a 90-second display lease,
renewed only while the chart is visible. Open exposure and the worker universe
retain subscription priority. Old prices keep their exchange timestamps.
If refresh reports a broker login is required, run `market.cmd login` privately
and retry; a web sign-in does not renew the daily broker session.
The option chain pairs calls and puts by strike and saved expiry. Its default
**Latest quotes first** order puts the pair with the newest exchange timestamp at
the top; choose **Strike: low to high** for strike order. Chain and contract views
show the saved underlying index reference in points, its change from previous
close and the nearest listed strike for the selected expiry. References populate
on chain price refresh or the worker's existing index read; ordinary page polling
does not fetch index prices. Prior-session references do not produce ATM markers. Open a contract
and choose **Depth** for up to five saved bid/ask price levels, or **Details**
for quote statistics, session OHLC and lot/tick information. Depth quantities are
shown only when the saved quote carries verified units and their source; otherwise
prices remain visible and quantities are unavailable.

Open **Markets → Chart** on an option contract to view mobile-first 1m/5m/15m
candle or line charts. Expand **Moving average** to choose EMA or SMA with a
9, 20, 50, 100 or 200-candle period. Timeframe, chart style and moving-average
choices are remembered on this device. Toggle **RSI 14** for a separate,
synchronized pane with 30/70 reference levels; its visibility is also remembered. Use **Get candles** to retrieve broker history for the selected
session. Chart polling reads saved data; missing minutes remain gaps and old
prices keep their timestamps. See [chart behavior and verification](./__workspace/43-live-candles-and-mobile-chart.md).

Open a contract's **Order** tab to preview a manual intraday BUY LIMIT plan.
Choose lots and limit/stop/target prices, then **Preview costs & risk**. Premium,
gross scenarios, fee allowances and account checks are computed by the server.
Usable depth at your limit accounts for reviewed participation limits, modeled
slippage and prior paper fills. Planning checks flag insufficient depth and
quantity limits. Missing reviewed inputs remain unavailable. This preview places no order and
reserves no funds. **Save paper plan** retains your inputs and a newly calculated
preview in your account. Expand **Saved paper plans** to load inputs or archive
a plan. Loading saved inputs requires a new preview; saved plans are not orders.

During a verified open session, **Manual paper trading** supports an explicit
five-minute session with one entry of one lot. Prepare the trading monitor in
**Account → Paper controls** first, then **Start manual session** in the ticket.
Preview and save a fresh plan, select **Review paper order**, then **Place paper
order**. The server repeats the checks before acceptance. Track fills and
protection in **Orders**. A session stop disables entries and drains exposure;
it does not promise an immediate fill. Closed-market planning remains available.
If a response is unconfirmed, **Retry same order request** retains the original
identity. Pending request IDs survive ticket reloads in account-scoped session
storage when the browser permits it; no credentials are stored there.


Resuming on another laptop: start with [RESUME.md](./RESUME.md), which records
the current milestone, setup requirements and private data that GitHub excludes.

Autonomous intraday options paper trading. Firebase login, the trading foundation, market worker, agent pipeline, authenticated API and dashboard are implemented. Configuration review, provider checks and actual-market execution validation gate autonomous activation. The app has no demonstration quotes, seeded trades or synthetic market recommendations.

The **Paper validation** tab now supports explicit sessions limited to one contract,
one entry attempt, one actual lot and a 1–15 minute window. Complete setup first;
then use `local.cmd worker-stop` and `market.cmd worker --local-owner --validation-only`
to prepare the worker while keeping web/API running. The tab starts the entry
window separately. Stop continues exit management until the account reconciles.
Session records do not enable autonomy. See the [operator flow and evidence](./__workspace/36-controlled-paper-validation.md).

Use **Paper controls** to prepare a local worker, inspect the server-derived
qualification matrix, review qualifying evidence and explicitly arm scoped paper
entries. Preparing any worker leaves entries paused. Restart, pause, invalidated
evidence or expired permission disarms entries; protective exits remain independent.
The local account is still unqualified and observation-only. See [M2 controls and
evidence boundaries](./__workspace/40-m2-qualification-worker-controls.md).

Use **Markets → Refresh prices** to retrieve last available NIFTY or SENSEX
option quotes, including after market hours. This deliberate action selects the
nearest listed expiry and up to five strikes; ordinary polling does not call the
broker. Quotes retain their exchange timestamps and are not relabeled as live.
See [after-hours data delivery](./__workspace/42-after-hours-market-data.md).

## Run locally on Windows

From `C:\x`:

```powershell
.\local.cmd start
```

Open `http://localhost:3000`. The launcher starts the local database, API, frontend and an observation-only worker in hidden background processes, with logs in `.local\run`. The worker requires an enrolled local owner; after first sign-in, run the launcher again if necessary. It keeps entries and agent generation disabled while monitoring existing exposure. Use `.\local.cmd status` to see managed processes and `.\local.cmd stop` to stop them. PostgreSQL stays running until `.\database.cmd stop`. The API/database health endpoint is `http://127.0.0.1:8000/health`; it does not report provider or trading readiness.

To run the services in separate terminals instead:

```powershell
.\database.cmd start
.\api.cmd
.\dev.cmd
```

Run the API and frontend commands in separate terminals. Open `http://localhost:3000`. They run until Ctrl+C. PostgreSQL listens only on `127.0.0.1:54329`; it is a manually controlled development instance, not a Windows startup service. Stop it with `.\database.cmd stop` and check it with `.\database.cmd status`.

The command wrappers permit execution of these project-owned PowerShell scripts in their own process; they do not change machine or user execution policy. To use local tools interactively, open a process-scoped shell and activate:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass
. .\scripts\activate.ps1
```

## Verify

Inside the activated shell:

```powershell
python scripts/verify_environment.py
ruff check scripts/verify_environment.py
uv sync --locked
cd apps/web
npm.cmd ci
npm.cmd run typecheck
npm.cmd run build
npm.cmd audit --omit=dev
```

`uv.lock` and `apps/web/package-lock.json` lock dependency versions. PostgreSQL requires the installed Microsoft Visual C++ runtime. The Python environment uses Psycopg's supported pure-Python implementation with the local PostgreSQL client library, because Windows application control rejected its bundled native extension. Activation configures this automatically.

## Configuration

Angel One setup and private login: [market adapter](services/market/README.md). Account worker commands: [runtime](services/worker/README.md). `market.cmd status` shows missing configuration without exposing credential values. Read-only broker connectivity was verified during setup; session renewal and fresh diagnostic evidence are still required as they expire. Connectivity does not qualify paper execution.

Apply the trading schema from the activated root shell using `python -m alembic upgrade head`. This creates empty tables only. See the [trading foundation](services/README.md) for module contracts and integration boundaries.

- `apps/web/.env.local`: Firebase public browser configuration extracted from the supplied `firebase.config`.
- Root `.env`: generated local database URL; do not print or commit it.
- `.tools/`: workspace-local Node, uv and PostgreSQL binaries; ignored.
- `.venv/`: locked Python development dependencies; ignored.
- `.local/postgres/`: development data/logs; ignored. Do not delete it to reset an account without an explicit decision.

Google sign-in and authorized development domains must be enabled in Firebase Console. Use localhost for the current local launch. The backend verifies Firebase tokens using Google's public certificates without an Admin key. Explicitly enabled local first-owner enrollment links the first verified user to a paused paper wallet automatically. See [Firebase public-key authentication](__workspace/31-firebase-public-key-auth.md), [API setup](services/api/README.md) and [agents](services/agents/README.md).

Current local setup: web/API/database are available, with [automatic local owner enrollment](./__workspace/31-firebase-public-key-auth.md) after genuine sign-in. The earlier [startup findings](./__workspace/30-local-startup.md) record the superseded Admin/mapping blocker. Autonomous operation still requires a renewed Angel One session, reviewed calendar/execution/fee/risk inputs, permitted news and actual-market validation. The managed worker observes only; it does not arm autonomous entries.

The dashboard's **System setup** page and `market.cmd status --account UUID` use the
same local readiness evaluator. Normal polling never calls providers. Explicit connection
tests record timestamped account-scoped results, which expire after 15 minutes and are
invalidated by relevant configuration changes. Tests cover broker profile, metadata,
stream transport, OpenAI access, structured output and permitted news retrieval. The
structured-output check makes one bounded model request charged against the account's
token budget; other diagnostics do not generate model output. No check places broker orders.

Use **Risk settings** to review the full policy. **System setup** supports validated,
revision-checked imports of execution, calendar and news JSON and a form for agent limits.
Imports require paused entries and no active orders/positions. Calendar JSON supports
explicit `closed_days` records; an unknown date is never inferred to be a holiday.
Agent settings are stored in non-secret `config/agents.json`; credentials stay in `.env`.
Restart a worker after changing its operating configuration. The current configured
model is `gpt-6.1-sol` with an initial 250,000-token daily cap; this is not a currency cap.

Paper execution remains gated pending connected validation; running the observation
worker or requesting resume cannot bypass it. The cash metric uses available funds
after reservations and restricted proceeds. See [milestone evidence](__workspace/33-readiness-milestone-implementation.md).

Firebase's umbrella dependency includes an unused Firestore dependency that pinned a vulnerable gRPC version. The frontend overrides `@grpc/grpc-js` to patched `1.14.7`; production build, type checks and audit must remain green. Firestore is not used; validate its compatibility separately before introducing it.

See [workspace index](__workspace/README.md), [implementation roadmap](__workspace/14-implementation-roadmap.md), and [environment setup evidence](__workspace/16-environment-setup.md).

Orders now supports confirmed cancellation of remaining paper entry units and
persistent exit requests for owned durable positions. Exit requests pause new
entries; fills still require monitoring and fresh market depth. See
[owned cancellation and exit](__workspace/59-owned-paper-cancel-and-exit.md).

Wholly unfilled manual paper entries also support reviewed changes to entry,
stop and target prices, with fresh risk checks and atomic reservation updates.
See [manual order amendments](__workspace/60-manual-order-amendments.md).

Open an order timeline to review recorded activity, amendments, actual fills and
itemized fees, or follow its linked position and entry/exit orders. See
[order lifecycle history](__workspace/61-order-lifecycle-history.md).

Home shows reconciled portfolio value and P&L, with explicit stale/unavailable
valuation states and separate recorded results. Estimates use executable bid
depth and exit fees. See [portfolio valuation and P&L](__workspace/62-reconciled-portfolio-value-and-pnl.md).

Contract charts show owned paper fills and current entry/stop/target levels, with
a show/hide control and recorded-fill details. Historical dates show fills only.
See [chart trade overlays](__workspace/63-owned-chart-trade-overlays.md).

Account activity separates recorded model analysis/proposals/review, evaluation
outcomes and deterministic risk checks, with explanations and actual order links.
See [recorded agent activity](__workspace/64-recorded-agent-activity.md).
