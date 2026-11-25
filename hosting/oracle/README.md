# Oracle backend deployment

Frontend: Vercel. Backend: one Ubuntu 24.04 LTS VM, amd64 or arm64, with Docker
Engine and Compose v2. PostgreSQL 17, API, market worker and Caddy run together.
Use at least 2 GB RAM; 4 GB is a comfortable starting allocation, not a measured
requirement. A 1 GB E2 Micro experiment is now in progress; it is not yet accepted
for sustained operation. The optional `compose.micro.yaml` overlay reduces
PostgreSQL memory and parallelism. Use it with
`hosting/oracle/swan -f hosting/oracle/compose.micro.yaml ...` for every Compose
operation in that experiment. Add host swap for transient spikes and measure
available memory, swap activity, CPU delay and application response before deciding
whether PostgreSQL needs a second VM. Swap does not increase CPU capacity.
Select an **Always Free eligible** shape and storage in the console;
trial credit is not the same as Always Free eligibility. Mumbai is the selected
region in the supplied screenshot; a compute instance has not been verified.

## Optional unattended daily broker login

`broker-login` is an isolated one-shot service. Only this service mounts
`/opt/swan/.private-broker`; the API and market worker never mount the PIN/TOTP
seed. Its session tokens use the existing private shared session volume. Credentials
are entered with getpass, saved mode 0600 in a directory owned by UID 10001/mode
0700, and excluded from Git and source bundles. The TOTP setup secret is the
base32 seed from broker enrollment, not a current six-digit authenticator code.
PyOTP is pinned to 2.9.0 for compatibility with broker-issued legacy seeds.

After building the current image, prepare and configure once on the VM:

```bash
sudo install -d -m 700 -o 10001 -g 10001 /opt/swan/.private-broker
cd /opt/swan
sudo hosting/oracle/swan -f hosting/oracle/compose.micro.yaml run --rm --no-deps broker-login python -m services.market.autologin configure
```

Install the supplied service and timer to `/etc/systemd/system/`, then run
`sudo systemctl daemon-reload` and
`sudo systemctl enable --now swan-broker-login.timer`. The timer runs on boot
and daily at 08:55 Asia/Kolkata. Before reading credentials or contacting the
broker, it checks for a verified NFO or BFO session remaining that day, including
before the open. Holidays, unknown dates, invalid calendars and finished sessions
skip login with an explicit status. Boot/catch-up runs use the same check. Maintain
the explicit exchange-calendar coverage; unknown dates are never inferred open.
The service also skips if credentials have not been entered.
It reuses a verified current-day session, otherwise performs fresh login and checks
the profile/account match. Transient failures get at most three attempts, 35 seconds
apart; credential rejection stops immediately. No retry loop runs every second.
It has a separate process, 0.1-CPU cap, low CPU share and 192 MiB memory limit
(256 MiB including swap); no API or worker startup depends on it. Failed login
does not stop the app. Broker-backed features still require a valid session.

Run immediately with `sudo systemctl start swan-broker-login.service`. Inspect
`sudo journalctl -u swan-broker-login.service -n 20 --no-pager` and
`sudo systemctl list-timers swan-broker-login.timer`. The job writes a private
`status.json` alongside its credentials (timestamp/outcome/safe error code).
Same-day broker revocation or changed credentials may require a manual job run;
the timer is not a guarantee against broker outages. Login never arms paper/live
trading. To revoke unattended access, disable the timer and remove the credentials
privately; invalidate broker sessions too if the server may have been compromised.

## Prepare before market hours

1. Create the VM and save its SSH key privately. Assign a public IPv4 address.
   Allow SSH only from your administration IP. Allow inbound TCP 80/443 in Oracle
   networking and the VM firewall. Do not expose PostgreSQL or port 8000 publicly.
2. Install Docker Engine and its Compose plugin using Docker's Ubuntu packages.
   Configure Docker to start at boot. No Node.js is required on this VM.
3. Point an API hostname you control at the VM IPv4, for example api.example.com.
   Caddy obtains and renews HTTPS certificates. This package requires a hostname;
   it does not assume HTTPS is available for the bare VM IP.
4. Run `python scripts/build_hosting_bundle.py` on the development PC. Upload
   `.local/release/swan-oracle-source.tar.gz` to the VM over SSH/SCP. Extract to
   `/opt/swan`. This archive intentionally includes uncommitted implementation
   files and excludes .env, broker sessions, keys, database data and frontend.
5. On the VM:

```bash
cd /opt/swan
cp hosting/oracle/deploy.env.example hosting/oracle/deploy.env
cp hosting/oracle/runtime.env.example hosting/oracle/runtime.env
chmod 600 hosting/oracle/deploy.env hosting/oracle/runtime.env
chmod +x hosting/oracle/swan hosting/oracle/backup.sh
sudo chown -R 10001:10001 config
```

Edit the two env files privately. Use a random hex database password (e.g.
`openssl rand -hex 32`), the real hostname, exact Vercel origin, existing Firebase
project, and explicit Firebase user UID to existing paper account UUID bindings.
Use VM network values for Angel One headers, not the Windows PC values. Confirm
the API key's allowed outbound IP configuration. Local owner bootstrap is forced
off by Compose. Existing account UUIDs come from the local database, not new IDs.
Keep server secrets out of Vercel NEXT_PUBLIC variables.

## Migrate the existing account

Check the local account is flat and stop local services for the final cutover;
otherwise later local writes will not be present in the transferred snapshot.
Run `.venv/Scripts/python.exe scripts/export_hosting_database.py` on the PC.
It exports a PostgreSQL custom-format backup using private local configuration
and refuses an account with open exposure or active validation. Transfer it separately by SCP, never in the source
archive. Preserve a local backup before starting hosted services.

```bash
cd /opt/swan
hosting/oracle/swan config --quiet
hosting/oracle/swan build api
hosting/oracle/swan up -d db
# Restore only into a NEW empty database. Do not add --clean or overwrite a live ledger.
hosting/oracle/swan exec -T db pg_restore -U swan -d swan_trade --no-owner --no-acl --exit-on-error < /private/path/swan.dump
hosting/oracle/swan run --rm migrate
hosting/oracle/swan up -d api
curl --fail http://127.0.0.1:8000/health
```

Run migrations once before API/worker startup. For later releases, back up first,
stop API and worker while migrations run, then start the new image. Do not run
two deployments against the same account. Broker sessions reside in a private
Docker volume shared only by the API and worker; PostgreSQL uses a separate volume.
Configuration is bind-mounted and writable so existing setup controls can persist
changes. `docker compose down -v` deletes data: do not use it.

## Broker login and worker

Enter PIN/TOTP privately through the server terminal, not a chat or command argument:

```bash
hosting/oracle/swan run --rm --no-deps worker python -m services.market.cli login
hosting/oracle/swan run --rm --no-deps worker python -m services.market.cli check
hosting/oracle/swan up -d worker caddy
hosting/oracle/swan ps
```

The worker defaults to OBSERVATION. A running container does not arm paper entries.
Keep one API process (it owns the durable agent consumer) and one market worker.
Explicit bounded validation/qualification/arming remain existing application
controls. Do not edit the command to bypass them. Broker login is day-scoped;
renew through the same CLI when required. No PIN or TOTP seed is stored.

## Vercel

Use `apps/web` as the project root. Build with the checked-in package lock and
`npm run build`. Set `NEXT_PUBLIC_API_BASE_URL=https://api.example.com` and the
existing NEXT_PUBLIC_FIREBASE_* browser configuration. Add the Vercel domain to
Firebase Authentication authorized domains. Set the exact same origin in
SWAN_WEB_ORIGINS on the backend. Rebuild Vercel after changing public variables.
No backend key, database URL or broker session belongs in frontend variables.

Before market hours, confirm sign-in, saved orders/P&L, chat, API HTTPS and process
restart recovery. Only provider freshness/depth, current bars and the bounded
paper lifecycle require an open market. Market execution remains unaccepted until
actually exercised. Extended strategy/profitability evaluation is later work.
The current calendar ends 30 November 2026: extend from verified exchange sources
before operating beyond that date.

## Backups and operating commands

```bash
hosting/oracle/backup.sh
hosting/oracle/swan logs --tail 100 worker
hosting/oracle/swan stop worker
```

The backup command writes a private verified custom-format database dump under
.local/backups. Schedule it daily using the host scheduler and copy backups off
the VM. Back up config files separately; keep any broker-session backup encrypted
or renew login instead. Docker logs rotate for backend/database services. Database
and broker-session volumes survive image rebuilds and ordinary container restarts.

## Verification status

Compose configuration, Bash syntax, packaging-script lint/types, archive hashes
and secret-file exclusions passed. Frozen dependency dry-runs succeeded for Linux
arm64 and amd64; they do not prove the image installs or runs on either platform.
The custom PostgreSQL backup catalog was readable; no hosted restore was run.

Deployment source is prepared locally. Building/running containers on the Oracle
VM, ARM dependency installation, TLS issuance, hosted sign-in and restore/restart
acceptance still require the actual VM. The local Docker engine was unavailable
during packaging; do not describe this package as an accepted hosted deployment.

### Local frontend against the hosted API

Set `NEXT_PUBLIC_API_BASE_URL=https://swan-api.137-23-62-124.sslip.io` in
`apps/web/.env.local`, preserving the existing Firebase client configuration.
Use `http://localhost:3100` for the real frontend; port 4173 is the separate design
playground and does not connect to services. Sign in with the authorized Firebase
account. Existing candle, watchlist, portfolio and order components use the shared
authenticated API request path.

On 24 November 2026 the hosted `SWAN_WEB_ORIGINS` list was extended from the
Vercel origin to also allow `http://localhost:3100`, `http://127.0.0.1:3100`,
`http://localhost:3000`, and `http://127.0.0.1:3000`. Only the API container was
recreated to apply this configuration; the worker and its permissions were unchanged.
Keep exact origins rather than wildcard access. Changes to runtime.env require API
recreation; this file contains secrets and must remain private.
