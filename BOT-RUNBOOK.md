# Isolated market bot

Workspace: `D:\s\swan-bot`. Git branch: `bot/read-only`. Original checkpoint:
`21c2c21` on `main`; original workspace and trading ledger are retained.

## What runs

- Authenticated advisory API behind existing Caddy and one singleton event worker.
  Legacy API/worker/PostgreSQL stay stopped; no order routers or execution tools.
- Two index references and at most eight selected SENSEX option contracts. History
  bootstraps once/session; targeted ten-minute repair is globally limited to one
  per minute with per-window backoff. Opening 15/recent 20 bars are independent.
- Versioned experimental range-retest/failed-break intraday ideas and separate
  five-completed-session weekly structure. Whole-lot quote/depth/noise/cost and
  user-budget checks apply. Unknown depth units prevent eligibility.
- Triggered compact AI research, shared one-call lease, persistent daily 30,000-token
  reservation ceiling or configured lower allowance. No tick/minute model polling.
- Official RSS excerpts every five minutes and verified daily history for weekly
  research; missing sources remain explicitly unavailable, not invented news.
- SQLite WAL, atomic revisions/feed/outbox, source snapshots, twenty revisions/idea,
  seven-day/1,000 unstarred buffer, 200 stars/account, 2,000 hypothetical evaluations.
- Chat and Insights only; SSE/poll fallback, private local archive, optional browser
  push with 60-second TTL. Generic lock-screen updates require fresh app validation.
- Verified calendar through 31 December 2026; renew before 2027.

## Backups and recovery

Worker creates a consistent local SQLite backup daily. Pre-engine snapshot:
`/app/bot-data/bot-before-decision-engine.sqlite3`. Off-host command:

```powershell
.venv/Scripts/python.exe scripts/backup_bot.py --key 'PATH/TO/EXISTING-SSH.key'
```

SSH fetches a consistent SQLite copy, encrypts with AES-GCM and an HKDF key derived
from the existing SSH private key plus random salt, decrypts a temporary copy and
checks SQLite integrity before retaining seven `.local/backups/*.enc` files.
Keep that SSH key: losing it loses these backups. No plaintext copy is retained.
Format: `SWANBACKUP1`, 32-byte salt, 12-byte nonce, AES-GCM ciphertext; HKDF-SHA256
info `swan-bot-offhost-backup-v1`, header as AAD. Windows task `SWAN Bot Encrypted
Backup` runs daily 00:20 local, StartWhenAvailable. This machine must be available.
First decrypt/integrity exercise passed; future scheduled operation and a complete
replacement-host application restore still require acceptance.

## Acceptance

Hosted health=200, private unauthenticated insights=401, trading arm=404, worker
heartbeat and broker-login timer active. At rollout markets were closed, RSS had
no usable current entries, and weekly daily history was incomplete. No eligible
idea, useful model answer, live latency or trading edge was claimed. See D34 for
remaining signed-in/offline/push, provider, model and prospective outcome work.

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

For a future cutover, recheck flat/inactive legacy paper state, take a readable
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
directory `apps/web`. Deploy `bot/read-only` as a preview first; the public API cutover is now complete, so this frontend deployment is required. A branch push
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

## Current public deployment and retention: 25 November

Caddy now serves `bot-api:8000`; external health identifies `swan-bot`. Original
`swan-api-1`, `swan-worker-1`, `swan-db-1` are stopped. Only bot API, bot worker and
proxy remain continuously running. Automatic login timer remains active and its
one-shot `run --rm --no-deps broker-login` does not require PostgreSQL to run.
Do not run the legacy stack's default `up` command: it would restart retired services.
No images, volumes, secrets or ledger data were deleted. One idle sample was
66 MiB API + 64 MiB worker + 10 MiB proxy; this is not a peak load guarantee.

Ledger backup: `/opt/swan/backups/bot-cutover-20261125T154552Z/legacy-ledger.dump`,
root-only, 4,657,144 bytes. `pg_restore --list` succeeded; full restore was not run.
`Caddyfile.before-bot` in that directory is the original upstream configuration.
To reverse, first stop bot collection, start original db/API (and observation worker
only if intended) using original Compose, restore the saved Caddyfile, recreate
Caddy with `--no-deps --force-recreate caddy` so bind mount inode changes take effect,
and verify service identity before restoring the original frontend. A simple reload
was insufficient on this host because the container had an older bind-mounted inode.
`hosting/oracle/Caddyfile.bot` is the versioned bot upstream template; install it at
`/opt/swan/hosting/oracle/Caddyfile` before recreating the existing proxy if needed.

The frontend restores account-scoped IndexedDB first and syncs deltas on either
screen every 15 seconds while visible/online. Server cursor and new local entries
commit atomically. Stars are account-scoped, retained on server until unstarred and
eligible for cleanup; limit 200/account. Unstarred evidence/insights expire after
seven days or 1,000 records. Worker prunes even outside sessions. Star retention
requires connectivity and a successful server response. Old expired local entries
cannot be uploaded back as trusted server evidence. No private API SW cache exists.
Source evidence is fetched on demand, not persisted in the device archive yet.

PWA root/static shell caching enables revisiting previously loaded screens offline;
fresh sign-in still requires network. Local history is removed on sign-out or site
data clearing and may be evicted by the browser. Suspended/closed PWAs cannot be
promised live delivery. Sync beyond server retention can miss unstarred insights.
No new behavioral test suite was run for this change; build/typecheck and Python
lint/mypy passed. D34 tracks persistence, offline and multi-device acceptance,
backup/recovery and outstanding SENSEX/swing/data-source work. Prior passing test
counts above refer to the earlier implementation and are not current acceptance.

## SENSEX and answer routing update: 25 November

Collector now queries SENSEX/BSE against verified BFO sessions and NIFTY/NSE against
NFO sessions; each is independently bounded to cash hours. One gap-repair call per
pass is allowed, never an unbounded retry loop. Whole-pass deadline remains 55s;
quotes are bounded to 12s and each history read to 10s. SENSEX is the default chat
analysis; NIFTY is selected explicitly. Cached same-context interpretations do not
reserve/spend another call. Ordinary observation questions use deterministic facts
and interpretation; explanation/research-style questions may use the existing
budgeted model only with current evidence. No background model loop exists.

Actual provider SENSEX history access succeeds but returns 371/375 minutes today;
a narrow retry retains the same four missing minutes (15:16-15:19 IST). NIFTY
returns 370/375. Both remain insufficient, and the bot withholds current scans.
This is source-access evidence, not source completeness or open-session acceptance.

Explicit calendar coverage is now through 31 December 2026 for both venues; source
links/broker-mirror qualification are recorded in config. Christmas is closed.
Both /opt/swan-bot/config and the original auto-login /opt/swan/config use the new
calendar. Old November-boundary statements above are historical. Renew for 2027
from official evidence before year end; do not infer weekday sessions.
