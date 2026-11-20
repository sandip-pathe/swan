# Instrument details and paired option chain

Implemented 20 November 2026. The full local stack was started and checked before
implementation, as requested. The worker process runs in observation mode but
reports unavailable market data; process availability is not live-feed readiness.
Broker login was not attempted.

## User flow

**Markets → Option chain** now pairs calls and puts around each numeric strike,
with a market and expiry selector. Last traded price, bid/ask, OI, volume and
exchange observation times are visible on each side. A missing side stays
unavailable. Tap a side to open its chart, then choose **Details** for session
OHLC, previous close/change, spread, volume/OI/IV, lot/tick size and exchange.
Switching between Chart and Details retains the mounted chart and its view.

The header distinguishes last traded price from a candle-close fallback. Recent
or last-saved labels use observation age, never imply executable readiness, and
retain the exchange date/time. Selected-instrument polling refreshes cached
details every five seconds while visible; errors retain the prior observations
with an explicit warning. IV retains its own observation time and declared unit.
No quote means unavailable values, rather than a zero or invented price.

## Data behavior

The cached chain endpoint now defaults to the nearest nonexpired expiry that has
saved quotes. Its expiry choices describe saved quoted contracts, not the full
exchange list. Pagination counts 50 distinct numeric strikes and returns both
available sides, preventing pairs from being split across pages. Missing,
duplicate or truncated coverage is explicit; the UI does not infer an ATM marker
without a retained underlying reference. The existing deliberate Refresh prices
action still retrieves its bounded nearest-expiry selection; other expiries need
already saved observations or discovery through Search.

The selected-instrument response adds display statistics computed with Decimal:

- Change = last traded price minus positive previous close.
- Percentage change = change / previous close × 100.
- Spread = ask minus bid for positive, noncrossed prices.
- Spread basis points = spread / ((bid + ask) / 2) × 10,000.

Missing inputs and invalid baselines leave the derived field unavailable. A
locked bid/ask produces a genuine zero spread. Zero volume/OI is retained.
Provider OHLC is not reconstructed from a partial candle sample. Depth quantities
remain unavailable pending unit verification. These calculations and chart
selection cannot affect fees, risk admission, orders, fills or qualification.

All new reads reuse authenticated owner checks and no-store responses. Opening,
polling, filtering and changing expiry call no provider endpoint. No migration or
credential/configuration change is required for this slice.

## Verification

Seven new tests cover display formulas, missing/zero/crossed prices, paired
pagination, numeric sorting, expiry exclusion/selection, account authorization,
quote-age preservation and unchanged account cash/orders. The full backend suite
passes 168 tests; the five frontend calculation tests, Ruff, mypy, type checking
and production build also pass.

Browser fixtures exercise the paired chain, Details, Chart return, existing
search/watchlist flows, touch, offline behavior and six viewport sizes without
overflow or runtime errors. Test market values stay outside the real account.

A read-only actual-database check returned ten saved NIFTY quotes and four
available derived statistics for a selected contract, with no provider request.
No nonexpired quoted SENSEX contract was saved, so its current chain correctly
returned empty. The actual account has zero orders/fills and entries disabled.
This does not establish current feed availability or complete provider coverage.

Further work: visible-instrument market-data priority and explicit price refresh
for discovered/saved contracts, verified depth display, additional studies and
eventually the separately specified manual paper-ticket workflow. Actual open
market/reconnect qualification remains outstanding.
