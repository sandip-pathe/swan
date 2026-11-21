# Closed-position statistics

The portfolio adds a concise closed-trade statistics section. It uses reconciled
closed positions and their recorded net realized results. A position is the sample
unit, including when it was closed through multiple partial fills.

Displayed measures are closed-position count, win rate, mean positive/negative
result, mean net result per closed position (expectancy), profit factor, average
holding time, and a realized-only peak-to-trough drawdown. Drawdown follows closed
positions in close-time order from a zero realized baseline; it is not account
equity drawdown and excludes funding, open P&L and market marks. A measure without
its required sample (such as profit factor without a loss) remains unavailable.

Results are streamed from the account's closed positions in database batches so
the API does not need to retain an unbounded list. Slippage, daily loss/headroom,
exposure and broader session/sample definitions remain open under D14. No
performance claim or trading permission is inferred from these historical values.
No tests/build checks or live/provider operations were run.
