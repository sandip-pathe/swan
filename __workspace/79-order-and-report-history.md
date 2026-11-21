# Order and daily-report history pages

The order timeline now pages related entry/exit orders beyond the first 50. The
cursor must reference an order owned by the account and linked to the same
position. Event history retains its existing separate cursor. Loading one list
preserves the other, appends without duplicates, and retries without clearing
loaded rows.

The daily report now pages dated fills 20 at a time in timestamp/UUID descending
order. Its fill cursor is checked against account ownership and the selected
IST day window. Counts and financial totals continue to cover all dated fills;
page requests do not narrow the report totals. A failed request retains displayed
fills and its cursor.

These are individually consistent request snapshots, not a frozen snapshot across
pages. Refresh the report or timeline to see later corrections/new records. The
risk decision page may still report an independent linked-order cap of 100; see
checkpoint 77. D16/D20 remain open for that edge, report activity limits, broader
query/load qualification, and evidence acceptance. Tests/build checks were not
run for this slice. No broker, live market or permission operation was performed.
