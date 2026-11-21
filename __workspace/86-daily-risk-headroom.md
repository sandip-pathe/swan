# Daily loss use and remaining risk headroom

Portfolio now reports the saved session loss limit, current loss used, risk
allocated to open positions and pending entries, and remaining headroom. The
calculation uses current session-opening equity, the account's reviewed daily
loss percentage, the portfolio's fresh liquidation estimate and existing risk
reservations. Remaining headroom is floored at zero.

The panel is unavailable unless the portfolio reconciles, valuation is fresh and
the stored opening baseline belongs to the current IST session. An active daily
block remains visible even if the arithmetic shows positive headroom; this display
cannot unlock entries or bypass existing risk checks.

This is session risk capacity, not a realized-only daily loss metric. Exposure
breakdowns and slippage remain open under D14; slippage is not fabricated from
limit prices or fill prices without defensible reference observations. No tests or
build checks were run. No broker, market, news or AI request was made.
