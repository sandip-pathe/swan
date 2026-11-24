# Option-chain quote ordering

Implemented 20 November 2026 after the user reported that the latest quotes
appeared at the bottom of Markets → Option chain.

The chain now defaults to newest quote pairs first. Each strike pair ranks by
the newest exchange timestamp of either call or put, with ascending strike as a
deterministic tie-break. Calls and puts stay together. Users can select
Strike: low to high. The API ranks before pagination, so this is not a visual
reversal of one page. The Home preview uses the same ordering. Retrieval time
cannot promote an old quote.

At implementation time, backend and frontend suites, Ruff, mypy, production
build, and six browser layouts passed. No broker orders were placed. These are
historical results for this change, not current project completion evidence.

For current priorities and held acceptance work, use the root
[project work list](../DEFERRED-WORK.md). This checkpoint no longer defines the
finish order.
