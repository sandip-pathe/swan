# Risk-decision history paging

Evaluation history now loads linked risk decisions in bounded pages of 20. The
cursor is scoped to the accepted strategy by checking both account ownership and
strategy ID. It uses stable ascending decision-ID order to preserve the existing
display sequence and returns a separate continuation cursor. Invalid or foreign
cursors share the existing run-cursor error. The UI appends only new decision IDs,
offers retry while retaining loaded rows, ignores stale responses after close,
and reports the independent linked-order cap.

This page limit prevents old risk-decision history from silently disappearing
after the first 20 decisions. Each decision can have at most one linked entry order by the database
one-entry-per-decision constraint, so a 20-decision page can link at most 20 such
orders. Individual order timelines have their own event cursor. Daily-report fill
paging, richer source/age evidence, and broader query/load qualification remain
separate follow-up items. No decision result creates trading permission.

No broker, market, manual, or trading permission operation was performed.
Implementation was not run through tests or type/build checks in this slice.
