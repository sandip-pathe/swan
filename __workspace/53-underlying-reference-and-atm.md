# Underlying reference and ATM context

Implemented 20 November 2026. M3 manual acceptance remains deferred at the user's
request. This slice adds display context without changing execution qualification.

## Data delivery

Retain NIFTY/NSE and SENSEX/BSE FULL quote references in a separate replaceable
underlying_references projection. Existing explicit chain refresh and existing
worker reference reads normalize/publish index observations; no new provider
endpoint, polling request, competing stream or executable instrument is introduced.
Identity must match the configured venue/token; timestamps cannot be in the
future and last price must be positive. Previous close zero/missing is unavailable.
An older response cannot overwrite a newer exchange observation.

Chain and selected-contract cache APIs include reference context. Page reads call
no provider. Index references are not option quotes, fill evidence, volumes or
execution permission. Failure/expiry of authentication retains existing behavior.

## Display and ATM rule

The chain and contract view show the index level in points, change/percentage
against its broker previous close, timestamp and Recent/Saved reference status.
Missing values remain unavailable. No hardcoded market levels are used.

ATM is the nearest strike in the full latest cached listing for the chosen
underlying/expiry, not merely the current quote page. Equal distance chooses the
lower strike. Require today's catalog and an index reference from the same IST
calendar date. Expired/missing expiry listings, stale catalogs and prior-session
references leave ATM unavailable. An old intraday reference is labeled nearest
strike at saved price; paired rows explicitly label ATM at saved price. The rule
is descriptive and does not select or admit a trade.

## Validation and local state

All 185 backend tests pass, including index venue/token/future/zero rejection,
missing previous close, monotonic retention, deterministic ATM tie handling,
shared chain/selection context, venue isolation and missing/stale catalog behavior.
Ten frontend calculation/preference tests, production build/type checking,
Ruff and mypy (70 source files) pass. Six browser layouts cover reference price,
ATM marker, prior-session reference and missing-price states, plus existing chart,
search/watchlist/depth/offline flows. No overflow or browser exceptions. Visual
review used the 390px chain screenshot; actual mobile sign-in/PWA smoke passes.

Migration c4b8def09609 is applied. API and the managed observation worker were
restarted to load the change; entries remain paused and orders/fills remain zero.
No manual quote refresh or M3 evidence exercise was performed. The local reference
projection was empty on startup and the observer logged its generic universe/
calendar-unavailable blocker; actual reference population was not verified this
turn. A subsequent successful normal chain refresh or worker index read will
populate it. No fresh live delivery is claimed from fixture tests.

Next: design and implement the manual paper-order preview/intent contract, then
submission through the existing risk/ledger path. Preserve unresolved depth/fee
and qualification gates.
