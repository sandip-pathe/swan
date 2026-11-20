# Evaluation-history query indexes

Added migration f7a9bcd87412 after the existing manual-intent migration. Two
composite indexes match the account, kind, evaluation-link, timestamp and UUID
expressions in evaluation history. One uses the top-level evaluation_id for
outputs, checks and evaluation outcomes; the other uses request.evaluation_id for
model reservations. SQLAlchemy metadata uses the same expressions. Index keys
contain correlation identifiers, not model output/rationale payloads. Existing
ownership checks, read-only routes, page limits and trading gates are unchanged.

The indexes support forward/backward ordered scans, including equal-timestamp
UUID keyset boundaries. They add storage/write overhead to audit insertion. The
migration uses ordinary transactional index creation; this is appropriate to the
current local installation, not a zero-downtime large-production migration.
Applied locally with a three-second lock timeout and 30-second statement timeout.
Migration downgrade/re-upgrade ran only in a disposable test schema.

A 30,000-row synthetic same-account audit dataset spans many evaluation links.
EXPLAIN ANALYZE BUFFERS checks the SQLAlchemy-generated first/older output queries
and first/older ascending reservation queries with natural planner settings.
Each returns 21 rows using the matching index, no sequential scan or sort and
fewer than 100 filter removals. Observed warm local execution was 0.015-0.033ms
and 5-7 shared hit blocks. These are illustrative query-level observations, not
an endpoint latency target or production load qualification. Plan checks avoid
brittle wall-time assertions. Migration roundtrip is included.

Verification: Ruff and mypy (89 modules) pass. All 341 backend tests pass. Local API health is 200;
actual orders/manual intents/enabled accounts remain zero, runtime OBSERVATION. No frontend changes. D20 still includes wider query
indexing, concurrent/cold-cache/full-endpoint load, integrated recovery/security
and actual-market acceptance. D16/D17 retain other history limits and billing.
Next slice: model-version history pagination. Ledger updated; no broker login,
market refresh or permission activation performed.
