# NIFTY ORB paper-plan mandate

**Mandate:** `S01-NIFTY-ORB-PAPER`, version `0.1-candidate`  
**State:** implementation candidate; pending product review; never executable  
**Strategy setup:** `S01-NIFTY-ORB`, version `0.1-setup`

This freezes the first paper-plan assumptions for implementation. It does not
establish strategy quality, authorize a paper session, or grant an order path.
Every candidate remains blocked until the existing account and paper controls
approve current evidence.

## Execution decision confirmed 22 November 2026

The owner selected an underlying-index target, a 20% premium stop based on
actual average entry fill, and a maximum five-minute hold. No option-premium
profit target is required or invented. The execution envelope version is
`S01-NIFTY-ORB-PAPER:0.2-underlying-target`; immutable `0.1-candidate` research
records remain unchanged.

`orb_execution.py` translates exact reviewed levels and fresh underlying and
option observations into paper contracts. `orb_admission.py` stages them only
under an existing scoped validation session or qualified paper arm, checks
review provenance and execution configuration, and does not enable an account.
The worker rechecks underlying entry bounds and uses existing paper admission.
The paper ledger recalculates premium protection from actual average fills.

The opportunity deadline applies to entries. It does not by itself invalidate
an already filled position; premium protection, underlying target/invalidation,
the stricter account/strategy holding limit, and mandatory exits still apply.
No worker/session/arm has been started by implementing this bridge. Genuine
source/model behavior, qualification and supervised paper acceptance remain
outstanding. Earlier "never executable" wording describes the immutable research
candidate, not a prohibition on separately admitted paper envelopes.

## Setup and opportunity

- Use only the deterministic NIFTY/NSE one-minute ORB assessment and its exact
  snapshot, assessment, and evidence links.
- Preserve the frozen 09:15–09:30 IST range, 5% range-width buffer, 25% maximum
  extension, first eligible completed-bar trigger, and 11:00 trigger cutoff.
- Permit one submitted entry attempt per session across both directions. A
  rejected, cancelled, or unfilled submission consumes it. A signal blocked
  before submission does not; its opportunity still expires.
- The opportunity expires 60 seconds after the trigger bar closes. Before
  submission, revalidate fresh underlying evidence: price must remain beyond
  the trigger boundary, within the anti-chase boundary, and short of the
  underlying target.

## Contract and entry

- Bullish setup maps to a long NIFTY call; bearish maps to a long NIFTY put.
- Select the first listed expiry strictly after the session date, no more than
  seven calendar days later. Exclude same-day expiry.
- Select the strike closest to the fresh underlying observation; break an
  exact tie with the lower strike. Freeze that contract for the opportunity.
  If it fails metadata, quote/depth, liquidity, spread, or risk checks, skip;
  do not walk to another strike or expiry.
- Use the actual contract lot size and tick size. The candidate entry is a BUY
  LIMIT at the qualifying observed ask, rounded to the permitted tick. Do not
  chase above the captured ask.
- Cancel an unfilled remainder at the 60-second opportunity deadline. For a
  partial fill, cancel the remainder and protect only the actually filled
  quantity. An unresolved fill or cancellation stays unresolved until
  reconciled and blocks a new entry.

## Protection, sizing, and costs

- The underlying invalidation and target are the deterministic levels in the
  assessment. They are index levels; never convert them into option-premium
  prices.
- The candidate premium stop is 20% below average actual entry fill. It is an
  experimental parameter, not a calibrated loss bound. Apply it only against
  qualifying executable option bids.
- Close on the first applicable premium stop, fresh underlying invalidation,
  fresh underlying target, 300-second maximum hold, or current account
  mandatory flatten cutoff. Existing account settings may shorten these
  limits; this mandate cannot lengthen them. Protective and mandatory exits
  take priority over a target when event order is uncertain.
- Missing executable exit quotes or unresolved orders remain pending; never
  synthesize a fill from an underlying level or option candle.
- Use the current account risk configuration, qualification, reviewed NFO fee
  schedule, actual lot size, and declared adverse-execution assumptions. Do
  not invent capital or rupee limits. If one lot does not fit the existing
  policy, abstain. Record full-premium-loss-plus-fees as a scenario; the stop
  does not cap gap or liquidity losses.

## Candidate blockers and release boundary

The candidate record is a distinct immutable version linked to the reviewed
agent artifact, deterministic assessment, source snapshot, and evidence. It
stays `BLOCKED` and `execution_eligible=false` while any of these are missing:

- Current account risk configuration and paper qualification.
- Selected current option contract and executable quote/depth evidence.
- Reviewed, effective NFO fee schedule.
- Fresh underlying revalidation and an independent protective-exit monitor.

The next milestone, P4, must map an admitted candidate into existing paper risk
and order controls. It must not mutate this research draft, bypass human/account
permissions, or impersonate a manual intent. Provider, broker, live-market,
manual paper, and human-review acceptance remain separate checks and are not
resumed by this mandate.
