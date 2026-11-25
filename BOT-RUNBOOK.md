# Isolated market bot

Workspace: `D:\s\swan-bot`. Git branch: `bot/read-only`. Original checkpoint:
`21c2c21` on `main`; original workspace and trading ledger are retained.

## What runs

- `services.bot.app:app`: authenticated saved insights, evidence drill-down and chat.
  Registers no legacy API routes and never opens the PostgreSQL trading ledger.
- `services.bot.worker`: one Linux process, shared-volume singleton lock, at most
  one collection pass per minute with failure backoff. No execution watchdog,
  strategy qualification, order handling or continuous model agents.
- `apps/web`: same Firebase setup and chat component; Chat and Insights are the only
  product destinations. Bot chat uses a separate owner namespace on the device.
- Independent SQLite WAL database: no trading migrations or copied trading records.
  Latest market context and up to 300 insights with their source snapshots persist.
  Insight lists omit the full snapshot; authenticated drill-down loads it on demand.

Current implementation is a first slice: NIFTY opening fifteen-minute range and
twenty-close SMA conditions, plus supported NIFTY/SENSEX quote observations.
Incomplete, stale, future or gapped bars cannot yield a current scan. Individual
quote and candle reads fail independently and old observations retain source times.
Index collection stops at 15:30 IST within verified exchange-calendar coverage.
Unknown days sleep instead of assuming weekday sessions. Existing calendar coverage
must be renewed after 30 November 2026; no new dates were guessed.

Chat has local concept definitions, deterministic numerical facts and optional
bounded OpenAI interpretation when current candle evidence exists. Model output is
validated for schema and allowed evidence IDs; digit-bearing model narrative is
rejected so displayed numerical facts come from code. This is not a semantic proof
of all prose claims or written-out quantities.
Qualitative correctness still needs actual output review; citations do not prove it.
The model is taken from the existing `config/agents.json`, with a global conservative
30,000-token daily reservation ceiling or the existing allowance, whichever is lower.
Reservations survive restarts; failed requests are not refunded or automatically
retried. One chat model call may run at a time. No proactive model explanation loop.

## Local use

Existing private configuration was reused in ignored `.env` and
`apps/web/.env.local`. No new credentials were created. The frontend API address is
explicitly `http://localhost:8002`, so it does not send chat to the original API.

```powershell
cd D:\s\swan-bot
$env:SWAN_WEB_ORIGINS='["http://localhost:3200","http://127.0.0.1:3200"]'
D:/s/swan/.venv/Scripts/python.exe -m uvicorn services.bot.app:app --host 127.0.0.1 --port 8002
# Another terminal:
cd D:\s\swan-bot\apps\web
npm run dev -- --port 3200
```

Use these bot commands rather than the inherited `local.cmd`, which belongs to the
archived trading runtime. The original source remains for reference and rollback;
it is not registered or started by the bot entry points.

## Oracle staging and cutover

Independent source directory `/opt/swan-bot` and Compose project `swan-bot`:

```bash
cd /opt/swan-bot
sudo docker compose --env-file /opt/swan-bot/.env -f hosting/oracle/compose.bot-isolated.yaml build bot-api
sudo docker compose --env-file /opt/swan-bot/.env -f hosting/oracle/compose.bot-isolated.yaml up -d --no-build bot-api bot-worker
curl --fail http://127.0.0.1:8001/health
```

It reads the existing private runtime env at `/opt/swan/hosting/oracle/runtime.env`,
joins the existing `swan_default` proxy network and mounts the existing broker-session
volume for the collector only. Original systemd auto-login continues using its
existing source, credentials, service and timer. Bot state has its own volume.
The existing PostgreSQL database and volumes stay intact. No `down -v` or database
cleanup is part of this migration.

Before production switch, recheck flat/inactive legacy paper state, take a verified
ledger backup, ensure the Vercel frontend is ready, then switch the existing Caddy
upstream to `bot-api:8000`, validate/reload and verify external TLS/auth/read behavior.
The old observation worker was stopped after a flat/inactive preflight when read-only
collection resumed; stop the old API after public cutover to release memory/CPU. Preserve their images,
Compose source and Caddy config for rollback. Do not run two active collectors.

Provider collection defaults off in source. On 25 November the user explicitly
resumed read-only checks. `/opt/swan-bot/.env` now contains the nonsecret
`BOT_COLLECTION_ENABLED=true` setting (root-owned, mode 0600), and passed explicitly with `--env-file /opt/swan-bot/.env` on Compose commands.
Omitting that flag on this host reverted collection to the source default; the
worker was recreated with the explicit file and enablement rechecked. The old observation worker is stopped to avoid
duplicate collection. Observe read-only freshness/recovery during verified sessions. The worker
never reads PIN/TOTP credentials; the existing isolated login service retains them.

Rollback: restore Caddy's saved `api:8000` upstream, start original API/observation
worker using `/opt/swan/hosting/oracle/swan -f hosting/oracle/compose.micro.yaml up -d api worker`,
validate/reload Caddy, then stop the bot services. Keep collection stopped on one side.

## Vercel

Keep the existing project, Firebase public environment variables and
`NEXT_PUBLIC_API_BASE_URL` pointing at the existing HTTPS API hostname. Keep root
directory `apps/web`. Deploy `bot/read-only` as a preview first; production must be
paired with the bot API cutover because the insight route is new. A branch push
alone is not evidence of a successful Vercel deployment. No Vercel CLI session or
linked project was available at the start of this work. The user chose to deploy
Vercel themselves; the pushed branch is ready. The frontend checks backend identity
and refuses chat submissions against the old API until public cutover.

## Verification and remaining acceptance

- 9 isolated bot tests + 13 existing auto-login tests pass; no provider calls.
- Python Ruff and Linux-targeted mypy pass for bot code.
- Six reused index-history normalization tests pass alongside the bot/login tests
  (28 Python tests total).
- Frontend production build/typecheck and 15 inherited chart tests pass.
- Private browser fixture passes sign-in, Chat/Insights navigation, reused chat,
  empty/paused source state, mobile overflow and absence of legacy API calls.
- Local real bot health returns database connected. Broker/model freshness and
  usefulness have not been accepted by these tests.
- Oracle bot staging is healthy on loopback port 8001. Three warm unauthenticated
  health requests took 3-60 ms. No-token Insights is 401, legacy arm route is 404,
  collector is enabled and reports closed after hours; automatic-login timer is active.
  Cold startup was slow under host contention; public traffic has not switched.

The bot-only Dockerfile reuses the installed `swan-backend:local` environment and
adds a small code layer. A fresh full dependency-layer build was cancelled during
slow export on the Micro host. For portability, build the supplied base Dockerfile
on a new host first; this is reuse of the locked environment, not dependency removal.

Remaining: actual source/model review, authenticated hosted latency, provider
recovery, calendar renewal, source correction/supersession UX, opening/closing
briefings, alert noise measurement, broader research and supported options scope.
See D34 in DEFERRED-WORK.md. No news coverage, SENSEX candle scans or options scans
are claimed in the first slice. No predictive accuracy or profitability is claimed.

## Actual read-only checks: 25 November, approximately 21:04 IST

Existing saved broker session created today successfully served bounded quote and
NIFTY candle requests. NIFTY quote source time was 16:08:11 IST, SENSEX 15:32:29 IST;
these were hours old and are historical observations, not current market evidence.
The candle response had 370 of 375 expected cash-session minutes, missing
15:15-15:19 IST. Analyzer returned insufficient and withheld scans. No interpolation
or model explanation was used to bypass missing data. The closed worker sleeps
without polling the broker; next verified open is 26 November at 09:15 IST.
Investigate these provider omissions and verify open-session freshness/recovery
before source acceptance. This check did not exercise a real model response.
Legacy paper state was flat/inactive (all five preflight counts zero) before
stopping swan-worker-1. Public API, DB, proxy and login timer remain intact.
