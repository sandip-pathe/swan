# Decision to linked-order bound

A decision page contains at most 20 DecisionRecord rows. PaperOrder has a unique
constraint on decision_id, so each row can link to no more than one entry order.
The earlier 101-row query and 100-order truncation warning were unreachable through
the supported schema and could imply records were omitted when they were not.
Removed the artificial query cap, flag and warning. This does not include exit
orders, whose correlation is through position_id and whose timeline/related-order
view is separate.

This corrects checkpoint 77 and the order/report checkpoint 79 notes. D16/D18/D20
remain open for daily-report activity limits, source suitability, other bounded
surfaces and integrated load/security/recovery qualification. Tests/build checks
were not run. No live or permission operation was performed.
