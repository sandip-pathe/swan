# Integrations and setup checklist

No secrets are requested or stored by this document. User has offered to supply required access. Configure secrets through an approved local or hosted secret destination when implementation reaches the relevant integration; never paste credentials into chat or planning files.

| Integration | Needed from user / account | Verification and fallback |
| --- | --- | --- |
| Firebase Auth | Project ID, public web configuration, approved domain, sign-in provider, allowed identity; backend service identity via secure configuration | Verify ID tokens server-side; use Auth emulator in tests |
| Angel One SmartAPI | Enabled developer application and account data access; authentication/renewal material configured securely according to supported flow | Verify NIFTY and SENSEX instrument/quote coverage separately, timestamps, bid/ask, OI, volume, Greeks/IV, limits and reconnect behavior; block unsupported features |
| OpenAI | Existing project/API access or secure new-key setup; spending budget | Resolve credential choice before API-backed implementation; verify current model/schema support and timeouts; mocked responses in CI |
| News/context | Choose licensed Indian-market coverage with publication timestamps, redistribution/storage terms and usable latency | Evaluate official documentation and sample coverage before selecting or paying; treat unavailable required context as a blocked strategy |
| Session/holiday source | Reliable exchange-session reference, including special sessions | Persist verified calendar versions; do not infer every weekday is open |
| Hosting | Vercel project, AWS deployment access, region, domain and budget | Proposed Lightsail API/worker plus managed AWS PostgreSQL; exact sizing follows workload measurement |
| Operational alerts | Preferred notification destination and authorization to send | In-app incidents always available; external delivery only after destination setup is authorized |

## OSS selection policy

Keep the agreed Next.js/TypeScript/Tailwind/shadcn/ui/Serwist/Lightweight Charts and FastAPI/Python/LangGraph/PostgreSQL/Docker baseline. Use maintained libraries for validation, decimal arithmetic, database migrations, tests and provider adapters. Select and pin compatible versions during scaffolding, review licenses and advisories, and record why each dependency is needed. No custom chart engine, custom trained model, or extra infrastructure without a concrete requirement.

## Documentation evidence, 15 November 2026

- [Firebase ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens): official page read; supports client token transmission over HTTPS and Admin SDK server-side verification. Account/project setup is not verified.
- [SmartAPI market-data documentation](https://smartapi.angelone.in/docs/MarketData): public search located the official page, but opening it returned an authorization error. This does not establish account entitlements, endpoint behavior or full instrument coverage. Authenticated documentation and read-only smoke tests remain required.

## Readiness boundary

Planning is ready for implementation. Foundational accounting, schemas, tests and local infrastructure can be developed in dependency order. Provider-specific integration and autonomous activation remain gated by actual access, capability evidence and passing acceptance checks. No claim of live integration readiness is made before those checks.
