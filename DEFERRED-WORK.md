# Project status and remaining work

## Oracle hosting preparation: 24 November 2026

The user now has Oracle access, but confirmed the VM is not created. Region shown
in the supplied console screenshot: India West (Mumbai). No cloud resource has
been created or public deployment performed in this preparation.

- Added hosting/oracle: non-root Python 3.13 image, PostgreSQL 17, single API,
  observation worker, Caddy HTTPS, persistent database/session volumes, private
  runtime templates, a backup command and deployment instructions. Existing
  application architecture and paper permission gates are preserved.
- Added allowlisted bundle/export scripts. Source archive is
  `.local/release/swan-oracle-source.tar.gz`; secrets, SSH keys and database data
  are excluded. A separate private PostgreSQL dump and manifest are under
  `.local/release/swan-database-20261124T054904Z.*`. It contains one account, nine
  orders and two closed positions. Export refused open exposure/active validation;
  the restore catalog was readable. Repeat after stopping local writers for final
  cutover; this snapshot alone does not prove a hosted restore.
- Checks passed: Compose configuration validation, Bash syntax, Ruff and mypy on
  packaging scripts, archive paths/hashes/secret-file exclusions/Python syntax/LF
  validation, frozen dependency dry-runs for Linux arm64 and amd64, one Alembic head.
- D26 remains open: no VM/IP/SSH/domain yet; Docker engine is unavailable locally,
  so actual image build, Linux/ARM dependency execution, database restore, TLS,
  Firebase/Vercel wiring, restart recovery and hosted market checks are unverified.
  No new full application test run was needed for deployment-only files.
- Next: create Always Free eligible Ubuntu VM (suggested A1 1 OCPU/6 GB if offered
  within account allowance), save SSH key privately, obtain public IP and API
  hostname. Follow hosting/oracle/README.md. Keep hosted entries paused until the
  existing bounded paper controls admit them. Calendar coverage still ends Nov 30.


## Latest closure evidence: 23 November 2026, afternoon

### Verification for this checkpoint

427 backend tests passed (one existing Starlette/httpx deprecation warning),
15 frontend tests passed, Ruff passed across services/tests, targeted mypy passed
on 12 changed source modules, frontend typecheck/production build passed, and
`git diff --check` passed. API/web listeners and managed observation worker are
running. These checks do not close actual-market autonomous paper acceptance.

This entry supersedes older implementation-gap descriptions below; stable IDs remain.

- **D19/D25:** automatic NIFTY completed-bar acquisition and durable ORB routing are
  implemented. Removed competing generic scheduled proposal execution. Reviewed
  depth mapping now reaches ORB staging; ORB-specific immutable source/review proof
  reaches qualification. These changes pass offline regression checks. Actual
  eligible strategy-to-fill acceptance remains open: today's ORB window is closed.
  Close with genuine current setup, provider review and bounded paper entry/exit
  evidence through existing controls. No new strategy cards were added.
- **D23:** free-text tool-grounded chat implemented and authenticated UI answer
  verified at 15:15 IST, with actual quote observation times and sources. Input,
  answer and indicator controls were inspected. Fixed conservative AI reservation
  leakage without increasing the daily allowance. General chat is read-only; the
  separate audited stop-new-entries control remains. Full dashboard visual coverage
  and actual stop-control acceptance remain open; do not infer them from this test.
- **D08/D19:** VWAP HLC3 and DEMA9 chart/tool implementations pass deterministic
  tests. Actual chart showed DEMA and explicit missing VWAP volume/history. An
  isolated real history refresh was provider-rate-limited. Close actual indicator
  history/consistency acceptance with usable complete provider bars and declared
  broker seeding comparison; do not fabricate index volume or treat stale points
  as current readings. Historical plotted series remain explicitly contextual.
- **Deployment:** the local app is running, but no production host, fixed egress IP,
  deployment credentials or external database is configured. Before publishing,
  choose a private single-user host, configure Angel One approved egress and HTTPS,
  and migrate the existing paper ledger and strategy records without data loss.
  The local Firebase callback Hosting target is a different static page and must
  not be overwritten. Angel One sessions expire at midnight and require daily login.
- **D07/D20/D21:** qualification proof now supports the actual ORB workflow, but
  genuine matrix evidence is still incomplete. No qualification, arm, new trade or
  accepted autonomous session was created. Account remains flat, nine orders total,
  cash INR 99,766.55. Existing post-fix holding/exit/reconnect checks remain open.
  Two earlier actual-source paper round trips were manual, not agent selections.

Evidence: [current checkpoint](./RESUME.md), [acceptance record](./MARKET-ACCEPTANCE-2026-11-23.md),
[chat](./services/agents/chat.py), [watcher](./services/worker/strategy_watch.py),
[qualification proof](./services/paper/orb_qualification.py). Private runtime evidence
is `.local/run/chat-watcher-checkpoint-2026-11-23.json` and
`.local/run/indicator-history-check-2026-11-23.json`.


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

## Current acceptance update: 23 November 2026

This update supersedes older zero-order and provider-failure statements below.
See [actual-market evidence](./MARKET-ACCEPTANCE-2026-11-23.md).

- D03: reviewed absolute-unit mapping is configured for paper execution using
  exchange protocol semantics, raw SDK decoding and live corroboration. Explicit
  SmartAPI confirmation remains unverified. Preserve that distinction when changing
  a feed or mapping. Source details are in SMARTAPI-DEPTH-UNITS-QUESTION.md.
- D04/D05: estimated paper fee schedules now admit paper tests with disclosed
  rounding assumptions and a BFO IPFT allowance. Broker-exact rounding and BFO IPFT
  evidence remain open because no actual contract note or authoritative BFO IPFT
  amount was obtained. Close exact parity only with that evidence and reconciliation.
- D01/D02/D07/D20/D21: six provider diagnostics passed and two manual one-lot
  NFO paper round trips closed and reconciled. Both exercised protective liquidation
  after insufficient valuation depth. Total net P&L was INR -233.45 with estimated
  fees. Three further entries expired unfilled. Qualification, autonomous arming,
  AI-directed acceptance and the remaining exit/reconnect matrix remain open.
  Manual execution evidence does not satisfy those criteria. Continue through
  existing bounded controls with fresh provider checks and eligible strategy signals.
- D08/D19/D25: a real index-history response supplied 137 completed bars and a
  deterministic expired ORB assessment. AI authentication and schema diagnostics
  and news now pass. Strategy/model-quality evaluation and an eligible connected
  strategy-to-fill session remain unaccepted. Do not execute the expired ORB signal.
- D23: dashboard/chat visual acceptance remains open. This continuation verified
  portfolio totals through stored fills and the portfolio read model, not a new
  visual inspection. Close with authenticated UI review of those actual records.

No open exposure or active entry remains. The worker is in OBSERVATION with
entries paused. No broker orders, autonomous qualification or arm was issued.
The current checkpoint is also recorded in RESUME.md.

Updated 22 November 2026 after the user explicitly resumed tests, verification, review,
broker/provider checks, live-market acceptance, qualification and paper-session acceptance.
This is the current project and finish list. An implemented
feature is not accepted evidence of live behavior. Keep IDs stable; close a row
only with evidence or an explicit scope decision. Every future slice
must add newly skipped/blocked work here and update resolved rows.

## Minimal first-release scope

The first release is a single-user, paper-only app: Angel One market data, NIFTY and
SENSEX research, charts, saved strategy assessments, chat grounded in saved records,
and paper orders with the existing risk and permission gates. Real-money orders,
profit claims, broad strategy research, and ongoing model-quality evaluation are
outside this release.

Before production publication: select a host with stable Angel One approved egress,
configure HTTPS and Firebase authentication, provision persistent PostgreSQL, and
migrate the local ledger/strategy history. Then verify the deployed market-data
connection and the existing paper workflow in an open session. Autonomous paper
entry remains behind the existing qualification and arm gates; release scope does
not bypass them. The user does not need to perform daily strategy evaluation, but
Angel One requires a fresh API login each trading day.

Current local service status: API, web app and observation worker are running on
this Windows machine. The worker checks new completed ORB evidence once each minute
at second 5 IST and invokes model work only for an eligible changed setup. This is
not a cloud deployment.

**Later work:** extended statistical evaluation, strategy improvement, expanded
indicator coverage, cross-device chat history, additional order types, exports,
and broad dashboard polish remain deferred unless a specific release blocker
surfaces. Stable IDs below remain the tracking record for those items.

**Scope boundary:** single owner, virtual funds, paper orders only. Keep the existing
permission gates and preserve actual-market evidence separately from offline tests.

| ID | Work / milestone | Status and reason | What closes it | Source |
| --- | --- | --- | --- | --- |

| D01 | M3 live candle, quote and reconnect acceptance (both supported venues) | Resumed 22 November; catalog probe passed and the authenticated stream decoded an actual quote packet, but 22 November 2026 is Sunday and neither quote freshness nor both-venue streaming/depth can be accepted outside a live session | Bounded open-market provisional-bar/value comparison, stream gap/reconnect and history overlap results, with actual timestamps and honest gaps | [M3](./__workspace/41-m3-market-data-foundation.md), [finish path](./__workspace/51-quote-order-and-finish-path.md), [NSE 2026 holiday circular](https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf) |
| D02 | Fresh broker login / connected diagnostics for acceptance | Resumed 22 November; user completed fresh login through the private CLI. Account-scoped read-only broker/account-match, catalog (316 NFO / 528 BFO), and stream checks passed. The stream decoded an actual quote, but the exchange was closed and current quote freshness/depth remain unverified. No broker orders placed | Repeat freshness/depth checks and verify both venue subscriptions during an open session; retain current account-scoped evidence | [credential handling](./services/market/credentials.py), [diagnostics](./services/market/diagnostics.py) |
| D03 | Depth quantity semantics for NFO/BFO REST and WebSocket | Evidence-blocked: live quantity units/mapping remain unverified; catalog succeeded (316 NFO, 528 BFO eligible contracts) but provider note says quantity semantics still require validation | Authoritative provider evidence and bounded observed checks for each transport/venue; record mapping provenance and invalidate affected qualification | [master plan](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D04 | Effective execution fees, tax dependencies, caps, rounding/allocation | Evidence-blocked: source/rounding review incomplete | Reviewed authoritative effective schedules and representative calculations for both venues; distinguish conservative assumptions from measured facts | [master plan](./__workspace/37-complete-system-and-broker-workspace-plan.md), [resume](./RESUME.md) |
| D05 | BFO IPFT component/evidence | Parked: only matters before using live fee estimates for this venue | Resolve applicable fee and effective-date evidence; do not assume a zero fee | [resume](./RESUME.md) |
| D06 | Calendar coverage after 30 November 2026 | Parked: current reviewed coverage ends then | Extend from official exchange calendars if dates beyond current coverage are needed | [resume](./RESUME.md) |
| D07 | Actual-market qualification matrix and explicit autonomous arm acceptance (M2/M8) | Resumed 22 November; fresh broker/account match and stream checks now pass, but qualification assessment still has no evidence across 8 NFO criteria, 8 BFO criteria or session rollover; account has zero qualification records, zero arms and zero validation sessions. No open market session. Entries remain disabled | Complete every required current-source qualification criterion and actual acceptance session, then separately arm through the existing gates; never infer eligibility from fixtures | [M2](./__workspace/40-m2-qualification-worker-controls.md), [qualification](./services/paper/qualification.py), [finish path](./__workspace/51-quote-order-and-finish-path.md) |
| D08 | Broader historical candle coverage / venue comparison | Evidence-blocked: bounded history reads exist; broad coverage/value parity not established | Verify supported instruments/dates/venues and provider limits; document remaining gaps rather than backfilling synthetic values | [after-hours history](./__workspace/42-after-hours-market-data.md), [live chart](./__workspace/43-live-candles-and-mobile-chart.md) |
| D09 | Physical phone PWA check | Parked and optional: responsive app is implemented; no phone-specific issue is currently blocking use | Reopen only if a concrete phone-specific problem appears | [master plan](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D10 | Remaining market/option analytics and studies (M5) | Planned: EMA/SMA/RSI, depth, reference and fills/levels exist; VWAP where valid, sourced change-in-OI, expanded IV/Greeks methodology and coverage-aware PCR/max-pain are not all delivered | Feature inventory and implementations with real inputs, source/method/time and unavailable states; never manufacture missing metrics | [M5 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D11 | Pending-order chart markers distinct from actual fills | Partially delivered: active entry/exit orders for the selected contract/day now have separate P/X markers and a status/price list; latest 200 cap is explicit | Add paging if volume requires it; verify marker alignment/lifecycle against order and fill history; preserve the distinction between working orders and executions | [chart overlays](./__workspace/63-owned-chart-trade-overlays.md), [pending chart orders](./__workspace/83-pending-order-chart-markers.md) |
| D12 | Broader manual paper permission and order types (M6) | Planned: currently a bounded HUMAN five-minute/one-entry/one-lot session with BUY LIMIT; unrestricted manual mode is not implemented | Specify separate explicit permission lifecycle, supported types, mutual exclusion, recovery and deterministic admission; keep current gates until accepted | [manual placement](./__workspace/58-mobile-manual-placement.md), [amendments](./__workspace/60-manual-order-amendments.md) |
| D13 | Bulk protected exits and broader modification scope (M6) | Planned: individual exit and wholly-unfilled manual price amendments exist; no bulk exit, quantity increase, expiry extension or filled-position amendment | Specify/review semantics and implement reservation/fill-race/unresolved outcomes; do not add cosmetic actions | [M6 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md), [owned controls](./__workspace/59-owned-paper-cancel-and-exit.md) |
| D14 | Remaining risk/exposure metrics and trade statistics (M6) | Partially delivered: closed-position statistics, daily risk headroom and per-instrument open/pending exposure breakdown are implemented. Slippage remains unavailable without defensible reference observations | Reopen only if a reference-price source is added; do not infer slippage from fills or limits | [exposure breakdown](./__workspace/87-portfolio-exposure-breakdown.md), [portfolio](./__workspace/62-reconciled-portfolio-value-and-pnl.md), [trade statistics](./__workspace/84-closed-trade-statistics.md), [risk headroom](./__workspace/86-daily-risk-headroom.md) |
| D15 | Historical equity/P&L snapshots, richer journal filters/exports and funding/reset decisions | Partially delivered: closed-position journal now pages without the workspace's former 50-row limit, and CSV streams all closed positions. Historical marked-equity series, journal filters, and reviewed funding/reset workflow remain open | Persist/reconstruct only defensible snapshots; add scoped filters; any funding/reset must be an audited ledger operation preserving history | [journal paging](./__workspace/85-paged-closed-journal.md), [M6 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D16 | Agent evidence/news citation drill-down and explicit evaluation/output correlation (M7) | Partially delivered: explicit context links, quote/headline age, evaluation IDs, stage checks, strategy/risk/order links, cursor paging, and complete daily-report activity aggregation in bounded batches are implemented. Older unlinked outputs remain unavailable; source-rights suitability and other bounded evidence surfaces remain open | Preserve unavailable legacy links; revisit source-rights suitability before wider distribution | [activity](./__workspace/64-recorded-agent-activity.md), [report activity](./__workspace/82-complete-report-activity.md) |
| D17 | Model/strategy version and spending/budget visibility (M7) | Partially delivered: Account activity shows today's conservative reservations/remaining allowance, recorded usage coverage and reservation model names. New runs also record requested/reported model names and local strategy/prompt/schema fingerprints. Immutable provider revision guarantees, monetary cost and unavailable provider usage remain open; incomplete/invalid HTTP-200 response totals are now retained; historical day selection is implemented | Record/pin stable provider revisions where supported, resolve missing transport/error usage where defensible and review the reproducibility boundary; add defensible pricing/billing attribution and any needed historical configuration timeline. Existing missing usage stays unknown, never zero or inferred from reservations | [agent runtime](./services/agents/README.md), [M7 scope](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D18 | News suitability, permission and delay acceptance | Evidence-blocked: finance-focused NewsData Market endpoint, publisher click-through and provider attribution are implemented; free feed is delayed by 12 hours. Resumed provider probe returned `NEWS_HTTP_ERROR`; source rights and coverage acceptance remain incomplete | Confirm rights for intended deployment and publisher-content display/storage, inspect actual India coverage after provider access recovers; preserve publication/retrieval/delay fields and do not present delayed headlines as breaking news | [agent news](./services/agents/README.md), [source review](./__workspace/81-india-news-feed.md) |
| D19 | Strategy lifecycle, research and evaluation | Core predefined ORB assessment, durable assignments and bounded analyst/reviewer work are implemented. Actual connected strategy-to-paper acceptance remains open; extended strategy and model-quality evaluation is deferred beyond the first release | Verify one eligible end-to-end paper lifecycle before enabling autonomous paper operation; keep profitability and comparative evaluation out of the release gate | [current checkpoint](./RESUME.md), [strategy handoff](./STRATEGY-INTELLIGENCE-HANDOFF.md), [watcher](./services/worker/strategy_watch.py) |
| D20 | Integrated autonomous-operation qualification | ORB-specific provenance is recognized, but genuine qualification evidence is incomplete; no qualification or arm is active | Complete the existing required paper qualification checks, then separately arm the paper worker; never infer eligibility from fixtures | [qualification](./services/paper/qualification.py), [finish path](./__workspace/51-quote-order-and-finish-path.md) |
| D21 | Supervised first autonomous paper session | Earlier two paper round trips were manual; no agent-selected paper trade has completed | During a fresh eligible market session, confirm one bounded strategy-to-paper path and reconcile its saved result; ongoing profitability/evaluation is deferred | [acceptance record](./MARKET-ACCEPTANCE-2026-11-23.md) |
| D22 | Extended tools and exports beyond the critical finish path | Review needed: drawings, additional studies, scanners, layouts, alerts, strategy builders, baskets/payoffs, tags, scheduled reports and export formats remain backlog | Explicit scope/dependency decision for each; unsupported controls must not appear usable | [backlog](./__workspace/37-complete-system-and-broker-workspace-plan.md) |
| D23 | User-facing chat and evidence retrieval | Free-text chat and read-only market/account/strategy/indicator tools are implemented and visually checked in the local app; stop-new-entries is a separate audited control. Cloud deployment is not configured | Configure production host/auth/origins and verify chat against deployed records; test the stop control as a release check | [chat](./services/agents/chat.py), [deployment checkpoint](./RESUME.md) |

| D24 | Separate strategy discussion: harness selection and human-intervention design | User-deferred in the strategy brainstorming: the user asked to discuss harness and human controls later. Earlier candidate notes remain proposals, not architecture or authority decisions | Resume those design topics when requested; define workflow recovery, generated-tool isolation and human position ownership without changing existing gates. The current strategy design does not authorize implementation | [separate discussion](./AUTONOMOUS-TRADING-DISCUSSION.md#strategy-system-design-22-november-2026) |
| D25 | Underlying-target and premium-stop paper execution | Reviewed ORB levels are connected to the existing dual-exit policy and ORB provenance checks; offline proof passes. Actual connected execution remains unaccepted | Complete the bounded paper lifecycle with fresh index and option data while preserving risk and account gates | [exit design](./services/paper/UNDERLYING-EXITS.md), [qualification proof](./services/paper/orb_qualification.py) |

## D26 - Oracle deployment acceptance

Status: deployment package prepared; hosting experiment deferred at the user's
request on 24 November 2026 while publishing the current project to GitHub. The user
reports a 1 GB Oracle VM now exists; A1 creation failed for capacity and the account
has no trial credits. SSH access and actual resource sizing remain unverified.
Local Docker engine is unavailable, so Compose/source validation must not be
represented as a successful container build or cloud deploy. Next: obtain VM access
and measure memory, including whether PostgreSQL needs a separate host.
Closure: build on the VM, restore the existing ledger and configuration, configure
HTTPS and explicit Firebase bindings/Vercel origin, verify startup/restart/backups,
then check current market data and bounded paper workflow through existing gates.
Evidence: [deployment package](./hosting/oracle/README.md), [checkpoint](./RESUME.md).

## Current exclusions, not delayed promises

### Connected checkpoint: 23 November 2026

D03 primary-source follow-up: inspected official SDK commit
`6bd06ff8e9085e95b709e560a3482586860fb2b3` and official market-data/margin field
descriptions. Raw integer decoding does not establish units; the NFO margin-input
note does not establish REST/WebSocket depth semantics for both venues. Mapping
remains unverified. Prepared [a precise support draft and evidence review](./SMARTAPI-DEPTH-UNITS-QUESTION.md);
no external message was sent, no setting was changed, and no paper trade was
attempted under guessed units. Closure requires explicit applicable mapping
evidence followed by observed corroboration and the normal admitted validation.

Underlying-fix continuation: D04/D05 now support explicit reviewed paper estimates
without pretending broker parity. Saved the audited estimated fee configuration;
its rounding assumptions and BFO IPFT allowance are disclosed and retained per
order. Exact broker-fee reconciliation remains unverified and separate. D03 is
the sole remaining execution-configuration blocker; assumed fee evidence cannot
verify quantity units. D08/D19: captured actual history and fixed inclusive-end
normalization; persisted 137 completed bars and an honestly EXPIRED ORB assessment.
Throttling may recur; reconnect/value comparison and strategy/model acceptance
remain open. D07/D20/D21 still have no admitted paper round trip. See the dated
implementation-correction record for source hashes, IDs and regression coverage.

Verification for that continuation: 400 backend tests, 13 frontend tests,
frontend typecheck/build, Ruff, targeted mypy and diff checks pass. D23 fee-disclosure
visual review remains open; automated frontend checks do not establish visual
acceptance. API restarted and observation mode restored; no live-data paper order
was admitted because D03 remains unresolved.

At 10:23 IST, attempted a five-minute HUMAN validation through the unchanged
service in VALIDATION worker mode. It rejected `VALIDATION_PREFLIGHT_INCOMPLETE`;
orders stayed zero, no validation lease was created, account stayed disabled.
Restored OBSERVATION mode. D07/D20/D21 remain blocked by execution evidence and
current readiness, rather than awaiting permission to try. D03 requires explicit
REST/WebSocket NFO/BFO depth-unit evidence; D04/D05 require fee rounding/allocation
and BFO IPFT evidence. Requested the path of an existing local contract note to
investigate the latter. The last isolated history retry was rate-limited. See the
dated admission-attempt record and ignored local structured result. No gate relaxed.

Paper-flow follow-up: the owner explicitly approved the bounded paper risk limits;
saved the reviewed policy with quantity cap 65 through the existing audited path.
The unreviewed 1-unit starter-policy blocker is resolved. 101 order/protection/
accounting/qualification tests pass in isolation. Owner portfolio output reconciles
flat at INR 100,000 equity and zero P&L/fees; there are still no actual owner paper
orders/fills. D03–D05 and genuine D07/D20/D21 trade evidence remain open. D08/D19
also need investigation of an observed `INDEX_HISTORY_INVALID_BAR` once a bounded
raw response can be captured; later retries were throttled. No validator was
relaxed, permission bypassed or actual-market round trip claimed. See the dated
report's paper-flow follow-up for remaining checks and evidence.

Follow-up at 10:16 IST: the `.env` OpenAI key is valid; a conflicting inherited
environment value caused the 401. Relaunched local services without that override.
Account-scoped AI authentication and strict-schema diagnostics both pass. D19/D20
no longer have an AI-authentication blocker in these running processes; model
quality, history throttling and execution-evidence requirements remain open.
Future launch environments must avoid the conflicting override. See the dated
report's credential correction; no secret was changed or disclosed.

This checkpoint supersedes the earlier closed-market descriptions above without
closing criteria from connectivity alone. See
[dated acceptance evidence](./MARKET-ACCEPTANCE-2026-11-23.md).

- D01/D02: fresh private login, account-match/catalog checks, index references,
  and sampled fresh REST/WebSocket five-level depth on both venues passed.
  Reconnect/history overlap and broader value comparison remain open.
- D03–D05: depth units, fee rounding and BFO IPFT remain evidence-blocked;
  authoritative transport/venue mappings and reviewed applicable fee evidence
  are required before qualification. Raw quantities were not relabeled.
- D07/D20/D21: observation worker now runs with entries paused. Zero paper orders,
  validations, qualifications and arms; all 17 matrix criteria remain unmet.
  AI HTTP 401, historical 403 throttling and execution configuration block further
  qualification. Close only with genuine bounded validation/qualification and
  separately armed supervised paper evidence through existing gates.
- D08/D19/D25: index-history acquisition is blocked by a provider access-rate
  rejection; recognized throttling is now classified correctly. Need successful
  source-backed opening bars/assessment and connected protection acceptance.
  No bars, decisions or fills were fabricated. News's unsupported filter is fixed
  and its diagnostic passes; AI needs private credential correction and schema
  verification before model-quality acceptance.
- D23: audited session-stop implementation and tests exist from the previous
  continuation; Strategies/chat visual acceptance remains open. The authenticated
  Markets screen was inspected, but embedded-browser input remained unreliable.

Real-money broker orders, public multi-user launch, broader asset classes,
margin-aware short selling/multi-leg execution, live broker holdings, banking,
funding/settlement and demat features remain outside the accepted single-owner,
long-options paper scope. Re-scope them explicitly before implementation.

## End review

Review every open ID with the final checkpoint. Preserve source evidence and note
what was built, what was actually verified, and what still needs a person, market
session, source evidence or a scope decision. Passing a fixture never closes an
actual-market or longitudinal acceptance item.
