# Trading foundation

Step one implements internal Python modules. It does not expose an unauthenticated trading API, connect to a broker, fabricate market data, generate agent replies or seed the application with demonstration trades.

## Modules

- `core/contracts.py`: versioned instrument, quote, session, cost/risk, strategy-envelope and decision schemas. Prices and cash use Decimal; JSON contracts serialize decimals as strings. Timestamps require timezone offsets.
- `core/models.py`: PostgreSQL accounts, instruments, snapshots, envelopes, decisions, orders, fills, ledger, positions and audit events.
- `risk/engine.py`: pure risk checks and whole-lot sizing using executable bid/ask, adverse tick rounding, explicit costs, available capital, daily allowance and configured liquidity.
- `paper/engine.py`: account/session lifecycle, pause/resume, idempotent entry, deterministic exits, pending exits, cash/position reconciliation and paused restart recovery.
- `core/export_contracts.py`: JSON Schema and TypeScript export into `shared/schemas`.

## Prepare the database

From the activated root shell:

```powershell
python -m alembic upgrade head
```

Migrations create schema only: no accounts, quotes, decisions or orders are inserted. There is no replay runner or market-data fixture. Unit/integration tests use isolated test inputs and disposable PostgreSQL schemas; they do not populate the application schema.

The next integration layer supplies real normalized instruments/quotes, verified session calendars, configured costs/liquidity and valid strategy envelopes. Until then, the frontend remains a sign-in screen and cannot execute trades. Session setup is explicit; it never infers exchange holidays from weekdays.

## Execution semantics

Every mutation locks the account row, and every fill commits with its ledger movements, position projection and audit event in one transaction. Database keys protect decision-to-entry and exit idempotency. A repeated decision returns its original result; changing its payload while retaining the identifier is a conflict. Rejected decisions remain auditable and cannot be retried under the same identifier to become a different decision.

Capital is deposited once when an account is explicitly created. Session opening equity is persisted and never reset by same-session retries. Recovery reconciles the account and disables new entries. Pausing entries does not stop deterministic exits. Forced exits without fresh quotes or sufficient modeled depth remain pending; no fill is invented. Bid gaps may produce a larger realized loss than the planned stop risk.

Cost settings must be supplied explicitly and versioned. The current configurable fee function is a flat per-fill component plus proportional turnover cost; it is not a verified Indian transaction-charge schedule. The live integration must supply a verified cost policy before connected operation. Each position freezes its entry configuration for consistent exit costing.

## Verification status and delivery preference

Existing checks passed: 45 domain/PostgreSQL tests, Ruff and backend type checking. Tests include whole-lot sizing, daily risk, expiry boundaries, stale/missing data, duplicate/concurrent entries, rollback, pause, gap exits, pending exits and recovery. Additional test development, wider integration QA, CI and release validation are deferred to final QA at the user's request. Existing checks are retained; no claim of live provider readiness is made.

Maintenance commands:

```powershell
python -m services.core.export_contracts
python -m ruff check services tests migrations scripts/verify_environment.py
python -m mypy services
```
