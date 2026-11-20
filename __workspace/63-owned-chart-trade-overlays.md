# Owned chart trade overlays

Implemented 20 November 2026. Contract charts now show owned paper fill markers
and the current open position's average entry, stop and target levels. This is
read-only chart context, not a new order or permission path.

## User behavior

Show/Hide my trades controls annotations in candle and line modes. Buy fills use
up arrows and B labels; sell fills use down arrows and S labels, at actual fill
prices. Each fill is aligned to an existing candle interval inside a verified
session. Missing candles, unknown sessions, future observations and shortened
session boundaries never move a fill onto a nearby candle. Fills without matching
candle coverage remain in an accessible recorded-fill list with exact time,
quantity, price and order-history links. Candles and indicators are unchanged.

Current-day open positions show named Entry, Stop and Target price lines. When
multiple positions exist, the user chooses one to avoid overlapping level sets.
The accompanying values list remaining units and pending-exit reason, with a
link to the position's order history. Pending exit orders are identified separately;
settings or order presence do not guarantee execution. Levels outside the visible
price range remain readable in the values list.

Historical dates show fills only; current position levels are never painted onto
an earlier date. Closed positions retain their fill history and lose their current
level lines. Stale snapshots or failed updates remove current position lines.
Immutable last-recorded fills can remain visible with their snapshot timestamp.

## Data and isolation

GET /api/paper/chart-trades accepts instrument_id and an IST calendar day. It
reads authenticated owned fills, current positions and pending SELL orders in a
repeatable-read snapshot. Fill timestamps use the half-open IST date interval.
Only current-day requests include open position settings. All reads are scoped to
the selected contract and owner, with whitelisted fields and no provider calls,
mutations or private configuration payloads.

Limits are latest 200 fills per day, 20 current positions and 100 pending exit
orders, with explicit truncation flags. The UI does not claim full exit coverage.
Retained reads poll every five seconds only on the visible chart surface; hidden
browser pages pause requests. Instrument/date changes abort obsolete requests
and reject mismatched data. Current levels expire locally after 15 seconds or
at a date rollover. No private chart trade data is persisted or PWA-cached.

A separate invisible line series carries annotations so fills and price lines
remain available when candle/line display modes change. Markers render above
other series. The installed Lightweight Charts API was checked before use.

## Verification

276 backend tests pass, including four new integration cases covering retained
fills, current position/protection links, read-only state, contract/owner/date
isolation, historical-date restrictions, closed positions and input bounds.
Ruff and mypy (80 modules), thirteen frontend tests, type checking and production
build pass. Three new frontend cases verify marker alignment, actual prices,
resampling, missing intervals, unknown/shortened sessions, future data, invalid
prices and deterministic ordering.

Browser fixtures cover actual chart rendering in candle/line modes, 5m switching,
show/hide, a fill in a candle gap, pending exits, failed update removal, closed
positions and responsive overflow at 360, 390, 430, 768, 1440 and 844 landscape
pixels. Existing workspace interactions remain green. The managed API was
restarted; the local mobile sign-in/PWA smoke check passes with only the offline
fallback cached. The actual account still has zero orders/manual intents, no
enabled entries and an OBSERVATION worker. Broker login/live-market
checks remain skipped at the user's request; M3 live evidence is not complete.

## Next slice

Continue M7 with user-facing agent activity and decision/risk/execution explanations
from recorded evidence, including WAIT and provider failures. Preserve bounded
manual permissions and the remaining qualification/fee/depth evidence gates.
