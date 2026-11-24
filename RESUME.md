# SWAN implementation checkpoint

## Oracle hosting preparation: 24 November 2026

The user now has Oracle access, but confirmed the VM is not created. Region shown
in the supplied console screenshot: India West (Mumbai). No cloud resource has
been created or public deployment performed in this preparation.

- Added hosting/oracle: non-root Python 3.13 image, PostgreSQL 17, single API,
  observation worker, Caddy HTTPS, persistent database/session volumes, private
  runtime templates, a backup command and deployment instructions. Existing
  application architecture and paper permission gates are preserved.
- Added allowlisted bundle/export scripts. Source archive is
  `.local/release/swan-oracle-source.tar.gz`; secrets, SSH keys and database data
  are excluded. A separate private PostgreSQL dump and manifest are under
  `.local/release/swan-database-20261124T054904Z.*`. It contains one account, nine
  orders and two closed positions. Export refused open exposure/active validation;
  the restore catalog was readable. Repeat after stopping local writers for final
  cutover; this snapshot alone does not prove a hosted restore.
- Checks passed: Compose configuration validation, Bash syntax, Ruff and mypy on
  packaging scripts, archive paths/hashes/secret-file exclusions/Python syntax/LF
  validation, frozen dependency dry-runs for Linux arm64 and amd64, one Alembic head.
- D26 remains open: no VM/IP/SSH/domain yet; Docker engine is unavailable locally,
  so actual image build, Linux/ARM dependency execution, database restore, TLS,
  Firebase/Vercel wiring, restart recovery and hosted market checks are unverified.
  No new full application test run was needed for deployment-only files.
- Next: create Always Free eligible Ubuntu VM (suggested A1 1 OCPU/6 GB if offered
  within account allowance), save SSH key privately, obtain public IP and API
  hostname. Follow hosting/oracle/README.md. Keep hosted entries paused until the
  existing bounded paper controls admit them. Calendar coverage still ends Nov 30.


## Agent, chat and watcher checkpoint: 23 November 2026, afternoon

### Verification for this checkpoint

427 backend tests passed (one existing Starlette/httpx deprecation warning),
15 frontend tests passed, Ruff passed across services/tests, targeted mypy passed
on 12 changed source modules, frontend typecheck/production build passed, and
`git diff --check` passed. API/web listeners and managed observation worker are
running. These checks do not close actual-market autonomous paper acceptance.

This checkpoint supersedes earlier statements that index acquisition is API-only,
chat is limited to canned actions, or ORB qualification accepts generic records only.

- A deterministic worker job checks NIFTY index evidence once per minute at second 5 IST during
  the verified ORB window. The API refresh cooldown is 55 seconds. Shared history acquisition, completed-bar assessment,
  watcher deduplication and durable assignments drive bounded model work. Generic
  snapshot reasoning no longer competes for automatic execution ownership.
- Free-text chat selects up to four named read-only tools for market, account,
  strategy and indicator records. Answers retain context/source IDs and timestamps;
  chat cannot create orders or change risk. The separate audited stop-new-entries
  control remains. An authenticated UI test at 15:15 IST returned actual NIFTY
  observations and correctly described the expired ORB trigger. Browser-local
  history is bounded and is not cross-device storage.
- Fixed daily AI allowance settlement: one valid provider usage receipt replaces
  its conservative reservation; absent, inconsistent or duplicate receipts retain
  the reservation. Actual usage above the estimate counts in full. No limit was
  raised. The failing UI request had 240,290 estimated tokens reserved versus
  58,323 settled tokens. A subsequent real UI answer passed after the fix.
- Session HLC3 VWAP and SMA-seeded DEMA 9 are available on charts and through
  read-only tools. Completed candles only; gaps/warmup and unavailable volume are
  explicit. Chart inspection showed DEMA and unavailable VWAP for incomplete
  history. These are context, not new strategy cards or automatic exit rules.
- ORB admission now applies the reviewed depth-unit mapping before executable
  quote checks. Qualification verifies the original ORB candidate, source bars and
  owned analyst/reviewer provider records; it does not fabricate generic reviews
  or grant qualification. Negative provenance tests remain fail-closed.
- Stream index references now publish to the database regularly; missing previous
  close in an LTP packet preserves the same-session previously observed close.
- Real option-history refresh returned provider rate limiting. Current VWAP parity
  and complete history acceptance remain open. No retry loop or fabricated volume.
- No new paper order was placed. Nine total orders, flat account, no active
  validation, qualification or arm; cash INR 99,766.55. Earlier round trips remain
  manual. Today?s ORB window ended at 11:00 IST. Next actual acceptance requires a
  fresh eligible setup and the existing bounded validation/qualification controls.
- Private runtime evidence: `.local/run/chat-watcher-checkpoint-2026-11-23.json`,
  `.local/run/indicator-history-check-2026-11-23.json` and the earlier paper ledger.


## Current audit checkpoint: 23 November 2026

Read [the execution and agent audit](./EXECUTION-AND-AGENT-AUDIT-2026-11-23.md)
and the latest entries in DEFERRED-WORK.md before continuing. They supersede
older descriptions of the 10% participation policy and forced valuation exits.

- Audited paper config `paper-displayed-depth-20261123-v2` now permits up to 100%
  of observed depth. Freshness, risk, slippage, durable consumption and permission
  gates remain. This models displayed capacity, not queue competition or guaranteed fills.
- Fixed the manual protection bug that confused an entry-only pause with session
  termination. Unavailable valuation and chat's stop-new-entries command preserve
  existing protection. Explicit validation stop and expiry still drain positions.
- Added execution-policy context, separate market/news citation lists, and clear
  planning versus execution freshness semantics to the generic agent pipeline.
  Citation validation was not weakened.
- A real-provider read-only rerun passed analysis and proposal checks and returned
  WAIT because snapshots lacked supported directional strategy evidence. Review
  was not invoked after WAIT. Order count remained nine. Owner account had zero
  durable ORB assignments and zero candidates. Both earlier round trips were manual.
- Confirmed integration gaps: ORB index-history acquisition is explicit API work,
  not scheduled worker production; generic proposals and ORB assessments need
  explicit priority and execution ownership. The generic path lacks recent index
  bars and deterministic strategy/tool results. D19/D25 retain these closure requirements.
- Final verification: 406 backend tests passed, plus focused Ruff and targeted mypy.
  Regression cases failed before the entry-pause fix and passed afterward. Actual
  holding acceptance after this fix is still open; no new trade was submitted.
- API and worker reloaded. Worker OBSERVATION, entries paused, account flat and
  reconciled, cash INR 99,766.55. No active order, qualification or arm was created.

Updated 23 November 2026 after actual-market manual paper tests.

Read [the latest acceptance checkpoint](./MARKET-ACCEPTANCE-2026-11-23.md),
[the delivery plan](./SWAN-DELIVERY-PLAN.md), and
[the deferred-work ledger](./DEFERRED-WORK.md).

Two NFO manual paper positions of 65 units each completed buy/sell round trips
against real provider depth. Both closed through protection after insufficient
liquidation-valuation depth paused entries. Account flat and reconciled. Cash and
equity INR 99,766.55, net P&L INR -233.45, estimated fees INR 168.45. All validations
stopped and orders terminal. Evidence is retained privately in
`.local/run/paper-round-trip-final-2026-11-23.json`.

The worker is back in OBSERVATION and entries are paused. API and web run locally. On 23 November at 18:52 IST the API, web and observation
worker were restarted; API health confirmed PostgreSQL connectivity. No production
host is configured. SmartAPI login sessions expire at midnight, so broker access
requires a fresh login on each trading day. No real-money broker order, autonomous qualification or arm was issued.
404 backend tests, focused Ruff and targeted mypy passed after runtime deadlock
and clock fixes. The existing frontend verification passed in the preceding slice.

Next acceptance work is the remaining qualification matrix and eligible
strategy-to-agent-to-paper execution, plus actual target/stop/max-hold behavior,
reconnect handling and authenticated dashboard/chat review. The captured ORB
assessment expired and must not be executed. Provider checks and broker login are
day-scoped or short-lived. Refresh them through existing controls as needed.
The user resumed provider and actual-market paper checks. Do not relax permission,
freshness, depth or risk gates. Exact broker fee parity remains unverified.
