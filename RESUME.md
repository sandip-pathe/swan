# SWAN implementation checkpoint

## Daily cap correction: 26 November 2026

User clarified minimum ZERO, maximum FIVE. Supersedes the scheduled-window and
fallback-brief design below: removed all timed slots and automatic filler briefs.
Qualified ideas can publish whenever their conditions pass, with a persistent
atomic five-new-insight ceiling per IST day. No requirement to produce any item.
Separate five-background-provider-attempt ceiling and all qualification gates
remain. No positive-quality/performance claim from static checks. Python compile
and focused Ruff passed; no tests/provider/live checks run. Local only, not pushed
or deployed; the explicit deployment hold remains in effect.

## Local daily curation and research limits: 26 November 2026

Implemented five persisted IST update windows: 09:35, 10:30, 11:30, 13:00,
14:30. Each has one stable insight identity. A qualified idea can take the window;
after 15 minutes without one, publish a deterministic source-timestamped market
brief, with zero AI usage. An idea may promote that same brief later in the window
without increasing the daily unique insight count. No past-window backfill after
an outage, no off-session scheduled updates and no fabricated trade to meet quota.
Four/five useful daily deliveries depend on worker uptime and available evidence;
missing data is reported honestly rather than turned into an entry signal.

Added directional-efficiency/chop filtering, deterministic candidate ranking and
trend-pullback strategy alongside range retests, failed breaks and existing weekly
structure. Scores are heuristics, not win probabilities. Live reference, option
identity/expiry/depth/spread/noise/cost checks run before new idea publication and
research enqueue. Existing eligibility, five-percent reference and stale-research
constraints stay; periodic fifteen-minute research re-enqueue was removed.

Provider boundary atomically reserves at most five background research attempts
per IST day and at most one per insight/day. Failures/interruption count; state
survives restart. Blocked attempts consume neither call nor token reservation.
Chat routing/answers remain on-demand and share the existing token budget; the
five-call ceiling applies to automatic Insights research, not interactive chat.
News can invalidate/suspend context but cannot bypass the paid-call ceiling.
Brief sources now display linked headlines instead of a missing candle action.

Python compile/Ruff and frontend typecheck/production build passed. No tests or
provider/live-market checks run for this slice. Strategies and quota behavior
have NOT been accepted on a real session. D34 remains open for observed delivery,
latency, restart behavior and prospective outcomes. All changes are LOCAL ONLY;
Oracle deployment remains held until explicit agreement. Latest orchestration
and curation changes have not been pushed to trigger Vercel either.

26 November correction: the hardcoded greeting remained after the previous
"remove templates" request. Removed it from chat and the orchestration fast path.
Greetings now use the router's natural direct_answer with sections=[]; no market
snapshots are loaded. General replies are model-written, not scripted. Hosted
backend remains unchanged per user's deployment hold. Static checks passed;
real provider routing/latency remains unverified for this local slice.

## Local-only chat orchestration: 26 November 2026

User explicitly requires agreement before further Oracle deployments. This slice
is local only; do not deploy it or treat earlier deployment permission as current.
Chat now plans context before retrieval. Greetings now receive AI-written replies without market retrieval;
AI plans session/market/news/weekly/ideas from request + bounded history. General
education/conversation can return directly from that same AI call with no saved
market reads. Data questions retrieve only selected sections of the worker's
existing SQLite snapshots (same sources used by Insights), then synthesize a reply.
No Angel One/news-fetch calls, collector triggers or full dashboard context load
occur in this chat path. Session/quote/analysis freshness and idea personalization
remain enforced. Selected idea lookup is lazy; only the ideas route loads it.
Routing failure returns an explicit failure without silently reading all data.
Both model stages reuse existing budget/lease/timeout controls; output is schema
validated and planner results can reuse the existing content cache. Response
includes context_sections/routing_status for diagnosis, not model reasoning.
Static Python compilation and focused Ruff checks passed. No test suites or
provider/live-market acceptance runs were performed for this slice. Closure:
agree on deployment, then observe real no-context/news/market/follow-up routing
and latency. This remains distinct from trading-edge acceptance under D34.

26 November chat correction: market-hours questions now use the exchange calendar,
not candle-gap assessments. Greetings are short; general questions reach bounded
OpenAI synthesis with calendar, available market/news/weekly context even when
candles are incomplete. AI failures are explicit. Hosted configuration reports
AI ready with model configured. One real hosted chat call returned VALIDATED
from OpenAI with a contextual news/price-action explanation. Conversational
answers now use a dedicated answer/evidence schema, without the research-report
thesis/counterargument template. This is integration evidence, not trading-edge
acceptance. Oracle API deployed and public health reports database connected.
Removed repeated generic source warnings and per-answer Insights buttons. Chat
scroll surface now spans the screen with centered padded content/composer.
Frontend deployment remains user-owned; production mobile visual review remains
pending. No tests added/run, no order permissions changed.

## Insights cleanup: 26 November 2026

Removed the no-idea Ask SWAN button and the About this research footer at the
user's request. Restored the earlier blue text/underline active Chat/Insights tab
style. Removed the corresponding unused footer/button CSS. Added an accessible
icon-only logout control, smaller header logo, mobile safe-area padding and more
comfortable feed/settings/chat spacing. Budget controls wrap on narrow screens.
Frontend typecheck and production build passed. No backend changes.


## Insights product UI simplification: 26 November 2026

User rejected the operational dashboard and repeated empty-state/caveat cards.
Used karpathy-guidelines and ui-ux-pro-max; scope is the existing Insights screen,
not a new application or backend rewrite. Latest/Saved filters, compact market
strip with real source timestamps (quote or historical candle fallback), current
idea feed, short linked news rows and a collapsed weekly view now lead the page.
One compact no-idea state replaces the stack of empty diagnostics. No fake setup,
prices, returns or live freshness were added. Chat and single-account login kept.

Budget, notification control and storage/data diagnostics are behind the Settings
icon. Existing affordability/5% reference, entry reporting, stars, local archive,
source evidence, sync and research boundaries remain. Empty prospective evaluation
metrics are no longer shown.
Idea cards show one waiting reason first and disclose remaining risk/evidence on
request. Real dates/times remain visible alongside historical market values.

Found a concrete development PWA issue during visual inspection: cached public
shell/dev chunk URLs served old React/CSS and old API target after reload. PWA
registration is production-only now; development unregisters only this origin's
root SW and clears only swan-public-bot-* public caches, preserving private IDB/
chat data. Production offline shell remains enabled, version bumped to v4.
Hard reload loaded the current signed-in layout. This also resolved conflicting
old/new preview appearances during the earlier login/configuration updates.

Observed the real signed-in UI with hosted market/news context, Settings expanded
and collapsed, and Latest/Saved empty states. Inspected desktop preview and 390px
mobile layout; restored normal width and Latest afterward. Typecheck, production
build and SW syntax checks passed; no test suites added/run. No active eligible
idea was available for visual acceptance; no fixture performance claimed.
Pushed bot/read-only; user Vercel deployment remains the external step.

## Local preview authorization/endpoint correction: 26 November 2026

The screenshot's running localhost:3200 bundle was compiled against localhost:8002,
despite another workspace's env pointing to Oracle. Both local .env files had no
SWAN_ACCOUNT_BINDINGS. That local bot API rejected every signed-in account with
403 ACCOUNT_NOT_AUTHORIZED. Saved-insights route only reads SQLite; it never calls
AngelOne, so daily broker login was not the cause. Initial assumption that this
was Oracle's mapping was corrected after inspecting the served bundle.

Synced the existing single hosted account binding into ignored local configurations
(same Firebase project, no new identity grant). Added exact localhost/127.0.0.1:3200
CORS origins locally, restarted only the local bot API. Actual signed-in preview
requests to insights/events then returned 200; embedded UI error disappeared and
loaded its full context. Local data was empty because no local collector ran.
Both ignored frontend env files now point to the existing Oracle API; added exact
3200 preview CORS origins to hosted runtime config, preserving existing origins
and account bindings. Hosted health/CORS verified. Embedded signed-in preview then showed hosted worker heartbeat, closed calendar, partial weekly history and available RBI/Mint sources with no authorization error. No broker login/order gate changed.

Frontend now parses detail codes: account binding, broker-session, provider rate
limit, generic forbidden, expired sign-in and connectivity are distinct categories.
Unknown HTTP 403 is no longer automatically called an account authorization issue.
Temporary private auth diagnostic deployed during investigation was removed from
source/hosted API; no token/password was captured. Existing cloud binding unchanged.
Frontend typecheck/build passed; no test suite run. Vercel user deployment remains
pending for the new frontend wording. Local API remains running on port 8002 as a
secondary dev service; the preview now targets Oracle for live saved context.

## Minimal login and offline shell: 26 November 2026

Full-page login now reuses Brand (existing SWAN SVG/wordmark), with just one masked
six-digit numeric password field and bottom Login button. Removed visible email,
Google option, card surface and introductory text; accessible labels and contextual
errors remain. Fixed email defaults to the literal user-supplied
`jit4xxxx@gmail.com`; NEXT_PUBLIC_BOT_LOGIN_EMAIL can override it if that address
was redacted. Firebase validates the existing password; no code/password was
invented, embedded, stored by application code or reset in this change. The account
must already have its requested six-digit password. Oracle still has one authorized
Firebase account binding; all users of that shared account share its server data.

Firebase persistent session is retained; existing account-scoped IndexedDB stores
insights, localStorage stores chat/drafts/preferences. Offline reopen defaults to
Insights when no screen is specified, provided the device previously signed in and
received data. First login/new data/model replies require network. Service worker
v3 caches all local fonts/icons/manifest and page chunks, commits a new HTML shell
only after its referenced chunks are cached, opens downloaded UI immediately and
refreshes a complete shell in background. Password/auth API responses are not put
in the service-worker cache. Sign-out intentionally clears this account's archive.
Browser/site-data deletion can remove offline data.

Deployment: Oracle API health 200, existing Vercel URL 200 but still serves the prior
frontend. User previously chose to deploy Vercel; deploy bot/read-only with root
apps/web and existing Firebase/API settings (plus email override only if needed).
No backend deployment needed for this UI change. Frontend typecheck/build and SW
syntax checks pass; visual preview could not run because browser access host was
unavailable. Real authenticated six-digit sign-in, offline cold launch and device
install behavior are not claimed verified. No password change/account creation
was performed. D34 records remaining deployment/device acceptance.

## Source continuity fixes: 26 November 2026

User explicitly requests autonomous integration and normal operation; live-market
observation is ongoing monitoring, NOT a user approval/release gate. No additional
questions or manual depth investigation are required from the user.

Root cause corrected: depth mapping had already been reviewed on 23 November in
config/paper-execution.json, SMARTAPI-DEPTH-UNITS-QUESTION.md and the later D03
acceptance update. The bot failed to reuse it. Advisory feasibility now applies
that reviewed units mapping ONLY to unknown AngelOne SnapQuote metadata, retains
source URLs and leaves raw quantities unchanged (no lot multiplier). Original paper
risk/qualification/order permissions are unchanged. Written broker confirmation
was never claimed and is not a newly imposed bot-release requirement.

RBI RSS was falsely empty because its publication dates omit the timezone. Explicit
source-level Asia/Kolkata interpretation fixes this; unknown offset-less sources
still require their own configured timezone. Replaced unusable BSE RSS with Mint
markets/economy publisher feeds. Hosted reads: RBI 10, Mint markets 35, economy 27
usable entries; bounded archive keeps 30. Linked short excerpts only, source times
and relevance filter, no full-article scraping. Source outages retain bounded old
items with original timestamps; retained items cannot trigger fresh-catalyst calls.

Daily history requests now start/end at calendar-day boundaries, persist completed
OHLC/session provenance and retry up to two missing days per pass. Broker returned
no daily rows in observed calls. Added bounded Yahoo ^BSESN daily-history fallback
with symbol/currency/exchange/type, completed-session and OHLC validation. Hosted
fallback recovered four required sessions; 25 November was still absent. Cache
retains valid context and automated hourly recovery continues without user action.
Partial weekly context exposes available-session range and last available close;
only the five-session breakout rule waits for its actual missing input. Secondary
history is labelled and never used for live option quotes or depth.

Independent opening/recent-bar facts remain usable and explicitly partial; chat/AI
can explain supported partial context instead of declaring the entire market
analysis unavailable. Range entry rules still require their actual dependencies.
Ruff and Linux mypy pass; no tests added/run. Oracle rollout and GitHub branch are
updated. Live latency/usefulness/outcomes remain observations to collect during
normal operation, not permission requests or guarantees of edge.

## Decision assistant implementation: 25 November 2026, 23:55 IST

Current worktree `D:/s/swan-bot`, branch `bot/read-only`. This checkpoint supersedes
earlier observation-only implementation descriptions. Built and deployed the
conditional SENSEX decision-assistant API and event worker on existing Oracle.
The user deploys Vercel; only Chat and Insights remain product destinations.

Implemented bounded streaming (two indices, at most eight selected options),
independent opening/recent bar windows, startup history plus targeted repair/backoff,
contract recentering, versioned range-retest-v1/failed-break-v1 intraday ideas and
separate five-completed-session weekly structure. Contract identity, quote age,
depth, premium noise, estimated fees/slippage, whole-lot affordability and the
5%-of-position-premium reference gate eligibility. Unknown depth units still block
eligibility. Premium stop/target scenarios freeze after initial eligibility.
No order routes, tools or broker holdings access were added.

Compact AI research provides thesis/counterargument/next observation for new ideas,
relevant fresh catalysts, bounded reassessments and explicit chat follow-ups.
Cross-process lease, bounded queue, persistent conservative daily reservations,
cache, strict schema/evidence/numeric validation limit token use. No tick/minute
model polling. RSS uses attributed official excerpts; unavailable/old data cannot
be presented as an immediate catalyst or a full report.

UI includes idea conditions, contracts, source times, net scenarios, budget setting,
manual entry reporting, selected-idea chat and hypothetical outcome summary.
Atomic revisions/feed/outbox, authenticated SSE with poll fallback, IndexedDB archive
and optional short-TTL generic browser push are implemented. Existing credentials,
Firebase, API address and Oracle deployment configuration are reused.

Evidence: Ruff, Linux mypy, frontend typecheck and production build passed. No test
suite added/run. Hosted health=200, unauthenticated insights=401, trading arm=404;
closed-session worker heartbeat current and broker-login timer active. Old API,
worker and PostgreSQL remain stopped with data preserved. Pre-migration SQLite
snapshot integrity passed. Off-host AES-GCM encrypted backup was decrypted and
passed SQLite integrity. Windows task `SWAN Bot Encrypted Backup` is Ready, daily
00:20 local/StartWhenAvailable, retains seven encrypted copies. Existing SSH key
is required to decrypt; machine availability and future task runs remain relevant.

D34 stays OPEN: markets closed; actual streaming/depth, latency/resource envelope,
reconnect/chaos, signed-in/offline/push delivery, real model usefulness and prospective
edge are not accepted from build checks. Hosted RSS had RBI empty/BSE unavailable;
weekly daily source coverage was incomplete. No supported eligible idea, model
answer, win probability or INR 500/day promise was fabricated. Full reports,
manual exit/actual-cost capture and per-reported-fill monitoring/alerts remain
unimplemented; entry reporting is not broker monitoring or an enforced 5% stop.
Full replacement-host restore and future scheduled backups still need acceptance.

## CEO design review: 25 November 2026

User requested plan-ceo-review only, after rejecting an observation-only bot and
repeated full-session scans. Saved docs/designs/market-decision-assistant.md as a
HOLD SCOPE design proposal based on prior user constraints; not implementation or
market acceptance. Recommended event-driven bounded collector + compact AI research
+ deterministic contract/risk/cost/freshness verification + versioned idea lifecycle.
Both intraday and weekly research retained. Reuse existing auth/PWA/archive, stream
and catalog adapters after audit; do not restart old trading services. User's
instruction against repeated questions overrides per-finding skill ceremonies;
recommendations are not represented as explicit individual user approvals.
Eight sequenced tasks, error/security/test/performance/rollout review and unresolved
acceptance criteria are in the document. Existing whole-session invalidation must
be replaced with dependency-specific validity. Existing delayed NewsData branch
(43,200 seconds) is unsuitable for claims of immediate catalysts. No code, tests,
provider calls or deployment changed in this review. Engineering review remains
required before implementation clearance; D34 tracks retained scope and acceptance.

## Product alignment correction: 25 November 2026

User explicitly clarified: wants AI-assisted trading decisions/best bets, including
predictions/scenarios, strategies, call/put/action ideas informed by broker data,
news/reports and analysis. No execution means user places orders, NOT that ideas
must avoid actionable guidance. Current observation-only bot is insufficient.
BOT-SCOPE.md now leads with the corrected intended deliverable and staged pipeline.
No speculative recommender was enabled in this clarification pass. Existing prompt
prohibits entry/exit recommendations; recorded as a mismatch to replace alongside
contract/quote evidence, structured conditional ideas, mechanical validation and
source-linked reasoning, not by simply deleting protective input checks. Weekly,
news, option feasibility, idea lifecycle and measured outcome evaluation remain
unimplemented/accepted scope in D34. Current deployed behavior is unchanged.

## Answer quality and SENSEX coverage: 25 November 2026

Implemented separate SENSEX/BSE and NIFTY/NSE completed-candle collection with
independent BFO/NFO calendar checks. SENSEX is the default chat focus; explicit
NIFTY questions select NIFTY. Both contexts appear in Insights. Correct venue/token
pairing is enforced; default NIFTY query compatibility remains. Docker bot image
now also overlays the updated index-history module from the source bundle.
One shared, bounded ten-minute gap-repair request per collection pass, ten-second
history timeouts and twelve-second quote timeout constrain load. Conflicting
backfill OHLC is rejected, never silently overwritten. Primary and repair snapshots
retain separate provenance. Unrepaired gaps cannot publish a current scan.

Hosted real saved-session reads returned 371 SENSEX candles, missing 15:16-15:19
IST; NIFTY returned 370, missing 15:15-15:19. A narrower SENSEX 15:14-15:24 request
returned six candles and the same four omissions. This confirms persistent missing
source observations in those responses, not successful recovery. Saved historical
snapshots are in bot storage; no insights were fabricated. Open-session latency,
SENSEX continuity and provider recovery still need actual acceptance under D34.

Answers now lead with deterministic interpretation, counterevidence/invalidation
and source limitations. Model calls require an explanation/research-style request
and current evidence. Repeated same-context explanations are cached; daily cache
cleanup, budget reservations and no background model calls remain. Explicit weekly/
news questions disclose missing history/feed instead of implying current research.
A position-loss question with a stated premium can calculate the agreed 5% using
Decimal; no orders, holdings monitoring or automated exits. Actual hosted calls to
answer() with saved evidence returned the SENSEX gap explanation and INR 300 loss
reference on INR 6000 with zero model calls. This is not signed-in frontend/model
quality acceptance. Public health sample 0.063 seconds, not a latency guarantee.

Extended explicit NFO/BFO calendar through 31 December 2026 from published 2026
holiday notices (Christmas closed), maintaining prior timing sources. BSE official
page returned 403; the BSE-authored notice from the existing broker mirror was read
again. Sources and retrieval basis are in calendar_source. Updated both bot config
and the original auto-login config; backed up original calendar beside ledger dump.
January 2027 dates were not inferred. D26 remains open for subsequent scheduled/
open-session acceptance and renewal before the new coverage boundary.
Frontend build/typecheck and Python Ruff/Linux mypy pass. No new test suite or
real model request ran in this pass. Vercel deployment remains the user's task.

## Local-first insights and slim public backend: 25 November 2026

Bot workspace D:\s\swan-bot, branch bot/read-only. User prioritized timing,
reliability, information quality and low token usage; intended SENSEX option buying
intraday/weekly swing research, total capital INR 25k or 1 lakh. User clarified
5% loss per position and explicitly reiterated that this bot does not trade.
For analysis, INR 6,000 premium paid gives an INR 300 reference loss threshold;
this is not an enforced cap, execution instruction or guaranteed realized loss. INR 500 net/day is an evaluation example, never a guaranteed quota.
BOT-SCOPE.md now separates implemented functionality from the intended catalogue.

Implemented account-scoped IndexedDB archive, monotonic paged insight sync,
15-second visible polling on either screen, reconnect catch-up and star/unstar
retention (200/account). Unchanged starred payloads are not retransmitted. Cursor
and new local records commit atomically. Public PWA shell/static chunks are cached
for offline reuse; private API responses are not. Browser eviction/sign-out clears
local history, catch-up past seven-day/1000-record server buffer is not guaranteed.
Unstarred server insights/evidence expire; starred evidence persists. Source evidence
is still on-demand, not archived offline. Closed/suspended delivery needs future push.
Collector is aligned to minute+03 rather than request-duration drift; insights now
carry publication time. No background model calls were added. Real source-to-device
latency and the new persistence/retention behavior still need acceptance (D34).

Oracle updated, bot health passed, then Caddy switched to bot-api:8000. Reload alone
initially saw an old bind-mounted Caddyfile inode; recreating only Caddy fixed it.
External health now identifies swan-bot, unauthenticated insights=401, trading arm=404.
Fresh legacy preflight counts all zero. Original API, worker and PostgreSQL are now
stopped; volumes/images/source remain. Login timer active; --no-deps login command
does not need PostgreSQL. Only bot API, bot worker and Caddy remain continuously up.
One idle sample: API 66 MiB, collector 64 MiB, proxy 10 MiB; host available 513 MiB.
These are samples, not capacity or open-session latency guarantees.
Root-only ledger backup /opt/swan/backups/bot-cutover-20261125T154552Z/legacy-ledger.dump
is 4,657,144 bytes, archive listing readable (243 lines); restore was not exercised.
Caddyfile.before-bot is beside it. See updated runbook for reversal/start order.
Vercel deployment is still assigned to the user; the legacy frontend is no longer
compatible with the public bot API. Build/typecheck and Python Ruff/mypy pass for
this change. No test suites or real model calls were run in this pass.

## Read-only collection resumed: 25 November 2026

User explicitly resumed read-only collection/freshness checks and will deploy
Vercel themselves. Bot branch remains bot/read-only; public Caddy still serves the
old API pending coordinated frontend/API cutover. No trading permission changed.
Oracle collector is enabled using root-owned /opt/swan-bot/.env (0600); pass
--env-file /opt/swan-bot/.env explicitly to Compose (see BOT-RUNBOOK).
Fresh legacy ledger preflight returned zero enabled accounts, open positions,
active orders, validations and arms. Stopped swan-worker-1 to avoid duplicate
collectors; original API/PostgreSQL/Caddy and automatic-login timer remain running.
Bot worker heartbeat reports closed after cash hours, not paused. Existing broker
session was created today; two bounded quote/history probes succeeded using it.
NIFTY quote timestamp 16:08:11 IST and SENSEX 15:32:29 IST were hours old at the
21:04 IST check and do not establish live freshness. NIFTY historical response
contained 370/375 expected minutes, missing 15:15 through 15:19 IST. Analyzer
returned insufficient and withheld scans. No bars were filled or insights invented.
Next verified session is 26 November 09:15 IST; actual open-session freshness,
provider gap investigation/recovery, authenticated latency and model usefulness
remain unaccepted under D34. Existing coverage ends 30 November (D26).

## Isolated market bot implementation: 25 November 2026

Active bot workspace is D:\s\swan-bot, branch bot/read-only, forked from 21c2c21.
Original project remains preserved. User confirmed exactly Chat and Insights; reused
the existing Chat component, owner-scoped device storage and Firebase configuration.
New services/bot exposes only bot reads/evidence/chat and uses separate SQLite WAL
storage. One collector calculates NIFTY SMA/range conditions on completed source
bars; no old trading runtime, database migrations or trade routes are started.
Collection defaults paused per the existing provider acceptance hold. Existing
Oracle automatic login is retained. Full source snapshots are separate from the
small insight list and inspectable on demand. Optional chat explanation uses the
existing model/config with durable conservative reservations and output validation.

9 bot + 13 isolated login tests, Ruff and Linux mypy pass. Frontend build/typecheck
and 15 inherited chart tests pass. Fixture browser check passes two-screen routing,
reused chat, paused/empty states and mobile overflow; screenshots inspected. Local
API health passes. Oracle isolated staging is now running under /opt/swan-bot;
bot-api is healthy, the collector reports paused/collection_enabled=false, and the
original auto-login timer remains active. Three warm unauthenticated local health
samples took 0.003-0.060 seconds. Hosted no-token Insights returns 401; the old arm
route returns 404. These are basic hosted boundary checks, not authenticated latency
or source acceptance. Image builds reuse the installed swan-backend:local environment
with a small bot-only layer after a fresh dependency-layer export was too slow.
Public traffic has not switched. Vercel access and resumption of read-only source checks
were asked asynchronously; neither is inferred from elapsed time. BOT-RUNBOOK.md
records deployment, rollback and remaining real acceptance. D34 remains open.

## Slim market bot scope: 25 November 2026

Created BOT-SCOPE.md after user requested slim research, market-data, validation and
insight workers. Proposal uses three logical jobs in one process, code-based scans
on completed bars, model explanations only for material changes/questions and a
shared saved evidence store. Initial suggested universe is NIFTY/SENSEX plus up to
ten explicitly selected option contracts; horizon and universe await confirmation.
No implementation or hosted changes in this scope pass. Existing worker/auto-login
remain retained; broker/live-market acceptance stays paused. D34 tracks the proposal,
implementation and real usefulness/data acceptance. Research references are linked
in BOT-SCOPE.md; trading bot execution responsibilities were reviewed and excluded
from the proposed new slice, not removed from the existing system.

## GitHub checkpoint and product hold: 25 November 2026

User requested preserving the complete current project on GitHub, then explicitly
withdrew undeployment. Oracle services, the worker and automatic login are retained;
no hosted change is authorized by this checkpoint. A smaller read-only market bot
was discussed but is not implemented, and existing trading code is not removed.
Frontend production build/typecheck and 15 chart tests pass; 13 isolated automatic
login tests and Ruff on changed Python files pass. The broader backend selection
encountered database-dependent fixture errors and was interrupted; full database
regression remains unverified. Staged credential-pattern scan found no private keys
or provider/GitHub tokens; local environments, keys and private artifacts are ignored.

## Backend follow-up: 25 November 2026

Resumed D33 with read-only Oracle diagnostics at 09:08-09:10 UTC. OCI metadata
identified VM.Standard.E2.1.Micro (1 GiB RAM; shape config reports 1 OCPU/2 vCPUs).
OCI documents this Micro shape receives less than a full OCPU and cannot burst.
Load rose from 3.63 to 5.48, with 350 MiB available RAM and 379 MiB swap in use.
Four vmstat intervals showed 94-95% CPU steal. Docker working sets were API 100 MiB,
worker 113 MiB, PostgreSQL 97 MiB and Caddy 25 MiB; the worker sampled at 206% CPU.
The API container was unhealthy after repeated 8-second health-check timeouts;
three external unauthenticated `/health` calls returned 200 in 1.09-3.47 seconds.
The VM is constrained by CPU availability during this sample; root quota/entitlement
is not established, and worker CPU is not proven causal. This is consistent with
the severe CPU limit observed, though the guest's exact current CPU entitlement is
not measured. Memory pressure/swap was also observed. No host service was
restarted or changed. Authenticated latency and
provider quota diagnosis remain open under D33. Broker and live-market acceptance
remain paused.

Backend chat now short-circuits a strict allowlist of greeting-only messages to a
source-free informational reply, avoiding planner/answer model calls and DB context
reads. This is a local D29 improvement; it has not been run against the hosted API.
Grounded-question latency, recovery behavior, authentication timing, and p50/p95
evidence remain open. No tests were run in this pass.

Worker quote/reference publication is now revision-gated locally: accepted cache
observations and a completed metrics refresh trigger persistence; unchanged cache
state no longer scans every contract and republishes references every second. The
1-second heartbeat and 250 ms execution watchdog are unchanged. This reduces idle
work without relaxing exit or permission checks; active-market CPU impact is not
measured. Not tested or deployed.

Static refresh-path review: authenticated quote refresh is a synchronous API route;
it holds a global advisory transaction lock/DB transaction while awaiting provider
calls (bounded at 80 seconds), with a 30-second cooldown. This can occupy a request
thread and DB connection during slow refreshes; causal impact on ordinary reads is
not measured. No quote refresh or provider call was made because live-market checks
remain paused. Review implementation and refresh semantics when that acceptance is
resumed.

## Trade page learner-focused pass: 25 November 2026

Trade now uses **Options / Watchlist / Find** with a quiet underline state. Find
starts with a short search and market selector; call/put and expiry are tucked under
Filters. Contract rows use readable strikes and plain Call/Put plus View chart labels.
The watchlist, option chain and underlying price context use simpler language, while
saved quote times remain explicit. Added a nearby, optional explanation for bid,
ask, open interest and volume. Fixed generic primary-button styling that had turned
every contract and option-chain row bright blue. Option-chain loading now shows
row-shaped skeletons. Charts open without VWAP/DEMA lines; optional controls
and a short explanation live under Indicators. The paper-order planner leads with
cash needed, available cash, planned loss and usable quantity; fee math stays in an
expandable breakdown. On phones the planner is a bottom sheet. All existing server
validation, review and trading permission gates remain in place.

Frontend typecheck, all 15 chart-data tests, diff checks and the isolated browser
workspace suite pass. That fixture suite verified Find-to-chart navigation, mobile
order-sheet display, Back/Escape dismissal and overflow; it made no order calls.
The local signed-in app showed hosted saved market observations. Its Find catalog was
marked stale, so we did not open a stale contract or test broker/live-market actions.
Actual-market and installed-device acceptance stay open in D28.

Follow-up after visual review: removed the always-visible desktop watchlist column
from Options/Find. Watchlist content now renders only when its own tab is selected;
the Options/Find view uses the full available width on desktop and mobile. Removed
stale CSS that had hidden the Watchlist tab on desktop. Typecheck, all 15 chart tests,
and the isolated browser suite pass after the correction. Fixture tests do not
establish fresh hosted option data or actual-market acceptance.

Spacing follow-up from owner review: restored a 28px desktop inset and 16px phone
inset between Trade content and the app edge/sidebar. Removed the optional Bid/Ask/OI
glossary disclosure from the Options chain. Verified the desktop inset and removed
glossary with an isolated browser assertion; typecheck and chart suite pass.

Chart/order follow-up: the candlestick chart is now the main full-width surface, with
its chart tools below the plot. Removed the persistent buy form; one Buy button opens
a responsive native dialog containing the existing estimate, review and paper-order
flow. Its copy now explains that the estimate is informational until the user
confirms the paper order. Replaced "practice session" wording with plain paper-buying
status and controls. No order permissions or server checks changed. Typecheck, build,
15 chart tests and isolated desktop/mobile dialog, Escape and browser-Back checks pass.
Browser tests use fixtures only; hosted data and actual-market acceptance remain open.

## Trades and History presentation refinement: 25 November 2026

Trades now leads with available cash and a proportional cash-availability bar;
accounting detail and sale-release reasons are disclosed on demand. Empty order and
position states use plain explanations, and past orders/fills are collapsed until
requested. History uses beginner-friendly daily result labels, a compact key-metric
set, expandable accounting detail, and skeleton loading for reports and closed
trades. Journal errors have an inline retry. Removed the full-width Dashboard view
rule and decorative borders below application panels/disclosures across SWAN;
retained separators inside dense tables and market rows. Tightened spacing after
removing those rules.

Typecheck, Dashboard spacing check, and isolated browser fixture/navigation/mobile
suite pass. No hosted account checks or live-market acceptance.

## Dashboard views: 25 November 2026

Kept Overview intact and replaced the Dashboard subnavigation with four views:
Overview, Trades, Decisions and History. Trades reuses the account-backed open
position, pending order, funds, order and fill components. Decisions combines the
saved cited decision view with recorded agent/risk decisions; malformed activity
responses now show an unavailable state instead of crashing the dashboard. History
groups the daily report, closed positions and expandable cash movements; incomplete
report/journal responses are handled as unavailable. Removed technical Activity from
Dashboard navigation and linked Discover to Decisions. Legacy URL hashes resolve to
the new destinations.

Typecheck and isolated browser fixture suite pass for the four tabs, their routes,
Overview return behavior, mobile overflow, chat and trade navigation. Fixtures do not
establish hosted backend acceptance. No hosted changes, broker checks or order actions.

## Cross-screen content and icon proposal: 25 November 2026

User requested brainstorming before extending dashboard simplification across the
important screens. SWAN-SCREEN-PLAN.md now specifies navigation, exact copy, show/
detail/hide priorities, icons/emoji/illustration choices, order/permission/recovery
semantics, state messages and capability limits. Standalone design-playground/
screen-plan.html is an interactive review board with 19 proposed views and inline
icons from the installed Lucide package; it makes no API requests. Dashboard strip
proposal: Overview / Trades / Decisions / History; technical Activity moves out of
routine navigation into relevant stories/operator maintenance. Native bottom tabs,
original blue/neutral identity and existing authority gates remain constraints.

No application/backend code changed in this planning pass. Board interactions and
320/390px overflow checked; light desktop/dark mobile screenshots inspected. This
is review-artifact verification, not learner research or completed implementation.
Existing D27/D28 cover design/journey review and actual UI migration/acceptance.

## Loading, saved snapshots and server diagnosis: 25 November 2026

Immediate route/auth/workspace/portfolio skeletons replace the text-loading waterfall.
Dashboard portfolio reads start independently of workspace. Owner-scoped display
snapshots (workspace, portfolio, linked agent evidence) persist in localStorage, bounded
to 1 MB each/24h and cleared on sign-out. They render as historical previews; cached
workspace does not establish monitoring/readiness/entry permission. Portfolio expiry
now advances independently of successful requests (the prior clock could freeze).
Failed/background reads preserve visible values; historical buying power is labeled.
Removed the duplicate workspace error/stale notices, unused Dashboard chain fetch,
workspace refetch on navigation and chain-filter changes. Chain polling now runs only
on Trade > chain. Hidden/offline reads pause; workspace failure retries back off
10/20/40/60s, portfolio 20/40/60s. Successful polling remains workspace 5s/portfolio
10s after completion, with no overlapping reads. Refresh balance activity is manual;
background reads do not toggle its label or disable it. Agent refresh retains records.

Read-only OCI diagnosis: health took 9.59s; uptime load 5.71, 422 MB swap; vmstat
measured 74?94% CPU steal in two interval samples. Containers healthy, zero restarts.
API error scan had no matching exception; Caddy recorded /api/workspace response
aborted after 15.70s with writing: http2: stream closed. CPU availability is a major
observed issue, not proof of a specific Oracle quota/root configuration. No server
changes, broker login, provider checks or trading changes. D33 tracks host follow-up.

Verification: production build/typecheck pass; isolated held-response browser check
passes immediate skeleton, parallel reads, cached reload, historical labels, retained
values after 503, no Dashboard chain requests, mobile overflow and sign-out cleanup.
The broader isolated workspace/native regression suite also passes after updating
its old dashboard heading assertion. Initial workspace revision arrival no longer
cancels a parallel portfolio request.
Evidence: .local/design/check-dashboard-loading.mjs. Real backend timing/logs are
read-only observations, not actual-market acceptance; D28 remains open.

## Dashboard surface alignment: 25 November 2026

Resolved legacy zero-side-padding panel rules and global details bottom borders
for the beginner dashboard. Cards now own consistent 28px desktop/20px mobile
insets, neutral surface backgrounds, borderless disclosures and aligned headers.
Dark desktop and mobile fixture screenshots inspected; spacing/overflow assertions
and typecheck pass. Local frontend running on port 3100 against existing hosted
API configuration; no local backend launched. Actual data acceptance remains D28.

## Beginner dashboard experiment: 25 November 2026

Local real Dashboard now uses plain labels, a cash available/held visual bar with
accessible text, expandable agent reasoning and source timing, simple agent role
names, friendly empty states and a static three-part trading lesson (idea, downside,
cost). Existing real GET data and permission gates retained. Emoji are decorative;
no trading streaks, reward loops, made-up returns or fabricated agent conclusions.
The cash bar is shown only for valid nonnegative cash/available values and describes
cash only. Advanced accounting remains expandable. Design is an experiment pending
user feedback, not validated learner research. Typecheck and isolated 390/1440px
render/overflow checks pass; screenshots inspected. No deployment or live checks.

## Dashboard evidence and account overview: 24 November 2026

Real local app overview now surfaces available cash, realized P&L and fees alongside
equity, exposure and session P&L; missing baseline is explained rather than zeroed.
Removed generic insight filler. DashboardIntelligence reads existing account-owned
agent activity (12 records) and up to three linked output evidence records, showing
rationale, concerns, saved headlines with publisher/date/provider delay and saved
contract prices. These are historical cited observations, not a live news feed.
Worker mode, readiness, heartbeat and account snapshot time are separate. Empty,
loading and error states preserve the rest of the overview; refresh issues GETs only.
Typecheck/build and isolated browser checks passed populated/empty/failure states,
attribution and 320?1440px overflow checks; broader workspace fixture suite passes.
No deployment, real broker/model checks or trading gate changes. D32 tracks live
news/index/learning expansion; D28 actual hosted/device acceptance remains open.

## Native PWA foundations: 24 November 2026

Implemented locally in the real Next app. Chat is a fixed-height app screen with
an independent conversation scroller, pinned auto-growing composer, remembered
per-thread reading position and Jump to latest. Incoming replies do not force a
reader away from older messages. VisualViewport/resize/focus events adapt available
height for the soft keyboard; bottom tabs hide while keyboard editing, then return.
Safe areas, touch manipulation, reduced-motion-aware drawer/sheet transitions and
native date/search/select/details controls remain part of the interface.

Navigation remembers per-screen scroll, Dashboard/Account subviews during the
session, owner-scoped Trade search filters and chart logical zoom by contract/day/
timeframe. Mobile browser Back dismisses navigation/Discover/order overlays first.
Native install prompt or browser-specific help and optional StorageManager.persist
request are in Account > More settings > On this device, alongside storage/privacy
copy. No installation/storage permission is requested automatically.

Storage choices: a host-only swan_appearance cookie stores only system/light/dark,
SameSite=Lax, Secure on HTTPS, 1-year expiry. Root layout reads it before rendering
(Next root now renders dynamically); localStorage provides fallback. Existing
owner-scoped conversations/drafts stay localStorage, with debounced writes/pagehide
flush; temporary positions/filters use sessionStorage. Firebase sign-in is unchanged.
Sign-out clears owner UI caches without clearing existing command/recovery state.
Service worker v2 caches exactly offline.html, 192/512 icons and Inter font. Account
HTML/API responses/writes stay network-only; there is no offline command queue.
Cold offline launches show the public offline screen, not an authenticated workspace.

Offline/reconnect notices distinguish connectivity from account freshness; offline
requests are blocked before authentication/fetch, order preview controls disabled,
chat draft preserved and reconnect triggers account refresh. Last received portfolio
snapshot remains separately labeled historical; current valuation freshness rules,
permission gates and request deduplication stay intact. Initial portfolio reads say
Loading rather than pretending missing data is zero. Manifest adds Chat/Dashboard/
Trade shortcuts; browser status theme follows app theme where supported.

Verification: production build/typecheck and 15 chart-data tests pass. Extended
isolated browser harness passes scroll/filter return, stored chart viewport, cookies
including SSR first render, install help, simulated keyboard geometry, incoming reply
scroll preservation, offline blocking/reconnect, Back/Escape/Tab drawer/order behavior,
mobile widths and sign-out recovery-cache preservation. Separate real service-worker
browser check verifies only four public cached assets and offline navigation fallback.
Inspected desktop and mobile screenshots. Private evidence harnesses:
.local/design/check-live-workspace.mjs, native-extras.mjs, check-native-offline.mjs.
These use fixtures/block external services, not actual-market acceptance. No backend,
broker/model calls, permission changes or deployments performed. Physical Android/
iOS installed-PWA tests remain D28; latency D29 and cross-device sessions D30 remain.


## Outline/filled navigation states: 24 November 2026

Removed the selected full-tab/primary-sidebar background. Inactive destinations
use Lucide outlines; active destinations use matching custom solid SVG variants,
with the existing adaptive purple/blue/teal/amber colors and slightly stronger text.
Trade fills candle bodies while preserving wick detail. Conversation-history rows
retain their separate faint selection tint. Browser/typecheck checks pass, including
one active filled tab and transparent selected-tab background. Mobile screenshot
inspected. Physical installed-PWA acceptance remains D28; backend unchanged.

## Colored icons and four-tab PWA bar: 24 November 2026

Primary icons now use purple Chat, royal-blue Dashboard, teal Trade and amber
Account with lighter dark-theme variants. Mobile bottom bar is an equal-width grid
of exactly Chat, Dashboard, Trade and Account, each with a Lucide icon and stable
label; Account uses UserRound and opens Account & workspace. Account selection is
shown for settings views. Existing fixed placement and safe-area bottom padding
remain. Isolated browser checks assert four labels/icons and responsive behavior;
typecheck passed and mobile screenshot inspected. Real installed-PWA acceptance
remains D28; backend untouched.

## Navigation icons and responsive labels: 24 November 2026

Added lucide-react for the primary navigation: MessageSquare (Chat), LayoutDashboard
(Dashboard), ChartCandlestick (Trade), and Plus (New conversation), with matching
21px/1.65 stroke styling. Other existing inline SVGs remain unchanged. Sidebar rows
share fixed-icon/flexible-label grid sizing and single-line, ellipsis-safe labels;
New conversation no longer wraps in the narrow desktop sidebar. Touch targets and
flat styling retained. Typecheck, production build and isolated responsive/browser
checks pass, including single-line label assertions at tested desktop/mobile widths.
Inspected mobile drawer screenshot. Installed-PWA device acceptance stays in D28.

## Quiet sidebar rows and static brand: 24 November 2026

Chat/Dashboard/Trade navigation, New conversation and the account footer now share
flat edge-to-edge square rows, regular-weight text, faint selected/hover tints and
no borders, shadows or press translation. Mobile bottom destinations use the same
quiet selection treatment. Logo is a noninteractive div, not a button: no navigation,
hover background or keyboard stop. Desktop/mobile isolated regression and typecheck
passed; real-phone/installed-PWA acceptance stays under D28. No backend changes.

## Mobile-first navigation drawer: 24 November 2026

Conversation rows now span sidebar edge-to-edge with square corners, no external
row padding/gaps and a subtle 5% foreground tint for selection. Added a light close
cross above the logo at sidebar top-right, revealed by hover or keyboard focus on
pointer desktops. Touch devices retain a visible 44px target. Desktop sidebar can
collapse and reopen from the screen top-left. Mobile now uses the full navigation
and conversation list in a fixed drawer, replacing the compact session picker.
Drawer has a dim backdrop, close/Escape, focus containment/return, inert background,
body-scroll lock, safe-area padding and closes after choosing a destination/chat.
Existing bottom navigation remains for primary mobile destinations.

Build/typecheck and isolated browser checks pass, including desktop collapse/reopen,
mobile conversation selection, Escape/backdrop dismissal, focus return and responsive
widths. Inspected mobile drawer and desktop session screenshots. Installed-PWA/real
phone keyboard and safe-area acceptance remain in D28; no broker/live checks run.


## Multiple local conversation sessions: 24 November 2026

Replaced the single clearing thread with an owner-scoped session index and sidebar
chat list. First message supplies a bounded title; New conversation preserves prior
threads. Separate per-session drafts/history survive navigation and reload. Existing
owner-scoped single-thread storage migrates into the first session. Thread components
remain mounted while switching so an in-flight response completes in its original
thread. Mobile offers a conversation picker and new-chat control. Unique textarea
IDs preserve accessible labels with multiple mounted threads. Sign-out clears the
owner's session index/history/drafts, preserving prior device-privacy behavior.

Typecheck/build and isolated browser checks passed: three sessions, failed question
and draft retention, switching while a response is in flight, reload restoration,
mobile switching, navigation and sign-out cleanup. No model/broker calls were made
by these fixture checks. Backend still accepts history through its stateless chat
endpoint: durable cross-device sessions are D30, not claimed complete. User's real
slow/failed greeting is recorded under D29 backend fixes, with timeout mismatch and
routing/provider/resource investigation targets; root cause not yet established.


## Local frontend connected to Oracle: 24 November 2026

Configured the real apps/web/.env.local API base to the hosted HTTPS origin,
preserving Firebase settings. Hosted SWAN_WEB_ORIGINS now includes exact local
localhost/127.0.0.1 origins on ports 3000 and 3100, plus the existing Vercel origin.
Backed up remote runtime.env privately and recreated only the API container.
Health returned 200/database connected; CORS preflights passed local and Vercel
origins, rejected an unrelated origin, and unauthenticated workspace requests still
returned 401 with correct local CORS headers.

Refreshed the actual signed-in VS Code integrated browser at localhost:3100.
Dashboard loaded hosted records: paper equity 99,766.55 INR, zero open positions,
and two closed-trade records. This is observed authenticated UI integration, not
a fixture run. Session P&L remains unavailable per its response. Existing Trade
components already reuse candles, indicators, watchlist/search and order preview.
No broker login, provider probes, live-market acceptance or trades performed;
worker observation-only settings and permission gates unchanged. Vercel frontend
was not redeployed. Remaining hosted journeys stay under D28.


## Chat chrome simplification: 24 November 2026

Removed conversation/session labels from the top area: only the Discover toggle
remains within the screen. Workspace fetch errors are a slim top strip with a blue
Retry text control and a close icon. The strip now floats at the top of the app
frame above screen chrome, without shifting the conversation or sitting below the
Discover toggle. Isolated browser checks confirm top positioning and dismissal. Dismissal persists through the same outage and
resets after a successful workspace fetch. Removed the chat footnote, conversation
controls/session-stop shortcut and global explanatory footer; existing dashboard
and permission controls remain. Mobile account access is in bottom navigation.
Production build and isolated browser checks pass, including retry/dismiss and
absence of old header/footer elements. No live acceptance or deployment performed.

## Account and Discover refinement: 24 November 2026

Removed the Paper workspace / Virtual funds labels. The bottom-left entry shows
only the authenticated user's name (email fallback), without an avatar/account icon
or generic workspace subtitle. It opens Account & workspace, including General,
risk limits and existing trading controls. More settings contains System/Light/Dark
buttons; appearance remains device-local and independent of account data loading.
The right Discover panel is reserved for news, account insights and learning links.
News currently has an explicit unavailable state; no headline feed is claimed.
Desktop content reserves space for the open panel. Settings padding, responsive
navigation, identity truncation and panel spacing refined. Typecheck, build and
isolated browser checks passed; no hosted deployment or market checks performed.

## Real frontend workspace migration: 24 November 2026

User approved the larger-text white/royal-blue playground and requested carrying
it into the real app. Local Next.js frontend now has Chat as default, three primary
destinations, shared sidebar/mobile navigation, neutral light/dark themes, original
logo, Discover panel and self-hosted Inter variable font with OFL license.

Chat reuses the authenticated endpoint, truthful request/response loading, preserved
failed questions, owner-scoped bounded local history/drafts, and the existing audited
session-stop control. It stays mounted across navigation and usable during workspace
fetch failure. Sign-out clears owner-scoped local data. Legacy unscoped history is
not imported into another identity. No streaming/background-task service is invented.

Dashboard uses the reconciled portfolio API for equity, session P&L and exposure;
missing baselines stay unavailable. Trade reuses watchlist/search, Lightweight Charts,
indicators and existing paper preview/placement, with selected-contract chat context,
desktop panes and a mobile order sheet. Server permission gates/execution unchanged.
No prototype fixtures enter production application source.

Typecheck, production build and all 15 existing chart-data tests passed. Local Chrome
authenticated checks used isolated Firebase/API fixtures and blocked external traffic;
covered API answers, failure recovery, account-load independence, navigation/drafts,
context, themes, mobile sheet/Escape, sign-out cleanup and responsive overflow.
Inspected desktop Chat/Dashboard/Trade, dark Chat and mobile Chat/order screenshots.
Private harness: `.local/design/check-live-workspace.mjs`; fixtures are not actual
market acceptance. Playground regression checks also pass with the shared font.

Not pushed or deployed. Hosted backend/worker untouched; no broker/model/live-data
checks or trades made. Owner review, full accessibility and hosted integration remain
under D28; market-acceptance holds and trading gates persist.

## Calendar-aware isolated login: 24 November 2026

Daily-login job now checks the verified local NFO/BFO calendar before reading
credentials or constructing a broker client. Any verified session remaining today
allows pre-open login; both known closed/finished sessions skip. Missing/invalid or
unknown coverage skips explicitly instead of guessing weekdays. Boot/catch-up runs
use this same gate. Timer changed to every day at 08:55 IST so verified special
weekend sessions are possible; ordinary weekends skip via calendar. Current calendar
coverage ends 30 November; extending verified coverage remains necessary.

Job container capped at 0.1 CPU, CPU shares 128, 192 MiB RAM / 256 MiB including
swap, 64 PIDs; API/worker have no startup dependency on the job. No in-process
authentication loop or app restart was added. Broker-dependent features still
require authentication; unrelated app work does not wait on this scheduled job.
13 focused tests passed, including no credential read/client creation on skip;
Ruff/mypy and Compose configuration checks pass. Hosted image caf368fc7263 built;
the real systemd job completed SKIPPED_MARKET_CLOSED on today's holiday at
08:46:33 UTC and exited successfully. API /health remained database connected;
existing API/worker were not restarted. Timer verified active with daily schedule.

## First hosted automatic login verified: 24 November 2026

User entered credentials privately and ran the scheduled-login service manually.
Service completed NEW_SESSION_VERIFIED at 08:39:33 UTC (14:09:33 IST), confirming
fresh login/profile match. Timer next run remains 25 November 08:55 IST. Remote
worker check: OBSERVATION_ONLY/OBSERVATION, heartbeat age 0 seconds, no problem,
no open positions. Quote projection still contains prior-session data (latest
23 November 10:16:42 UTC); no fresh market stream acceptance claimed. Today is
the configured and officially documented Guru Nanak holiday:
https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf.
Subsequent scheduled renewal and next-open-session data remain unverified.

## Scheduled broker authentication: 24 November 2026

Implemented services.market.autologin and isolated Compose broker-login job.
It accepts PIN/TOTP seed privately through getpass; writes mode-0600 JSON into a
separate mode-0700 UID-10001 .private-broker directory, mounted only by this job.
API/worker only share resulting session tokens. Uses PyOTP 2.9.0 (broker legacy
seed compatibility), current-day profile-verified reuse, fresh login/profile match,
exclusive Linux file lock, max three transient attempts 35 seconds apart, no retry
on invalid credentials. Safe outcome/status file and exit code; no trading gate
changes. Six focused tests, Ruff, targeted mypy, merged Compose validation passed.

Installed/enabled swan-broker-login.timer/service on Oracle: weekdays 08:55 IST
plus boot, persistent catch-up, 600-second job timeout, no automatic restart loop.
Server reports NTPSynchronized=yes. Missing secret file correctly skips the job.
User must configure credentials privately then start the service for first real
authentication. Real PIN/seed login, subsequent daily renewal and live stream
acceptance are still unverified. See hosting/oracle/README.md for wiring commands.
Hosted image f4adb0b7cc92 built successfully; the isolated Compose login job's
--help command executed successfully without any broker requests. Existing
API/worker containers remained running throughout the image build.

## Public HTTPS backend: 24 November 2026

User supplied the deployed frontend https://swan-one.vercel.app and opened OCI
ingress TCP 80/443. Opened the same ports in the VM INPUT firewall and saved with
netfilter-persistent. Configured Caddy and obtained a Let's Encrypt certificate for
https://swan-api.137-23-62-124.sslip.io. External Python requests with normal TLS
verification returned /health 200 and database connected; CORS preflight allowed
exactly https://swan-one.vercel.app and rejected an unrelated origin (400, no allow
origin). No credentials were exposed. API startup after recreation took roughly
two minutes under CPU contention; added 180-second healthcheck start_period in
the Micro overlay for future recreation (uploaded, existing container unchanged).

Next frontend step: set Vercel Production NEXT_PUBLIC_API_BASE_URL to
https://swan-api.137-23-62-124.sslip.io and redeploy. No Vercel CLI/session was
available locally to perform this setting change. Frontend integration, hosted
broker login/data, authenticated chat, backups/restart and paper acceptance remain
open under D26. Worker remains observation-only and account entries disabled.

## Oracle Micro experiment resumed: 24 November 2026

Connected over SSH to the user's Ubuntu 24.04 x86_64 Micro VM. Observed 952 MiB
RAM, 706 MiB initially available, 45 GB root disk with 42 GB free, and no swap.
Restricted the local SSH private-key ACL; keys remain excluded from Git. Installed
Ubuntu's Docker/Compose packages and enabled Docker at boot. Added a 2 GiB swapfile
with persistent fstab entry. Uploaded the allowlisted source bundle and private
runtime configuration with bootstrap disabled and explicit existing owner binding.
No public API hostname or Vercel deployment exists yet; allowed web origins are
empty until the frontend URL is known. Caddy is not started.

Added optional hosting/oracle/compose.micro.yaml PostgreSQL tuning (64 MB buffers,
2 MB work memory, 40 connections, no parallel query workers/JIT). The local managed
API, web and worker were stopped before exporting the flat/inactive ledger to
`.local/release/swan-database-20261124T065942Z.dump`. It was transferred privately
and restored into the new hosted database without pg_restore errors.

Initial database-only sample: approximately 57 MiB container memory, 584 MiB host
available, 108 MiB swap occupied. Busy setup samples showed 90–91% CPU steal time;
do not interpret Docker's transient CPU percentage as sustainable allocated CPU.
Docker image build and Alembic migration completed successfully. API, observation
worker and PostgreSQL are running; hosted /health returns database connected.
After startup, three health samples took 3/7/2 ms. Container working-set samples:
API 92 MiB, worker 77 MiB, database 57 MiB. Host available memory was about 451 MiB;
later vmstat samples showed 97–98% idle CPU, zero steal and no active swap I/O.
The initial 2.7-second successful health request was during startup. The worker
record shows OBSERVATION_ONLY/OBSERVATION, heartbeat age 1 second, no problem;
account enabled=false, no open positions, all three containers zero restarts and
OOM=false. These short idle observations support continuing on one VM, not live
market performance acceptance. Broker login/data, HTTPS, Vercel, restart recovery
and sustained resource acceptance remain pending. No broker orders were placed.
Do not restart local and hosted account workers concurrently. D26 remains open.

## Hosting decision: 24 November 2026, after VM creation

The user reports that the 1 GB Oracle VM has been created after A1 Flex requests
failed with out-of-capacity errors in Mumbai. The account has no trial credits.
The user requested publishing the current project to GitHub and explicitly deferred
the 1 GB hosting experiment until later. No SSH connection or cloud deployment has
been performed. Resource sizing remains unverified; next session should obtain the
public IP, SSH username and local private-key path, then measure API/worker/database
memory before deciding whether to split PostgreSQL. D26 remains open.

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


## Agent, chat and watcher checkpoint: 23 November 2026, afternoon

### Verification for this checkpoint

427 backend tests passed (one existing Starlette/httpx deprecation warning),
15 frontend tests passed, Ruff passed across services/tests, targeted mypy passed
on 12 changed source modules, frontend typecheck/production build passed, and
`git diff --check` passed. API/web listeners and managed observation worker are
running. These checks do not close actual-market autonomous paper acceptance.

This checkpoint supersedes earlier statements that index acquisition is API-only,
chat is limited to canned actions, or ORB qualification accepts generic records only.

- A deterministic worker job checks NIFTY index evidence once per minute at second 5 IST during
  the verified ORB window. The API refresh cooldown is 55 seconds. Shared history acquisition, completed-bar assessment,
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


## Current audit checkpoint: 23 November 2026

Read [the execution and agent audit](./EXECUTION-AND-AGENT-AUDIT-2026-11-23.md)
and the latest entries in DEFERRED-WORK.md before continuing. They supersede
older descriptions of the 10% participation policy and forced valuation exits.

- Audited paper config `paper-displayed-depth-20261123-v2` now permits up to 100%
  of observed depth. Freshness, risk, slippage, durable consumption and permission
  gates remain. This models displayed capacity, not queue competition or guaranteed fills.
- Fixed the manual protection bug that confused an entry-only pause with session
  termination. Unavailable valuation and chat's stop-new-entries command preserve
  existing protection. Explicit validation stop and expiry still drain positions.
- Added execution-policy context, separate market/news citation lists, and clear
  planning versus execution freshness semantics to the generic agent pipeline.
  Citation validation was not weakened.
- A real-provider read-only rerun passed analysis and proposal checks and returned
  WAIT because snapshots lacked supported directional strategy evidence. Review
  was not invoked after WAIT. Order count remained nine. Owner account had zero
  durable ORB assignments and zero candidates. Both earlier round trips were manual.
- Confirmed integration gaps: ORB index-history acquisition is explicit API work,
  not scheduled worker production; generic proposals and ORB assessments need
  explicit priority and execution ownership. The generic path lacks recent index
  bars and deterministic strategy/tool results. D19/D25 retain these closure requirements.
- Final verification: 406 backend tests passed, plus focused Ruff and targeted mypy.
  Regression cases failed before the entry-pause fix and passed afterward. Actual
  holding acceptance after this fix is still open; no new trade was submitted.
- API and worker reloaded. Worker OBSERVATION, entries paused, account flat and
  reconciled, cash INR 99,766.55. No active order, qualification or arm was created.

Updated 23 November 2026 after actual-market manual paper tests.

Read [the latest acceptance checkpoint](./MARKET-ACCEPTANCE-2026-11-23.md),
[the delivery plan](./SWAN-DELIVERY-PLAN.md), and
[the deferred-work ledger](./DEFERRED-WORK.md).

Two NFO manual paper positions of 65 units each completed buy/sell round trips
against real provider depth. Both closed through protection after insufficient
liquidation-valuation depth paused entries. Account flat and reconciled. Cash and
equity INR 99,766.55, net P&L INR -233.45, estimated fees INR 168.45. All validations
stopped and orders terminal. Evidence is retained privately in
`.local/run/paper-round-trip-final-2026-11-23.json`.

The worker is back in OBSERVATION and entries are paused. API and web run locally. On 23 November at 18:52 IST the API, web and observation
worker were restarted; API health confirmed PostgreSQL connectivity. No production
host is configured. SmartAPI login sessions expire at midnight, so broker access
requires a fresh login on each trading day. No real-money broker order, autonomous qualification or arm was issued.
404 backend tests, focused Ruff and targeted mypy passed after runtime deadlock
and clock fixes. The existing frontend verification passed in the preceding slice.

Next acceptance work is the remaining qualification matrix and eligible
strategy-to-agent-to-paper execution, plus actual target/stop/max-hold behavior,
reconnect handling and authenticated dashboard/chat review. The captured ORB
assessment expired and must not be executed. Provider checks and broker login are
day-scoped or short-lived. Refresh them through existing controls as needed.
The user resumed provider and actual-market paper checks. Do not relax permission,
freshness, depth or risk gates. Exact broker fee parity remains unverified.

Trade chart presentation follow-up, 25 November 2026: removed the chart-level
“Ask SWAN about this” prompt and decluttered the chart to candles, timeframe, date
and the explicit history update action. Removed optional indicators, RSI, zoom
buttons, raw candle tables, chart trade overlays and their five-second polling
request. These presentation-only changes do not change order safeguards or the
separate Dashboard trade history. Frontend typecheck, chart-data tests, and the
isolated responsive workspace/browser suite pass. No broker login, live-market
refresh or order action was performed.
