# Complete daily-report activity totals

Daily paper reports previously loaded at most 2,001 agent-output and evaluation
events, then withheld all decision totals when a day exceeded 2,000. The report
now reads the selected IST day in ascending, 500-row keyset batches and folds each
batch into the same five counters. It no longer requires all matching audit rows
in memory at once, and totals are not silently truncated at an arbitrary row cap.

Each page uses `(timestamp, id)` ordering inside the same repeatable-read report
transaction. Invalid or unrecognized records continue to count as unclassified;
the counters remain counts of recorded stages, not unique trades or permission to
trade. Fill pagination, financial totals and their reconciliation rules are
unchanged.

This removes the report-activity completeness gap for arbitrarily long days, but
does not qualify worst-case query duration or database load. Integrated query/load
qualification remains D20. No tests/build checks were run. No live market, broker
login, external news or provider request was performed.
