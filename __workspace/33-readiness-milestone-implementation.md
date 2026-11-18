# Readiness milestone implementation

18 November 2026, Asia/Kolkata.

## Delivered

- Shared typed readiness checks used by the workspace and CLI. Each check identifies
  status, reason, action and check time. Saved broker sessions, actual authentication,
  configuration, worker heartbeat, market schedule and fresh-market validation are separate.
- Explicit account-scoped diagnostics for broker authentication, real instrument metadata,
  stream transport, OpenAI authentication/model availability, structured output and licensed
  news. Results expire after 15 minutes or relevant input changes. Polling performs no
  provider tests. Overlapping diagnostics serialize and identical tests have a cooldown.
- Non-secret execution/calendar/news/agent configuration imports with schema validation,
  revision checks, shared-file locking, atomic replacement and audit history. Imports are
  blocked with active orders, positions or entry permission. Database save failures restore
  the prior file. Process termination across the filesystem/database boundary still requires
  operator reconciliation; this is not claimed to be a distributed atomic transaction.
- Complete account risk-policy review, with immutable capital/history, a revision guard
  and hash-bound review evidence. Changes invalidate previous review. Existing startup
  limits remain visibly unreviewed until a user actually reviews them.
- Verified closure records supported by the calendar. Missing dates stay unknown;
  unknown schedules cannot be represented as closed-market success.
- Managed local observation worker, genuine heartbeat, singleton lock/reconciliation and
  paused restart. Observation mode makes no agent requests or new entries. Business/setup
  failures no longer overwrite stream-cache transport health.
- Dashboard configuration/actions, specific highest-priority blocker, explicit diagnostic
  buttons and complete risk fields. Chain failures no longer erase account data; polling
  no longer erases control/save/export errors. Temporary browser fixture route removed.

## Actual configuration and connection results

The user authorized reuse of the existing API key and selected `gpt-6.1-sol` (with
`gpt-6-luna` as an alternative). Configured `gpt-6.1-sol`, an initial 250,000-token daily
cap, 2,000 output-token limit and 25-second timeout in `config/agents.json`. Credentials
were not changed or displayed. The observation worker makes no ongoing model calls.

- OpenAI authenticated successfully; the selected model was returned by the project model
  list. One actual bounded strict structured-output check passed, using the account budget
  and persisting its real response/usage evidence. No market recommendation was requested.
  The authentication check uses the documented [model-list endpoint](https://developers.openai.com/api/reference/resources/models/methods/list).
- Angel One public metadata retrieval passed: 316 eligible NFO and 492 eligible BFO
  contracts were present in the sampled master. This establishes metadata retrieval,
  not feed quantity semantics, streaming freshness or execution readiness.
- Initial broker tests reported daily login required. After the user renewed the private
  session, authentication/account matching passed on 18 November at 09:18 IST. The stream
  authenticated and decoded an actual quote at 09:19 IST. This does not establish both-venue
  executable-depth freshness or authorize entries. A subsequent metadata refresh at
  09:23 IST found 316 eligible NFO and 500 eligible BFO contracts.
- News retrieval reported that no permitted sources are configured.
- Observation worker reported `OBSERVATION_ONLY`, a recent heartbeat and entries disabled.

## Verification

All 65 backend tests, backend lint/type checks and the frontend production build passed.
The test run reported one dependency deprecation warning for Starlette's httpx TestClient.
New isolated tests cover calendar closure versus
unknown dates, configuration validation/revision conflicts, credential-evidence expiry
and invalidation, risk-review persistence/invalidation, capital preservation, identity
requirements, observed-worker resume rejection, serialized diagnostic persistence/cooldown,
failed-save restoration and observation-mode behavior. Existing domain and database tests
remain part of the final test run.

Playwright exercised the actual dashboard component at 1440, 735 and 390 pixels with
intercepted synthetic API fixtures. Setup pages, individual diagnostics, complete risk
saving and independent chain failures passed, without page overflow or browser runtime
errors. Screenshots and the fixture script are in `.local/qa-ui-milestone-20261118`.
These checks do not certify real Firebase sign-in or live provider behavior.

## Still required for the target milestone

The target “Configuration complete · Connections verified · Worker paused · Awaiting
market-open validation” is **not yet achieved**. Do not mark it complete merely because
its implementation and local tests work.

1. Broker authentication and stream connection checks are now passed following private
   login renewal. Keep session-expiry and evidence freshness checks active.
2. Sourced calendar coverage is now imported for both venues, 18–30 November 2026:
   09:15–15:40 IST normal sessions, November 24 holiday and explicit weekend closures.
   The current NSE timing page and October CAS FAQ resolved the earlier discrepancy.
   BSE timing notice 20260801-2 was retrieved directly; its holiday notice was read via
   an identified broker mirror. Full provenance and limits are in
   `configuration-review/REVIEW.md` and `configuration-review/calendar-sources.json`.
   Beyond November 30, coverage remains unknown. Extend with current source review;
   December timing changes must not be assumed away.
3. Execution assumptions are saved and explicitly approved by the owner; current
   published fee components remain draft/unreviewed. The owner confirmed standard
   published account pricing. Verify depth quantity units, contract-note rounding
   and the missing explicit BFO IPFT component. Angel One's contract-note guide
   confirms IPFT in the GST base; the NFO draft has been corrected. Readiness now
   reports component/evidence gaps separately from the review flag.
4. The owner approved the complete risk/liquidity/quantity/cutoff policy; it has been
   applied through the guarded settings service with revision and digest-bound review
   audit. Actual eligible lot metadata was NFO 65, BFO 20. The approved 65-unit cap
   replaces the startup one-unit cap; it is not a one-lot limit across both venues.
5. NewsData.io free adapter is now wired using the existing private `NEWS_API_KEY`.
   The actual diagnostic passed on 18 November at 09:52 IST with 10 attributed
   headlines published within 24 hours. Setup, diagnostics and agent context identify
   the provider's 12-hour free-plan delay. Header authentication keeps the key out of
   URLs; errors are sanitized, responses bounded, and invalid/future/old headlines
   rejected. The worker caches results for 15 minutes without refreshing publication
   timestamps. Live-news suitability and comprehensive coverage remain unverified.
6. Complete actual-market execution/protection verification in the later milestone.
   The existing final execution gate remains closed; no activation bypass was added.

Existing paper capital, fills and ledger history were preserved. No real broker orders
were placed, no production trades were seeded and no replay product was added.

## Configuration milestone verification, 18 November 2026

The full Python suite passed (76 tests), as did Ruff and mypy. New tests cover exchange
date/open/close boundaries, next imported session versus unknown dates, and fee drafts
that cannot bypass missing-component or unverified-evidence requirements with a review flag.

At 10:03 IST, broker authentication and stream transport passed again. The observation
worker had two-sided depth for 34 instruments per venue; 15 NFO and 16 BFO quotes were
within two seconds at the read-only check. These are observations at that instant, not
ongoing freshness guarantees or depth-unit/execution qualification. Safe aggregate
evidence is retained in `.local/market-observation-status.json`. The worker remains
observation-only; entries and autonomous generation remain disabled.
