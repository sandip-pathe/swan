# Operations and security

## Environments

- Local: web, API, worker and PostgreSQL; fixtures by default.
- CI: isolated database, synthetic fixtures, no live credentials or external calls.
- Deployed paper environment: Vercel frontend; Lightsail API/worker; AWS PostgreSQL placement to be resolved. No live brokerage order execution in any environment.

## Authentication and configuration

Firebase Auth replaces the original authentication choice. Use Google sign-in initially, client ID tokens as HTTPS bearer tokens, and Firebase Admin verification in FastAPI. Require verified email and an allowlisted UID; validate signature, issuer, audience and expiry. Check revocation for sensitive mutations. Use Firebase SDK token refresh and never log tokens. Restrict CORS to the configured frontend. Apply CSRF protection if using cookies; never put secrets into public frontend environment variables.

Store provider credentials and OpenAI credentials server-side in a suitable secret store or protected runtime environment. Redact secrets and auth headers from logs. User UI exposes connection status, never secret values. Trading enablement is an explicit authenticated command after preflight.

Risk settings use versioned validated updates and an audit event. AI cannot invoke these routes. Review changes affecting open positions and reject configurations inconsistent with already committed exposure.

## Health and observability

Track worker heartbeat, active scheduler lease, quote age/coverage, provider auth, evaluation duration, model errors/cost, pending exits, reconciliation drift, daily-loss state and order rejection reasons. Use correlation IDs across jobs, decisions, risk checks, fills and events.

Readiness must expose dependency health safely. UI must distinguish paused, blocked, running, stale-data and unresolved-position states. Operational alerts should identify the condition and required operator action; configure delivery explicitly during deployment.

## Recovery runbook outline

1. Disable entries and confirm persisted state.
2. Diagnose provider/auth/network/database condition through redacted logs.
3. Restore dependencies, fetch fresh data, reconcile ledger and positions.
4. Process pending exits with valid quotes; retain unresolved incidents visibly.
5. Verify session baseline and risk state, then explicitly resume.

Back up PostgreSQL with retention and access controls; choose recovery objectives before deployment. Test restoration. Run schema migrations as a controlled release step with a database backup and compatibility/rollback strategy. Do not depend on frontend/serverless requests for continuous monitoring.

## PWA behavior

Cache versioned static assets only. Avoid caching authenticated API responses and sensitive pages. Offline mode displays a clear disconnected state and cannot enqueue trading enablement or settings mutations. Closing the PWA does not stop the backend worker; show this in the controls' help text.
