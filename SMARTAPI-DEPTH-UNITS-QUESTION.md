# SmartAPI depth quantity units: evidence review and support draft

## Later resolution for the paper model

The earlier unresolved conclusion below is historical. The reviewed paper
configuration now maps depth quantities to absolute option units. It does not
multiply raw quantities by the lot size.

The [NSE F&O protocol](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/TP_FO_Trimmed_NNF_PROTOCOL_9.36_0.pdf)
describes absolute order quantities in board-lot multiples and aggregate order
quantities in market-by-price data. The [BSE derivatives IML specification](https://www.bseindia.com/downloads1/Equity_Derivative_IML_API_version_1_1.pdf)
section 7.4.1 describes absolute order quantity in market-lot multiples and total
quantity in best bid/offer data. The pinned official SDK below decodes raw depth
quantities without multiplying them. Mapping the SmartAPI output to these units
is an inference from those sources, not a written broker confirmation.

Actual NFO and BFO calls and puts supplied 80 sampled depth levels over FULL
REST and SnapQuote. Each quantity was a multiple of its catalog lot size, 65 for
NFO and 20 for BFO. Divisibility corroborates the inference but is not its proof.
WebSocket samples were about 0.71 seconds old. The NFO REST sample was about
3.65 seconds old and failed freshness acceptance. It was quantity corroboration
only. The private report is `.local/run/depth-unit-corroboration-2026-11-23.json`.

This mapping was saved through audited configuration as
`paper-unit-mapping-20261123-v1`, not by bypassing an admission check. Both completed
paper round trips retained the mapping and sources with their orders. No support
message was sent. Explicit SmartAPI venue/transport confirmation remains absent.

Reviewed 23 November 2026. This is a draft; no message has been sent.

## What the primary sources establish

The [official Python SDK depth parser at commit 6bd06ff8e9085e95b709e560a3482586860fb2b3](https://github.com/angel-one/smartapi-python/blob/6bd06ff8e9085e95b709e560a3482586860fb2b3/SmartApi/smartWebSocketV2.py)
reads each best-five quantity as a signed 64-bit integer at bytes 2–10 within
each 20-byte depth record. It returns the raw integer without a lot-size conversion.
That establishes encoding, not economic units: a decoder can return either units
or lots unchanged. Its intermediate buy/sell naming is swapped again by the main
SnapQuote parser; that naming is not a reason to reverse our observed depth sides.
The file was inspected as text, not installed or executed.

The [official market-data reference](https://smartapi.angelone.in/docs/MarketData)
describes FULL REST `depth.buy[n].quantity` and `depth.sell[n].quantity` as quantities
at each level. The reviewed description does not explicitly specify units versus
lots for each venue/transport. Direct documentation access was intermittently
unavailable; searchable primary-source excerpts do not resolve the ambiguity.

The [official instruments/margin reference](https://smartapi.angelone.in/docs/Instruments)
contains a note about NFO units under margin-calculator `qty`. It concerns an
input to another endpoint, not the output units of market depth. It does not
establish BFO or WebSocket depth semantics.

Actual earlier samples retained five-level depth for NFO and BFO over REST and
SnapQuote. Quantities being multiples of catalog lot sizes corroborate a possible
interpretation but do not establish it. Third-party trading-app order quantity
conventions are likewise not authoritative feed evidence.

Conclusion: unit mapping remains unverified. No execution setting, admission gate
or quote quantity has been changed on the basis of these sources.

## Draft question for Angel One SmartAPI support

Subject: Confirm best-five option depth quantity units for NFO/BFO REST and WebSocket

We are implementing a paper-only options simulator using SmartAPI market data.
Please confirm the exact quantity units for each of these four cases:

| Venue | Transport / field | Quantity means individual option units or number of lots? |
| --- | --- | --- |
| NFO | FULL REST `/rest/secure/angelbroking/market/v1/quote/`, `depth.buy/sell[n].quantity` | Please confirm |
| BFO | Same FULL REST depth fields | Please confirm |
| NFO | WebSocket v2 mode 3 SnapQuote, quantity in each 20-byte best-five depth record | Please confirm |
| BFO | Same SnapQuote best-five depth quantity | Please confirm |

For example, if the current instrument-master lot size is 65 and a depth level
contains quantity 130, does that mean 130 individual option units (two lots), or
130 lots (8,450 units)? Please provide the corresponding example for a BFO option
using that contract's current lot size as well.

Does the mapping differ between REST and WebSocket, between venues, or by contract
type? Are there exceptions or an effective-date change we should account for?
Please link an authoritative protocol reference or confirm the mapping explicitly.
We are asking about displayed depth output, not place-order or margin-input quantity.

No account credentials, tokens, client identifiers or private financial data are
included in this draft. No broker trade is required to answer the protocol question.

## What happens after confirmation

Record the applicable venue/transport mapping and source, corroborate against
fresh observations, and save through the existing audited configuration path.
Then refresh connection checks and attempt the existing bounded one-lot paper
validation. Do not treat this research or a prepared draft as an accepted trade.
