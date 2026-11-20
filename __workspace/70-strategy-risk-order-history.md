# Strategy, risk and order history

Evaluation history now shows accepted strategy details and their linked risk
results, entry orders and actual filled units. The API follows the single owned
AGENT_EVALUATION envelope, validates StrategyEnvelope, selects owned DecisionRecord
payloads by exact strategy ID, validates TradeDecision identity and approved risk
contracts, then selects owned orders by decision ID. Actual fill quantities are
summed from PaperFill. Existing order timeline buttons expose fill/fee events and
related exits. No timestamp-proximity or coincident price joins are used.

The read-only repeatable-read projection keeps no accepted strategy, unavailable
acceptance, no risk decision, rejected risk, no order, open order and actual fills
distinct. Duplicate or malformed acceptance roots remain unavailable. Historical
validity is labelled historical and grants no present permission. Safe fixed risk
explanations are returned; raw configuration/output/provider identifiers are not.
Risk decisions are capped at 20 and orders at 100 with explicit truncation.

D16 remains open for richer age/depth/news/risk evidence, pagination/index/load
review and pre-admission denial events where no DecisionRecord was persisted.
Related exits are reached through existing order timelines, not auto-attributed
as model execution. Next slice: D17 per-run model/strategy version binding. M3/M7
acceptance remains incomplete; broker/login/live/manual checks remain skipped.

Verification: 312 backend tests, Ruff, mypy 87 modules, 13 frontend tests,
TypeScript and production build passed. New disposable-schema tests use actual
RuntimeStore acceptance, coordinator admission/rejection and depth fill cycles;
cover no decision, no fills then recorded fills, read-only revisions, ownership,
truncation, duplicate/invalid/missing acceptance. Six-size browser fixtures cover
strategy/risk/order links, partial fill display, order timeline and empty/unavailable
states, without overflow; reviewed the 390px screenshot. Activity regression and
local public PWA smoke pass. API restarted; actual account remains zero orders,
manual intents and enabled accounts, runtime OBSERVATION. Trading behavior and
permission gates are unchanged.
