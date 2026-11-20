# Linked evaluation history

Account activity now offers Evaluation history on model/evaluation records. The
worker passes the existing durable evaluation slot ID into AgentPipeline; context
and future AI_OUTPUT events retain it. The owned GET activity/{id}/run endpoint
validates both the source event and slot owner before selecting only explicitly
linked model outputs. It uses a repeatable-read snapshot, timestamp/ID order,
safe typed summaries and bounded rationale. It returns current slot outcome and
first 20 model outputs with truncation flag, not raw payloads or response IDs.

The phone-first disclosure fetches on open, supports retry and unavailable states,
and can open each stage's existing evidence without closing the history. Older
model outputs without evaluation IDs remain unlinked. Older evaluation events with
valid slot IDs can show their outcome but do not acquire nearby outputs. Missing
stages are not invented. Pending slots stay pending after interruptions; failed
calls can lack saved outputs. Current slot status is distinct from model text.

D16 remains partially delivered: stage validation events, strategy/risk/order
correlation and richer evidence details remain open. History pagination and
query-index/load qualification are tracked in D16/D20. D17 version/billing/history
limits remain open. Next slice: persist validation outcomes before downstream joins.
Broker/login/live/manual acceptance remains skipped; no permission gates changed.

Verification: 292 backend tests; Ruff; mypy 85 modules; 13 frontend tests;
TypeScript and production build passed. New disposable-schema tests exercise
pipeline evaluation ID propagation, typed stage history, owner/legacy isolation,
read-only revisions, invalid stages, failure status and bounded truncation. Existing
mocked-provider test verifies evaluation ID reaches persisted output. Six-size
browser fixtures pass retry, nested evidence, unavailable legacy and overflow
checks; reviewed the 390px screenshot. Activity regression and local public PWA
smoke pass. API and idle observation worker restarted through the managed launcher.
Actual orders/manual intents/enabled accounts remain zero, mode OBSERVATION.
