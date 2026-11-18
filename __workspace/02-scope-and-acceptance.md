# Scope and acceptance

## product outcome

A single allowlisted user can configure a paper account, enable autonomous trading, inspect timestamped market data and decisions, pause entries, and reconcile trades and daily reports with the ledger. The system remains safe when data, credentials, network, or AI services fail.

## Included

- Authenticated, installable Android PWA with dashboard, activity feed, positions, journal, risk settings, and daily reports.
- Angel One market-data adapter for NIFTY/SENSEX options, subject to capability verification.
- Option-chain metrics with provenance, timestamps, availability flags, and documented derivation.
- Structured AI analysis and BUY_CALL / BUY_PUT / WAIT proposals; post-session review.
- Deterministic risk engine, virtual order lifecycle, cash/position ledger, transaction costs, exits, and reconciliation.
- Durable scheduling, operational health, audit events, restart recovery, fixture-based integration tests.

## Excluded

Real-money orders, brokerage order permissions, custom model training, multiuser product features, billing, social tools, custom chart engines, and AI modification of account settings or risk limits.

## Proposed screens

| Screen | Required behavior |
| --- | --- |
| Sign-in | OIDC login, allowlist rejection, expired-session handling |
| Dashboard | Trading state, freshness, capital, realized/unrealized P&L, positions, pause control |
| Market | Index/expiry selection, chain metrics, missing-data labels, timestamps |
| Activity | Decision evidence, WAIT/rejection reasons, order and system events |
| Journal | Orders, fills, exits, fees, realized results, linked decision |
| Settings | Validated paper capital/risk settings; credentials represented by status only |
| Reports | Daily totals, reconciliation status, AI narrative, data/error limitations |

## Acceptance matrix

| ID | Requirement | Evidence |
| --- | --- | --- |
| AC01 | Android PWA installs and opens; unauthorized access is denied | Device install check; API authentication/allowlist tests |
| AC02 | Timestamped NIFTY/SENSEX snapshots; no fabricated fields | Adapter fixtures, null/availability tests, UI inspection |
| AC03 | Decisions validate; invalid output becomes WAIT | Schema, timeout, contradictory-field tests |
| AC04 | Autonomous fixture session runs without intervention | End-to-end session including entry, monitoring, exit, report |
| AC05 | Every accepted order passes risk checks | Audit trace and risk bypass tests |
| AC06 | Fills use bid/ask, slippage, and configured costs | Deterministic ledger examples and arithmetic assertions |
| AC07 | Risk breaches block entries and create events | Risk-boundary and daily-loss tests |
| AC08 | Pause stops new entries by next evaluation cycle | Pause/commit race test; dashboard confirmation |
| AC09 | Duplicate decisions never duplicate orders | Concurrent retry/idempotency tests |
| AC10 | Dashboard and journal reconcile to ledger | Portfolio/report reconciliation tests |
| AC11 | No real-money endpoint invocation | Adapter interface review, mocked outbound request assertions, source review |
| AC12 | Integration tests need no live credentials | Clean fixture-only CI run |

Completion requires these checks, documented deployment/recovery steps, and resolved blocking dependencies. Live credentials are needed only for the separately gated market-data smoke test.
