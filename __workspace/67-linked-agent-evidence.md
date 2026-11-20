# Linked agent evidence

Account activity model outputs now have an Evidence used disclosure. It loads
only when opened, uses the authenticated account, and shows cited saved bid/ask/
last prices, contract labels from the saved instrument context, observation/receipt
times and source. Analysis news shows headline/source, publication/retrieval times
and declared provider delay. No raw context, credentials, response IDs or article
URLs are returned. Missing/invalid observations and unverified exchange time stay
explicit. Citing a record does not prove validation or grant trading permission.

Future pipeline contexts persist an audit ID, which each generated output carries.
The owned evidence endpoint accepts only that explicit context link, never nearest
timestamp or quote ID search across accounts. Legacy, wrong-kind and foreign links
are unavailable. Quote evidence is capped at 40; news at 100; omitted citations
remain counted as unavailable. Proposal/review news is not inferred from analysis.

D16 remains partially delivered in DEFERRED-WORK.md. Evaluation/strategy/risk
correlation, validation outcomes, article links and richer depth/age views remain.
Next slice: durable evaluation/run IDs before connecting end-to-end decision stages.
D17 version/history/billing limits stay open. Broker/live/manual acceptance skipped.

Verification: 289 backend tests; Ruff; mypy 84 modules; 13 frontend tests;
TypeScript and production build passed. New disposable-schema tests exercise a
mocked provider response through persisted context/output linkage, safe projection,
owner isolation, no legacy time join and missing/invalid records. Six-size browser
fixtures exercise lazy evidence, retry, prices, news delay, unverified timestamps,
legacy unavailable state and no overflow. Activity regression and public PWA smoke
pass. Reviewed the 390px evidence screenshot. Managed API and idle OBSERVATION
worker restarted to load the implementation; actual orders/manual intents/enabled
accounts remain zero. No login, manual acceptance or trading activation performed.
