# Daily report and deferred-work ledger

History now starts with a date-selectable IST daily paper report. Owner-authenticated
GET /api/paper/daily-report uses a repeatable-read snapshot of owned ledger records,
fills and recorded decision stages. It never requests broker data, inference or orders.
Today is provisional. Past days are calendar-day reconstructions, not immutable final
session certificates. Realized P&L uses cumulative entry cost allocation across partial
sales, including earlier-day entries; cash movement is separate and includes funding.
Historical open units use dated fills rather than the current position projection.
Reconciliation failure/undated fills suppress financial totals. Latest 20 fills link
to existing order history; daily totals include all dated fills. Activity counts are
stages, not unique trades, and are unavailable above 2,000 source records.

Created root DEFERRED-WORK.md with 22 stable IDs covering user skips, evidence gaps,
accepted remaining work and scope-review items. Each records reason and closure criteria.
Daily-report limits are included under D14/D15/D19/D22. AGENTS.md requires future
slices to maintain the ledger; README and RESUME link it for final review.

Verification: 283 backend tests; Ruff; mypy 82 modules; 13 frontend tests; TypeScript
and production build passed. Browser fixtures passed retry, date selection, empty and
unreconciled states at widths 360/390/430/768/1440/844, with no overflow/page errors.
Reviewed the 390px screenshot. Local public PWA smoke passed; offline cache contains
only /offline.html. API restarted through the managed local launcher.

Broker login/current-price/live-market/manual acceptance remain skipped per user.
Actual database retains zero orders/manual intents/enabled accounts; mode OBSERVATION.
M3 and M7 are not complete. Next slice: D17 recorded usage/budget/model visibility.
