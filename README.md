# SWAN Trade

SWAN is a single-user web app for NIFTY and SENSEX market research, charts,
source-grounded chat, saved strategy work and paper orders. It uses real Angel One
observations when available and never sends live broker orders. The app currently
runs locally on Windows; production hosting is not configured. The first release
scope is a minimal paper-only application. Profitability, extended evaluation and
strategy improvements are later work.

## What to read

- [Current project status and next work](./DEFERRED-WORK.md)
- [Current code checkpoint](./RESUME.md)
- [Current product requirements](./__workspace/11-current-product-requirements.md)
- [Accepted product decisions](./__workspace/09-decisions-and-dependencies.md)
- [Original source PRD](./__workspace/01-source-prd.md) — preserved as historical input; later accepted decisions supersede it.
- [System architecture](./__workspace/03-architecture.md)
- [Complete workspace plan](./__workspace/37-complete-system-and-broker-workspace-plan.md)

Implementation checkpoints in [`__workspace`](./__workspace/README.md) record
what changed and the evidence available at that time. They are an archive, not
the current backlog.

## Run locally on Windows

Check the managed services:

```powershell
.\local.cmd status
```

See [local startup and wiring](./__workspace/30-local-startup.md) for startup,
shutdown and offline operation. First-time environment setup is documented in
[integrations](./__workspace/12-integrations-and-setup.md),
[environment setup](./__workspace/16-environment-setup.md), and
[Firebase authentication](./__workspace/31-firebase-public-key-auth.md).

The root `.env` and `apps/web/.env.local` contain private local configuration.
Do not paste or commit their contents. `market.cmd login` handles broker session
renewal privately; a web sign-in does not renew the broker session.

## Product and safety boundary

The active local scope is a single-owner virtual ledger and paper orders. Code
availability is not permission to trade. Broker login, live-market acceptance
and autonomous qualification remain separately gated; the worker must remain
stopped unless deliberately prepared. Real-money execution and multi-user
onboarding are future, separately scoped releases.
