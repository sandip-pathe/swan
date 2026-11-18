# Durable worker routing and independent protection

Updated: 17 November 2026, Asia/Kolkata.

This increment connects the existing agent-approved strategy trigger to durable paper admission, actual-observation matching, holdings and protective orders. It implements the routing/protection portion of step 3B. Trading remains disabled while execution configuration, connected dependencies and final QA are incomplete.

## Entry and portfolio path

`services/paper/coordinator.py::PaperCoordinator.admit` applies verified feed-unit metadata to the actual observation, locks the account, loads reconciled portfolio state, and calls the depth-aware whole-lot calculator. It persists genuine quote evidence, the strategy, the decision and its typed approval. Submission is a subsequent ledger transaction: the ledger checks the account revision and current strategy again. A competing pause, changed holdings or expired approval rejects admission. Rejected submission is recorded on the decision rather than presented as an accepted order.

Approvals now include net liquidation equity and a fixed entry limit. Entries must be LIMIT orders using that limit. Approval lifetime is also bounded by the freshness of observations used for entry and liquidation equity. The ledger checks daily headroom against approved net liquidation equity instead of the previous cash-only proxy. Runtime strategy validity is rechecked under a control-row lock before admission and before buying units.

`services/paper/portfolio.py` constructs the account snapshot from actual durable positions, frozen entry execution configuration, complete executable bid valuations, fees, remaining liquidity capacity, pending reservations and restricted sale proceeds. Cash available for another entry excludes reservations and funds holds; equity retains cash and includes only complete net liquidation estimates. Incomplete valuations block entry and pause an enabled account. The existing portfolio/monitor state now delegates to this valuation for durable holdings; historical-only holdings retain their earlier path.

## First partial fill and risk allocation

New orders record `risk_allocation: whole_order_until_flat` in their immutable request evidence. Before any fill the whole risk budget remains with the pending order. After the first held units, the whole budget remains assigned to the position until it is fully closed. Further partial exits do not reduce it. Reconciliation recognizes this policy; records without the marker retain their historical proportional allocation.

This deliberately conservative allocation prevents flat entry/exit fees from being understated by prorating a whole-order estimate across the first partial units. It does not cap actual loss through a market gap.

The matcher yields after the first successful entry-level fill. The coordinator requests and acknowledges cancellation of the unfilled entry remainder in separate ledger transactions, reloads actual held quantity and installs protection. This policy prefers protecting acquired units over walking additional entry depth. A cancel/fill race is serialized by account locking and the subsequent holdings read; terminal orders never reopen. An interruption between fill and protection leaves durable holdings for the next watchdog pass/recovery, not a claimed atomic exchange bracket.

## Independent watchdog and exits

`TradingRuntime.execution_watchdog` runs a single coalesced consumer independently of agent/news evaluation and entry admission. It processes the latest cached real observations, checks expiration and protection, then matches a bounded pass of at most 32 orders with exits first. It waits 250 ms between completed passes. Database work is sequential within that consumer; this is not a measured 250 ms execution-latency guarantee. Persistence cost and account-history reconciliation still require final performance QA.

Protection uses a frozen stop, target, maximum holding period and pre-close interval. Reason priority is daily loss, pre-close, stop loss, strategy invalidation, maximum holding time, then target. Pauses, recovery, changed strategy or unhealthy data prevent pending buys; disappearance/change of the active strategy requires a protective exit. Existing holdings continue to be monitored while new-entry readiness is false.

A held position without an urgent exit gets a durable STOP_MARKET order for its actual remaining units. An urgent reason cancels an existing protective stop and submits a market-style paper exit. A higher-priority reason can explicitly cancel/replace a lower-priority exit. Each new order observes configured latency and freezes its own price-protection anchor on eligible subsequent real data. An existing protected market order is not repeatedly re-anchored to chase price. If its bound or available depth prevents execution, the remainder stays pending and visible.

No verified exit session, missing/stale depth, rejected matching and unavailable execution inputs produce persistent unresolved-exposure events/status. Individual protection/matching validation failures do not prevent processing other positions/orders. Completed flattening records resolution and leaves entries paused. Orders expiring at close do not erase holdings or create a synthetic closing fill. Overnight residual exposure remains an incident; it is not a successful EOD close.

Startup uses durable reconciliation with entries paused. Pending orders and held positions are included in the pinned subscription universe. Existing legacy records remain supported by the historical monitor and cannot enter the new matcher.

## Configuration and remaining work

Readiness diagnostics now expose routing/protection code availability and `FINAL_CONNECTED_QA_PENDING`. `engine_ready` remains false. Enabling observation requires a later explicit implementation/verification of that final gate after approved configuration and QA; setting policy values alone cannot activate trading.

The local status check reports an expired saved broker session, zero configured calendar sessions, unreviewed execution assumptions, unverified feed quantity units and missing NFO/BFO fee schedules. No rates, calendar sessions or latency observations were invented. Funds holds retain the conservative existing release policy; evidence-backed release tooling is still pending. Other OpenAI/news/Firebase connected requirements must also be checked before running the complete product.

Next product increment: expose durable lifecycle, partial quantities, reservations, fee components, valuation uncertainty, protective orders and unresolved incidents clearly in the authenticated workspace. Then complete reviewed provider/configuration inputs and final numerical, race, restart, data-loss and connected checks before the actual-market observation period.

## Verification performed

- Ruff and Python type checking pass across the backend (45 source files).
- Exported 16 JSON schemas and TypeScript contracts; frontend TypeScript checking passes.
- Read-only local configuration diagnostics confirm the engine remains disabled.
- No ORM/schema migration is needed; database models are unchanged.

Per user instruction, no tests, synthetic inputs, replay, seeded trade or behavioral simulation were added/run. No provider request, worker activation, paper fill, real broker order or deployment was performed. Static checks establish integration/type consistency, not numerical or operational acceptance.
