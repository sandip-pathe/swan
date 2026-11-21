Latest slice: order and daily-report history paging. Read
__workspace/79-order-and-report-history.md. Related position orders page beyond
50; daily fills page beyond 20 while report totals remain full-day totals. Next:
close the remaining dense decision-order cap and review agent-history limits under
D16/D20. Tests/build checks were not run for this slice. Entries remain disabled.

Latest slice: richer age context for cited evidence. Read
__workspace/78-evidence-age-context.md. Evidence cards show quote and headline
age relative to saved output time, plus quote receipt and headline retrieval lag.
Zero delay is shown as a recorded value, not proof of actual feed delay. Next:
bounded order/report history as one batch; source suitability, provider guarantees
and actual-market acceptance remain in the ledger. Entries remain disabled.

Latest slice: paginated risk-decision history. Read
__workspace/77-risk-decision-history.md. Decision pages are account/strategy
scoped and retain rows on retry. Orders within each page still have a visible
100-row cap; report fill paging and richer source/age evidence remain D16/D20.
Next: complete agent evidence and bounded order/report history as one batch.
No broker/live/manual acceptance; entries remain disabled.

Latest slice: paginated model-request history and grouped finish path. Read
`__workspace/76-model-history-and-finish-batches.md`. Models now page newest first
with owner/run/kind cursors and independent retry/dedup/stale-close handling.
Response-metadata overflow has a separate warning. Next batch: remaining owned
history/evidence gaps (D16), using larger related reviewable slices. Preserve the
ledger, skipped live/manual acceptance and disabled entry gates.

Latest slice: indexed evaluation-history queries. Read
`__workspace/75-history-query-indexes.md`. Evaluation links and nested model-request
links now have account/kind/link/time/UUID indexes. Disposable 30,000-row plan
checks cover first/older pages and migration reversal. Next slice: model-version
history pagination (D16/D17). Integrated recovery/load acceptance remains D20;
broker/live/manual acceptance remains skipped and entries remain disabled.

Latest slice: paginated evaluation outputs and stage checks. Read
`__workspace/74-paginated-evaluation-history.md`. Both lists load newest first,
with independent owned cursors, append/dedup/retry and stale-close suppression.
Next slice: history query indexes and bounded load verification (D20). Remaining
version/risk/report pagination and billing gaps stay in DEFERRED-WORK.md.
Broker/live/manual acceptance remains skipped; entries remain disabled.

Latest slice: daily report and deferred-work ledger. Read
`__workspace/65-daily-report-and-deferred-ledger.md` first, then
`DEFERRED-WORK.md`. Maintain stable ledger IDs for every skipped/held item.
Continue M7 spending/model/version visibility (D17); do not restart M3 manual
acceptance or broker login. M7 is not complete.

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

Contract search is implemented at **Markets ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ Search**, using a separately cached
supported instrument catalog and direct chart selection. See
`__workspace/45-contract-search.md`. An account-owned 50-contract watchlist is
implemented with Search stars, cached quotes and chart links; read
`__workspace/46-saved-watchlist.md`. Paired calls/puts, expiry/strike pagination
and a chart-adjacent Details view are implemented; read
`__workspace/47-instrument-details-and-paired-chain.md`, then
`__workspace/48-selected-prices-and-display-subscriptions.md`. Exact selected
quote refresh and expiring chart/watchlist feed interest are implemented. The user renewed broker login on 20 November and confirmed price refresh works.
Actual open-market stream/reconnect verification remains pending.

Read `__workspace/49-chart-studies-and-preferences.md` for configurable EMA/SMA
and device-local chart preferences. The last full backend suite passed 343 tests;
thirteen frontend calculation/preference/annotation tests pass. RSI 14 is implemented in a
separate synchronized pane; read `__workspace/50-rsi-chart-pane.md`. Ruff, mypy, frontend type checking and production build
passed. No real broker orders were placed. The original account has no paper
orders/fills, no qualification and no arm. Its worker runs in observation mode.
Fee/rounding evidence, BFO IPFT and depth quantity-unit verification remain open.
The option chain now defaults to newest quote pairs first, with strike ordering
available. Read `__workspace/51-quote-order-and-finish-path.md` for the fix and
remaining delivery priorities.
M3 manual/live acceptance was explicitly deferred at the user's request; continue
implementation without marking that evidence complete. The contract Depth tab is
implemented; read `__workspace/52-mobile-market-depth.md`.
Underlying reference/ATM context is implemented; read
`__workspace/53-underlying-reference-and-atm.md`. It populates from existing
chain refresh/worker reference reads; no fresh live evidence is claimed.
The manual BUY LIMIT preview is implemented in the contract Order tab; read
`__workspace/54-manual-paper-order-preview.md`. It is read-only and cannot place
orders or issue approvals. User-owned, idempotent saved paper plans are implemented; read
`__workspace/55-durable-manual-paper-plans.md`. Actual manual order admission
and fill/protection integration now exist as an internal, bounded HUMAN validation
path; read `__workspace/57-manual-execution-lifecycle.md`. The authenticated
submission API and mobile session/review/place flow are implemented; read
`__workspace/58-mobile-manual-placement.md`. Placement remains gated by a bounded
HUMAN session and fresh deterministic checks. This is not unrestricted manual
trading or completion of M6. Read `__workspace/56-usable-depth-in-manual-preview.md` for shared
depth-capacity checks used by both AI sizing and manual previews. A preview still
does not create an approval or authorize an order.
Owned entry cancellation and persistent position exit controls are implemented;
read `__workspace/59-owned-paper-cancel-and-exit.md`. They preserve fill races,
pause new entries on exit and use the existing watchdog for actual exit fills.
Guarded amendments for wholly unfilled manual entries are implemented; read
`__workspace/60-manual-order-amendments.md`. Quantity and expiry cannot increase.
Per-order lifecycle, amendment, fill and fee history is implemented; read
`__workspace/61-order-lifecycle-history.md`. Reconciled portfolio value and P&L
with explicit valuation freshness are implemented; read
`__workspace/62-reconciled-portfolio-value-and-pnl.md`. Owned fill and current
position/protection overlays on the contract chart are implemented; read
`__workspace/63-owned-chart-trade-overlays.md`. The first M7 activity slice is
implemented; read `__workspace/64-recorded-agent-activity.md`. Model stages, WAIT,
review rejection, evaluation failures and deterministic risk/order outcomes are
kept distinct. Next is a daily paper session report from recorded evidence.
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
Ask the next coding agent to read the latest checkpoint and deferred-work ledger,
then continue the next implementation slice above. M3 manual acceptance stays deferred.
Keep paper entries disabled until genuine connected qualification and explicit
arming have passed. Chart history must never substitute for executable depth.
