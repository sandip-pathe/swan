# Data and API contracts

Use PostgreSQL migrations, UUID identifiers, UTC timestamps, fixed-precision numeric money/prices, explicit currencies, and integer quantities in instrument units. Never use binary floating point for ledger arithmetic. Backend schemas are authoritative; generate/check TypeScript contracts from versioned schema exports.

## Entities

| Entity | Important fields and constraints |
| --- | --- |
| Instrument | provider token, exchange, underlying, expiry, strike, option type, lot size, tick size, validity dates; verified provider identifiers |
| MarketSnapshot | PRD fields plus instrument ID, exchange/provider/received timestamps, source, availability and quality flags, schema version |
| ChainSnapshot | Underlying, expiry, constituents, coverage, computation window, PCR/aggregate metrics and derivation version |
| TradeDecision | Snapshot references, action, instrument, proposed entry/stop/target, rationale, evidence references, model/prompt version, status, expiration, session/slot key |
| RiskConfig | PRD fields plus version, effective timestamp, slippage/cost model references, cutoff and exit policy; validated user changes only |
| TradingState | Account ID, enabled/paused state, revision, session, blocked reasons, last reconciliation |
| RiskResult | Decision ID, config version, approved quantity, checks, reasons, quote references, evaluated timestamp |
| PaperOrder | Decision ID, instrument, BUY/SELL, quantity, status, rejection reason, idempotency key |
| PaperFill | Order ID, quote ID, quantity, fill price, slippage, itemized costs, fill time, model version |
| LedgerEntry | Fill/event reference, account, signed cash amount, category, timestamp; append-only corrections |
| PaperPosition | Instrument, open quantity, average cost, realized/unrealized P&L, marking timestamp; reconcilable projection |
| AuditEvent | Actor, event type, correlation ID, sanitized payload, timestamp |
| DailyReport | Session, deterministic totals, reconciliation status, narrative, model version, limitations |

For WAIT, execution fields must be absent. For BUY_CALL / BUY_PUT, instrument and prices are required, option type must match action, and for long options stop < entry < target. Quantity is calculated by the risk engine, not accepted from the model.

Preserve market-reported and locally derived metrics separately. Null means unavailable; a genuine zero remains zero. Record inputs and derivation for IV/Greeks/PCR. Reject dependent analysis when required inputs are absent.

## API plan

All routes below are authenticated except minimal health/readiness endpoints. Internal commands additionally require service-level authorization and are not exposed to the browser.

| Route | Audience | Contract |
| --- | --- | --- |
| GET /market/snapshot | User | Underlying/expiry filters; timestamps, quality and availability |
| POST /agents/evaluate | Internal worker | Session/slot key; typed decision, including WAIT reason |
| POST /paper/orders | Internal worker | Decision reference and idempotency key; server recalculates risk and size |
| GET /portfolio | User | Cash, equity, position marks, costs, risk utilization, reconciliation timestamp |
| POST /trading/pause | User | Atomically disable entries and increment state revision; monitoring continues |
| POST /trading/resume | User | Explicit enable after preflight; return blocking reasons when unsafe |
| GET /trading/status | User | State, health, block reasons, next scheduled evaluation |
| GET/PUT /risk/config | User | Versioned validated config; reject conflicting updates |
| GET /journal | User | Cursor pagination over orders/fills and linked decisions |
| GET /activity | User | Cursor pagination over sanitized audit events |
| GET /reports | User | Session report summaries and details |

Use a consistent error envelope: code, safe message, correlation ID, retryable flag. Distinguish invalid requests, unauthenticated, forbidden, conflicts, provider unavailability, and rate limits. Do not leak provider response bodies or secrets.

Database uniqueness must protect decision-to-entry-order mapping and idempotency keys. Exits use their own position/version-based idempotency keys. Each ledger mutation, fill, position projection and event commits atomically.
