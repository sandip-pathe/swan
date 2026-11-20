# Quote order and path to completion

Implemented 20 November 2026 after the user confirmed price refresh works and
reported that the latest quotes appeared at the bottom of Markets / Option chain.

## Fix

The chain previously used ascending strike order in both database pagination and
frontend grouping. That order did not reflect quote age. Latest quotes first is
now the default; a strike pair ranks by the newest exchange timestamp of either
side, with ascending strike as a deterministic tie-break. Calls and puts remain
together. The UI retains an explicit Strike: low to high option.

The API groups/ranks strikes before applying pagination, then orders the returned
pairs consistently. This is not a page-only reversal. Changing order resets the
page and cancels the old UI request. Exchange timestamps are unchanged; a newer
retrieval time cannot promote an old quote. The Home market preview follows the
same chain response. No provider reads, worker restart or trading activation.
Only the managed API was restarted to load the handler change.

Verification: all 178 backend tests, ten frontend tests, Ruff, mypy, frontend
production/type checks and six browser layouts pass. Regression coverage gives
the highest of 51 strikes the newest quote on only one side and confirms both
sides lead the first page, the final page remains correct, strike order remains
available and invalid sort values fail. The local mobile sign-in/PWA smoke check
passes. Existing private/local setup edits were excluded from the commit.

## Current milestone truth

M3 implementation includes historical storage/backfill, observed candles, chart
intervals, quote retention and bounded subscriptions. The user's renewed login
and working refresh establish successful quote refresh, not the entire M3 gate.
Actual provisional-bar updates, same-provider value comparisons and controlled
reconnect/gap recovery still need recorded acceptance evidence.

M4/M5 work has already progressed alongside M3: mobile PWA, search/watchlist,
paired chain, details, candle/line chart, configurable EMA/SMA and RSI exist.
Those milestones are partly implemented, not future blank slates.

## Recommended finish order

1. Close M3 with bounded actual-market observations and a controlled reconnect
   exercise. Preserve honest gaps and verify both supported venues within scope.
2. Complete the core M4/M5 trading workspace: verified depth presentation,
   reference/ATM context and paper fill/position/protection overlays. Treat further
   indicators and extended tools as lower priority than the order flow.
3. Implement M6 manual paper intent and a mobile order ticket through the existing
   risk/ledger path. Then supported cancel/exit, order/fill timeline, fees and
   reconciled cash/equity/P&L. No fake AI approval and no real broker orders.
4. Complete M7 user-facing agent decision/risk/execution explanations and daily
   reports from actual evidence; record WAIT and provider failures distinctly.
5. Complete M8 integrated recovery/security/load tests and the declared bounded
   actual-market qualification matrix. Preparing a mode never arms entries.
6. Run M9 supervised paper observation and reconciliation for the planned one-to-
   two-week period, with stop conditions and a tested handover/recovery guide.

M1/M2 foundations exist, but unresolved depth quantity units, fee/rounding evidence
and BFO IPFT remain execution dependencies. Calendar coverage ends 30 November
2026 and must be maintained. Qualification and explicit permission are still
required before autonomous paper operation. Extra studies, drawings, broad news
and advanced analytics remain in the master backlog; postponing them from the
critical completion path does not mark them implemented.
