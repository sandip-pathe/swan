# India market news source review and slice

The existing reader supplies cited agent evidence, not a standalone market-news
screen or an official exchange-filings service. This slice makes its currently
configured provider more relevant to financial markets and makes attribution and
publisher navigation visible where cited evidence is reviewed.

## Source decision

- NewsData.io's Market endpoint is selected over its general Latest endpoint for
  the existing owner-local feed. The implementation continues to use one bounded
  request, India and English filters, the existing 15-minute process cache and
  24-hour publication window. It does not use pagination, article bodies or paid
  parameters. The provider lists Market News on its free plan, with 200 credits a
  day and a 12-hour delay, and describes the free plan as for testing/personal
  projects: [pricing](https://newsdata.io/pricing),
  [documentation](https://newsdata.io/documentation).
- Agent evidence now links each cited title to the validated publisher URL and
  displays the NewsData.io attribution when that provider is recorded. Original
  publication and retrieval times plus the 12-hour provider delay remain visible.
- NewsData.io's terms require attribution and state that publisher content remains
  owned by its respective content owner; its API terms do not themselves settle
  downstream rights for that content. This local single-owner display is not a
  determination that a public or multi-user service may republish it. See
  [provider terms](https://newsdata.io/terms). D18 remains open for intended-use
  rights, India coverage quality and delay acceptance.
- Economic Times RSS is not chosen: its terms describe personal, non-commercial
  use, restrict aggregation/display and require direct article links:
  [ET RSS terms](https://economictimes.indiatimes.com/markets/stocks/rss.cms).
- NSE website scraping wrappers such as NseIndiaApi are not a suitable default
  production source. NSE prohibits systematic/automated collection from its site
  and offers formal data subscriptions, including an EOD corporate-announcement
  product: [NSE terms](https://betanseapi.nseindia.com/static/nse-terms-of-use),
  [NSE corporate data](https://www.nseindia.com/static/market-data/corporate-data-subscription).
- BSE offers a self-data-feed route with registration, KYC, pricing and agreements;
  it should be evaluated if official BSE filings become a requirement:
  [BSE data products](https://marketdata.bseindia.com/).
- Marketaux, yfinance and third-party NSE/BSE wrappers are not added. No free
  provider was verified here for durable user-facing redistribution rights plus
  complete official announcements.

## Scope and follow-up

This does not add a consumer News screen, ticker search, sentiment, official
exchange filings or real-time alerts. The provider was not contacted and no live
news request was made. Keep D18 open until intended deployment rights and source
coverage are accepted. Preserve the explicit user instruction to skip broker login
and live-market acceptance. No tests or build checks were run for this slice.
