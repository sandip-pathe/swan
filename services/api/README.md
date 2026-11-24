# Authenticated workspace API

Execution visibility additions, 18 November 2026: workspace includes `active_orders`
(oldest first, maximum 200), `order_summary.active_count` and `active_truncated`,
separate from the 50 most recent `orders`. Fill rows include joined order side and
instrument ID, and `instruments` supplies stored labels for visible records. Unreleased
funds holds sort before released history. A truncated list cannot establish complete
exit coverage; cash restrictions are still calculated across all current holds.

18 November 2026 readiness additions (supersede earlier deferred-configuration notes):

- `GET /api/workspace` includes server-owned checks, actions, evidence freshness,
  independent configuration/connection/worker status and known/open/closed/partial
  exchange state. Ordinary polling makes no provider calls.
- `GET /api/settings/setup` returns non-secret configuration documents and revisions.
- `POST /api/settings/setup/{execution|calendar|news|agents}` validates and atomically
  imports a document with `expected_revision`. Shared-file updates require the sole
  configured account, paused entries and no active orders/positions; ordinary database
  commit failures restore the previous file. Abrupt termination between filesystem
  replacement and database commit still requires operator reconciliation of the file/audit.
- `POST /api/settings/risk-policy` requires every policy field, expected account revision
  and explicit `reviewed: true`. Capital and historical legacy costs cannot be rewritten.
  Review evidence is bound to the policy digest; later changes invalidate it.
- `POST /api/diagnostics/{broker|catalog|stream|ai|ai_schema|news}` executes bounded,
  account-scoped tests under a singleton diagnostic lock, with a 30-second same-input
  cooldown and 15-minute evidence lifetime. `ai_schema` uses the token budget; other
  checks make no generation request. Responses never include credentials/profile data.
- Resume is rejected for the managed observation-only worker. Entry validation remains
  a separate milestone; these endpoints do not enable execution.

Auth, configuration/risk review, conflicts, diagnostic persistence/cooldown, observation
mode and database-failure compensation now have isolated tests in `tests/test_setup.py`.

Launch `api.cmd` from the root in its own terminal, or use `local.cmd start` for background web/API/database services. Uvicorn binds only to `127.0.0.1:8000` and disables access logs. No account is created by starting the service. With explicit local owner enrollment enabled, the first genuine verified Firebase login initializes the user's paused paper wallet.

## Configuration when ready

Ignored root `.env` needs `FIREBASE_PROJECT_ID` for token verification. An Admin service-account key is not required. `SWAN_LOCAL_OWNER_BOOTSTRAP=true` enables local first-owner enrollment after successful signed-token verification. Both the client peer and database must be local. A transactional database advisory lock serializes enrollment; the persisted owner record prevents subsequent users from claiming the wallet. An already-existing unlinked account is never silently adopted. This flag defaults to false and must remain disabled for hosting. `SWAN_ACCOUNT_BINDINGS` remains optional compatibility configuration for existing accounts.

The frontend reads `NEXT_PUBLIC_API_BASE_URL`, defaulting to `http://localhost:8000`. Set it to the actual HTTPS API origin for deployment. This URL is public, never a secret. `SWAN_WEB_ORIGINS` is an explicit JSON array, defaulting to localhost and 127.0.0.1 port 3000. Production needs a restricted real origin list and HTTPS termination; the local launcher is not a production deployment.

The backend verifies RS256 signature, key identity, project audience/issuer, expiration, issued/authentication times and nonempty bounded Firebase subject using Google Auth and Google's public certificates, cached according to their HTTP headers. No private credential or broker API is involved. Verification failures deny access. Immediate revocation/disabled-user checks are not performed on this path: a previously issued token may remain valid until expiration. The browser refreshes tokens through Firebase. Live-money authorization needs a separate review before activation.

Tokens are sent as Bearer headers, never query parameters or browser-managed backend cookies. API responses use `Cache-Control: no-store`; CORS allows only configured origins. Restart after configuration changes.

Local enrollment initializes the agreed virtual capital and default risk fractions, with entries disabled. Remaining spread/liquidity/quantity inputs are unreviewed startup limits; the one-unit quantity cap deliberately blocks option-lot entry. Legacy fee configuration is absent rather than represented as free execution. Durable execution still requires reviewed fee schedules and final QA. No account/fill/agent result is manufactured before actual authentication.

## Routes

- `GET /api/workspace`: a repeatable-read account snapshot, runtime heartbeat, open/closed positions, orders, fills, ledger, decisions, evaluations and recent activity. Recent-history collections are bounded to 30/50 records. Full AI input contexts are excluded from this polling response; persisted audit evidence remains in the database.
- `GET /api/chain?underlying=NIFTY&offset=0`: up to 100 persisted instrument/quote pairs, with an optional next offset. SENSEX is also supported. Historical observations remain explicitly timestamped; UI freshness uses the configured quote age. Missing metrics are not replaced with zero.
- `POST /api/control/pause`: atomically disables entries, clears the strategy and resume request, and audits the action. The worker remains responsible for open-position exits. Offline workers cannot provide exit monitoring.
- `POST /api/control/resume`: requests worker preflight; it does not enable execution itself. Requires a recent heartbeat and no daily loss block. The worker rechecks the request under the account/control locks before enabling entries to prevent a stale resume from overriding a user pause. Reconciliation and pending-exit checks remain required.
- `POST /api/settings/risk`: optimistic account-revision check, strictly validated trade/daily risk fractions and holding seconds (maximum 300). Account must be paused, with no resume request or open positions. Preserves capital, costs and other limits, generates a new policy version, clears the active strategy and records before/after policies.

Strategy paper candidates expose `GET /api/strategies/paper-plan-candidates/{candidate_id}/preflight`. It rechecks source-plan/reviewer provenance and fingerprints, then reads current account risk configuration, qualification, arm and paper-engine blockers. It is read-only and never creates an approval or order; the ORB dual premium/underlying exit adapter is still missing, so candidates remain blocked.

`GET /api/strategies/paper-plan-candidates/preflight` returns a bounded current blocker snapshot for the Strategy Intelligence view. `GET /api/strategies/assignments` returns bounded watcher-workflow states and safe artifact summaries for one session. Both are authenticated read-only views.
- `GET /api/reports/journal.csv`: latest 10,000 closed positions, decimal strings and UTC timestamps. Spreadsheet formula prefixes in instrument names are escaped. The UI explicitly discloses the export limit.

The dashboard polls every five seconds without overlapping loads; sign-out/unmount aborts fetches and discards account state. Network failure clears the displayed snapshot. Stale snapshots disable controls; stale quotes remain labeled. No provider secrets are returned. No API endpoint creates broker orders.

## Product and validation status

Responsive overview, observed option chain, position journal, ledger, evaluations, activity, risk settings and CSV download are implemented. Manifest and generated 192/512 icons support installation on compatible browsers over HTTPS/localhost; Android installation has not been validated. No service worker caches authenticated data or creates an offline trading mode. Icon assets are reproducible with `scripts/icons.ps1`.

Firebase Admin dependency is installed and locked. Backend lint/types and frontend production build pass. Tests and connected/browser acceptance remain deferred: authorization, control races, policy conflicts, provider failure and Android installation require final QA before operation. No credentials were provisioned and no seeded accounts or synthetic observations were added.

Firebase reference: [Verify ID tokens](https://firebase.google.com/docs/auth/admin/verify-id-tokens), [session revocation checks](https://firebase.google.com/docs/auth/admin/manage-sessions).
