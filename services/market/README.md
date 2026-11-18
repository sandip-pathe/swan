# Angel One market-data integration

17 November 2026: quote normalization retains best-five depth, order counts, feed timestamps and stable market-event identity. WebSocket quotes also retain sequence and connection identity; repeated/older observations do not refresh the cache. Quantity units remain explicitly unknown until verified. See [paper step 1 evidence](../../__workspace/25-paper-step-one-implementation.md). `market.cmd status` now includes paper configuration blockers; completing configuration alone does not enable the pending enhanced execution engine.

The adapter exposes authentication, token renewal, FULL quotes and option Greeks only. The WebSocket client subscribes to SnapQuote with verified TLS. Brokerage execution methods are not available through its endpoint allowlist.

## Access setup

Finish registering your SmartAPI application with legitimate callback/network details. Add the server-only variables from root `.env.example` to your ignored root `.env`, preserving the existing database configuration. Never copy over the real database URL with the template value. Never use frontend `NEXT_PUBLIC_` variables for broker credentials.

- `ANGELONE_API_KEY`: SmartAPI app API key.
- `ANGELONE_CLIENT_CODE`: Angel One client code.
- `ANGELONE_LOCAL_IP`, `ANGELONE_PUBLIC_IP`, `ANGELONE_MAC_ADDRESS`: the actual backend host's network identity for provider headers. These do not replace registration requirements.
- `ANGELONE_NIFTY_INDEX_TOKEN`, `ANGELONE_SENSEX_INDEX_TOKEN`: actual provider index reference tokens, used to fetch real spot prices for near-money strike selection. Tokens are not guessed.

Check presence without displaying values, then privately log in from your own terminal:

```powershell
.\market.cmd status
.\market.cmd login
```

Login prompts privately for PIN and current TOTP; neither is saved. Session tokens are saved in ignored `.local/angel-session.json` with restricted permissions. They never reach the frontend. Sessions are capped at local midnight and require a fresh daily login; eligible token renewal occurs within the same day. Actual account behavior and entitlements still need connected verification.

## Instruments and calendar

`market.cmd catalog` reads real public Angel One metadata and reports eligible counts/expiries, never generated prices or trades. NIFTY/NFO and SENSEX/BFO options retain provider token, actual expiry and lot/tick details. Published paise strike/tick fields normalize to rupees; unknown or malformed records are rejected.

Subscriptions select actual listed expiries 0–7 calendar days away, inclusive of expiry day, and a bounded strike range around real spot prices. Open positions remain pinned. An oversized universe blocks selection rather than silently dropping held instruments.

`config/exchange-calendar.json` currently imports sourced sessions and explicit closures for 18–30 November 2026. Coverage beyond that range must be reviewed before use. Each session entry contains `exchange` (`NFO` or `BFO`), `official_source_url` on the relevant NSE/BSE domain, and `session` matching `shared/schemas/ExchangeSession.json`: date key, timezone-aware open/close, calendar source and reviewed verified status. Unknown dates block entries. Special sessions use actual times; no weekday/holiday fallback is inferred.

## Data semantics

- Exchange feed timestamps and local receipt timestamps remain separate. Stale/future/crossed/incomplete quotes cannot authorize entries.
- SnapQuote integer option prices normalize from paise. Missing depth remains unavailable.
- Fresh REST data may recover open-position exits during stream reconnects, without silently enabling entries.
- OI/volume/Greeks/IV retain provider values. IV is labeled percent. Greeks receipt time is explicit; an unavailable provider timestamp remains null.
- Published documentation describes Greeks as NSE-only. SENSEX Greeks remain unavailable until account capability is established; no invented substitutes are supplied.
- PCR is scoped to selected contracts within one underlying/expiry and requires fresh complete OI. It is not labeled full-exchange-chain PCR.
- Short-window trends use actual observed midpoint quotes, with no generated historical points.

## Documentation evidence

M3 foundation now retains optional LTP, session OHLC/previous close, average price and last-trade quantity in normalized quotes. REST trade time is retained where provided; WebSocket trade-time units are not assumed. These display fields never replace executable depth.

Owner-authenticated history endpoints provide explicit bounded backfill and cached reads for current stored NFO/BFO options. Batches preserve provider rows, provenance, gaps and unavailable OI separately from trading snapshots. Live candle aggregation is still pending. The first real history probe returned `BROKER_AUTH_REJECTED`; actual history access is not yet verified. See [M3 implementation record](../../__workspace/41-m3-market-data-foundation.md).

Reviewed 15 November 2026: [authentication](https://smartapi.angelone.in/docs/User), [streaming protocol](https://smartapi.angelone.in/docs/Instruments), [market data/Greeks](https://smartapi.angelone.in/docs/MarketData), [official SDK](https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartWebSocketV2.py), and [public master](https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json).

The actual public master was reachable and contained NFO/BFO records. Some documentation pages required authorization; public indexed documentation and the official SDK were also consulted. This does not verify your account access, field units, streaming compatibility or latency. Connected validation is deferred to final QA as requested.
