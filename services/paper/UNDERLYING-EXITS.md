# Underlying exit monitoring

Durable paper positions may carry an optional `UnderlyingExitPolicy` in addition
to the existing option-premium stop and target. The policy names the underlying,
direction, invalidation level, and target explicitly; index points are never
converted into option prices.

The worker subscribes to configured NIFTY/NSE and SENSEX/BSE index tokens using
the provider's LTP stream mode and stores the latest observations in the in-memory
quote cache. The paper coordinator requires matching underlying identity and a
fresh exchange timestamp and receipt time. An invalidation or target crossing
requests a market exit through the existing durable order ledger. If a required
underlying observation is missing, stale, future-dated, or mismatched, the
coordinator requests a protective market exit and preserves existing
reconciliation behavior; missing option execution quotes still leave exposure
unresolved rather than creating a fill.

ORB mapping now preserves reviewed deterministic levels in the envelope's
underlying policy and permits `target=null` for the option premium. Such an
envelope requires an underlying exit policy. Its 20% premium stop is recalculated
from actual average entry fills, rounded upward to a valid option tick. Index
levels never become option-premium prices. Legacy/manual premium targets remain
supported.

For ORB, `entry_deadline_only` separates the entry opportunity's expiry from the
filled position's holding limit. Invalidated strategies, lost data, risk limits,
and mandatory exits continue to apply. A generic model evaluation cannot replace
an active ORB envelope.

Migration `f9d2e3a4b5c6` makes the position premium target nullable and is applied
locally. A disposable PostgreSQL-schema test covers an actual simulated fill,
fill-relative premium protection, preservation after entry expiry, and an
underlying target exit request. This is software evidence only. Candidate
research records remain immutable/non-executable; staging uses separate existing
validation or qualification/arm authority. Actual-market acceptance is not implied.
