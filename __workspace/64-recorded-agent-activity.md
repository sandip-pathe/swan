# Recorded agent activity and risk explanations

Implemented 20 November 2026. Account > Account activity now has a user-facing
Agent activity view. This is the first M7 slice, not completion of daily reports
or evidence drill-down. Existing account/control history remains collapsed below.

## What users see

Cards separate market analysis, model proposal, independent review, evaluation
outcome and deterministic risk checks. Actual model WAIT, review rejection,
provider failure and risk rejection have distinct labels. A review supporting a
proposal is not labelled as an accepted order. Historical risk approval shows
its recorded quantity, cash/risk allowances and expiry only after validating the
approval schema. A linked owned order shows its actual current status and fill
progress, with the existing order timeline available in place.

Each card can disclose the recorded rationale, bounded concerns and cited market
observation count. Text is rendered as plain escaped content, never HTML. Model
outputs are explicitly separate from citation acceptance, current permission,
risk admission and execution. The API makes no inference about those later stages
from a model's text. Current observation mode explains that automatic analysis is
idle and displayed records are history.

Older AGENT_WAIT_OR_REJECT evaluation records are labelled as unspecified outcomes.
They cannot identify whether WAIT or review rejection occurred. Unknown statuses
are unavailable, not fabricated WAIT or failure. Provider errors are mapped to
controlled user-facing explanations; raw exception strings are not displayed.

## Data and isolation

GET /api/paper/agent-activity reads selected owned audit stages in a repeatable-read
snapshot. Category filters are all, agents or risk. Pages default to 20 and cap at
50; newest-first keyset cursors use timestamp/UUID and are owner/category-bound.
Risk decision references and linked orders are loaded through owned bulk queries.
Contract labels resolve through a bounded shared metadata query. Foreign decision
references cannot disclose another account's rationale or execution.

Output/decision/approval schemas are validated before projecting allowed fields.
AI_CONTEXT, raw prompts/context, provider response IDs, token accounting, private
configuration and arbitrary audit detail are excluded. Rationales cap at 2,000
characters and concerns at five 300-character items. No model call, provider read,
broker login, re-evaluation, session activation or order is triggered by viewing,
filtering, refreshing or pagination. No migration is required.

Older stages lack durable evaluation/output correlation. This view presents each
recorded stage separately and does not join them by approximate timestamps.
No new retrospective relationship or explanation is invented.

## Verification

281 backend tests pass, including five new integration cases for a real risk
approval/order link, read-only state, distinct WAIT/review/failure/unspecified
outcomes, controlled projection, keyset pagination with equal timestamps,
filters/input bounds, owner/cursor isolation, malformed output, foreign decision
references and a known risk rejection explanation. Ruff and mypy (81 modules),
thirteen frontend tests, type checking and production build pass.

Browser fixtures cover error/retry, expanding rationale, safely escaped model
markup, filtering, older activity, order timeline links and honest empty states
at 360, 390, 430, 768, 1440 and 844 landscape pixels without horizontal overflow.
Existing workspace flows pass. No actual agent call or trade is made by fixtures.
The managed API was restarted and the local mobile sign-in/PWA smoke check
passes with only the offline fallback cached. The actual account still has zero
orders/manual intents, no enabled entries and an OBSERVATION worker. Broker login
and live-market checks remain skipped at the user's request.

## Next slice

Continue M7 with a daily paper session report from recorded outcomes, fills and
fees. Evidence/citation drill-down and explicit future evaluation correlation
remain separate work. Preserve M3's deferred live acceptance and all execution
permission/qualification gates.
