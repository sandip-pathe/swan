# Decisions and dependencies

## Accepted direction - 17 November 2026

## Accepted direction - 18 November 2026

- D24 (accepted): autonomous trading/review agents operate throughout the session independently of the user-facing chat. Chat is a separate user-only point of contact; it retrieves persisted agent findings when asked and does not receive routine unsolicited agent reports. Critical operational safety alerts remain visible separately.
- D25 (accepted): chat is the primary app surface; detailed dashboard views are secondary and opened on demand. The chat assistant may answer questions using timestamped, attributed workspace evidence and may invoke a narrow authenticated command set. Initial command: "stop trading today" blocks new entries for the current verified exchange session, keeps existing positions under deterministic monitoring/protection, and does not liquidate them. Resuming requires a separate explicit request and normal preflight.
- D26 (accepted boundary): the chat assistant cannot place or modify orders, change risk limits or strategy, bypass deterministic controls, or access provider/execution credentials. Its failure or absence cannot affect autonomous execution. Commands are authenticated, idempotent, and audited.

Latest implementation: [durable worker routing/protection](29-paper-worker-and-protection.md). New entries use fixed-limit approvals and an account-revision check. New request evidence explicitly assigns the whole risk budget to any held units until fully flat, preserving historical allocation for older records. The first entry-level fill yields for cancellation/protection. Exit replacement requires a change to a higher-priority reason; blocked price bounds remain unresolved rather than automatically chasing the market. Code availability is not acceptance: configuration and final connected QA continue to block activation.

Latest implementation: [depth-aware sizing](28-paper-depth-risk-sizing.md) adds deterministic whole-lot sizing and revision-bound approval contracts using reviewed depth/fee inputs. Its cash allowance requires a fixed-limit entry; a later market-price anchor is outside that approval. Stop risk remains an estimate subject to gaps. Locked portfolio loading, first-partial fee/risk allocation and independent protection are pending before worker routing or activation.

Latest engineering evidence: [step 3A](27-paper-step-three-matching-and-fees.md) adds fee accrual, observed-depth matching, persistent participation budgets, explicit paper price protection and incomplete-depth valuation states. These are implementation policies requiring final QA and reviewed configuration, not newly verified broker behavior. Full step 3 activation remains pending deterministic risk/protection routing and provider/account evidence.

Implementation evidence: [step 1 contracts](25-paper-step-one-implementation.md) and [step 2 ledger/migration](26-paper-step-two-implementation.md). Durable order/accounting code is implemented with static/schema verification; depth matching, applied fees, behavioral QA and activation remain pending. D21's accepted direction is being implemented incrementally and must not be marked fully validated.

The user selected SWAN-owned virtual capital and paper execution using actual Angel One market data, with realistic execution/accounting as the goal. External paper platforms and paid paper credits are not dependencies. The implementation plan is [24-realistic-paper-execution-plan.md](24-realistic-paper-execution-plan.md); it supersedes external-provider-first proposals in documents 22/23 and immediate full-fill assumptions in document 05.

- D20 (accepted): one persistent internal virtual-cash ledger; current single owner/account; no automatic refills or loss resets.
- D21 (accepted direction; implementation pending): evidence-backed, latency-aware bid/ask/depth execution, persistent orders and partial fills, reservations, itemized effective-dated fees, independent protective exits, recovery and auditable assumptions. Missing evidence must never become an invented fill.
- D22 (accepted): retain real provider inputs and genuine agent outputs; no synthetic market fixtures, replay runner or seeded trades. Simulated execution using virtual money is now explicitly accepted.
- D23 (accepted): local implementation and iterations; new tests/broad QA deferred until final QA, with connected readiness required before autonomous observation. No deployment or real-money activation in this increment.

Existing D08 fee/slippage configuration and D12 liquidity settings remain unresolved activation dependencies. This planning update neither certifies their correctness nor claims the enhanced engine is implemented.

Status values: accepted from PRD, proposed, verify, unresolved. Resolve blocking items before the dependent milestone. Planning assumptions are not verified provider facts.

| ID | Topic | Status / proposal | Blocks |
| --- | --- | --- | --- |
| D01 | Trading mode | Updated 2026-11-16: autonomous paper observation now; autonomous real execution is future product scope, separately implemented and explicitly enabled | Paper observation / future live release |
| D02 | Stack/hosting | Accepted PRD baseline; verify versions and deployment constraints at scaffolding | M1/M6 |
| D03 | User authentication | Firebase Auth; one owner initially, isolated user/broker accounts are future product scope | Current access / future multi-user release |
| D04 | NIFTY/SENSEX coverage | Verify exchange access, subscriptions, instrument metadata and bid/ask support in SmartAPI | M0/M2 |
| D05 | IV/Greeks/OI/volume | Verify native fields, units, timestamps and coverage; approve derivation only with valid inputs | M0/M2 |
| D06 | Provider limits/auth | Verify rate limits, streaming semantics, reconnect and token renewal requirements | M2 |
| D07 | Session calendar | Verify authoritative source, holidays, exceptional sessions, expiry and lot-size metadata | M2 |
| D08 | Fee/slippage model | Unresolved: configurable, itemized, versioned; verify current schedules | M1 live-realistic configuration |
| D09 | Risk basis | Proposed: equity capped at initial configured capital; costs included in planned stop risk | M1 |
| D10 | Daily loss | Proposed: session-opening equity vs net liquidation equity; block entries and request flatten | M1/M2 |
| D11 | Cutoff/overnight | Accepted: intraday scalping, no overnight holding; session-relative defaults in current requirements | M2/live-data enablement |
| D12 | Liquidity thresholds | Unresolved spread, volume/OI, depth/quantity constraints and allowed expiries/strikes | M2/live-data enablement |
| D13 | Monitor frequency | Verify rate limits; configure independent short monitoring loop and latency target | M2 |
| D14 | AI provider access | Accepted: OpenAI API configured separately; no assumption of transferable ChatGPT credits | M3 live API work |
| D15 | Model/cost budget | Unresolved current supported model, timeout, token budget, per-session spend limit | M3 |
| D16 | Restart behavior | Proposed: reconcile, prioritize exits, remain paused for new entries | M2 |
| D17 | Database hosting | Unresolved managed PostgreSQL vs self-hosted; backups, network access and budget | M6 |
| D18 | Retention/licensing | Verify market-data storage/fixture permissions; decide decision/log retention | M0/M6 |
| D19 | Performance evaluation | Unresolved observation period and reporting benchmarks; no guaranteed-return criterion | Observation phase |

## Capability evidence template

For each external dependency record: official documentation URL, date checked, account entitlement, supported instruments/fields, limits, tested response shape, failure behavior, and implementation consequence. Never store credentials in evidence.

## Change log

- 2026-11-15: Step-two adapter/runtime implemented. Official metadata contains NFO/BFO records; account access remains unverified. Published NSE-only Greeks capability is respected, and provider-unknown metric timestamps remain null. Use an explicitly reviewed calendar instead of guessed sessions. No synthetic responses or replay added; connected QA deferred per user direction.

- 2026-11-15: Created planning baseline from supplied product PRD. Added proposed deterministic execution details, monitoring separation, transaction boundaries and milestone gates. No live API capability checks or implementation performed.

## Accepted user decisions — supersede conflicting earlier proposals

- Autonomous paper execution without per-trade approval now. The 16 November clarification adds future autonomous real execution and multiple broker-linked users; earlier permanent paper-only/single-user restrictions are superseded. No real-money operation during the immediate observation period.
- Intraday long-option scalping on NIFTY/SENSEX; close before session end, never extend holding to contract expiry.
- Listed expiries within 0–7 calendar days, inclusive of same-day expiry; Angel One metadata determines actual contracts and lot sizes.
- Firebase Auth replaces Cognito. SWAN owns its paper ledger; TradingView integration is not required.
- Deliver the full agreed product with maintainable sizing, tests, recovery and release evidence; staged implementation does not reduce scope.
- User will supply required service access. Never request plaintext secrets in chat.

## Resolved engineering defaults

Delivery update, 15 November 2026: user requested removal of the replay runner and synthetic market-data fixture; both were removed. No demonstration data, generated news, agent replies or example trades are added to the application. Keep ordinary isolated numerical tests already implemented. User subsequently requested implementation-first delivery: defer additional test development, wider integration QA and CI expansion to final QA while retaining existing checks. Missing integrations remain explicitly unavailable, not substituted with invented output.

Authentication update: user requested email/password login alongside Google sign-in. Implemented existing-account sign-in through Firebase; no public registration. Enable the provider and create the user's password account securely in Firebase Console. Server-side token verification and UID allowlisting remain required for protected APIs.

These are implementation choices, not additional user-confirmed strategy parameters: Google sign-in and UID allowlist; session-relative entry/flatten offsets of 20/10 minutes; tick-driven monitoring with a one-second watchdog target; two-second executable-quote freshness target with a 10-second ceiling; five-minute maximum holding time; 180-second AI context/envelope lifetime. All are versioned, validated and visible. See current requirements for semantics.

Proposed managed AWS PostgreSQL is the deployment baseline, pending account/budget selection and benchmark sizing. Provider/news capabilities, licensed retention, numerical liquidity thresholds, realistic fees/slippage, current model selection and API budgets remain verification/configuration dependencies. They block dependent activation, not every foundational task.

- 2026-11-15: Updated planning baseline with user decisions; added complete product requirements, integration setup and AC13–AC21 quality criteria. Official Firebase verification guidance reviewed; SmartAPI documentation access was restricted. No credentials or application code changed.
# 15 November 2026: access and QA deferred

The user will add all API credentials later and requested skipping tests now. Continue implementing without creating keys or making live provider requests. Keep explicit unavailable states, deterministic risk controls and no synthetic responses/data. Tests and connected acceptance remain final-QA work. See 18-agents-and-news-implementation.md.

