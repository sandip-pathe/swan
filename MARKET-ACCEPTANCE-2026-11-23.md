# Open-market acceptance checkpoint: 23 November 2026

## Agent, chat and watcher checkpoint: 23 November 2026, afternoon

### Verification for this checkpoint

427 backend tests passed (one existing Starlette/httpx deprecation warning),
15 frontend tests passed, Ruff passed across services/tests, targeted mypy passed
on 12 changed source modules, frontend typecheck/production build passed, and
`git diff --check` passed. API/web listeners and managed observation worker are
running. These checks do not close actual-market autonomous paper acceptance.

This checkpoint supersedes earlier statements that index acquisition is API-only,
chat is limited to canned actions, or ORB qualification accepts generic records only.

- A deterministic worker job checks NIFTY index evidence every 30 seconds during
  the verified ORB window. Shared history acquisition, completed-bar assessment,
  watcher deduplication and durable assignments drive bounded model work. Generic
  snapshot reasoning no longer competes for automatic execution ownership.
- Free-text chat selects up to four named read-only tools for market, account,
  strategy and indicator records. Answers retain context/source IDs and timestamps;
  chat cannot create orders or change risk. The separate audited stop-new-entries
  control remains. An authenticated UI test at 15:15 IST returned actual NIFTY
  observations and correctly described the expired ORB trigger. Browser-local
  history is bounded and is not cross-device storage.
- Fixed daily AI allowance settlement: one valid provider usage receipt replaces
  its conservative reservation; absent, inconsistent or duplicate receipts retain
  the reservation. Actual usage above the estimate counts in full. No limit was
  raised. The failing UI request had 240,290 estimated tokens reserved versus
  58,323 settled tokens. A subsequent real UI answer passed after the fix.
- Session HLC3 VWAP and SMA-seeded DEMA 9 are available on charts and through
  read-only tools. Completed candles only; gaps/warmup and unavailable volume are
  explicit. Chart inspection showed DEMA and unavailable VWAP for incomplete
  history. These are context, not new strategy cards or automatic exit rules.
- ORB admission now applies the reviewed depth-unit mapping before executable
  quote checks. Qualification verifies the original ORB candidate, source bars and
  owned analyst/reviewer provider records; it does not fabricate generic reviews
  or grant qualification. Negative provenance tests remain fail-closed.
- Stream index references now publish to the database regularly; missing previous
  close in an LTP packet preserves the same-session previously observed close.
- Real option-history refresh returned provider rate limiting. Current VWAP parity
  and complete history acceptance remain open. No retry loop or fabricated volume.
- No new paper order was placed. Nine total orders, flat account, no active
  validation, qualification or arm; cash INR 99,766.55. Earlier round trips remain
  manual. Today?s ORB window ended at 11:00 IST. Next actual acceptance requires a
  fresh eligible setup and the existing bounded validation/qualification controls.
- Private runtime evidence: `.local/run/chat-watcher-checkpoint-2026-11-23.json`,
  `.local/run/indicator-history-check-2026-11-23.json` and the earlier paper ledger.


## Later execution and agent audit: 23 November 2026

The [execution and agent audit](./EXECUTION-AND-AGENT-AUDIT-2026-11-23.md)
supersedes earlier descriptions of the 10% paper participation configuration.
The audited model now permits up to 100% of observed depth, with existing
consumption, freshness and risk checks. Entry-only valuation pauses and chat
session stops no longer force manual liquidation. Explicit lease termination and
position protection remain enforced.

D19/D25: the ORB index-history producer is still an explicit API operation, not a
scheduled worker task. Generic option-snapshot reasoning and predefined ORB work
also need explicit ownership and fallback priority. These are confirmed integration
gaps, not missing broker depth. Close with automatic completed-bar acquisition,
durable assessment/agent work and an eligible strategy-to-paper session through
existing controls. No eligible current ORB opportunity or qualification was
invented during this audit.

D07/D20/D21: both earlier round trips were manual. A new real-provider, read-only
agent run passed analysis and proposal validation and returned WAIT for missing
directional evidence. Review was skipped after WAIT and order count stayed nine.
This does not qualify autonomous trading. The first trial rejected an invalid
citation; prompt/context corrections retained that rejection guard. Actual holding
acceptance after the entry-pause fix remains open until a bounded market session
exercises it. No new paper or broker trade was submitted in this audit.

## Latest checkpoint: real-data paper round trips, 23 November 2026

This checkpoint supersedes the older status sections below. Two one-lot NFO
paper positions completed a buy and a sell against actual Angel One observations.
No real-money broker order was submitted.

| Contract | Units | Buy | Sell | Estimated fees | Net P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| NFO:64458 | 65 | INR 183.10 | INR 182.40 | INR 75.54 | INR -121.04 |
| NFO:64490 | 65 | INR 295.15 | INR 294.85 | INR 92.91 | INR -112.41 |

Final cash and equity were INR 99,766.55 from INR 100,000. Total realized P&L
was INR -233.45, including INR 168.45 in estimated fees. Both positions were
closed, all orders were terminal, all validation leases stopped, and ledger
reconciliation returned no problems. Available cash was INR 68,852.54 because
the configured sale-proceeds holds remain in force. This is not reserved entry
cash or an open position.

Both exits followed `ENTRIES_PAUSED_UNAVAILABLE_VALUATION` with
`INSUFFICIENT_EXECUTABLE_DEPTH`, then `MANUAL_SESSION_STOPPED`. The watchdog
cancelled the protective stop before filling the replacement exit. The first
entry used WebSocket evidence and its exit used FULL REST evidence. The second
round trip used WebSocket evidence on both sides and held for about 13 seconds.
These are manual execution tests, not profitable strategy signals or accepted
AI-directed trading. Three other accepted entries expired unfilled; an additional
manual intent was rejected for insufficient executable depth. No fill was forced.

Private local evidence is in `.local/run/paper-round-trip-final-2026-11-23.json`,
including order IDs, immutable snapshot IDs, provider event IDs, fills and totals.
First entry order: `41d5b095-395e-4ccf-8ecb-af0c4ca2494c`.
Second entry order: `aeeb19b3-f99b-49bc-bee0-1085ca4d164c`.

Runtime fixes address observed PostgreSQL deadlocks and concurrent clock reads.
Quote and candle publishers lock instrument metadata in a stable order and do
not regress its verification time. Heartbeat publication follows account-to-control
lock order. Validation and manual protection read the clock after account locking;
manual quote checks read it after awaited scope work. Freshness, depth and risk
limits were not increased. Regression tests cover concurrent publications, packets
arriving during scope reads, and heartbeat changes during account-lock waits.
The two actual exits above were caused by insufficient depth, not proven clock
failures. The clock regressions are separate implementation findings.

All six refreshed provider diagnostics passed: broker, catalog, stream, AI,
structured AI output and news. The project OpenAI key works after removing the
expired override from launched processes. Real NIFTY history produced 137 complete
bars without gaps in the captured range. Its ORB signal had expired before these
tests, so it was not executed. Recognized provider history throttles remain visible.

Depth mapping now uses absolute option units, supported by exchange quantity
semantics, the official SDK's raw decoder and 80 sampled depth levels across both
venues and transports. This is a documented inference, not explicit SmartAPI
support confirmation. See [the source review](./SMARTAPI-DEPTH-UNITS-QUESTION.md).
The NFO REST corroboration sample was stale and was not used as fresh admission
evidence. Paper fees disclose rounding assumptions and the unresolved BFO IPFT
modeling allowance. Exact broker contract-note parity is still unverified.

Verification after the runtime fixes: 404 backend tests passed, Ruff passed for
the changed runtime modules and regressions, and targeted mypy passed for seven
source modules. The only test warning concerned Starlette's deprecated httpx
integration. Frontend checks from the preceding increment passed; no frontend
code changed in this runtime continuation.

The worker was returned to OBSERVATION after confirming the account was flat.
Entries remain paused. The API was restarted to load the fixes. Qualification,
autonomous arming, AI-directed paper-session acceptance, target/stop/max-hold
acceptance against actual market data, broader reconnect checks and dashboard/chat
visual acceptance remain open. No qualification or arm was fabricated from these
manual tests. R1 is not fully accepted.

## Depth-unit research follow-up

Reviewed the official Python SDK at a pinned commit and official endpoint field
descriptions. They do not establish the required mapping for all four
venue/transport combinations. Prepared the promised
[evidence review and broker-support question](./SMARTAPI-DEPTH-UNITS-QUESTION.md).
No message sent, mapping inferred, permission changed or paper order placed.
Fresh connection checks and bounded paper validation remain dependent on that
external protocol fact. This follow-up does not add acceptance evidence.

## Implementation correction: estimated fees and inclusive index history

Verification: all 400 backend tests pass (one existing Starlette/httpx warning),
13 frontend tests pass, frontend typecheck/build pass, Ruff passes, targeted mypy
passes for four source modules, and `git diff --check` passes. API restarted with
the fixes and reports database connected. Observation mode is restored after
isolating tests. Authenticated visual review of the new fee disclosure remains
open; no visual acceptance is inferred from the build.

The owner authorized underlying fixes rather than another unchanged admission
attempt. Added an explicit estimated fee-schedule basis and `assumed` evidence,
keeping documented schedules strict. Estimated schedules still require all
components and explicit review; unresolved sources remain invalid. Assumptions
cannot establish depth-unit or reusable-sale-proceeds verification. Existing
arm, validation, risk, freshness and account permission gates are unchanged.

Saved version `paper-estimated-fees-20261123-v1` through the revision-checked,
audited setup update. Standard rates were rechecked against the
[Angel One tariff](https://www.angelone.in/exchange-transaction-charges).
Paise cumulative-order rounding is explicitly assumed. BFO IPFT has an explicit
INR 1 per executed order modeling allowance, including GST dependency; this is
not a verified broker rate or guaranteed upper bound. No missing component was
silently set to zero. Original policy remains in setup audit history.

Orders already retain their execution configuration, so fee basis/provenance is
preserved with each order. Portfolio output now derives `fee_basis` from filled
orders and their actual venue, and the UI discloses modeled fees. This avoids
today's settings rewriting the interpretation of earlier results. Added checks
for partial-fill flat-fee charging, assumption boundaries and portfolio disclosure.

Captured a successful actual historical response at 11:32:41 IST after earlier
throttling. It contained 138 rows, including the 11:32 boundary candle. Root
cause of `INDEX_HISTORY_INVALID_BAR`: provider `todate` is inclusive, while our
assessment contract is half-open. The normalizer now validates the inclusive
boundary but excludes it from assessment bars; raw hash retains the observation.
Rows outside the inclusive bounds and malformed boundary OHLC remain rejected.
Added regression tests for all these cases.

Persisted 137 completed NIFTY bars with no missing assessment intervals, original
receipt availability, snapshot `e0d90cbb57b8e5b0e6b6684d815a2373e91195e1c140df735a7fcd18c88d58e5`,
and assessment `f2d4d2cdb9b6b312385aa399745521efb28a5339c8fa9f1ce55e72368210dfb6`.
The ORB trigger closed at 09:33 and expired at 09:34; the actual assessment is
EXPIRED. It was not backdated or converted into a current executable plan.
Raw source capture is ignored local file `.local/run/index-history-response-2026-11-23.json`.

Configuration now reports only `QUANTITY_UNIT_UNVERIFIED`. That requires external
provider/protocol evidence, not a fee-policy change. No paper order or position
was created by this continuation; a genuine round trip remains unaccepted.

## Admission attempt at 10:23 IST

The owner instructed continuation toward the paper round trip. Temporarily prepared
the worker in VALIDATION mode and attempted a five-minute HUMAN validation through
`ValidationService.start` for an actual previously sampled NIFTY contract,
`NFO:47814`. The unchanged service rejected it with
`VALIDATION_PREFLIGHT_INCOMPLETE`. Before and after: zero owner orders, zero active
validations, account disabled and resume_requested=false. No order-submission or
fill API was invoked. Restored OBSERVATION mode immediately afterward. Local
structured evidence: `.local/run/paper-validation-attempt-2026-11-23.json`.

Another isolated history request remained `PROVIDER_RATE_LIMITED`; further retries
were stopped. No actual-market paper round trip or trade P&L has been established.
The owner was asked for a local existing options contract-note path to investigate
fee rounding; no new real trade, upload or external message was requested/performed.

External evidence still needed before changing the execution configuration:

- Explicit Angel One confirmation/protocol evidence of whether each best-five
  depth quantity is option units or lots, for NFO and BFO via FULL REST and
  SnapQuote WebSocket. Matching raw multiples of lot sizes is insufficient.
- Fee rates/bases and rounding/allocation evidence from applicable schedules and
  representative existing contract notes; explicit BFO IPFT applicability and GST
  treatment. A missing tariff line is insufficient evidence of zero.

The existing gate requires both venues' configuration. This attempt did not change
that gate to permit an NFO-only session or relabel assumptions as broker evidence.

## Paper-flow follow-up at approximately 10:21 IST

The owner requested actual-market paper-order and P&L checks, and explicitly
approved the reviewed paper limits: INR 100,000 virtual capital, INR 500 trade
risk, INR 2,000 daily loss, one position, five-minute holding limit, 65-unit
quantity cap, two-second quote age and 1% maximum spread. Saved the policy using
the existing revision-checked risk-review function and its audit event. Each
validation remains separately limited to one actual contract lot. No arm was issued.

Ran 101 tests covering paper execution, manual admission/amendment, cancellation
and fill races, protection/target/stop exits, restart behavior, ORB underlying
protection, qualification boundaries, order history and portfolio accounting.
All pass against isolated fixture/test schemas. This is automated verification,
not evidence of an actual-market paper round trip. One existing Starlette/httpx
deprecation warning remains.

Read the owner account through the actual portfolio endpoint function. At
10:21:23 IST it reported FLAT, reconciled=true, cash/available cash/equity
INR 100,000.00, zero positions, realized/unrealized/total/session P&L INR 0.00,
and fees INR 0.00. The ignored local response is
`.local/run/paper-flow-checkpoint-2026-11-23.json`. There are still no owner paper
orders or fills; zero P&L is not evidence of successful trade accounting on live data.

A bounded history retry returned `INDEX_HISTORY_INVALID_BAR`, followed by
provider rate-limit rejections. The response causing the validation error was
not captured, so its exact cause remains unconfirmed. No normalization rule was
relaxed based on a guess, and no bars were inserted by that failed acquisition.
Need a successful bounded raw response to diagnose timestamps/shape/OHLC validation.

Actual-market paper orders remain blocked by depth-unit and fee evidence, with
history/model-strategy acceptance still needed for the ORB route. The observation
worker was stopped while tests ran and history was probed, then restored in
OBSERVATION mode. Existing gates remain unchanged. Pending live-flow evidence:
one permitted entry and actual later-depth fill, partial/cancel behavior where
observed, protective exit, incremental fees, reservations/cash reconciliation,
closed-trade P&L and matching UI/journal records. Stop/target/recovery criteria
must be evidenced separately; do not force market outcomes to complete a checklist.

## Credential correction at 10:16 IST

The root `.env` OpenAI key is valid. An inherited `OPENAI_API_KEY` differed from
the file and took precedence in Pydantic settings, causing the earlier 401s.
Direct verification of the file's key returned HTTP 200 and listed the configured
model. Restarted API and OBSERVATION worker with the inherited variable removed
only from their launch environment. No saved secret or system setting was changed.
Account-scoped `ai` and `ai_schema` diagnostics now both pass; the model produced
a valid strict structured connection-test response. No trading decision was made.
This resolves the authentication/schema-connectivity blocker, not model-quality
evaluation. Future launches from environments containing the conflicting variable
can reintroduce the issue; `.env` does not normally override process variables.

The earlier AI failure and first dependency below describe the initial check and
are superseded by this correction. History throttling and execution evidence
remain blockers.

The owner completed private broker login and explicitly resumed connected checks.
These observations establish connectivity and sampled fresh data, not trading
qualification or profitability. R1 remains open.

## Evidence captured

- At approximately 10:07 IST, account-scoped broker authentication/account match,
  catalog retrieval and WebSocket decoding passed. The catalog contained 316 NFO
  and 528 BFO contracts within the diagnostic's seven-day window.
- At 10:08:11 IST, actual NIFTY and SENSEX index references had exchange-to-receipt
  ages of approximately 0.15 seconds. Saved references retain original timestamps.
- REST sampled one near-money call and put per venue. All four quotes contained
  five bid and five ask levels, with ages of approximately 0.09–1.09 seconds.
- WebSocket sampled the same four contracts at 10:08:50–51 IST. All four contained
  five bid and five ask levels, with ages of approximately 0.13–1.12 seconds.
  These ages include timestamp precision and are not end-to-end execution latency.
- Raw normalized depth remains `quantity_unit=unknown`. Lot-size divisibility is
  not accepted as proof of units. Observations do not resolve D03.
- Local sampled results are in the ignored
  `.local/run/market-acceptance-2026-11-23.json`. Account-scoped diagnostic results
  are persisted as `CONNECTION_CHECK` audit events. No credentials are in this report.

## Failures investigated and fixes

The NewsData market request returned HTTP 422 with `UnsupportedParameter`.
Removing the unsupported `category=business` filter returned HTTP 200; the market
endpoint already selects financial news. The integration now keeps `country=in`
and `language=en`, matching the [official market API reference](https://newsdata.io/documentation/market-news-api).
The application diagnostic subsequently retrieved 10 attributed headlines within
24 hours. Free-tier 12-hour delay labels, provenance and freshness filters remain.

NIFTY index-history acquisition returned HTTP 403. A bounded follow-up established
that the response explicitly described an access-rate rejection. Profile and quote
requests still succeeded. The client previously treated every 403 as authentication
failure; it now reports recognized throttle responses as `PROVIDER_RATE_LIMITED`,
without exposing response bodies or immediately retrying that rejection. Other
403 responses still fail closed as authentication errors. SmartAPI documents
[403 for rate-limit excess](https://smartapi.angelone.in/docs/MarketData).
The actual provider-side reason for throttling is unconfirmed; no new historical
bars or ORB assessment were fabricated. Existing chart gaps remain visible.

OpenAI model-list authentication still returns HTTP 401. The owner was asked to
replace the configured key privately. Model generation/schema quality remains
unverified; no strategy generation was requested in these checks.

## Runtime and UI

Web and API are running locally. The managed worker was started in OBSERVATION
mode, briefly stopped to isolate a database advisory-lock conflict with integration
tests, then restarted with the fixes. Entries remain paused and the account disabled.
The API was restarted to load the fixes.

The authenticated Markets screen was inspected in VS Code's integrated browser;
it displayed current option prices, monitoring connected and entries paused.
It also retained an older selected chart date and showed missing candles explicitly.
The browser automation host remains unavailable; native input did not reliably
navigate the embedded browser. Strategies/chat visual acceptance remains open.

## Verification and remaining finish lines

All 19 focused news/history tests pass, including four new cases distinguishing
403 throttling from authentication failure. Ruff and mypy pass for the touched
provider modules; `git diff --check` passes. The first integration attempt returned
429 while the observation worker held the shared history lock; the isolated rerun
passed after stopping the worker. No test bypass or permission relaxation was added.

The owner account still has zero paper orders, validations, qualifications and arms.
All 17 qualification criteria lack accepted session evidence. No broker orders were
placed. No autonomous or validation worker mode was started.

Next dependencies:

1. Restore usable AI credentials and verify strict structured generation.
2. Resolve historical endpoint throttling and capture current NIFTY opening-range
   history through the normal assessment/watcher path. Do not reconstruct missing
   opening bars from later observations.
3. Resolve authoritative NFO/BFO depth units and fee/rounding evidence, including
   BFO IPFT. Current execution configuration remains blocked.
4. Complete bounded validation and qualification criteria, then separately arm
   and conduct supervised paper acceptance through existing controls.
5. Finish Strategies/chat visual review and broader reconnect/history comparison.
