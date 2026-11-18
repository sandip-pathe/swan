# Controlled paper validation lifecycle

Implemented 18 November 2026. This milestone supplies bounded session controls and evidence records. Actual-market validation and autonomous qualification remain incomplete.

## Behavior

- An authenticated owner explicitly starts a session for one contract, one entry attempt and at most one actual lot. The requested window is 60–900 seconds, shortened by broker expiry, connection-evidence expiry and the entry cutoff.
- Start requires a flat, reconciled, paused account; current account revision and session baseline; a validation-mode worker with a recent heartbeat; complete shared configuration and connection checks; eligible current contract metadata; and actual fresh exchange-timestamped best-five depth. Unknown depth units or unreviewed fees block start.
- Only a real approved strategy may trigger an entry. Existing deterministic sizing, fee, reservation, market-depth, latency, freshness, price protection and risk checks apply. Admission and every buy fill recheck the session. Database constraints and account locks enforce one live session and one entry order per session.
- The input digest binds service code, all setup documents, account policy and provider configuration/session fingerprints. Only digests are stored for private provider inputs. Changes, stream-generation changes, stale heartbeat, expiry, pause, worker shutdown or restart stop new entries. A late agent result cannot restore a stopped session's intent.
- Stop first enters `STOPPING`. The independent execution watchdog cancels pending entries and continues protective exits using the entry's frozen execution model. Unavailable depth can leave exposure unresolved; stopping never fabricates an exit. Completion requires no active orders, no open positions and successful reconciliation.
- A completed record includes order/fill references, original market event and snapshot references, quantities, prices, fees and fee versions. A session without fills is recorded as `NO_TRADE_OBSERVED`. Neither result grants autonomous qualification.

## Operator flow

1. Complete the outstanding evidence in **System setup**. Refresh the explicit broker, catalog, stream, AI access/schema and news diagnostics. Use private broker login when required.
2. With the account flat, run `local.cmd worker-stop`. This stops only the managed observation worker; web and API remain running. Exit monitoring is unavailable until the replacement worker starts.
3. Run `market.cmd worker --local-owner --validation-only` and keep the terminal open. This prepares the worker without starting an entry window. The singleton account lock prevents concurrent workers.
4. In **Option chain**, copy the actual contract ID. Open **Paper validation**, enter the contract and duration, and explicitly start the session. A strategy may wait or reject; a trade is not guaranteed.
5. Use **Stop session and manage exits** or the general pause control to stop entries. Follow Execution until all exposure resolves. Review the validation record and source evidence.
6. After the account is flat and reconciled, stop the manual worker with Ctrl+C and run `local.cmd start` to restore the managed observer. Restart never rearms a validation session.

`local.cmd start` continues to start an observation-only worker. General Resume cannot replace the explicit validation start flow. No real broker order route was added.

## Verification

- 106 Python tests passed in disposable PostgreSQL schemas, including the existing lifecycle suite and new start/preflight/scope/idempotency, one-lot admission, stop/expiry/restart/input/stream invalidation, late-agent, owner-isolation and no-autopromotion checks. A final 24-test focused rerun also passed, including the additional observer-restart regression. Provider boundaries use isolated test inputs; these are not live-market evidence.
- Ruff and mypy passed (52 service files). Frontend type checking and the production build passed. Browser fixtures passed at 1440, 735 and 390 pixels for blocked setup, explicit start, active cap, stop, no-trade report and unavailable status. All browser mutations were intercepted. Screenshots and harness: `.local/qa-validation-20261118/`.
- Additive migrations through `b7a1cde32902` are applied locally, including binding each in-flight evaluation to its original validation session. Existing history is preserved. The local account remains disabled; the managed worker reports `OBSERVATION_ONLY`; there are zero orders, fills and validation sessions. An attempted start in observer mode was rejected with `VALIDATION_WORKER_REQUIRED` before any write.
- `local.cmd worker-stop` was exercised: API health and the web root remained available while the managed worker stopped. `local.cmd start` restored the observation worker.

## Remaining blockers

Actual depth quantity semantics remain unverified. Both fee schedules require review and rounding evidence; the BFO IPFT component/evidence is incomplete. These gates were preserved. No actual-market session was started and no execution or profitability claim follows from isolated tests. After evidence is resolved, collect actual fresh-market execution/protection/recovery evidence for both venues and review qualification separately.
