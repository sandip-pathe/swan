# Chart studies and device preferences

Implemented 20 November 2026 as a frontend-only M5 slice. M3 still needs actual
open-market/reconnect acceptance evidence. The user renewed broker login and
asked to handle price refresh themselves; no provider requests or worker restarts
were performed for this slice.

## User flow

Open a contract chart and expand Moving average. Choose EMA or SMA, then a
9, 20, 50, 100 or 200-candle period and Show average. The existing chart toolbar
also toggles the selected average. Its label and crosshair readout follow the
chosen type and period. About the average explains its formula and missing-input
rules. Controls retain 44px touch targets, 12px form spacing and mobile font sizes.

The selected timeframe (1m/5m/15m), candle/line style, average type, period and
visibility are stored in swan.chart.preferences.v1 on this browser/device. Choices
carry across contracts and reloads. Storage contains presentation fields only;
contract selection, sessions, quotes, credentials and account permissions are not
stored there. Invalid fields revert individually to defaults, and unavailable
storage leaves the chart usable for the current mount.

## Calculation

Both studies use completed closes from verified sessions only. Each contiguous
run starts independently; a missing or forming candle breaks the run. Neither
study bridges a session boundary. Until the selected period is available, the
readout explains the missing candle requirement rather than displaying zero.

SMA is the equally weighted mean of the latest selected number of closes. EMA
starts with that mean, then updates as previous + 2/(period+1) * (close-previous).
The displayed value follows the crosshair candle or latest candle. A provisional
candle has no computed study value. This is chart analysis and has no effect on
order prices, risk settings, agents, entry permission or execution evidence.

## Validation

Eight Node tests pass: existing resampling/alignment/volume/gap checks, default
EMA compatibility, selected-period SMA/EMA numerical results, invalid periods,
forming/gap/session resets and damaged/untrusted preferences. Frontend type
checking and production build pass. The backend was unchanged; its preceding
full suite passed 177 tests.

Browser checks use isolated in-memory data, never production seed prices. All
six sizes (360, 390, 430, 768, 1440 and landscape 844) pass navigation, study
selection, readout, insufficient data, reload persistence, chart interaction,
search/watchlist and offline checks with no overflow or browser exceptions.
The actual localhost mobile sign-in/PWA smoke check passes. Visual review used
the 390px screenshot. API and worker were left running for the user's session.

Next focused chart slice: RSI in a separate pane, with explicit warm-up and gap
handling. VWAP still needs dependable volume semantics. Live reconnect acceptance
remains separate from these chart feature checks.
