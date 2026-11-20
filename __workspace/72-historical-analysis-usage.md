# Historical analysis allowance and usage

Account activity > Analysis allowance now has an IST date selector. The owned
read-only API accepts an optional day (default today), rejects future/invalid
dates, and selects reservations in that IST calendar day. Usage outputs are joined
by exact owner/reservation ID so a response saved after midnight remains attributed
to its request day. Reported usage remains separate from conservative reservation
units, with missing/duplicate/invalid usage unknown and monetary cost unavailable.

New reservations save the exact daily allowance used by their budget guard.
Past-day views do not read today's settings. Uniform valid saved limits yield a
recorded request allowance and unused allowance against that limit; these do not
claim final day-end settings. Missing/mixed limits, including legacy or empty days,
leave historical allowance unavailable. Current-day behavior remains explicitly
based on current configured settings. No reservations are refunded or gates relaxed.

Date changes abort/ignore stale responses, clear previous results, and handle a
blank date without retaining old totals. Historical missing allowance is a normal
notice rather than a broken-account alarm. Model configuration is not presented as
historical fact. D17 remains open for failed/incomplete response usage, billing,
provider revision/reproducibility limits and any final historical configuration
timeline; D20 retains query/index/load qualification. Broker/live/manual acceptance
remains skipped. Next slice: retain supplied usage for incomplete/invalid responses.

Verification: 324 backend tests; Ruff; mypy 89 modules; 13 frontend tests;
TypeScript and production build passed. Added tests cover historical stored limits,
late linked usage, no current-settings reads, read-only revisions, legacy/empty/
invalid/mixed budgets and future/invalid dates. Existing mock-provider tests verify
allowance persistence. Six-size browser fixtures pass date changes, deliberately
late stale responses, changed limits, blank-date clearing, no overflow and current
retry/unknown/empty states; reviewed the 390px historical screenshot. Public local
PWA smoke passes. Managed API/idle worker restarted; actual orders/manual intents/
enabled accounts remain zero, OBSERVATION mode. No live AI request or activation.
