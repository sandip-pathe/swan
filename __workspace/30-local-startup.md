# Local application startup

Updated: 17 November 2026, Asia/Kolkata.

The local PostgreSQL instance, API and Next.js frontend were started in background processes. No trading worker, provider login, agent evaluation or order execution was started.

## URLs and operator commands

- App: http://localhost:3000 (use localhost, which is already in the supplied Firebase authorized-domain list).
- API/database health: http://127.0.0.1:8000/health.
- Database: 127.0.0.1:54329, credentials kept in the ignored root `.env`.
- `local.cmd start`: start the database and managed background API/frontend processes.
- `local.cmd status`: report listener state.
- `local.cmd stop`: stop only the recorded managed API/frontend process trees, checking recorded process identity/start time before stopping them. PostgreSQL remains running.
- `database.cmd stop`: stop the local database when finished.
- Process metadata and output/error logs: ignored `.local/run/`.

Existing foreground launchers (`api.cmd` and `dev.cmd`) still work for separate terminals. The background launcher avoids spawning another instance when its port already has a listener; it does not take ownership of unrelated existing processes. Listener status alone is not application/provider readiness.

## Verified during startup

Actual HTTP requests returned 200 for the app on localhost and for `/health`, which executes a real database query. The protected workspace route returned 401 without a token. The CORS preflight for the existing frontend origin and Authorization header returned 200 with the expected localhost origin.

The database is on migration `95d7e32c10ab`. Direct read-only counts show zero accounts, runtime controls, orders and fills. Nothing was seeded or automatically funded. No schema upgrade was needed.

Browser Firebase required fields are present. The frontend API origin is the configured/default `http://localhost:8000`, and the API permits the localhost frontend origin. Backend lint and typing pass for the health-route change. These startup probes do not establish authenticated or trading acceptance; automated tests remain deferred.

## Remaining inputs

1. Private Firebase Admin service-account credential file or valid Application Default Credentials. Neither was configured/found in the standard local locations. Browser Firebase config is public client configuration and cannot supply that server credential.
2. Actual Firebase owner UID and a configured, paused paper account, followed by an explicit UID/account mapping. The account must use reviewed risk inputs; no demonstration account or invented applied fee schedule was created for startup.
3. Renew the expired Angel One session through `market.cmd login`, with PIN/TOTP entered privately in the user's terminal.
4. Reviewed exchange sessions, execution assumptions, verified feed quantity semantics and effective NFO/BFO fees. The existing execution file is valid structurally but incomplete.
5. Explicit agent model/budget and remaining provider configuration, then final connected QA before autonomous observation. No OpenAI provider request was made during startup.

Current services can serve the sign-in application and respond to API requests; full authenticated account access and autonomous paper operation are not yet ready. Keep secrets out of chat and workspace documentation.
