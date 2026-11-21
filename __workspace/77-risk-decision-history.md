# Risk-decision history paging

Evaluation history now loads linked risk decisions in bounded pages of 20. The
cursor is scoped to the accepted strategy by checking both account ownership and
strategy ID. It uses stable ascending decision-ID order to preserve the existing
display sequence and returns a separate continuation cursor. Invalid or foreign
cursors share the existing run-cursor error. The UI appends only new decision IDs,
offers retry while retaining loaded rows, ignores stale responses after close,
and reports the independent linked-order cap.

This page limit prevents old risk-decision history from silently disappearing
after the first 20 decisions. Orders linked to each page remain bounded to 100;
overflow is explicitly surfaced. Individual order timelines already have their
own cursor. D16/D20 remain open for making every order visible within dense
decision pages, daily-report fill paging, richer source/age evidence, and broader
query/load qualification. No decision result creates trading permission.

No broker, market, manual, or trading permission operation was performed.
Implementation was not run through tests or type/build checks in this slice.
