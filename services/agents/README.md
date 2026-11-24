# Evidence-bound agents

23 November: free-text chat uses bounded allowlisted read-only tools. The worker
checks for a new completed ORB bar once each minute during its window; the durable consumer runs
analyst/reviewer work only for eligible changed setups. Indicator context includes
DEMA 9; index VWAP remains unavailable without traded volume. Daily allowance uses
reported usage from one valid receipt, otherwise its conservative reservation.
ORB qualification recognizes the original workflow proof; no gate is granted by
these modules. See ../../RESUME.md for connected acceptance and remaining gaps.

## Explicit strategy assessment workflow

`services.agents.assessment_workflow.AssessmentWorkflow` is the separate,
read-only spike path. Call `request` with a stable request key, an already stored
index snapshot ID, an aware as-of timestamp, and the verified session. It saves
an assignment before work, records typed snapshot/ORB tool results, and saves
analyst, reviewer, research, and outcome artifacts for `readback`. Requests
with the same account and key return the existing assignment. Interrupted or
expired work stays explicit; there are no billable automatic retries.

The first tool surface is deliberately small: read one stored, as-of-eligible
index snapshot and run the deterministic predefined strategy evaluator. Empty,
late, gapped, unsupported, and expired evidence terminates without an analyst
opinion. A research child assignment is created only when the analyst requests
it after a valid `NO_SETUP` assessment. Research hypotheses remain inactive.
The provider uses the existing key, budget reservation, timeout, structured
output and audit path. No provider access is enabled by this module.

The research run has a separate assignment linked to its parent, snapshot,
assessment and evidence. Parent `readback` includes the bounded child outcome
and artifacts so a consumer can retrieve the saved hypothesis and its sources.

The analyst can select only the exact deterministic strategy version attached
to the assessment, abstain, report insufficient data, or request research only
after a valid `NO_SETUP`. Selection and reviewer citations must belong to the
assessment's evidence set. The reviewer must cover every analyst citation.
Provider access, budget exhaustion, and transport failures end as unavailable;
invalid model output and failed contract checks remain failures. A reviewer
rejection and analyst abstention are saved as their own outcomes.

Saved drafts and hypotheses are not `StrategyEnvelope` values and are not
connected to risk admission, worker scheduling, or order creation. ORB watcher
transitions persist a bounded queued assignment. The application background
consumer claims queued work and invokes the existing assessment workflow; this
can make budgeted model calls when a qualifying watcher event is queued. The
authenticated `POST /api/strategies/watcher-assignments/{id}/run` endpoint is
also available for explicit recovery and atomically claims one queued item.
Queued work survives restart, and expired in-flight work is closed instead of
replayed. Chat UI, broker integration, and market acceptance are outside this
slice.

The worker invokes analysis, proposal and independent review through the OpenAI Responses API. A reviewed proposal becomes a short-lived strategy envelope. Models have no broker tools, settings controls or execution permission; deterministic live risk checks, sizing and the paper ledger remain responsible for execution.

User instruction defers all API credentials and tests. No requests are made until configured, and missing dependencies produce explicit statuses rather than synthetic market data or agent opinions.

## Deferred configuration

Server-only variables are listed in `.env.example`; real values belong in the ignored root `.env`. `OPENAI_MODEL` has no assumed default: select a project-accessible model supporting strict structured output. `SWAN_AI_DAILY_TOKEN_BUDGET=0` disables requests. No secrets belong in frontend variables.

`config/news-sources.json` selects `provider: "newsdata_free"`. The existing server-only `NEWS_API_KEY` authenticates to NewsData.io through the `X-ACCESS-KEY` header, never a URL or browser variable. One request uses the Market endpoint for Indian English finance/market headlines with no pagination or paid parameters. The reader reuses results for 15 minutes within its lifetime and checks publication freshness again on cache reads. Restarts and explicit diagnostics can make additional requests; this cache is not a durable quota counter.

The free plan delays articles by 12 hours. Each headline retains its original publication time and carries `provider_delay_seconds: 43200` into agent context. Readiness, connection diagnostics and cited-evidence cards disclose this delay; retrieval success does not establish live news coverage or justify a breaking-news strategy. Cited articles link to the publisher, and displayed NewsData results include provider attribution. RSS remains supported with `provider: "rss"`; each source requires `name`, an HTTPS RSS/Atom `url`, a `license_reference`, and `automation_and_storage_permitted: true`.

News collection fails closed when a configured source fails. It retains at most 30 timestamped headlines from the preceding 24 hours, with publisher links and receipt times; no article-body scraping. This window does not establish comprehensive or real-time coverage. The NewsData.io free plan is listed for testing and personal projects; its terms distinguish API metadata from publisher-owned content. Do not treat this local integration as clearance to redistribute content or launch a multi-user news service. Coverage acceptance and provider entitlements remain pending. Exchange filings require separately reviewed rights; do not scrape NSE or assume exchange announcements RSS can be republished.

## Runtime

- Unique durable evaluation slots prevent duplicate requests for one account/session slot. Interrupted slots are not automatically retried.
- The existing audit table stores actual context, outputs, response IDs, reported usage, reservations and final statuses. No migration is needed.
- Each request reserves conservative input bytes plus maximum output tokens and overhead under the account lock against its IST daily budget. Failed calls retain reservations. Restart does not reset the budget. This token allowance is not a currency spending cap; configure provider billing controls when connecting access.
- Requests have bounded timeouts/output tokens, a 100-second pipeline deadline and no automatic billable retries. Refusals, incomplete output, invalid schema and unknown citations block approval.
- Finite positive prices must satisfy stop/entry/target ordering; direction must match actual metadata. Review must cite the proposal evidence. Risk remains independently enforced at entry.
- Envelope expiry starts at evidence capture, never model completion. Stream changes invalidate in-flight results. Database operations run off the event loop so model work does not block the exit watchdog.
- Genuine model WAIT/rejection produces no envelope. Dependency failure is recorded as failure, never an agent opinion.

On 18 November 2026, the real news diagnostic retrieved 10 attributed headlines using the saved key. Provider contract tests, the full Python suite (74 tests), Ruff and type checks passed. Coverage suitability and model quality remain unverified.

Reference: [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create).

News references: [authentication](https://newsdata.io/documentation/api-authentication), [latest endpoint](https://newsdata.io/documentation/latest-news-api), [free-plan delay and quota](https://newsdata.io/documentation), [provider terms](https://newsdata.io/terms).
