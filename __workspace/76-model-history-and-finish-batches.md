# Model history and grouped finish path

Model requests in evaluation history now use newest-first 20-row keyset pages,
scoped to owner, evaluation and AI_RESERVATION kind. Equal timestamps use UUID
ordering. Invalid/missing/foreign/wrong-run/wrong-kind cursors share a 400 response;
malformed UUIDs return 422. The existing nested request index supports this query.
Outputs and checks retain independent cursors. Model pages append/deduplicate only
their own list, share abort/generation protection and retain rows on retry.

The older combined truncation flag conflated extra reservations with overflowing
linked outputs. Model pagination now has its own next_before/truncated fields;
outputs_incomplete separately warns that response metadata could not be verified.
The 201-output defensive read remains bounded; overflow never becomes a fabricated
model revision. Requested names remain visible and reported names stay unknown.
Immutable provider revisions, billing and historical gaps remain D17.

Verification: tied-timestamp 45-request traversal without duplicates/gaps; foreign,
wrong-run, wrong-kind, missing and malformed cursors; independent output/check
pages; output-overflow warning distinct from pagination. Frontend typecheck,
13 tests and production build pass. Six browser sizes cover model-page retry,
deduplication, retained rows and metadata warning alongside existing output/check
paging and stale-close checks. All 343 backend tests, Ruff and mypy (89 modules) pass. Public PWA smoke
passes; managed API restarted. Actual orders/manual intents/enabled accounts
remain zero, runtime OBSERVATION. Reviewed the 390px history screenshot.

## Finish batches

Use larger coherent batches, one reviewable commit per batch or independently
reviewable component. Run focused checks during editing and the appropriate full
checks once at the end; repeat only for new changes or unresolved failures. Keep
DEFERRED-WORK.md as the canonical scope/evidence ledger. This grouping is not a
claim that each batch takes one turn or that acceptance is already complete.

1. Agent transparency: risk-decision paging is delivered in checkpoint 77 and
   richer citation ages in checkpoint 78. Remaining order/report history paging
   and source/age acceptance (D16), plus version/usage guarantees and pricing
   attribution (D17), remain open.
2. Trading workflow and reporting: pending chart markers, permission/order-type
   lifecycle, bulk exits/modifications, risk/trade statistics, historical equity
   and journal/export requirements (D11-D15). Preserve reservation and fill-race
   semantics; do not introduce controls that merely look functional.
3. Market analytics: complete the supported feature inventory and implement
   defensible studies/option analytics using available input coverage (D10).
   Keep strategy research/performance validation explicit (D19), not an implied
   result of adding indicators. Extended tools remain a scope decision (D22).
4. Integrated qualification: recovery/security/concurrency/load checks (D20),
   then broker/market/phone checks only when the user resumes them (D01-D09).
   Provider depth, fees, calendars and news suitability need actual authoritative
   evidence (D03-D06/D18), not fixture completion. Track the unresolved pieces.
5. Supervised operation and handover: after qualification, the planned one-to-two-
   week paper observation period, reconciliation, incident handling and recovery
   handover (D21). Elapsed real observation cannot be replaced by automated tests.

Next implementation batch: bounded order and daily-report history paging under D16.
No broker login/live refresh/arming is authorized by this plan. No milestone is
closed merely because implementation tests pass.
