# Firebase sign-in without Admin credentials

Updated: 17 November 2026, Asia/Kolkata.

The previous service-account requirement was a consequence of choosing Firebase Admin SDK revocation checks, not an inherent requirement of Firebase sign-in, virtual money or Angel One. The user correctly challenged that requirement. This increment replaces it with public-key ID-token verification and local single-owner paper-wallet enrollment.

## Current flow

1. The browser uses the existing Firebase web environment configuration and signs in normally.
2. Its Firebase ID token reaches the API as a Bearer header.
3. Google Auth verifies the token against Google's public signing certificates, audience/project and timing claims. The API additionally restricts algorithm/key header, issuer, subject length and authentication time. Certificates honor Google HTTP cache headers; network timeout is bounded. Emulator tokens are not accepted.
4. With local enrollment explicitly enabled, the first verified Firebase UID becomes the sole local owner. Its wallet is created transactionally with the already-agreed ₹1,00,000 virtual capital and a CAPITAL ledger entry. Subsequent logins load that same account; they never top up/reset it. Other UIDs are denied.

Enrollment is serialized with a transaction-scoped advisory lock. The owner enrollment audit event retains the verified project/UID. Existing unlinked accounts are not guessed or adopted. Local-only client/database checks and a default-off enrollment flag keep this initialization separate from hosted user onboarding. This is for the current one-owner setup, not a new multi-user broker implementation.

## Configuration

Frontend: existing `NEXT_PUBLIC_FIREBASE_*` values in `apps/web/.env.local`.

Backend: `FIREBASE_PROJECT_ID` plus `SWAN_LOCAL_OWNER_BOOTSTRAP=true` in the ignored local `.env`. No Admin JSON, Google Application Default Credentials or manually copied Firebase UID is required for this flow. Existing explicit account mappings are retained as an optional migration path, not a local enrollment prerequisite.

## Risk and limitations

The initial wallet is paused and unreviewed. The agreed trade/daily fractions remain 0.5%/2%, one position, and five-minute maximum holding. A conservative one-unit maximum blocks whole-option-lot entry until review. No applied fee values were invented: `RiskConfig.costs` is now optional for the durable engine, which obtains charges exclusively from reviewed execution fee schedules. Historical immediate-fill functions explicitly reject missing legacy costs.

This authentication path does not perform immediate Admin revocation/disabled-user lookups. A valid previously issued Firebase ID token can remain usable until expiration. Production/live-money identity policy needs separate review. Signature verification, project scope and account isolation remain mandatory.

## Verification and operational status

Backend lint/type checks and contract regeneration are performed; the Google public certificate endpoint was reachable with HTTP 200. Local web/API services are restarted with the new configuration. A genuine browser login remains necessary to verify authenticated wallet creation end to end; no fake identity, sample token, seeded wallet or authentication bypass is used to claim success.

Trading is still gated by broker session/calendar, reviewed execution/fees, agent dependencies and final QA. No broker/agent requests, paper trades, real orders or deployment were triggered.

References: [Firebase ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens), [Firebase session lifecycle](https://firebase.google.com/docs/auth/admin/manage-sessions).
