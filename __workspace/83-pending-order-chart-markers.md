# Pending-order chart markers

The contract chart already marked actual fills and drew current position entry,
stop and target levels. It did not show working orders separately. The owned
chart-trades response now includes active orders for the selected account,
instrument and IST date. The mobile chart marks pending BUY entries with `P` and
pending SELL exits with `X`, distinct from the filled BUY/SELL arrows. A list
below the chart shows each working order's side, type, remaining units, status,
recorded price and timestamp.

For a marker, the display uses the order limit price, falling back to trigger price
when there is no limit. It plots only when order time maps into verified session
candle coverage. Orders outside visible/verified coverage remain in the details
list and do not get snapped onto an unrelated bar. Working orders are not fills;
the order pipeline and permission gates are unchanged.

The response is capped at 200 pending orders per instrument/day and reports when
older rows are omitted. Paging and lifecycle alignment review remain open under
D11/D20. No tests/build checks or live-market, broker, or provider operations were
performed.
