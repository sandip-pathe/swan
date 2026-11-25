# Project status and remaining work

## D34 - Slim read-only market bot scope and acceptance

25 November local-first/slim deployment update (supersedes earlier hosted status):
Public Caddy now serves bot-api:8000; legacy API/worker/PostgreSQL stopped after
all-zero preflight and root-only readable pg_dump archive backup. Login timer active.
Archive restore remains unverified. Vercel deployment remains the user's task.
Implemented IndexedDB incremental archive, star/unstar, seven-day/1000 transient
server retention, 200 saved/account and public offline shell. New behavior passed
build/typecheck/lint/mypy only; automated persistence/restart/account isolation,
retention boundary, multi-device star, browser eviction and actual offline PWA
acceptance have not been run. Closure: verify those paths and migrations against
isolated data, then signed-in hosted clients without substituting fixtures for
live-market acceptance. Existing old test counts predate these behavior changes.

Accepted intended scope is now SENSEX option buying and separate weekly research;
current implementation still has only NIFTY intraday scans and index quote reads.
SENSEX candle/history/contract acceptance, cost-aware option analysis, multi-session
swing pipeline, official announcement feeds, structured invalidation/supersession,
noise/expectancy evaluation and durable data-health events remain unimplemented.
See latest BOT-SCOPE.md for required fields, boundaries and proposed sequencing.
These need source validation and selected-horizon acceptance before useful setup
claims. User's 5% loss basis is unresolved; no capital allocation was inferred.
No daily profit promise or automated trade authorization exists.

Closed/suspended-device notifications, guaranteed delivery/acknowledgments, offline
source-evidence storage, important-insight backup/restore and off-host bot backups
remain open. Local records can be evicted; long-offline clients can miss expired
unstarred server records. Closure requires implementing/accepting retained delivery
and backup requirements, or an explicit scope decision. Scheduling is minute+03
collector and 15-second foreground sync; actual end-to-end latency and uptime
remain unmeasured. Zero background AI token calls; chat budget remains enforced.

25 November resumed acceptance: user explicitly authorized read-only collection
and freshness checks; Vercel deployment is assigned to the user. Collection is now
enabled persistently on Oracle. Legacy observation worker stopped after fresh
all-zero inactive/flat ledger preflight; automatic login remains active. See the
latest RESUME checkpoint and BOT-RUNBOOK for actual-host evidence. Existing session
successfully returned validated NIFTY/SENSEX quotes after hours; these are historical,
not live freshness acceptance. NIFTY history returned 370/375 minutes with 15:15-15:19
IST absent; scans correctly withheld. Investigate provider omissions and recheck in
a verified open session before accepting reliable continuous scans. Do not impute
missing candles. Public API cutover, user Vercel deploy, authenticated latency,
open-session freshness/recovery and model usefulness remain open. Earlier paused
entries below are historical and superseded only for read-only collection/checks.

25 November implementation: isolated branch bot/read-only in D:\s\swan-bot now has
Chat/Insights only, separate bot API/storage/collector, NIFTY completed-bar range/SMA
scans and optional constrained chat interpretation. See BOT-RUNBOOK.md for exact
boundaries and passing isolated checks. Oracle staging is being prepared separately;
production cutover, Vercel deployment/access, authenticated hosted latency and resumed
provider/model acceptance remain open. The user has been asked whether to resume
the read-only provider hold; do not infer permission. Remaining scope from the draft
includes options scans, SENSEX history, opening/closing briefings, source correction
supersession, research breadth and actual usefulness/noise evaluation. These were
not included in this initial bot slice so that unsupported data is never implied.
Isolated Oracle bot staging now passes health and unauthenticated boundary checks:
local health 3-60 ms in three warm samples, Insights 401 without a token and old
arm route 404. Collector is confirmed paused, original auto-login timer active.
Public Caddy/Vercel traffic is unchanged. Initial cold import/startup was slow under
host CPU contention; do not infer p95 or recovery acceptance from warm health samples.
Closure requires implementing/accepting any retained scope or an explicit scope
decision, plus the deployment and actual-data criteria below. Calendar renewal
before the existing 30 November coverage boundary remains required under D26.

Proposed, not implemented: [BOT-SCOPE.md](./BOT-SCOPE.md) defines one background
process with collection/validation, deterministic scanning and bounded research/
publication jobs, plus saved insights and chat. Existing deployment is retained.
Universe/horizon confirmation, implementation, provider freshness and model usefulness
acceptance remain open. No trading migration/removal or broker checks are authorized
by the scope document. Closure: confirm the scope, implement the read-only boundary,
then satisfy its offline, actual-host and explicitly resumed provider acceptance
criteria. Do not close from fixtures or model-generated citations alone.

25 November GitHub checkpoint: user withdrew undeployment; retain Oracle worker,
automatic login and existing services. Read-only bot direction remains a discussion,
not delivered scope or authorization to remove trading code. D29/D33 remain open.
Full backend database regression was not completed: the broad non-integration test
selection still reached database fixtures, encountered setup errors and was stopped.
Closure: rerun the relevant database suite against an isolated local test database;
never substitute hosted provider/market acceptance. Frontend build/typecheck/15 chart
tests, 13 isolated login tests and changed-Python lint pass for this checkpoint.

25 November cross-screen planning: [SWAN-SCREEN-PLAN.md](./SWAN-SCREEN-PLAN.md)
and [review board](./design-playground/screen-plan.html) cover 19 proposed views.
Dashboard Overview / Trades / Decisions / History are now implemented locally,
with isolated fixture/browser verification recorded in RESUME.md. Hosted/device
acceptance remains open under D28; fixtures do not close it. Remaining screens from
the broader plan are still out of scope for this Dashboard pass. D29-D33 backend/
persistence/feed/host dependencies remain separately open. No broker acceptance
was resumed.

Beginner dashboard experiment (25 November 2026): plain-language summaries,
visual cash breakdown and expandable reasoning implemented locally. Real learner
comprehension/usability evaluation is pending under D27/D28. Detailed saved agent
rationales retain their original wording; reliable plain-language paraphrasing would
need a grounded backend contract and evaluation, not guessed frontend explanations.

## D32 - Dashboard live market briefing and learning expansion

Open. Current local dashboard uses existing account-owned activity/evidence GETs
for real saved decisions, cited historical news and contract observations. Dedicated
current NIFTY/SENSEX index snapshots, a browsable current news feed, and personalized
learning recommendations are not exposed by those APIs. Do not label saved evidence
as live, fabricate agent activity, or start broker/model work on dashboard load.
Closure: scoped read-only backend contracts with timestamps, provider attribution,
delay/session status, bounded caching and independent failures; wire and verify the
resulting dashboard sections. Current fixtures verify rendering, not actual-market
acceptance. Signed-in hosted payload and physical mobile acceptance remain D28;
broker/login/live-market checks stay on hold until explicitly resumed.
Evidence: apps/web/src/app/dashboard-intelligence.tsx; private fixture harness
.local/design/check-dashboard-data.mjs. No deployment performed.

## D33 - OCI CPU availability and authenticated latency

Open. Follow-up read-only VM sample on 25 November at 09:08-09:10 UTC: OCI metadata
identifies VM.Standard.E2.1.Micro (1 GiB RAM; shape config reports 1 OCPU/2 vCPUs).
Load average rose from 3.63 to 5.48, 350 MiB memory available,
379 MiB swap occupied, and vmstat showed 94-95% CPU steal in four consecutive
samples. CPU pressure was high; memory pressure and swap I/O were also present.
Docker reported API 100 MiB, worker 113 MiB, PostgreSQL 97 MiB and Caddy 25 MiB;
worker CPU was 206% in the sample. API container health checks repeatedly exceeded
their 8s timeout, while three external unauthenticated /health requests returned
200 in 1.09-3.47s. This is fresh evidence of severe host CPU scheduling pressure;
it does not identify the provider quota/entitlement or prove worker CPU is the cause.
OCI documentation says the Always Free E2.1.Micro receives less than a full OCPU
and cannot burst, consistent with the observed CPU constraint but not a measurement
of this guest's exact entitlement: https://docs.oracle.com/en-us/iaas/Content/Compute/References/burstable-instances.htm
Local code now gates quote/reference publication on accepted cache revisions or a
completed metrics refresh, avoiding unchanged-data scans and write attempts. The
heartbeat and 250 ms execution watchdog stay unchanged. CPU benefit is unmeasured;
the change is local, untested and not deployed. This cannot correct the Micro shape's
CPU entitlement or substitute for authenticated endpoint/recovery measurements.
Authenticated endpoint latency remains unmeasured. No services were restarted or
reconfigured; broker, provider and live-market checks remain on hold.
Static review found the explicit quote-refresh route holds its global advisory
transaction lock and database transaction while awaiting provider calls (up to
80 seconds), with a 30-second cooldown. No refresh was invoked; review this path
without provider access first, then preserve the market-acceptance hold for any
provider validation.

Earlier read-only diagnosis on 25 November: /health returned 200 in 9.59s,
load average 5.71, swap 422 MB; vmstat 1-second interval samples reported CPU
steal 94% and 74%. Containers healthy/zero restarts. API exception scan found no
matching traceback in the checked hour; Caddy logged /api/workspace abort after
15.6996s, writing: http2: stream closed. This establishes slow service and heavily
restricted host CPU availability during observation, not a specific quota cause or
a proven application deadlock. Authenticated endpoint timing was not measured;
no tokens extracted and no broker/provider acceptance resumed.

Frontend polling/load fixes and saved display snapshots implemented locally (see
RESUME.md). Closure requires sustained guest/host CPU and quota diagnosis, bounded
resource/read-only endpoint measurements, then an authorized deployment or hosting
capacity change and measured authenticated latency/recovery. Do not merely extend
all timeouts or treat local fixture success as host resolution. No host mutations
or deployment performed in this investigation.

## D31 - Planned native extensions beyond the local app-shell pass

25 November update: owner-scoped account display snapshots now persist locally
for up to 24h, with historical labels and sign-out cleanup. This partially expands
local reading; service-worker account HTML/API caching and push remain unimplemented.

Planned, not implemented: opt-in push alerts with account-authorized deep links and
private offline-reading expansion. They require backend subscription/delivery,
consent and notification payload design, device testing and retention/privacy rules;
the current stateless chat endpoint and public-only offline cache do not provide
these. No notification permission is requested automatically. Current manifest
shortcuts and existing hash routes work without claiming push delivery. Closure:
authorized implementation plus real-device delivery/read/offline-recovery evidence.
Trading actions must remain online and server-authorized; never queue them offline.

## D29 - Backend fixes: chat latency and greeting failure

Partially implemented locally: exact greeting-only inputs now return a bounded,
source-free response without planner/answer model calls or database tool reads.
This avoids the expensive chat pipeline for greetings and does not claim account
or market facts. It has not been executed against the hosted API. The owner reported
that a plain "hello" took a long time and ended in the failed
answer UI after connecting the real local frontend to Oracle (24 November 2026).
Do not treat fixture chat success as resolution. Current frontend has an outer
30-second API deadline, while Chat requests specify 60 seconds; that mismatch is
one investigation target, not an established root cause. Trace authenticated chat
queueing, database/context work, tool selection, model calls, retries and resource
contention on the 1 GB VM. Inspect provider errors and timeouts without logging
credentials or private prompts. General greetings should not require market data
or broker readiness; ground market questions through appropriate tools. Define
latency budgets, truthful progress/streaming where supported, cancellation and
recoverable errors. Do not merely extend every timeout. Closure: measured real
end-to-end greeting and grounded question success, p50/p95 latency and failure
recovery evidence, with existing budget/permission gates preserved. Grounded-question
backend work and model/live checks remain open; broker acceptance hold is unchanged.

## D30 - Durable cross-device conversation sessions

Open follow-up. Multiple owner-scoped conversations now exist in the local UI,
including separate histories, drafts and concurrent in-flight responses. Persistence
is device-local only, and sign-out clears the device cache. Server-owned session
IDs, authorized list/detail APIs, retention/deletion policy and cross-device history
are not implemented by the existing stateless chat endpoint. Closure: durable owner-
authorized session storage and tested restoration/isolation across devices; never
substitute fabricated server persistence for this local implementation.


## D28 - Frontend workspace migration and hosted acceptance

Native PWA foundation implemented locally (see RESUME checkpoint): independent chat
scroll/pinned composer, reading-position preservation, incoming-reply restraint,
keyboard-aware visual viewport, tab/screen/filter/chart-view memory, native Back for
mobile overlays, install/storage controls, preference cookie with SSR, safe public
asset cache and offline/reconnect guards. Build/typecheck, 15 existing chart tests,
extended browser fixtures and a service-worker/offline-launch check pass. Existing
financial freshness/permission/recovery rules were preserved. Physical Android/iOS
installed-PWA keyboard, safe areas, rotation, pinch zoom, hardware Back and optional
storage/installation outcomes still require actual-device acceptance. Browser
keyboard simulation and public offline fallback are not proof of those outcomes.
No broker/model/live-market checks, backend changes or deployment in this pass.

Trade page learner-focused pass: local copy, filters, option-chain styling/loading,
chart indicators and order-planner layout are implemented; the isolated browser suite
verified the search-to-chart route and mobile sheet with fixtures. The signed-in
contract catalog was marked stale, so no stale contract was opened and no live order
or broker action was attempted. Close this slice with fresh, authorized market data
and the existing paper-workflow checks only when the owner resumes broker/live-market
acceptance. No trading gate was weakened.

25 November visual follow-up: removed the persistent desktop watchlist sidebar; its
content is now only shown from the Watchlist tab, and Find/Options use the main width.
Typecheck, chart tests and the local fixture browser suite pass. This closes the local
layout correction only. Fresh hosted quotes, broker checks and installed-device
acceptance remain deferred under this item; resume only when the owner explicitly
resumes market acceptance.

Additional visual correction: restored desktop/mobile inset spacing for Trade content
and removed the optional Bid/Ask/OI glossary link from Options. Automated layout and
content assertions pass. No new acceptance work was skipped; the existing hosted/live
and installed-device acceptance hold remains unchanged.

Chart-order iteration: the candlestick view is now the main full-width surface; the
persistent order form was replaced with one Buy trigger and a responsive native
dialog. The dialog preserves the existing estimate, confirmation, and server-side
permission checks. Copy now describes the short paper-order window without the term
"practice session." Typecheck/build/chart tests and fixture browser checks pass.
Real broker/live-market and installed-device acceptance remain deferred under D28.


Native-style tab state iteration implemented: inactive outlines, active solid glyph,
no selected tile background. Isolated browser/typecheck verification passes; real
installed-PWA/device acceptance remains open.


Four-tab mobile bar and adaptive colored icons implemented. Browser checks confirm
Chat/Dashboard/Trade/Account labels, four icons and responsive layout; typecheck
passed. Physical installed-PWA safe-area and keyboard acceptance remains open.


Lucide primary navigation and shared single-line label layout verified by build,
typecheck and browser checks across existing responsive widths. This resolves the
reported New conversation wrap locally; physical-device/PWA acceptance remains.


Sidebar row follow-up verified locally: flat primary/new-chat/account rows and
noninteractive SWAN brand; browser checks assert square styling and no logo button.
Mobile drawer regression and typecheck pass. Installed-PWA acceptance remains open.


Mobile-first sidebar iteration: full-width quiet active rows, hover/focus desktop
close and touch-visible mobile drawer controls implemented. Isolated desktop and
mobile checks pass for collapse/reopen, conversation selection, Escape/backdrop and
focus return. Physical-phone/installed-PWA safe-area, soft keyboard, rotation and
platform back behavior remain unverified; close via actual-device walkthrough.


Multiple local sessions correction implemented: sidebar history, independent drafts,
new-thread preservation, existing-thread migration and mobile picker. Isolated checks
cover three sessions, pending reply isolation, reload and sign-out cleanup; typecheck
and build pass. Real model latency remains D29; durable cross-device sessions D30.


24 November actual integration evidence: configured local API URL and exact hosted
CORS origins; only hosted API recreated. Real signed-in VS Code localhost:3100
Dashboard displayed hosted equity, zero positions and two closed-trade records.
Health/CORS/auth-required checks passed; unrelated origin rejected. This closes the
local-to-hosted account-read connection gap, not all journey/live acceptance. News
panel source, hosted Vercel release and remaining journeys still need closure.
Broker-login and live-market holds remain in force. Evidence: RESUME local frontend
connection checkpoint; hosting/oracle/README.md local frontend instructions.


Error-layer refinement: top overlay placement and dismissal verified with isolated
browser fixtures and typecheck; hosted visual acceptance remains pending.

Chat chrome follow-up: removed header labels and bottom explanatory controls;
inline retry/dismiss strip implemented and verified with isolated failure fixtures.
Build passed. Hosted acceptance and owner visual review remain outstanding.


24 November account/Discover iteration: name/email-only identity entry opens
Account & workspace; theme buttons moved into More settings. Removed redundant
workspace/funds labels and reserved desktop space for Discover. Typecheck,
production build and isolated responsive browser harness passed. News headlines
remain unwired in this panel: closure requires a read-only source contract with
attribution, observation/publication time, delay and failure handling. Until then,
show explicit unavailability. This is UI implementation, not live-data acceptance.


24 November 2026: migrated the approved playground into the actual Next.js frontend.
Chat / Dashboard / Trade; neutral white/charcoal, royal-blue original branding;
Inter body/support font self-hosted with license. Existing authenticated account,
watchlist, chart, risk, preview/placement and execution contracts reused. No backend
or trading-authority changes, production fixtures or fake model progress added.

Local checks passed: frontend typecheck/build, 15 chart-data tests, isolated Chrome
Firebase/API fixture checks for chat/error recovery, account failure independence,
request survival across navigation, context/drafts, selected contract, sign-out cleanup,
themes, mobile sheet/Escape and viewport overflow. Inspected desktop/mobile/dark
screenshots. These prove bounded UI behavior, not hosted/market acceptance.

Remaining: owner review, comprehensive accessibility/phone/zoom checks, publishing
and deployment when requested, then hosted Firebase/CORS/account/chat/chart evidence.
Broker login/live-market acceptance remains held until explicitly resumed. Close
with reviewed UI and deployed evidence; preserve D01/D07/D26 boundaries. Private
harness: `.local/design/check-live-workspace.mjs`; screenshots `.local/design/live-*`.

## D27 - Integrated UX design and journey validation

Typography iteration: increased playground body text to 16px, generally raised
labels/supporting text by 2px (minimum 12px), and larger display headings by 4px.
Local Chrome journey and mobile/landscape overflow regression checks passed.
Owner readability feedback remains pending; production app unchanged.

Latest visual refinement: user rejected blue-tinted surfaces. Playground now uses
white/neutral-grey light surfaces and charcoal dark surfaces, original #2455e6
royal-blue action buttons/logo, restrained native sans typography and tabular
financial figures. Layout unchanged. Re-ran local Chrome journey/viewport checks
and inspected light/dark Chat screenshots. Owner appearance acceptance remains open.

Visual correction: user rejected the green/editorial theme and explicitly chose
the main application's blue palette, original angular logo and font identity.
Playground now uses those colours, IBM Plex Sans/Mono (local assets and licenses)
and original SVG logo. Layout remains unchanged and unapproved. Local Chrome
journey/mobile regression checks passed; inspected updated light Chat/Trade and
dark Chat screenshots. This does not close layout/usability/accessibility work.

Standalone layout exploration: `design-playground/` now contains plain HTML/CSS/JS
for Chat, Dashboard and Trade, using fictional fixtures with no API/broker/model
connections. Production application source is untouched. Includes desktop and
mobile layouts, optional context drawer, local example chat, chart/depth/chain,
manual paper preview and order lifecycle, session stop and failure scenarios.
Local Chrome checks passed for the linked order lifecycle, stale preview
invalidation, mobile sheet/Escape and no horizontal overflow at 375/390/768/1024
widths and 844×390 landscape; no page errors. Captured and inspected desktop
Chat/Trade/Dashboard, mobile Chat/ticket and dark Chat screenshots.
This is bounded prototype verification, not a complete accessibility audit or
owner usability acceptance. Remaining: owner feedback, actual chart-library
integration, real schema integration, comprehensive accessibility/text scaling
and deployed acceptance. Fixed schematic chart data and in-memory-only chat are
documented in [the playground README](./design-playground/README.md).

Review checkpoint: behavioral brief v1 completed using Product Design and UX.
Resolved routine defaults DD-01–DD-08; added IC-01–IC-08 interface contracts,
state/recovery and AI-authority models, dependency ownership, evidence boundaries
and a handoff reading order. Reviewed normal and high-risk partial-fill, uncertain
submission, stale-preview and session-stop paths at document level. No app code,
broker request or trading permission changed. This completes the requested brief
review, not the whole D27 milestone: visual specification, owner walkthrough and
actual browser/accessibility verification remain open with owners/gates in the brief.

Skill-backed handoff update: installed `product-design-and-ux` from
`magnus919/agent-skills` at `cb581ffec17d3bb0aee2cf605716d107c6e378ad` in the user's
Codex skills directory. Applied state/AI-boundary/handoff guidance to add staged
implementation gates and UX-01–UX-10 observable criteria in the design brief.
Criteria are planned, not executed application acceptance. Visual direction,
mobile ticket choice, owner walkthroughs and browser checks remain open under D27.

Latest design instruction: disregard all current UI pages as layout/style/navigation
constraints. Preserve product requirements and backend semantics; design task-first
from scratch. The brief now includes practical hierarchy, cognitive-load, thumb-reach,
target-size, accessibility, feedback, recovery and data-honesty review criteria.
Existing prototypes remain exploratory; these criteria are not yet visually or
usability-verified. No application code deletion or rewrite is authorized by this note.

Prototype update: linked interactive journey now covers Chat → Trade → paper
preview/order/partial fill/position/exit → Dashboard review, mobile preview and
holiday/stale/chat failure/exposure-alert scenarios. Local DOM interaction checks
passed, including preview invalidation after a restriction and preserved input.
See the walkthrough matrix in [the design brief](./SWAN-UX-DESIGN.md).
Visual browser inspection and owner usability walkthrough remain unperformed;
these are design verification boundaries, not actual-market acceptance.

24 November 2026: [SWAN UX design](./SWAN-UX-DESIGN.md) now reconciles the original
PRD, current requirements, autonomous brainstorming, strategy handoff, workspace
plan and latest implementation checkpoint. Records Chat / Dashboard / Trade,
backend-to-experience contracts, primary-source UX frameworks, release/vision
boundaries and six priority journeys. Paper design only; no app code or permissions
changed. Existing illustrative mockup is exploratory, not user-tested acceptance.

Remaining by design: compare low-fidelity desktop/mobile alternatives, refine the
linked task journeys and error/exposure states, conduct owner walkthroughs, and
agree the implementation scope. Close this design item with reviewed prototypes
and recorded journey outcomes; track subsequent implementation separately. Actual
market qualification, hosted acceptance and broker checks remain under their
existing IDs and are not resumed by this design work.

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

Calendar-aware login now skips explicit holidays/finished sessions and missing or
unknown coverage before reading login secrets or contacting the broker. Daily and
boot jobs remain independent of API/worker startup and are resource bounded.
Hosted systemd run on today's holiday returned SKIPPED_MARKET_CLOSED at 08:46:33
UTC, exited successfully, and API health stayed connected; 13 focused tests pass.
Existing calendar coverage ends 30 November 2026; extend verified coverage before
then. Beyond coverage the job explicitly skips rather than inferring open days.
Subsequent actual scheduled login/stream acceptance remains outstanding.

24 November first hosted automatic login: user-configured secrets and manual
service invocation returned NEW_SESSION_VERIFIED at 08:39:33 UTC. Private one-time
setup and first login/profile verification are resolved. Observation heartbeat is
current with no problem/open positions; quotes remain prior-session data on today's
official Guru Nanak holiday. Subsequent scheduled renewal and open-session stream
checks remain required. This supersedes the missing-credential blocker below.

24 November broker automation: isolated daily-login job and host timer installed;
six focused tests and static checks pass. Missing credentials correctly skip the
service; server clock synchronized. Blocked on the user's private one-time PIN and
TOTP-seed entry. Closure requires successful hosted login/profile verification,
market-data reconnection and observed subsequent scheduled renewal. Do not equate
unit-test success or an enabled timer with actual authenticated broker access.

Status: HTTPS now passes external certificate-verified health checks at
https://swan-api.137-23-62-124.sslip.io. CORS permits the user's deployed frontend
https://swan-one.vercel.app and rejects an unrelated origin. Vercel's Production
NEXT_PUBLIC_API_BASE_URL setting and redeploy require the user's Vercel access;
no CLI/session was available locally. End-to-end browser acceptance remains open.
Experiment resumed after the user supplied SSH access on 24 November.
Docker and persistent swap are installed, the private flat-ledger snapshot is
restored, and a PostgreSQL memory overlay is prepared. Image build, migrations,
API health and observation-worker heartbeat now pass on the VM. Short idle samples
show approximately 226 MiB combined container working set, 451 MiB host available,
2–7 ms warmed health checks and no OOM/restarts. Sustained/live-data resource
acceptance remains open; busy setup showed severe CPU steal, later idle samples
did not. See latest RESUME.md for current evidence, superseding earlier missing
hostname/frontend status.
Earlier status: deployment package prepared; hosting experiment deferred at the user's
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
