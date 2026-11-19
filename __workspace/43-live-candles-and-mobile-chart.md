# Observed candles, recovery and mobile contract charts

Implemented 19 November 2026. Continues the M3 foundation and adds the first
contract-chart workflow. M3 actual-market acceptance remains incomplete.

## User flow

Open **Markets**, retrieve prices if needed, then choose **Chart** on a contract.
Desktop contract names open the same chart. Select a session and use **Get
candles** for an explicit, bounded broker-history request. Ordinary chart polling
reads the database only. The initial session uses the quote's IST date; prices
retain their actual candle timestamps. The chart does not label old prices live.

The one-minute chart supports touch pan/pinch, crosshair OHLC/volume, zoom/fit
buttons, a session picker and browser back/forward. It shows provider volume only
when available. Known missing minutes remain whitespace; no price or volume is
carried across them. The latest 20 candles also have a readable text view. The
chart library loads when the chart opens. TradingView attribution is included.

Phone controls have at least 44-pixel targets. The layout uses the existing PWA
safe-area navigation, local fonts and mobile-first styles. Offline/error states
retain already displayed candles with an explicit warning. The service worker
still caches only the public offline notice, never authenticated account data.

## Data behavior

- The worker independently observes valid NFO/BFO SnapQuote LTP snapshots before
  execution-cache deduplication. Exchange feed timestamps, connection identity,
  advancing sequence, verified session bounds and maximum ten-second feed delay
  gate these chart observations. They cannot grant executable evidence.
- One-minute OHLC segments persist by account, instrument, stream and opening
  timestamp in `live_candle_segments`. Duplicate/out-of-order observations do not
  regress bars. Segments are provisional observations, not all exchange trades.
- Cumulative volume differences across missing feed data, reconnects or minute
  boundaries cannot be allocated accurately. Observed bars therefore expose null
  total volume. Known intra-minute deltas remain separate diagnostic information.
- Stream starts, reconnects and gaps queue bounded historical recovery. A persisted
  watermark supports restart recovery; a cold session begins at its verified open.
  One background request uses the shared history lock and five-second budget.
  Busy requests stay queued; terminal provider failures remain recorded gaps until
  a later gap or explicit refresh. There is no unlimited retry loop.
- Chart persistence and recovery run separately from the exit watchdog. A bounded
  dirty buffer retries failed writes; overflow queues history recovery. Abrupt
  shutdown can lose unflushed observations; recovery is not a guarantee of tick
  completeness or provider availability.
- `GET /api/market/candles` returns bounded, owner-scoped reconciled one-minute
  bars, known-session gaps, unknown calendar dates and truncation metadata.
  Closed provider bars replace overlapping observed bars; volumes are never
  summed. A newer empty provider response does not resurrect older provider bars.
  Elapsed intervals do not imply exchange-confirmed finality.

Migration `e0d4fab65205` is applied locally. It refuses a downgrade that would
discard recorded segments. Entry, qualification and execution gates are unchanged.

## Verification and remaining work

The full backend suite passed 153 tests. Focused candle tests also cover
same-connection gaps arriving during a recovery request and chart-failure isolation.
Ruff, mypy, migration/model comparison, frontend type checking and production build
passed. Isolated UI fixtures exercised six viewport sizes, chart navigation,
zoom/fit controls, emulated touch/pinch, empty history, broker errors, offline
retention and explicit history refresh. Fixture prices were never inserted
into the application database.

A read-only check against the actual local database returned 16 previously saved
BFO bars through the new endpoint, with no provider request and no gaps in that
requested range. There are zero observed live segments after hours, zero orders
and fills, and entries remain disabled. Services were restarted in observation
mode. Successful after-hours provider evidence is recorded in checkpoint 42.

Still required: observe a real open-market stream, force reconnect/restart and
check recovery against actual broker history; verify broader contract coverage;
review the chart on a physical phone. Additional intervals, index charts, studies,
drawing tools and order-ticket integration are future work. Fee, rounding, depth
unit and BFO IPFT evidence remain open. Calendar coverage ends 30 November 2026.

Library API and attribution reference: [Lightweight Charts documentation](https://tradingview.github.io/lightweight-charts/docs).
