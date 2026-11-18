# Broker-style feature/data inventory

Source audit: 18 November 2026. Provider-side declarations are not account entitlement. Availability below is a code inspection, not a new live connection test.

| Feature / metric | Existing source | Current SWAN path | Required work / evidence | Priority |
| --- | --- | --- | --- | --- |
| Instrument identity, expiry, strike, lot, tick | Public instrument master | Catalog normalizes and persists metadata; chain shows contract IDs | Search, expiry-aware selection, shared selected instrument, watchlists | M3/M5 |
| NIFTY/SENSEX reference prices | Existing FULL reference requests | Runtime reads raw LTP for universe selection; no dedicated persisted index strip | Normalize/source index observations, expose fresh overview and meaningful closed-market state | M3/M5 |
| LTP | FULL/SnapQuote declared | Not retained in `Quote`; reference selection's raw LTP is a separate use | Add optional sourced trade-price fields; never substitute bid/ask midpoint or execute at LTP | M3 |
| Session open/high/low/previous close | FULL/SnapQuote declared | Not retained in `Quote` | Specify provider close semantics and session identity, normalize and persist | M3 |
| Price / percent change | FULL declared; can derive after close semantics verified | Not retained or displayed as dedicated metrics | Define `(LTP - previous_close)` and denominator rules; absent/zero reference means unavailable | M3/M5 |
| Bid/ask and spread | REST and SnapQuote | Retained; chain shows bid/ask; risk uses spread | Add price/bps spread and timestamps to instrument panel | M5 |
| Best-five depth, order count | REST and SnapQuote | Retained/persisted, consumed by matcher; full ladder not displayed | Verify quantity semantics E01, render separate level quantities, timestamps and coverage | M1/M5 |
| Volume and OI | REST and SnapQuote | Retained; displayed in chain | Verify per-field units/session semantics; chart volume and OI histories need dedicated contracts | M3/M5 |
| OI change | Historical OI route / SnapQuote field declaration | No normalized reference baseline/change series | Verify field encoding and baseline; don't infer change from the first observed tick | M3/M5 |
| Average traded price, total buy/sell quantity | FULL/SnapQuote declared | Not retained in `Quote` | Confirm units and field meaning; do not label average traded price as our calculated VWAP without verification | M3/M5 |
| Circuit limits / 52-week range | FULL/SnapQuote declared | Not retained | Verify instrument applicability; absent/unsupported is not zero | M3/M5 |
| IV and Greeks | Existing optionGreek adapter | Time/provenance retained; IV shown; NIFTY supported in adapter, BFO access not established | Full display, freshness, assumptions; SENSEX remains unavailable until supported | M5 |
| PCR | Existing chain analysis | Selected-contract fresh-OI PCR exists in analysis, not full-chain coverage | Expose scope/coverage and formula; no full-exchange PCR claim | M5 |
| Max pain / payoff analytics | Derived inputs | Not implemented | Define complete-chain coverage, expiry and methodology; payoff models don't guarantee execution | Later M5/backlog |
| Historical OHLCV candles | Official SDK `getCandleData` declaration | No allowlisted route, normalized bar model, persistence or API | Verify permissions, intervals, history/expired-contract coverage, quotas, retention and time alignment | M3 |
| Historical OI | Official SDK `getOIData` declaration | Not implemented | Verify coverage and schema separately from price candles | M3 |
| Live candle updates | Actual feed observations | No candle aggregation | Session-aligned bars, provisional/final state, cumulative-volume resets, duplicates, out-of-order data, reconnect gaps | M3 |
| Candle/line chart and volume panel | New chart component | Not implemented | Library/license proof of concept; real history, crosshair, pan/zoom and accessible controls | M4/M5 |
| SMA/EMA/RSI/VWAP | Derived valid candle/trade inputs | Not implemented | Versioned formulas, sufficient-history checks; VWAP needs valid volume inputs; index VWAP may be unavailable | M5 |
| Drawings, indicators, chart layouts | New UI tools | Not implemented | Start small; save user layout without credentials; advanced/multi-chart tools follow | M5/backlog |
| Fill/order/stop/target chart markers | Existing ledger records | Execution tables/cards exist; no chart overlays | Join exact instrument/time; requested order markers differ from actual fills | M5 |
| Cash/reserved/restricted/available funds | Paper ledger and reservations | Implemented API and funds panel | Reuse authoritative values; no independent frontend cash calculation | M6 polish |
| Remaining position units / average fill | Paper positions/fills | Implemented, including partial closes | Integrate chart/details/order selection and retain precision | M6 |
| Gross/net realized P&L and fee totals | Ledger, fills and closed positions | Net realized values and fee drilldowns exist; no complete performance dashboard | Document allocation/basis; partial-close consistency; time/session filters | M6 |
| Unrealized net liquidation / risk headroom | Portfolio/risk engine | Internal portfolio valuation exists; not all measures exposed to person | Public definition/snapshot contract; executable side, cost basis, stale state and session baseline | M6 |
| Daily equity curve / drawdown / expectancy | Reconciled history plus new metric snapshots | Incomplete; no full performance series | Define sampling, trade grouping, net/gross basis and undefined ratios; no hindsight reconstruction of missing intraday equity | M6 |
| Manual paper ticket and place/cancel/exit | Existing durable ledger can be reused | No authenticated human order lifecycle API/ticket | Explicit manual intent, risk approval, idempotency and ownership; no fake agent envelope | M6 |
| Order modification / bulk exits / baskets | New orchestration | No person-facing workflows | Specify replacement/fill races and unresolved results. Multi-leg/basket accounting is separate expanded scope | M6/backlog |
| News | Existing NewsData free / configured permitted feeds | Actual reader/agent integration and diagnostic; no full news panel | Attributed panel with publication/retrieval time and declared provider delay; revalidate terms before broader display/retention | M5/M7 |
| Agent proposal/review/risk explanation | Pipeline/evaluation/audit records | Evaluation/activity views exist; no complete linked person-facing timeline | Genuine response/citation/version/usage links; WAIT differs from dependency failure | M7 |
| End-of-session review and reports | Ledger, market and evaluation evidence | No complete user-facing daily-review workflow | Reconciled report, incidents, unresolved evidence and performance limitations | M7 |
| Alerts, scanners, strategy builders | Provider/derived inputs or new jobs | Not implemented | Separate spec, quotas, persistence, notification consent and risk semantics | Backlog |
| Real holdings, funds transfers, settlement, broker orders | Broker account/execution APIs | Outside current paper scope; order routes excluded | Separate authorization and implementation project | Excluded |

## Source and entitlement strategy

Authoritative references inspected: [SmartAPI market data](https://smartapi.angelone.in/docs/MarketData), [official SnapQuote parser](https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartWebSocketV2.py), [official client routes](https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartConnect.py). Some hosted documentation required authorization; indexed documentation and official source establish discovery only. The SDK must not be imported wholesale: our endpoint allowlist, TLS verification and private credential handling remain in force.

For each M3 integration, record documentation source/version, actual entitlement check, field units, interval/retention limits, rate budget, missing-field behavior, normalized storage/API path and UI acceptance. No paid data subscription or new broker integration has been selected by this inventory. A web-displayed field is not proof of API availability.

First complete product slice: select one real eligible contract → load sourced history → show current depth and freshness → inspect a permitted paper intent → follow orders/fills/protection → reconcile and report. Historical candles must never serve as executable depth.
