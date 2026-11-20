# Manual paper execution lifecycle

Implemented 20 November 2026. The internal manual admission service now connects
owned saved plans to the existing durable order ledger, depth matcher, positions
and protective exits. The mobile placement flow and authenticated submission
route remain the next slice. There is no Place order action yet. This is bounded
paper validation, not unrestricted manual trading or autonomous qualification.

## Human intent and deterministic admission

ManualEntryIntent records the plan, exact requested units, BUY limit, stop,
target, bounded holding duration and submission window. ManualIntentRecord stores
that immutable payload, the original command, instrument snapshot and server risk
result. It has no AI decision or strategy role. Client preview results never
become approvals.

ManualPaperService.submit locks the account, verifies plan ownership/archive state,
revision and current contract identity, and requires HUMAN permission. It maps a
real observation through the reviewed execution policy and reads a reconciled,
current portfolio and durable depth budgets. size_manual_entry checks the exact
quantity rather than silently resizing it. Freshness, session/cutoff, lot/tick,
expiry, position capacity, liquidity/spread, reviewed fees, available cash,
per-trade risk and remaining daily risk all remain gates. Usable depth is bounded
by the human limit and prices above the stop. Fees/slippage use the shared models.
Approval expiry includes the quote, portfolio evidence, pending-order lifetime and
permission window.

The separate ledger transaction repeats permission, revision, budgets, evidence,
configuration and scope checks before creating an order. A pause or competing
transaction between approval and admission wins. Request retries return the same
order after account revision changes or configuration becomes unavailable.
Conflicting reuse and cross-owner intent access fail. Accepted order identity is
unique per human intent, in addition to existing account/request uniqueness.
An approved risk result alone does not mean an order was accepted.

## Entry ownership and worker behavior

ValidationRequest adds entry_source with AI as the backward-compatible default.
HUMAN must be explicit; it retains the existing validation-start readiness,
verified connection/configuration, session, flat-account and one-lot/one-entry
limits. Existing source-less validation request retries still compare as AI.

Permission is checked at admission and every BUY fill. A HUMAN lease cannot
approve AI entries, an AI lease cannot approve human entries, and human entries
cannot use an autonomous arm. An active AI envelope blocks human permission.
The worker skips agent evaluation during HUMAN sessions and enables entries only
while that same explicit resume request, lease and feed generation remain valid.
Stopping, switching mode, changing inputs, stale heartbeats, expiry and restart
retain their fail-closed behavior. This slice does not relax shared readiness to
remove AI/news prerequisites for manual sessions.

Human sessions are explicitly excluded from the autonomous qualification matrix.
No AI DecisionRecord or StrategyRecord is fabricated by manual admission.

## Fills, protection and recovery

OrderRequest requires exactly one source for BUY and no entry source for SELL.
PaperOrder has a nullable manual_intent_id foreign key and unique constraint;
a database check forbids simultaneous human and AI sources. AI request payloads
omit the new null field so existing durable retry comparisons remain compatible.
The exported JSON/TypeScript schemas include the new intent and order reference.

Every manual BUY fill rechecks its source lease, identity, immutable contract,
intent expiry and human price bounds. Existing matching still enforces latency,
later observations, actual usable depth, frozen costs, fees, cash and reservations.
Positions copy human stop/target and the risk-policy holding limit. Protection
uses those fields without looking up an AI strategy. Stops, targets, daily loss,
pre-close, max hold, feed loss and stopped manual sessions feed the existing exit
machinery. Unresolved fills remain incidents rather than promised exits.
Partial entries cancel the remainder and protect only acquired units. Pauses and
restart recovery keep entries disabled while positions drain through protection.
Protection permission reads use account-first lock ordering.

## Verification and local state

All 236 backend tests pass, including 28 manual lifecycle cases. They cover
latency, fills and target/stop/feed-loss exits, partial fills, fees/reconciliation,
concurrent retries, ownership, conflicting identities, source exclusivity,
revision/cash/risk/depth/staleness rejections, fill-time permission changes,
stop-price boundaries, pause races, restart draining, worker activation without
agent evaluation and exclusion from AI qualification. Existing AI/qualification
lifecycle tests still pass. Ruff, mypy (73 modules), frontend type checking and
ten frontend tests pass. No UI was changed in this slice. Alembic reports no
metadata drift, and the restarted localhost mobile sign-in/PWA smoke passes.

Migration e6d0fab21811 adds the intent table and order reference. Downgrade refuses
to discard populated manual intent history. It is applied locally before the
managed application restarts. Fixture orders stay in disposable test schemas.
The actual account remains disabled, with zero orders; its worker is OBSERVATION.
No real broker or local paper order was submitted. M3 live/manual evidence stays
deferred at the user's request.

## Next slice

Add the authenticated owner-scoped submission route and mobile flow for an
explicit bounded human session, fresh preview, review and paper placement.
Show exact rejection reasons, source/session state and accepted-order identity.
Keep retry keys stable across uncertain network responses. Cover API ownership,
concurrent submission, stale preview/session changes and mobile success/error
flows before exposing placement. Broader manual permission outside bounded
validation requires its own evidence and permission scope.
