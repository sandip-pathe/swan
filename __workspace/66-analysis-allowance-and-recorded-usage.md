# Analysis allowance and recorded usage

Account > Account activity now starts with Analysis allowance. A read-only owned
GET /api/paper/agent-usage exposes today's IST reservation count, conservative
reserved/remaining allowance, current configured model/budget, historical reservation
model names, uniquely linked recorded provider token totals and missing-usage coverage.
It returns no credentials, context, model output, response identifiers or monetary cost.

Reservations are deliberately not called measured usage or refunded after failure.
The existing budget guard is unchanged. A completed valid saved output is required
for recorded usage; duplicate/missing/invalid links remain unknown. Calls are grouped
by reservation date, matching the allowance guard, including before midnight when an
output completes later. Current settings may differ from a running worker. A model
name does not establish an immutable model or strategy version. Invalid reservation
amounts suppress reserved/remaining totals; invalid settings suppress policy/remaining.

D17 is partially delivered and remains open in DEFERRED-WORK.md for exact version
binding, failed/incomplete usage persistence, historical views and monetary billing.
Do not infer spend from reservations or call missing usage zero. Next appropriate
slice: D16 owner-scoped evidence/citation drill-down without invented correlation.
M3/M7 acceptance are not complete; broker login and market/manual checks stay skipped.

Verification: 286 backend tests, Ruff, mypy 83 modules, 13 frontend tests, TypeScript
and production build. Disposable-schema tests cover owner isolation, read-only state,
IST boundary, exhausted allowance, duplicate/missing/invalid usage and invalid policy.
Browser fixtures cover six sizes (360/390/430/768/1440/844), retry, empty, missing policy,
unknown usage, model names and overflow; reviewed the 390px screenshot. Full browser
regression and public local PWA smoke also pass. API restarted through local launcher;
real-account read succeeds with zero reservations today, zero orders/manual intents,
zero enabled accounts and OBSERVATION mode. No provider calls or orders were made.
