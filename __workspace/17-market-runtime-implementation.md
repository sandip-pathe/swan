# Step two — market adapter and worker implementation

Updated: 15 November 2026. Code implemented; real-account connection and broader QA pending.

## Delivered

- Endpoint-allowlisted Angel One authentication, token renewal, FULL quotes and NSE Greeks client. No real-money order methods.
- Private operator login and restricted local session-token storage; PIN and TOTP are not persisted.
- Real instrument-master normalization, provider token/lot/tick/expiry handling and bounded near-money selection within 0–7 days.
- TLS-verified SnapQuote decoding, bounded latest cache, heartbeat, reconnect backoff and invalidation of old quotes/strategies.
- Provider timestamps, freshness checks, partial-chain PCR grouped by underlying/expiry, available Greeks/IV and actual observed price trends.
- Explicit calendar loader: unknown dates remain unavailable; no invented holidays, expiry schedules or sessions.
- Singleton account worker, three-minute durable evaluation slots, independent position watchdog, pause/recovery and real REST quote recovery for exits.
- Latest observed quote projection for future API consumers, published independently from the position monitor.
- Real-clock entry/exit freshness checks inside the paper transaction; concurrent metadata publication uses conflict-safe instrument insertion.
- Local `market.cmd` commands for status, login, public catalog, deliberate account creation, worker, pause and resume request.
- Worker/evaluation migration `5735abf0674c` and latest-quote migration `31fa5ac4735a`, applied locally. JSON/TypeScript contracts regenerated.

No application accounts, quotes, trades or agent replies were seeded. No replay runner or synthetic market-data file exists. No new tests were added or run, following the user's implementation-first instruction. Basic Ruff/type checks pass and dependency versions are locked; this is not a claim of final QA or live provider compatibility.

## Current actual connection state

The status command reports absent Angel One API key, client code, local/public IP and MAC configuration. No broker session is saved. Calendar sessions are empty. Actual index references and explicit account/cost/liquidity settings also need configuration. The worker has not connected to live quotes, and autonomous trading is not enabled.

Finish SmartAPI registration using legitimate required callback/network details, then follow [market setup](../services/market/README.md) and [worker operation](../services/worker/README.md). Configure secrets locally; do not send them through chat.

## Provider limits and final-QA work

The client conservatively limits REST traffic to one request per second and batches at most 50 quote tokens. Streaming subscriptions are bounded by configured budget up to 1000. Confirm actual provider/account limits before activation.

Official published descriptions mark Greeks NSE-only; SENSEX Greeks remain unavailable. Greeks receipt time does not masquerade as an exchange timestamp. Verify real field units, market entitlements, feed decoding, special sessions, renewals, reconnects and measured latency during connected QA. Broader integration/security/load testing and CI remain deferred, not waived.

## Next implementation

Step three supplies the actual analysis/proposal/review agents and licensed news context. Until then, durable evaluation slots remain `AWAITING_AGENT` rather than generated responses. A current approved strategy and explicit operator resume are both required for entries.
