# Step-one readiness — 15 November 2026

Update: the environment blockers below have been resolved for runtime/database development; see [environment setup evidence](./16-environment-setup.md). This document retains the earlier inspection for history.

## Completed in the Firebase setup pass

- Located the supplied nonstandard root `firebase.config`.
- Extracted the six recognized Firebase web settings into ignored `apps/web/.env.local` without displaying values.
- Added root ignore rules for supplied configuration, environment files and common service-account file names.
- Created the initial Next.js/TypeScript frontend with Firebase initialization, Google popup sign-in, session restoration, sign-out and accessible status/error handling.
- Added frontend setup documentation and a public configuration template with no values.
- Checked that all six settings are populated and the package/TypeScript JSON files parse.

## Not yet verified

No Firebase login or live API request was performed. Google provider enablement, authorized domains, key/project validity and account ownership are not established by possession of web configuration. No backend exists yet, so server-side token verification and the UID allowlist are still required before protected trading data is exposed.

Node.js/npm, Git, Docker, uv and a working Python runtime were not available through the checked PATH/standard locations. The `python` command resolves to the Windows Store alias rather than a working interpreter. Package installation, TypeScript checks and production build have therefore not run. The frontend dependencies need installation, a generated lockfile and validation before considering this implementation verified.

## Ready to start step one?

Requirements and domain scope: yes. Angel One, news and OpenAI credentials are not required for deterministic accounting/risk work. Local execution environment: not yet ready; provision Node.js/npm, working Python and PostgreSQL (locally or through a suitable container runtime), plus Git for version control. Docker is the planned convenience for the database, not an intrinsic application requirement.

Step one itself is not complete: repository tooling, database migrations, risk engine, paper ledger, execution model and fixture-based tests still need implementation. Auth configuration was brought forward at the user's request.

## Firebase Console actions

Enable Google under Authentication sign-in providers, set the support email and authorize the development host (`localhost`) and future production host explicitly. Backend service identity and the allowed UID will be configured when API authorization is implemented. Never place service-account private keys in `NEXT_PUBLIC_` variables.

References: [Firebase Google sign-in](https://firebase.google.com/docs/auth/web/google-signin), [Firebase SDK release notes](https://firebase.google.com/support/release-notes/js), [Next.js installation prerequisites](https://nextjs.org/docs/app/getting-started/installation).
