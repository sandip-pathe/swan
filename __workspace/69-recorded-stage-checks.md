# Recorded stage checks

New pipeline evaluations persist AI_STAGE_CHECK audit events for analysis,
proposal, review and strategy stages, carrying explicit evaluation/context IDs.
Each stage covers generation and its existing validation. Success records only
after the executed branch completes; a valid WAIT or rejected review returns
without becoming an accepted strategy. Provider/format errors record safe fixed
reason codes and rethrow; cancellation records interruption and rethrows. Strategy
lifetime/envelope validation is recorded separately. Existing entry gates remain.

The owned evaluation history includes a separate bounded list of check results,
with fixed public explanations and no raw exception/provider payload. Unknown
stages/states are unavailable. Older histories have no inferred pass/fail results.
Each list is capped at 20 with explicit truncation. UI supports existing lazy load,
retry, nested evidence and mobile layout. No individual predicate or execution
permission is inferred from a stage result.

D16 remains open for strategy/risk/order linkage, detailed predicate outcomes and
richer evidence views. Pre-context failures, process death and unavailable audit
storage may lack stage-check results; missing never means success. Pagination/load
qualification remains D16/D20; model/version/billing gaps remain D17. Next slice:
explicit accepted-strategy to risk/order correlation. Broker/login/live/manual
acceptance stays skipped. No milestone completion or connected qualification claim.

Verification: 305 backend tests; Ruff; mypy 86 modules; 13 frontend tests;
TypeScript and production build passed. New disposable-schema scenarios cover WAIT,
invalid citations/news, invalid WAIT, incomplete proposal, rejected/missing-evidence
review, expired/accepted strategy, provider/format errors, interruption and safe
bounded invalid-record projection. Six responsive sizes pass check states, retry,
nested evidence and legacy unavailable history; reviewed the 390px screenshot.
Activity regression and local public PWA smoke pass. Managed API and idle worker
restarted. Actual account has zero orders/manual intents/enabled accounts and
OBSERVATION mode. No trading activation, broker login or manual acceptance performed.
