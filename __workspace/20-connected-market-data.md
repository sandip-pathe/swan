# Connected market-data status

Updated: 16 November 2026, Asia/Kolkata.

Verified the saved Angel One session using the read-only profile endpoint, including matching its client code without displaying profile data. Added `market.cmd check` for this authentication check; it does not establish quote freshness or enable trading.

Downloaded actual provider instrument metadata and identified index tokens by exact underlying, venue and AMXIDX instrument type. Confirmed fresh REST index quotes for NIFTY and SENSEX. Sampled one call and one put per underlying with listed expiry within seven calendar days; all four returned five bid/ask levels, volume and open interest. This sampling does not establish complete chain, streaming, Greeks or reconnect coverage.

Saved verified index tokens in the ignored local environment and the read-only observation report under `.local/market-connection-report.json`. No broker orders were placed, no paper account was created and no autonomous worker was enabled. No unit tests or simulations ran; lint/type checks passed for the modified client/CLI.

Backend Firebase project ID now matches the existing browser project. Private service identity and explicit owner/account binding are still missing. Other pending setup: reviewed exchange sessions, explicit paper risk/cost policy, OpenAI model/budget and the NewsData provider adapter. Login success and sampled quotes do not establish full product readiness.
