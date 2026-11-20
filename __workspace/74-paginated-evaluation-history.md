# Paginated evaluation history

Evaluation history now shows model outputs and stage checks newest first, with
independent Load older controls. GET run accepts optional outputs_before and
checks_before UUID cursors. Every cursor must be an existing audit event of the
same owner, evaluation and collection. Invalid/foreign/wrong-kind/wrong-run cursors
return the same 400 error; malformed UUIDs return 422. Descending timestamp/UUID
keysets load 20 records with a next cursor, preserving deterministic ties and
bounded reads. Missing/invalid records remain visible as unavailable rows.

The client appends only the requested collection, deduplicates IDs and preserves
already-loaded metadata, evidence and the other list. A failed older-page load
keeps rows/cursor and offers retry. Closing/reopening aborts pending pagination and
invalidates stale callbacks. Reopening starts a fresh first page. Page reads use
repeatable-read individually, not a frozen full-history snapshot; new newer rows
appear on refresh rather than entering an already-requested older page.

D16/D20 remain open for model-version/risk/order/report pagination and query/index/
load qualification. Other list limits still show explicit notices. No trading
behavior, broker login or live/manual acceptance was exercised. Next slice:
history query indexes and bounded load checks. M3/M7 acceptance remains incomplete.

Verification: 340 backend tests; Ruff; mypy 89 modules; 13 frontend tests;
TypeScript and production build passed. New disposable-schema tests page 45 outputs
and 43 checks with tied timestamps, concurrent newer insertion, no gaps/duplicates,
independent cursors, read-only state, and invalid/foreign/wrong-kind/wrong-run
cursor rejection. Six-size browser fixtures cover independent append, retries,
deduplication, end-of-list controls and close/reopen stale-response suppression,
without overflow; reviewed the 390px screenshot. Existing activity/history and
public PWA smoke pass. Managed API restarted; actual orders/manual intents/enabled
accounts remain zero, runtime OBSERVATION. Deferred ledger updated.
