# Realistic paper execution - step 1 implementation

Updated: 17 November 2026, Asia/Kolkata.

Scope delivered: quote evidence and configuration contracts. This is the first step of [the accepted plan](24-realistic-paper-execution-plan.md). Durable order states, partial fills, reservations, fee calculation and matching remain the next implementation steps; the existing immediate-fill engine has not been upgraded or activated by this change.

## Changes

- Added immutable depth-level contracts and retained up to five actual bid and ask levels, including displayed quantity and provider order count when available. Best prices/quantities must match sorted retained depth. Duplicate price levels or invalid structures cannot silently become valid depth. Empty depth remains unavailable.
- Both REST FULL and WebSocket SnapQuote normalization now preserve depth. WebSocket observations retain provider sequence and a local connection identifier. Provider feed time and local receipt time remain separate; no local time is substituted for provider time.
- Added stable market-event fingerprints derived from market observation fields, excluding local receipt/connection identity and later Greek enrichment. Local snapshot UUID remains separate so receipts do not conflict with immutable persisted snapshots. Fingerprints identify repeated observations, not proof of new liquidity or actual queue turnover. Cross-feed fingerprints are intentionally distinct; the future execution engine must prevent double counting across feeds/reconnects using its own consumption state.
- The quote cache ignores exact repeated events, older event times and nonadvancing sequences within one stream connection, and invalidates the cached book on future-at-receipt timestamps or crossed prices. Per-instrument rejection diagnostics appear in the chain view. This is not a durable liquidity budget; that belongs to steps 2/3.
- Added versioned execution-policy, provenance, fee-rule and effective-dated fee-schedule contracts. The fee contract distinguishes flat-per-order, premium-based and charge-based formulas, sides, caps, rounding and upstream tax bases. It includes brokerage, exchange, STT, SEBI, stamp, GST, IPFT and clearing components, plus a declared other component. Formula/dependency/window validation rejects ambiguous definitions. Calculation and ledger application remain pending.
- Created `config/paper-execution.json` as an explicit unreviewed configuration, with unknown assumptions left null and no invented fee rates. Diagnostics list activation blockers rather than treating absent inputs as free execution or unlimited liquidity. The status explicitly says the durable execution engine is pending, even if configuration becomes complete.
- Added the paper configuration report to `market.cmd status`; no live provider call, order, worker start, credential update or database migration was performed. Exported JSON Schema/TypeScript definitions for the new contracts.

## Provider source review and limits

First-party protocol references checked on 17 November 2026:

- https://smartapi.angelone.in/docs/Instruments : indexed documentation describes five buy/sell entries at bytes 147-346, flag 1 buy / 0 sell, quantity, paise price and order count; event time is epoch milliseconds. It says index sequence numbers should be ignored. This adapter handles option instruments, not index streams. Direct documentation access required authorization during review.
- https://raw.githubusercontent.com/angel-one/smartapi-python/main/SmartApi/smartWebSocketV2.py : inspected official SDK layout for token, sequence, event time and SnapQuote depth. The SDK and public issue history contain conflicting buy/sell naming. Retained SWAN's existing protocol-flag mapping (1 bid, 0 ask); do not silently copy swapped SDK labels. Connected side/quantity verification remains required.
- https://smartapi.angelone.in/docs/MarketData : indexed FULL contract documents exchange feed time and best-five buy/sell depth. Direct page required authorization. REST explicit buy/sell arrays are used as named; REST does not gain a fabricated sequence number.
- https://www.angelone.in/exchange-transaction-charges : reviewed current public brokerage/statutory component descriptions. This is a source reference, not an approved account fee schedule. Effective dates, account tariff/promotions, exchange components, GST basis and rounding must be reconciled against applicable official rules/account evidence before activation. No rates were silently copied into active execution configuration.

Quantity units are deliberately `unknown` in normalized quotes until supported account/feed evidence establishes units versus lots. There is no unit conversion based solely on a lot-size guess. Provider documentation review does not establish current account entitlements, complete coverage, live streaming compatibility, latency, redistribution or storage permission.

Prior 16 November sampling documented five REST levels for one call and put per index; this change did not repeat that sampling or claim streaming verification. The new static schemas are implementation evidence only.

## Local readiness and verification

`market.cmd status` ran locally without provider calls. Required Angel One configuration is present; the saved session is expired, the reviewed calendar has zero sessions, and the new execution configuration is syntactically valid but unreviewed/incomplete. NFO/BFO fee schedules and quantity-unit evidence are missing, as are chosen latency, participation, slippage, freshness, order lifetime and partial-fill parameters. Filling those fields will not enable the legacy engine as a realistic replacement.

Ran Python lint and backend type checks, regenerated shared contracts, and loaded the actual local configuration via the operator status command. Frontend TypeScript compatibility was checked against the regenerated contracts. No new automated tests, replay, synthetic fixture, fabricated provider response or simulated trade was created/run. Broad and connected QA remain deferred to final QA by user direction.

## Next implementation task

Step 2: migrate orders/fills/positions and add reservations, multiple fills per order, durable state transitions and idempotent accounting. Remove the existing one-fill-per-order reconciliation assumption. Retain historical records under their original version. Wire configuration readiness into the enhanced engine's entry preflight before any autonomous use. Step 3 will consume depth/time evidence and calculate/apply the verified fee model; this step does not claim those functions are implemented.
