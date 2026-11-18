# Implementation roadmap and access timing

17 November 2026 update: the next increment is [realistic internal paper execution](24-realistic-paper-execution-plan.md): contracts/configuration, durable orders/ledger, conservative execution/protection, agents/UI integration, then final QA and local observation. Use actual Angel One market inputs; no external paper key or paid virtual-credit service is required. Current code is the earlier foundation, not completion of these enhancements. New test expansion stays deferred to final QA; local iterations precede deployment.

This is the short execution roadmap. The detailed build checklist and release acceptance criteria remain authoritative for task coverage. Credentials are configured securely, never pasted into chat or committed to source control.

16 November 2026: prioritize a one-to-two-week autonomous paper observation period while iterating locally. Future product scope explicitly includes autonomous real execution and multiple broker-linked users. Those require separate execution/account-isolation releases; current operation remains paper-only. See [accepted product direction](./21-autonomous-product-direction.md).

| Step | Build and verify | Access needed | Completion gate |
| --- | --- | --- | --- |
| 1. Foundation and trading engine | Implemented: repository, database, schemas, risk sizing, paper fills/costs, ledger and strategy contracts; replay removed by user | No live service keys for domain-only work | Existing checks passed; further QA deferred to final validation |
| 2. Market data and intraday runtime | Angel One adapter, instrument/expiry selection, streaming quotes, freshness, session calendar, monitoring, pause, forced exits and recovery | Angel One SmartAPI developer app and account access, configured securely at the start of this step; confirm documented session/renewal requirements and account entitlements | Read-only data coverage verified for both indices; stale data, reconnect and pre-close behavior tested |
| 3. AI and news | Structured analysis/proposal/review agents, strategy envelopes, licensed news adapter, evidence, timeouts and spending controls | OpenAI project/API access and budget decision before API-backed implementation; news-provider access after coverage/licensing selection | Mocked and connected contract checks pass; agents cannot bypass risk or settings controls |
| 4. Authenticated product interface | Firebase sign-in, identity allowlist, dashboard, option chain, journal, settings, reports and installable PWA | Firebase project/public web config, allowed identity and domain, plus secure backend service identity at the start of this step | Protected endpoints, browser flows, accessibility and Android install checks pass |
| 5. Release and operation | Full acceptance suite, load/latency checks, deployment, backups, recovery rehearsal, alerts and controlled autonomous paper sessions | Hosting accounts, region/budget, domain if wanted, and authorized alert destination before deployment; production secrets configured in the runtime | AC01–AC21 evidence, reconciliation, recovery and live read-only preflight pass before enabling autonomy |

## What to prepare now

- Confirm access to your Angel One account and SmartAPI developer application. Prepare the app/account setup, not a screenshot or message containing secrets.
- Decide whether to use an existing OpenAI project/key or provision a new project key, and choose a monthly spending ceiling. No key is needed for planning or domain-only work.
- Identify an existing Firebase project or plan to create one; choose the Google account allowed to sign in.
- Keep news-provider purchases and hosting size decisions until coverage and workload requirements are checked.

## Credential handling

15 November 2026 update: the user will add all API access later and requested skipping tests now. Continue implementation with integrations disabled until configured. This supersedes the earlier requirement to supply OpenAI access before implementation. See [agent/news delivery](./18-agents-and-news-implementation.md).

The builder will request only the next integration's access, explain the required configuration and use an approved ignored local secret file or hosted secret store. Follow the OpenAI credential-choice workflow before implementing API-backed AI functionality; no silent key reuse. Public Firebase web configuration is distinct from private backend credentials. Never send account passwords, OTPs, TOTP seeds, service-account private keys or API secrets through chat.

Planning readiness does not establish provider capability or operational readiness. Unsupported market-data fields, expired sessions, missing required news or failing preflight checks block dependent trading behavior.
