# Resume SWAN on another laptop

## Development checkpoint

Read `__workspace/37-complete-system-and-broker-workspace-plan.md`, then
`__workspace/40-m2-qualification-worker-controls.md` and
`__workspace/41-m3-market-data-foundation.md`.

M1 audit/checklist and M2 qualification/explicit paper arming are implemented.
M3 quote price retention and bounded historical candle refresh/cache APIs are
implemented. On 19 November, renewed login verified NFO/BFO last-quote reads and
one NFO request returned 376 actual one-minute candles, and one BFO request
returned 16. See
`__workspace/42-after-hours-market-data.md` for the explicit after-hours refresh
API and connected evidence. Observed one-minute aggregation, persisted segments,
bounded reconnect/restart history recovery and a mobile-first contract chart are
implemented; read `__workspace/43-live-candles-and-mobile-chart.md` next. Remaining
M3 work includes real open-market/reconnect verification and broader candle
coverage. The chart now supports derived 1m/5m/15m bars, candle/line views and
EMA 20; see `__workspace/44-chart-timeframes-and-ema.md`. Other studies and
order-ticket integration still follow. Do not treat M3 as complete.

Contract search is implemented at **Markets → Search**, using a separately cached
supported instrument catalog and direct chart selection. See
`__workspace/45-contract-search.md`. An account-owned 50-contract watchlist is
implemented with Search stars, cached quotes and chart links; read
`__workspace/46-saved-watchlist.md`. Richer instrument/chain details remain next.

The last full backend suite passed 161 tests; five frontend chart-calculation
tests also pass. Ruff, mypy, frontend type checking and production build
passed. No real broker orders were placed. The original account has no paper
orders/fills, no qualification and no arm. Its worker runs in observation mode.
Fee/rounding evidence, BFO IPFT and depth quantity-unit verification remain open.
Calendar coverage currently ends 30 November 2026; extend it from official
sources before testing later dates. Preserve all execution gates.

## What GitHub contains

Application source, non-secret reviewed configuration, migration history,
dependency lockfiles, tests and development plans. GitHub does not contain
credentials, Firebase local configuration, broker sessions, database/account
records, logs, installed tools or virtual environments. A clone alone does not
restore the existing local wallet, diagnostic history or credentials.

## Windows setup

```powershell
git clone https://github.com/sandip-pathe/swan.git
cd swan
```

The supplied launch scripts currently target Windows. Install Git, Python 3.13,
Node.js 24, uv and the Microsoft Visual C++ runtime. Supply PostgreSQL 17 Windows
runtime files under `.tools/pgsql/bin` (including `pg_ctl.exe`, `initdb.exe`,
`psql.exe`, `createdb.exe`, `postgres.exe` and their required libraries/share
files). Use official distributions. Installed Python/Node/uv must be on PATH;
`scripts/activate.ps1` also supports workspace-local tool locations. See
`__workspace/16-environment-setup.md` for the original environment and its Windows
application-control constraints; its old Git-installation status is historical.

For a **fresh empty development database**, run `database.cmd start` before
creating root `.env`. It generates a random database password and writes the
local connection URL. Do not pre-create `.env` from the example: the database
initializer deliberately refuses that ambiguous case. Then append the required
settings from `.env.example`, preserving the generated `DATABASE_URL`.

In an activated PowerShell session:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass
. ./scripts/activate.ps1
uv sync --locked
python -m alembic upgrade head
cd apps/web
npm.cmd ci
Copy-Item .env.example .env.local
```

Fill `apps/web/.env.local` privately using your existing Firebase web app
configuration. Set the matching server `FIREBASE_PROJECT_ID` and provider keys
in root `.env`; use the examples as a field inventory. Enable
`SWAN_LOCAL_OWNER_BOOTSTRAP=true` only for this single-owner local development
setup. Sign in as the intended owner. A fresh database starts a new account;
it does not inherit old qualifications. Launch from the repository root with
`local.cmd start`, open `http://localhost:3000`, then log into Angel One privately
with `market.cmd login`. Update backend network identity/provider registration
for the new machine as required. Rerun deliberate connection diagnostics;
saved diagnostic results and broker sessions are not portable readiness proof.

## If you need the existing account/database

Transfer root `.env` and frontend `.env.local` through an encrypted private
channel, never a Git commit or chat. Use a consistent PostgreSQL logical backup
and restore with matching versions; do not copy a running database's data
directory. Stop the old worker before moving operational responsibility. Do not
run both laptops as workers against one account. Broker sessions should be
renewed privately on the destination; never reactivate entries from old process
state. Backups contain account/provider evidence and must stay private.

The original laptop's `.local`, `.env` and installed tools remain in place;
publishing this repository does not delete them or migrate the database.

## Verify and continue

From an activated root shell with the disposable-test database available:

```powershell
python -m ruff check services tests migrations
python -m mypy services
python -m pytest -q
```

Run `npm.cmd run typecheck` and `npm.cmd run build` in `apps/web`.
Ask the next coding agent to read this file and milestone 41, then continue M3.
Keep paper entries disabled until genuine connected qualification and explicit
arming have passed. Chart history must never substitute for executable depth.
