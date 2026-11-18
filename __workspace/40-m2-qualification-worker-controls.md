# M2: scoped qualification, explicit paper arming and worker preparation

18 November 2026. This milestone implements the lifecycle; it does not qualify or arm the local account. Fee rounding, BFO IPFT and depth-unit evidence remain unresolved.

## Operator workflow

Use **Paper controls** to prepare an observation, validation or autonomous worker while the account is flat and paused. Preparation is authenticated, loopback-only and limited to the enrolled single-owner local setup. It stops/replaces only the recorded managed worker and leaves web/API available. A manually launched worker may need to be stopped from its terminal first; the account singleton lock remains enforced. Do not expose this local supervisor through a public proxy/deployment.

Preparing a worker does not enable entries:

- Observation collects data and manages existing exposure without agent generation or entries.
- Validation remains idle until the owner explicitly starts a bounded session in **Paper validation**. Existing fee/depth/configuration gates still apply.
- Autonomous remains idle without agent generation until valid qualification and an explicit paper arm exist. A fresh genuine strategy and deterministic admission checks are still required afterward.

The old general Resume API/CLI cannot arm entries and now directs the owner to explicit paper controls. Pause/disarm, restart, changed inputs, expired permission, stale heartbeat, a stream-generation change, invalid preflight or a daily block remove entry permission. Independent protective exits keep using the entry's frozen execution model. Disarm is not a guarantee of an immediate fill or flat account; follow Execution until exposure resolves.

Worker preparation is a request, not proof of health: confirm the resulting mode, runtime status and heartbeat. Failure is audited and leaves entry intent disabled. `local.cmd start` defaults newly created workers to observation; it does not replace an already managed worker or implicitly rearm it. The CLI fallback remains available through the documented worker commands.

The supervisor waits within a bounded 45-second operation for initialization in the requested mode with a new heartbeat. It does not treat process creation alone as success. An interrupted mode-switch request becomes retryable after that window rather than permanently disabling the preparation controls. Initialization still does not establish feed freshness.

## Preregistered matrix: `paper-live-v1`

For **each of NFO and BFO**, original server-side records must establish:

1. A completed, reconciled buy/sell round trip with distinct qualifying market snapshots.
2. A protective stop order associated with the actual held position.
3. An actual stop-loss exit.
4. An actual target exit.
5. A user-stop cancellation of an accepted, unfilled entry.
6. A worker-restart session with clean durable recovery.
7. A recorded feed-gap/stream-change stop followed by resolved account exposure.
8. A recorded expiry followed by resolved account exposure.

A further rollover check requires qualifying round trips on at least two session dates and their actual `SESSION_STARTED` audit references. This is 17 checks. Missing scenarios stay unobserved. Do not force entries or manufacture gaps, fills or approvals to pass them. Bounded validation may need multiple sessions/days. Operational correctness tests and fee/depth calibration remain prerequisites; this matrix does not replace them or prove profitability.

Evidence inspection uses original account-scoped validations, orders, fills, immutable snapshots, frozen instrument metadata, strategy/evaluation links, model review response references, stop events and recovery/session audits. Outcome JSON or a client-supplied success flag cannot substitute. It checks real adapter source names, exchange timestamps, fill/event identity, quantity units, per-fill freshness, buy lifetime/stop boundaries, actual closed exposure and ledger reconciliation. Source metadata alone cannot cryptographically attest an exchange; trust rests on the restricted ingestion/persistence path and qualified code/configuration, not arbitrary user uploads.

Old validation records without the newly captured qualification binding and frozen instrument metadata cannot qualify. They remain historical records. The status screen inspects the latest 100 validations and discloses truncation; the review API accepts explicit session IDs for a selected evidence set.

## Qualification and arming boundaries

Qualification review is an explicit authenticated action and persists the server's assessment. It never arms entries. Scope is limited to the observed instrument identities, immutable contract metadata, actual one-lot caps and strategy versions; it is not authorization for every future option on an exchange. Qualification expires no later than its earliest scoped contract expiry.

Its binding includes service code, the Python dependency lock, setup documents, account policy and relevant provider/model/news settings. Private values contribute only to hashes. Daily broker JWT contents are excluded from the stable release binding so a routine renewal does not erase execution evidence. Validation's short-lived binding still includes the saved broker session; arming and per-entry preflight separately require current authentication/configuration/connection evidence, session eligibility, risk and data checks. Changed contract metadata invalidates qualification as well.

Explicit paper arms persist separately from qualification, expire at the earliest applicable qualification, broker, diagnostic or entry cutoff, and bind stream generation. Existing diagnostics have a 15-minute TTL: an arm is correspondingly limited and can require renewed diagnostics/rearming. This milestone does not silently introduce periodic billable diagnostic refresh or promise unattended multi-day operation.

Every buy admission and fill rechecks either a valid bounded-validation permission or an active arm within qualified scope. Evaluation records bind to their original validation/arm, preventing a late response from rearming a replacement session. Restart clears both intent types. Qualification revocation retains history, invalidates all account qualification records and disarms entries; existing exposure remains under exit management.

The workspace's execution readiness is now derived from current account qualification and configuration rather than a permanently false release flag. Global configuration inspection alone still grants no execution permission. No client may supply `qa_complete=true` to bypass review.

## Local supervisor controls

The API accepts only a typed mode and account revision. A database advisory lock serializes requests; the operation requires the enrolled single-owner account, no active validation/arm, no active orders/positions, paused intent and reconciliation. It commits the paused mode-switch intent before invoking a fixed script with an argument list and `shell=False`. There is no arbitrary command, path, PID or account input. PowerShell validates the mode again, uses hidden processes and serializes managed-worker operations with a mutex. Existing PID/start-time/script ownership checks remain in place.

Migration `c8b2def43003` adds qualification/arming records, nullable bindings for historical validations, and arm references on orders/evaluations. It preserves account history and refuses destructive downgrade when qualification/arm evidence exists.

## Verification and current limitations

Isolated tests cover original-record evidence inspection, incomplete/edited outcomes, both-venue matrix requirements, idempotent review/arming, exact scope and strategy caps, admission/fill/exit wiring, permission invalidation, late analysis, restart, revocation, ownership, supervisor failure and fixed-command boundaries. Test fixtures and seam-specific assessment tests are not actual-market evidence. Browser fixtures exercise preparation/review/arming/disarming, disabled/unavailable states and responsive layouts with all mutations intercepted.

Verification: 129 Python tests passed in disposable schemas. After tightening worker-initialization confirmation, all 19 qualification/control tests passed again. Ruff, mypy (56 service files), frontend type checking, production build and PowerShell syntax checks passed. Browser fixtures passed at 1440, 735 and 390 pixels with 15 intercepted mutations and no runtime errors. Temporary fixture source was removed before the production build; the harness/screenshots are in `.local/qa-m2-20261118/`.

Migration `c8b2def43003` is applied locally. The real supervisor smoke test prepared only `OBSERVATION`, confirmed initialization with a new heartbeat and left entries disabled. Qualification/arm/order/fill counts remained zero, and cash was preserved. No actual-market qualification or arming was attempted.

Actual qualifications and arms remain absent locally; there are no paper orders/fills. The only intended connected supervisor smoke test is preparation of the observer. No real broker order routes, provider billable calls, unreviewed fee assumptions or activation switches were introduced.

Next independent milestone: M3 historical/live market-data contracts, preserving LTP/OHLC and verifying the historical candle endpoint before chart implementation. E01–E03 from the M1 audit remain prerequisite evidence for actual paper validation.
