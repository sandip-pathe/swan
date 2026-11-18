# Configuration milestone review

Prepared 18 November 2026. Entries remain disabled. Existing capital and ledger history are preserved.

## Saved and verified

- Both venues have explicit sessions/closures for 18–30 November 2026, with normal trading 09:15–15:40 IST and the November 24 holiday. Dates beyond this range remain unknown. December timings must be reviewed separately before extending coverage.
- NSE timings came from its current official timing page and October CAS FAQ; its 2026 F&O holiday circular supplies the holiday. BSE timing notice 20260801-2 was downloaded directly from BSE and parsed locally. BSE-authored holiday notice 20251212-8 was inspected through the Steel City broker mirror because the original holiday page was unavailable. URLs and retrieval limitations are in `calendar-sources.json` and the imported session provenance.
- The owner confirmed standard published Angel One pricing. Current eligible instrument-master lot sizes are NIFTY/NFO 65 units and SENSEX/BFO 20 units; these are observed metadata, not hardcoded instrument definitions.
- The owner explicitly approved the proposed paper limits in this conversation. Execution assumptions and the complete account risk policy are now saved and audited as reviewed. Fee schedules remain unreviewed; quantity-unit verification remains an independent blocker.

## Approved paper assumptions

| Input | Proposed value | Meaning |
|---|---:|---|
| Assumed latency | 250 ms | Simulation assumption, not a measured broker guarantee |
| Displayed-depth participation | 10% | Limits consumption of observed depth |
| Extra adverse slippage | 5 bps | Additional paper penalty; not historical calibration |
| Market protection | 100 bps | Reject depth outside the configured price band |
| Maximum quote age | 2 seconds | Applies alongside independent account checks |
| Pending entry lifetime | 5 seconds | Unfilled entry cannot wait indefinitely |
| Partial-fill granularity | Whole lots | Conservative simulation assumption |
| Sale proceeds reuse | Blocked | No assumption of immediate reuse |
| Feed quantity unit | Unresolved | Order quantity documentation does not establish depth quantity semantics |

## Approved account policy

Preserve existing capital. Risk at most 0.5% per trade and 2% per day; one open position; maximum holding 5 minutes; maximum spread 100 bps; minimum volume and open interest 1,000 each; quotes at most 2 seconds old; stop entries 20 minutes before close; begin flattening 10 minutes before close.

Approved quantity cap: 65 **units**, derived from current eligible lot metadata. This permits at most one current NIFTY lot or three current SENSEX lots before the independent cash/risk checks. It is not a one-lot guarantee and does not force an entry. `risk-policy.draft.json` now records the applied policy and review status; any later import must check the current account revision again.

## Fee draft and unresolved evidence

The fee draft records the published brokerage (₹20 per executed order), venue transaction charges, sell-side STT, SEBI fee, buy-side stamp duty, GST and explicit published zero clearing charge. NSE IPFT is recorded from the current broker tariff. **BFO IPFT is omitted pending explicit evidence; omission never means zero.** Schedules cover only the proposed 18–30 November observation window, not the historical introduction date of each rate.

The broker's own contract-note guide confirms that GST includes IPFT; the NFO fee draft now includes IPFT in the GST base. Contract-note rounding increment/scope remains unverified. Draft rounding settings are visibly provisional; fee schedules cannot be marked reviewed while these evidence records are unverified. A successful login and standard-plan confirmation do not prove contract-note allocation behavior. No actual contract note, account statement or real-money order was generated to resolve this.

Next evidence: compare a privately available Angel One contract-note charge breakdown with the tariff (no credentials needed in chat), or obtain an explicit broker explanation of charge allocation/rounding and BFO IPFT. Verify both venues' depth quantity units using provider confirmation and actual market observations. Owner review has resolved policy-choice blockers; it cannot substitute for missing fee/feed evidence.

## Sources

- [NSE timings](https://www.nseindia.com/static/market-data/market-timings), [October CAS FAQ](https://nsearchives.nseindia.com/web/mediaattachment/2026-10/FAQs_on_Closing_Auction_Session_CAS_in_the_CM_and_changes_in_FO_Segment_ver3_20261023220345.pdf), [NSE holidays](https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf).
- [BSE timing notice](https://www.bseindia.com/downloads/UploadDocs/Notices/20260801-2/20260801-2.pdf), [BSE holiday notice](https://www.bseindia.com/markets/MarketInfo/DispNewNoticesCirculars.aspx?page=20251212-8), [BSE-authored holiday notice via broker mirror](https://www.steelcitynettrade.com/Circulars/BSE-Trading%20Holidays%20for%20the%20Calendar%20Year%202026%20for%20Equity%20and%20Equity%20Derivatives%20Segments.pdf).
- [Angel One current charges](https://www.angelone.in/exchange-transaction-charges), [SmartAPI order/response documentation](https://smartapi.angelone.in/docs/ResponseStructure), [SmartAPI depth protocol](https://smartapi.angelone.in/docs/Instruments).
- [Angel One contract-note GST base](https://www.angelone.in/knowledge-center/online-share-trading/what-is-a-contract-note-and-how-to-read-it).

Configuration preparation is complete; configuration readiness is not yet complete. Final connected paper execution qualification remains a later gate.
