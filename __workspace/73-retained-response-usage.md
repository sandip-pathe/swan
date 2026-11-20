# Retained response usage

The provider now saves a minimal AI_RESPONSE_USAGE receipt after a bounded HTTP-200
JSON object is parsed, before completion/refusal/structured-output checks. Only
owner/request/evaluation/context/role links and valid nonnegative token counters
(total/input/output and declared cached/reasoning breakdowns) are retained; raw body, error text and extra usage fields are not copied into this
receipt. Missing/invalid totals stay absent and are not reconstructed from other counters. Output validation still rejects
incomplete/refused/malformed responses; malformed block structures are rejected
cleanly rather than escaping with AttributeError. No trading gate is relaxed.

Daily usage prefers a unique receipt per owned reservation. A mirrored AI_OUTPUT
is not added again; old output-only records remain supported. Duplicate receipts,
invalid totals or conflicting receipt/output totals are unknown. Late receipts
follow reservation day. UI adds Usage without saved output and explains that
reported usage is neither a valid model output nor trading approval or billing.
The new audit kind is hidden from generic account activity and represented by
user-facing usage totals instead.

The [official Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
is the source for supplied response usage metadata. No live API request was made.
Non-200/oversized/non-JSON/transport-lost/cancelled responses and unavailable audit
storage can still lack totals. Reservation allowance is not refunded, and actual
provider billing is not reconstructed. D17 remains open for those limits and
provider/reproducibility guarantees. D16/D20 retain bounded-history pagination and
index/load qualification. Next slice: paginate evaluation output/check history.
Broker/login/live/manual acceptance remains skipped; no milestone-complete claim.

Verification: 335 backend tests; Ruff; mypy 89 modules; 13 frontend tests;
TypeScript and production build passed. Mock-HTTP/disposable-schema cases cover
valid output, incomplete/refused/invalid-schema/block responses, missing/bool/zero
usage, non-200/non-JSON responses, deduplication, conflicts and legacy fallback.
Historical tests cover late receipts without double counting. Six mobile/desktop
sizes pass current and historical usage states, stale-date suppression and no
overflow; reviewed the 390px usage screenshot. Public PWA smoke passes. Managed
API/idle worker restarted; actual orders/manual intents/enabled accounts remain
zero and mode OBSERVATION. Existing credentials/model selection are unchanged.
