# Complete paper-trading setup and readiness

Prepared: 18 November 2026, Asia/Kolkata.
Status: plan only. No application code, configuration, credentials, account state or services changed for this planning request. No provider calls or trades performed.

## Outcome

Finish the configuration, connection checks, missing wiring, status reporting and QA needed to begin an actual-market paper observation period. Complete everything that can be verified while exchanges are closed first. Leave only explicitly identified fresh-market checks for the next verified exchange session.

The warning “Paper execution setup is incomplete. Review the checklist to see what needs attention.” must disappear because its underlying requirements are satisfied. Merely hiding it, changing a readiness boolean to true, or treating old quotes as current is not completion.

Scope is the current single-owner local SWAN app, Angel One market data, OpenAI agents, licensed news and SWAN's durable virtual execution/ledger. Real broker order placement, external execution-provider migration and multi-user expansion remain separate work. Existing account history and ledger records must be preserved.

## Findings from the current source

| Finding | Evidence | Consequence |
| --- | --- | --- |
| Execution readiness is permanently false, including after valid configuration | `services/paper/settings.py` | There is no implemented path to clear the final activation blocker. It is checked by API resume, worker resume, runtime and coordinator admission. |
| Execution assumptions are unset; policy is unreviewed; quantity units are unknown; fee schedules are empty | `config/paper-execution.json`, `services/core/execution.py` | Configuration changes alone are insufficient, and real calibration/source evidence is still required. |
| Calendar and news source lists are empty | `config/exchange-calendar.json`, `config/news-sources.json` | Session eligibility and agent news context cannot operate as intended. |
| Account enrollment installs unreviewed spread/liquidity limits and a one-unit maximum fill quantity | `services/api/owner.py` | Successful login does not create a usable reviewed option-lot trading policy. |
| The settings API/UI changes only trade risk, daily loss and holding time | `services/api/app.py`, `apps/web/src/app/dashboard.tsx` | Other blocking risk/execution inputs have no complete user/operator configuration path. |
| Broker readiness checks saved expiry, not actual provider connectivity; AI and news are absent from the checklist | `services/market/readiness.py`, dashboard | A “passed” local check cannot establish a working end-to-end connection. |
| Required index reference tokens are not included in `MarketSettings.missing()` | `services/market/settings.py`, runtime universe refresh | Setup can appear complete while no fresh index reference/universe can be obtained. |
| Durable orders, fills, order events and funds holds are returned by the API but not rendered | workspace API and dashboard types/views | Partial execution, protection, reserved cash and unresolved exposure are insufficiently visible. |
| Position UI uses cumulative quantity and lacks partial-close fields; CSV lacks durable order/fill/fee detail | dashboard `Position`/`Positions`, journal exporter | The screen/report does not describe remaining exposure or explain durable accounting fully. |
| Risk-update rejection code differs between backend and frontend | API returns `PAUSE_AND_RESOLVE_ORDERS_POSITIONS_BEFORE_SETTINGS`; UI maps an older code | A useful orders/positions blocker becomes a generic error. |
| An option-chain fetch failure clears the whole workspace, and polling can clear action errors | dashboard load effect and shared error state | Independent endpoint failures hide account data and useful feedback. |
| `problem()` writes all business/configuration failures into the stream cache's health field | `services/worker/runtime.py`; stream clears that field on connect | Feed health and execution readiness are coupled. Recovery/protective-exit consequences need targeted reproduction. |
| Daily-loss rejection precedes the runtime session-start/reset path | runtime `cycle()`, API resume, `PaperEngine.start_session()` | Investigate whether a previous session's daily block can prevent starting the next legitimate session. |
| Several READMEs describe earlier incomplete implementations as current | paper/worker/agents/API READMEs versus later source and workspace notes | Existing implementation and genuinely missing work must be reconciled before building more code. |

The expired broker session was observed in the preceding investigation; recheck it at implementation time. Current AI credentials/model entitlement and all live connectivity remain unverified. Findings above are source observations, not claims that every suspected runtime defect has been reproduced.

## Readiness model to implement first

Replace the single readiness flag with separate capabilities and timestamped evidence:

1. **Application available:** Firebase identity, account ownership, API, database and schema work.
2. **Configuration complete:** reviewed account policy, execution assumptions, effective fees, calendar, dependency configuration and supported instruments are valid.
3. **Connections verified:** broker authentication, metadata, stream transport, AI and news have independently recorded results.
4. **Market closed / awaiting fresh data:** an expected operating state when the verified calendar says the exchange is closed; not an app failure.
5. **Ready for supervised paper validation:** offline/configuration/connection checks passed; a narrowly scoped paper-only validation session may exercise the remaining live-data checks.
6. **Ready for autonomous paper observation:** required current-session validation evidence passed and the account can be explicitly armed within its policy.

Keep worker process liveness, feed transport, quote freshness, session eligibility, strategy state, entry permission and exit-protection health separate. A worker heartbeat never proves a healthy feed. A current saved token never proves successful authentication. No active strategy outside trading hours is an expected waiting state.

Each check should expose: stable code, status (`passed`, `failed`, `not_checked`, `waiting_for_market`, `not_applicable`), explanation, last checked time, evidence/source, affected capability and next action. Aggregate capabilities server-side so UI, CLI, worker and admission use the same semantics.

Resolve the current circular gate: connected fill QA cannot require unrestricted autonomous readiness to run. Implement an explicit, bounded paper-validation lifecycle using the actual durable execution path, with no broker order routes and no generic bypass switch. It must enforce reviewed policy, real observations, verified sessions, account/venue/expiry/size limits, expiration, audit and independent exits. Validation success must not silently arm autonomy.

Persist qualification evidence bound to code/build, relevant configuration versions, account and validation scope. Material policy, fee, provider-contract or execution changes invalidate affected evidence. Dynamic checks such as authentication and quote freshness must expire independently; a manually editable `qa_complete=true` is insufficient.

## Phase 1 — Establish the complete baseline

- Inventory every configuration source and consumer: environment variable names, JSON policy files, account risk JSON, database runtime state, frontend settings and operator commands. Never include secret values in output.
- Compare latest source with the original requirements and steps 1–3B; classify each item as implemented/untested, partially wired, missing, expected closed-market behavior or obsolete documentation.
- Record database migration revision, account-policy review status, open/pending exposure, configuration versions and current service ownership.
- Consolidate the CLI/API readiness implementation; remove divergent presence-only interpretations and include both index reference tokens.
- Establish the paper-only provider route boundary and prove broker order endpoints are unreachable.

Acceptance: one traceable inventory lists every blocker, its consumer, remediation, evidence needed and whether it can be completed with the market closed. No missing value is replaced with a guessed default.

## Phase 2 — Remove hidden business defaults and complete configuration

### Account and risk

- Move paper capital, risk fractions, maximum positions, liquidity/spread limits, maximum quantity, holding time, quote freshness and session-relative cutoffs into a validated, versioned policy with explicit review state.
- Replace the bootstrap one-unit sentinel with an honest “risk policy requires review” blocker. Do not remove the cap without installing a reviewed whole-lot limit.
- Provide a complete configuration workflow for the current local operator, with an authenticated UI summary and clear edit actions. Use existing schema validation rather than a second independent policy definition.
- Keep risk/execution configuration changes blocked while active orders or exposure make them unsafe; show the actual pending orders/positions preventing edits.
- Preserve opening capital/history. If the user changes paper capital, use an explicit audited funding/reset workflow; never rewrite the existing CAPITAL ledger entry or erase trades.

### Execution model

- Resolve every required input: assumed latency, displayed-depth participation, extra adverse slippage, market protection, maximum quote age, entry lifetime, partial-fill granularity and quantity units.
- Record the distinction between measured provider properties and chosen conservative simulation assumptions. Parameter values require review and provenance; unmeasured latency must never be described as measured.
- Verify depth quantity units and lot/tick semantics against current official provider documentation and actual account observations. If closed-market observations cannot establish them, retain a named market-open verification item.
- Reconcile overlapping account/execution freshness and holding/cutoff policies; specify precedence and reject contradictory combinations.

### Fees, calendar and news

- Build effective-dated NFO/BFO fee schedules from current authoritative exchange/broker sources and the actual account's pricing. Include buy/sell applicability, caps, taxes, dependencies, rounding and any explicitly sourced zero components.
- Verify cumulative-order fee allocation, partial-fill fee behavior and the supported handling of session/contract-note rounding. Any unsupported declared scope is a blocker, not a silent approximation.
- Configure sourced NFO/BFO sessions with holidays, special sessions, cutoffs and next-session information. Distinguish a verified closed day from missing calendar coverage; no assumed weekday opening times.
- Configure permitted news sources with attribution, publication/retrieval time, entitlement/retention evidence and coverage/freshness policy. The current pipeline requires news; do not silently disable that requirement to obtain a green check.

Acceptance: schema-valid, reviewed and versioned inputs; explicit remaining calibration items; no placeholder rates, tokens, market prices, news or approval results. Fixed protocol identifiers, schema versions and legitimate test fixtures are not business data to delete.

## Phase 3 — Broker connections and closed-market diagnostics

- Guide the user through private broker login using the existing supported local flow. PIN/TOTP/session tokens stay outside chat, frontend logs and reports.
- Run the existing read-only profile verification and record only a safe status, account-match result and timestamp.
- Validate saved-session expiry, daily renewal, refresh behavior, wrong-account rejection, missing configuration, network timeout and bounded rate-limit/retry behavior.
- Check public instrument-master retrieval, schema, current metadata, NFO/BFO coverage, listed expiries, lot/tick sizes and configured index reference identifiers.
- Check WebSocket authentication and subscription/transport acknowledgments where available while closed. Record lack of ticks as `waiting_for_market`, not as proof of failure or fresh data.
- If REST observations are available after hours, verify parsing and timestamps but label them historical/stale. Never admit entries from them.
- Add deliberate “Test connection” diagnostics with timestamps/rate limits. Do not place external provider requests inside ordinary five-second dashboard polling.

Acceptance: authentication and transport results are independently visible and reproducible. No broker orders placed; no quote freshness claim without qualifying observations.

## Phase 4 — AI and news connections

- Safely check presence of credentials, selected model, project/model access, structured-output support, token budget, output limits and timeout settings. Follow the existing credential setup workflow before any API provisioning/use.
- During implementation, agree a bounded live connection test and spending limit before billable calls. A tiny schema-only test can establish API access without inventing a market recommendation or writing a strategy approval.
- Verify analysis → proposal → independent review → typed envelope → deterministic risk handoff, retaining genuine response IDs, usage, citations and versioning.
- Test refusals, malformed/incomplete structured output, unknown citations, unavailable news, stale evidence, exhausted budget, cancellation and provider errors. Dependency errors must not appear as AI WAIT decisions.
- Ensure stale/invalidated evidence cannot become an approved strategy after a slow model call or reconnect.
- Reconcile the promised daily-review/report capability with the current per-proposal reviewer. Implement the missing end-of-session review/report wiring if still required; a proposal reviewer is not a daily report.

Acceptance: dependency readiness is visible separately from strategy approval. No after-hours connection test creates a production trade signal. Strategy-quality/live-context acceptance remains a market-session check.

## Phase 5 — Worker startup, session transitions and recovery

- Complete managed worker start/status/stop/log handling for the current account, with an explicit observed/paused state and duplicate-worker prevention. Starting it outside hours must allow diagnostics without entering a repeated “broken” state.
- Keep the singleton account lock, reconciliation and paused restart behavior; supervise task failures and distinguish process death from session closure.
- Separate configuration/runtime blockers from stream health. Reproduce and fix stale business errors poisoning feed health or forcing incorrect protection behavior; recovery must clear only the conditions actually resolved.
- Make verified session rollover happen in the correct order. Reproduce prior-day daily-loss blocking; reset a daily baseline only for a legitimate new session after required reconciliation and unresolved-exposure checks.
- Validate NFO/BFO session handling individually, including differing close/special-session times, rather than inheriting whichever session was found first.
- Confirm quote publication, catalog refresh, evaluation scheduling, resume request, strategy approval, deterministic admission, watchdog, fills and journal form one connected path.
- Confirm scheduler/model/database work cannot starve heartbeat, protection or exits. Health and freshness thresholds should have named configuration and measured rationale where appropriate.

Acceptance: a managed worker can remain visibly healthy and paused after hours; stale data cannot enable entries; shutdown/restart/reconnect cannot duplicate workers or exposure; actual monitoring health is reported accurately.

## Phase 6 — Finish durable execution and accounting wiring

- Audit every active entry/exit path and preserve historical legacy records without routing new orders through the old immediate-fill engine.
- Verify the actual coordinator → sizing → risk approval → order ledger → matcher → fills/fees → cash/positions → protection/exit path, including remaining quantity and immutable frozen policy versions.
- Cover pending/accepted/partial/filled/cancelled/expired/rejected orders, cancellation/fill races, first-partial entry remainder cancellation and protection installation.
- Preserve reserved cash, risk allocation and restricted sale proceeds across restart and partial closes. Complete evidence-backed funds-hold release tooling; do not make proceeds spendable merely to remove a blocker.
- Verify stop/target/invalidation/max-hold/daily-loss/pre-close priority and independent exit handling during model failure, pause, data gaps and configuration changes.
- Represent missing depth, price-protection limits, session uncertainty and overnight residual exposure as explicit unresolved incidents. Never fabricate a close at the requested price.
- Reconcile positions, fills, fees, orders, reservations, funds holds and ledger totals after each relevant transition and recovery.

Acceptance: durable numerical/lifecycle/race/restart checks pass; no shortcut fill, duplicate liquidity use, double fee, double spending, lost holding or false successful flattening.

## Phase 7 — Make the UI and reports reflect actual state

- Replace the generic warning with the highest-priority actionable cause: e.g. “Broker login expired”, “Risk policy needs review”, “Fee schedule missing” or “Market closed — awaiting fresh quotes”. Show additional blockers without making normal waiting states look like failures.
- Clear resolved requirements from the same server-owned readiness model. A genuinely ready but closed market should show “Setup complete · Market closed”, not “Paper execution setup incomplete”.
- Add AI/news, actual broker verification, account-policy review, execution qualification, calendar, data freshness and protection checks. Distinguish “not checked” from “failed”; qualify saved-session checks correctly.
- Render pending orders, partial fills, remaining position quantities, protection status, entry/exit reasons, execution fees, reserved/restricted/available cash, liquidation-value uncertainty and unresolved incidents.
- Expand journal/export/reporting to reconcile durable fills and charges. Use instrument labels/metadata instead of opaque IDs where available; retain evidence access for diagnosis.
- Correct the risk-update error-code mismatch; display field-level validation, active-order restrictions and save/action results reliably.
- Separate account-load errors from chain errors and action errors. Retain last-known data with explicit stale state where appropriate; disable affected controls and prevent background polling from erasing important failures.
- Check all desktop/mobile tabs and non-empty states, keyboard/focus behavior, loading/empty/stale/error states, sign-in/out and expiry. Remove every production demo/placeholder value if discovered; unavailable information must remain unavailable.

Acceptance: the user can tell what works, what is blocked, whether the market is closed, what action resolves each issue and whether any position lacks working protection. No hardcoded healthy metrics or misleading readiness counts.

## Phase 8 — Complete pre-market QA and operational checks

Extend existing tests where they cover the boundary. The previous 51-test pass and fixture browser checks do not certify the newer durable execution path, real providers or actual owner-session behavior.

Required coverage:

- Authorization/ownership for every protected read, control, settings and export endpoint; expired/wrong-project/wrong-user tokens; local-owner enrollment and concurrent first access.
- Missing/invalid/expired policy, fee, metadata, calendar and dependency configuration; midnight IST and source/effective-date boundaries; malformed diagnostics cannot take down balances unnecessarily.
- Readiness transitions and qualification invalidation, including preventing the circular activation gate and all UI/CLI/worker/admission disagreement.
- Durable matcher, liquidity consumption, sizing, fees, partial fills/exits, funds restrictions, cancellation races, protective orders, reconciliation and recovery through the real internal boundaries.
- Pause/resume races, pending buys during pause, duplicate evaluations, stale in-flight strategy results, stream loss/reconnect, database interruption, task death and lost singleton lease.
- Daily baseline rollover, holidays/special sessions, separate venue sessions, entry cutoff, pre-close flattening and unresolved overnight exposure.
- Agent budget persistence, timeout/refusal/schema/citation failures and licensed news outage/freshness behavior.
- Signed-in browser flows using the real authorized local owner where needed; synthetic fixtures remain test-only and never populate production trading views or approvals.
- Dependency/security checks, reproducible frontend build and type checks, backend lint/types/tests, migrations and a private backup/restore rehearsal in an isolated database.
- Measure processing latency, watchdog lag, database reconciliation cost and subscription/cache behavior against configured freshness thresholds. Record results rather than asserting an unmeasured latency guarantee.

Use focused deterministic unit/integration fixtures and failure injection for software correctness. Respect the existing rejection of a product replay runner, seeded production trades and synthetic market/agent responses. No replay product is added under this plan.

Acceptance: all after-hours acceptance checks have passing evidence or an explicit justified blocker. Record fresh evidence and limitations; update contradictory READMEs, operator commands and troubleshooting instructions. Do not label not-run checks as passing.

## Phase 9 — Controlled fresh-market paper validation

This is the first phase that requires a verified open session and qualifying fresh observations. Schedule it by the sourced exchange calendar, not an assumed “tomorrow at 09:15”.

1. Renew/verify broker authentication as required and confirm actual NIFTY/SENSEX instrument metadata, timestamps, depth and quantity semantics for both venues.
2. Observe real quote transport and persistence without enabling entries; measure gaps, duplicates, ordering, REST/stream differences and processing lag.
3. Exercise the bounded supervised paper-validation lifecycle through the same durable coordinator. Use only actual observations and valid strategy/risk evidence; no forced market entry simply to make a test pass.
4. Verify order acceptance, applicable partial fills/rejections, fees, cash reservations, protection, permitted exits and reconciliation. If required scenarios do not occur, record them as unobserved instead of manufacturing market evidence.
5. Demonstrate reconnect/restart/pause and end-of-session handling without real-money execution. Validate incident visibility and operator recovery.
6. Promote qualifying evidence only after required checks pass. If qualification remains incomplete, keep autonomous entry blocked with the specific reason.

Acceptance: actual-market paper evidence establishes both supported venues and the required execution/protection behaviors. Unit tests or a successful broker profile request cannot substitute for this phase.

## Phase 10 — Arm paper observation and hand over

- Produce a concise readiness report with exact code/configuration/strategy/model versions, dependency results, qualifying evidence and residual limitations.
- Let the user explicitly arm autonomous **paper** observation after readiness passes. Restart, session expiry and material changes continue to enforce defined preflight behavior.
- Begin the agreed one-to-two-week observation period with daily reconciliation/reporting, dependency/budget monitoring and visible pause/incident controls.
- Keep performance/profitability assessment separate from software readiness. Real broker trading remains a separately authorized project.

## Completion gates and order

| Gate | Required outcome | When |
| --- | --- | --- |
| A — Configuration | Reviewed policy, effective fees, sourced calendar, metadata inputs, AI/news settings and complete blocker inventory | Market closed is sufficient for most work; some calibration may need Gate C |
| B — Setup and connection validation | Real auth/API access where available, managed worker lifecycle, offline correctness/recovery checks, accurate UI | Market closed; no fresh-tick claim |
| C — Supervised paper validation | Fresh market data, actual coordinator/matcher/protection/ledger checks and recorded qualification evidence | Verified open market |
| D — Autonomous paper ready | Gates A–C passed, no unresolved blocking exposure/configuration issues, explicit paper arming | After validation |

Execution order: baseline/readiness design → complete configuration → broker/AI/news connection checks → worker/durable wiring fixes → UI/report completion → pre-market QA → controlled market validation → autonomous paper observation. Test plans are designed alongside each change, not postponed until the end.

User inputs required during implementation are limited to private broker login, review of trading/simulation policies, any unavailable account-specific fee/permission evidence, permitted news source selection and bounded billable AI connection-test approval. None is required to finish this plan. Do not request passwords or secret values in chat.

Definition of done: no unresolved setup/wiring defect is hidden by a generic warning or hardcoded success state; everything testable after hours is verified; market-dependent checks are explicitly completed before autonomous paper arming; no real broker order has been placed.
