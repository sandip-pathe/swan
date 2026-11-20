# RSI chart pane

Implemented 20 November 2026 as a focused frontend-only M5 slice.

## Behavior

RSI 14 On/Off adds or removes a separate lower pane inside the same Lightweight
Charts instance. It shares the selected contract, session, timeframe, timeline,
zoom and crosshair with the price chart. It has a 0-100 scale and labeled 30/70
reference guides. The chart grows when RSI is enabled to keep both panes readable
on a phone. Visibility is saved with the existing device-local preferences; old
preferences default RSI to off. No new provider reads or account permissions.

The RSI readout follows the selected candle, or the latest candle when no
crosshair is selected. Insufficient data is shown as unavailable, not zero.
About RSI 14 explains the calculation and the session-reset policy.

## Calculation and limits

Use 14 completed close-to-close price changes, requiring 15 consecutive completed
closes. Seed average gains/losses with the arithmetic mean of the first 14 changes;
subsequent averages use (previous * 13 + current gain/loss) / 14. RSI is
100 - 100 / (1 + average gain / average loss). All gains returns 100, all losses
returns 0, and a flat seed with neither gain nor loss uses an explicit neutral 50.

Missing and provisional candles break the calculation run. Restart at each verified
session boundary; never carry hidden prior-session state or bridge a data gap.
This policy can differ from broker indicators that carry earlier history forward.
RSI is chart analysis only and does not alter strategies or execution permission.

Reference: [TradingView RSI documentation](https://www.tradingview.com/support/solutions/43000502338-relative-strength-index-rsi/).
Pane APIs were checked against the installed Lightweight Charts type declarations.

## Verification

Ten frontend tests pass, including numerical Wilder seed/smoothing values,
rising/falling/flat cases, forming bars, gaps, session resets and preference
validation. Type checking and production build pass. The backend was unchanged;
its preceding full suite passed 177 tests.

Browser fixtures cover all six established widths, repeated pane add/remove,
no pane accumulation, reload persistence, insufficient 15m data, synchronized
chart controls, offline fallback and existing search/watchlist flows. No overflow
or browser exceptions were found. Visual review of the 360px screenshot caught
inherited price-axis margins extending beyond RSI bounds; the RSI scale now uses
small RSI-specific margins with its explicit 0-100 range, keeping values at 0/100
visible at pane edges. Fixture data stays isolated from the
running application. The actual localhost sign-in/PWA smoke check passes.

The user's price refresh and worker session were left alone. M3 live/reconnect
acceptance remains open. Next chart work should address usable range selection or
paper fill/position overlays; VWAP still depends on reliable volume semantics.
