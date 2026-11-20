# Recorded model and local-rule versions

Evaluation history includes a Models and rules disclosure. New AI_RESERVATION
records carry explicit evaluation/context IDs, the exact requested model and
SHA-256 fingerprints of instructions and response JSON schema. Reservations persist
before HTTP, so a failed request retains request metadata. Valid completed outputs
record the provider-returned model field when present. The pipeline context records
the unchanged agents-v1 strategy label and a pipeline-source fingerprint computed
when that module loads. The accepted envelope uses the same strategy label.

The read-only owned projection links request -> unique matching response -> owned
same-evaluation context by IDs. It does not read current settings for history.
Missing/invalid model names, absent metadata, duplicate/mismatched responses and
foreign context links remain unavailable. Results are capped at 20 requests with
explicit truncation. Response scans are capped; overflow suppresses ambiguous
reported-model claims. UI exposes plain names, strategy label and fingerprint
recorded/unavailable status, without raw hashes cluttering the main history.

Source: [official Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
documents the response model field. A returned name is provider metadata, not
proof of immutable weights. Prompt/schema/pipeline fingerprints do not snapshot
all dependencies, environment, provider state or risk/configuration artifacts.
D17 remains open for those guarantees where available, billing, failed/incomplete
usage and historical allowance/usage views. D16/D20 pagination/index/load and
connected/manual acceptance remain in the deferred ledger. Existing credentials
and model selection are unchanged; only mocked HTTP responses were used in tests.
Next slice: historical analysis allowance and usage by IST day.

Verification: 317 backend tests; Ruff; mypy 89 modules; 13 frontend tests;
TypeScript and production build passed. New disposable-schema/mock-HTTP tests
compare recorded metadata to the actual sent request, preserve it across settings
changes, cover missing provider model, failed requests, duplicate outputs, foreign
contexts, legacy/invalid records and truncation. Six responsive sizes pass long
model-name wrapping, nested disclosure, missing metadata and legacy empty states;
reviewed the 390px screenshot. Activity regression and public PWA smoke pass.
Managed API/idle worker restarted; actual orders/manual intents/enabled accounts
remain zero and mode OBSERVATION. No live API call, login or trading activation.
