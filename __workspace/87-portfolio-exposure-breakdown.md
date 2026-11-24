# Portfolio exposure breakdown

The Portfolio view now groups open positions and pending BUY entries by
instrument. It shows remaining open units, entry cost basis, recorded planned
stop risk, pending units, pending limit notional where complete, and risk
reserved for pending entries.

Cost basis is deliberately labeled separately from fresh liquidation value. If
any pending entry in an instrument group has no limit price, pending limit
notional is shown as unavailable instead of summing only the priced subset.
Exposure is suppressed when account reconciliation fails. Stop risk remains a
saved estimate, not a guaranteed maximum loss. Slippage remains unavailable
without defensible reference observations.

This closes the remaining exposure breakdown implementation in D14. No broker,
market, news, or AI request was made; no permission gate changed.
