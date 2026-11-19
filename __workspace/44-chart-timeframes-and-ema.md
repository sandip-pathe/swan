# Chart timeframes and EMA

Implemented 19 November 2026, continuing checkpoint 43 and M5 chart tools.

**Markets → Chart** now offers 1m/5m/15m, candle/line views and an optional EMA 20
overlay. Session and history controls remain shared; changing the chart view makes
no broker request. The selected contract, date and cached source data stay the
same. Normal chart polling continues to read the database only.

The candle endpoint now returns calendar sessions. Five- and fifteen-minute bars
are derived in the browser from reconciled one-minute bars, anchored to verified
session opens, including shortened sessions. They are not separate provider bars.
The initial cached read covers the selected IST date; explicit history retrieval
uses its verified session open/close instead of the earlier fixed 15:30 cutoff.
Open/close use first/last constituent prices; high/low use their extrema. Volume
is summed only when every constituent has volume. A missing elapsed minute
suppresses that larger candle and leaves a gap. An incomplete current interval is
marked forming; a sliced historical interval is not presented as complete.
Unknown/unverified sessions cannot produce larger bars or EMA.

EMA uses completed closes from the selected timeframe. Its first value is the
arithmetic mean of 20 consecutive closes; subsequent values use
`previous + (2/21) × (close − previous)`. It resets at every session or gap and
excludes forming candles. Fewer than 20 consecutive completed candles means
unavailable. Observed-stream closes retain their sampling limitations. These are
analysis values, never execution prices or evidence that permits entries.

Line and EMA runs use separate plotted series around gaps so the renderer cannot
draw artificial continuity. The EMA has an explicit label and dashed amber line;
its value appears beside volume in the OHLC readout. A collapsed explanation
documents its scope and formula. The text candle view follows the selected
timeframe and identifies combined broker/observed data.

## Verification

- Five Node tests cover alignment, OHLC/volume, missing inputs, shortened and
  forming sessions, range clipping, EMA seeding/recursion and gap/session resets.
- Ten focused backend candle tests pass, including session metadata delivery.
- Isolated browser checks exercise all three timeframes, candle/line switching,
  EMA, zoom/fit, touch gestures, empty/error/offline states and browser navigation
  across six viewport sizes, with no horizontal overflow or runtime errors.
- No market fixture is written into the actual account database. No execution,
  qualification, fee or entry permission path changes.

A read-only pass over the saved 376-bar NFO response produced 75 five-minute and
25 fifteen-minute bars. Each larger view flagged the clipped final interval as
missing, instead of treating its lone 15:30 minute as a full larger bar. This
exposed the earlier fixed-close request window and led to the session-boundary
correction above. No new provider call was made by that check.

Live open-market acceptance and physical-phone review remain outstanding as
described in checkpoint 43. Search/watchlists, richer instrument/chain details,
other studies, drawings and paper order tickets remain later work.
