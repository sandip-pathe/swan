"""Observed-candle fixtures are isolated from provider and execution evidence."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api import candles as api
from services.api.app import app
from services.api.auth import account_identity
from services.core.models import (
    Account,
    LiveCandleSegment,
    MarketHistoryBatch,
    PaperOrder,
    SnapshotRecord,
)
from services.market.candle_store import CandleStore, reconciled_bars
from services.market.live_candles import LiveCandles
from services.market.settings import MarketSettings
from services.worker.runtime import TradingRuntime


def inputs(scenario):
    instrument = scenario.instrument.model_copy(update={"exchange": "NFO"})
    quote = scenario.quote.model_copy(
        update={
            "source": "angelone-websocket-v2:snapquote",
            "timestamp_basis": "exchange_feed",
            "stream_id": uuid4(),
            "sequence": 1,
            "volume": 500,
            "last_price": Decimal(100),
        }
    )
    return instrument, quote


def tick(quote, seconds, sequence, price=100, volume=500, **changes):
    stamp = quote.timestamp + timedelta(seconds=seconds)
    return quote.model_copy(
        update={
            "timestamp": stamp,
            "received_at": stamp,
            "sequence": sequence,
            "last_price": Decimal(price),
            "volume": volume,
            **changes,
        }
    )


def test_ohlc_duplicate_ordering_and_cumulative_volume_reset(scenario):
    instrument, quote = inputs(scenario)
    candles = LiveCandles()
    assert candles.observe(quote, instrument, scenario.session)
    assert candles.observe(tick(quote, 1, 2, 105, 510), instrument, scenario.session)
    assert candles.observe(tick(quote, 2, 3, 99, 530), instrument, scenario.session)
    assert not candles.observe(tick(quote, 2, 3, 999, 9999), instrument, scenario.session)
    assert not candles.observe(tick(quote, -1, 100, 999, 9999), instrument, scenario.session)
    row = candles.drain()[0]
    assert (row["open"], row["high"], row["low"], row["close"]) == ("100", "105", "99", "99")
    assert row["observations"] == 3 and row["observed_volume_delta"] == 30
    assert row["volume"] is None  # The first snapshot is not a full interval baseline.
    assert candles.observe(tick(quote, 3, 4, 101, 5), instrument, scenario.session)
    assert candles.observe(tick(quote, 4, 5, 102, 10), instrument, scenario.session)
    row = candles.drain()[0]
    assert row["observed_volume_delta"] == 35 and "cumulative_volume_reset" in row["issues"]


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "angelone-rest:full"},
        {"timestamp_basis": "unknown"},
        {"stream_id": None},
        {"last_price": None},
        {"sequence": None},
    ],
)
def test_non_stream_or_unavailable_observations_do_not_create_bars(scenario, changes):
    instrument, quote = inputs(scenario)
    candles = LiveCandles()
    assert not candles.observe(quote.model_copy(update=changes), instrument, scenario.session)
    assert not candles.drain()


def test_session_alignment_gaps_reconnects_and_no_carried_prices(scenario):
    instrument, quote = inputs(scenario)
    candles = LiveCandles()
    assert not candles.observe(
        tick(quote, 0, 1, received_at=quote.timestamp - timedelta(seconds=1)),
        instrument,
        scenario.session,
    )
    assert not candles.observe(
        tick(quote, 0, 1, received_at=quote.timestamp + timedelta(seconds=11)),
        instrument,
        scenario.session,
    )
    assert not candles.observe(tick(quote, 6 * 3600, 2), instrument, scenario.session)
    candles.observe(quote, instrument, scenario.session)
    new_stream = uuid4()
    candles.observe(tick(quote, 5, 1, 102, 800, stream_id=new_stream), instrument, scenario.session)
    candles.observe(
        tick(quote, 130, 2, 104, 1000, stream_id=new_stream), instrument, scenario.session
    )
    rows = candles.drain()
    assert len(rows) == 3
    openings = {datetime.fromisoformat(row["opens_at"]) for row in rows}
    assert openings == {quote.timestamp, quote.timestamp + timedelta(minutes=2)}
    assert all(row["volume"] is None for row in rows)
    assert candles.recoveries[instrument.id][0] == new_stream
    bars = reconciled_bars(
        rows,
        [],
        quote.timestamp,
        quote.timestamp + timedelta(minutes=3),
        quote.timestamp + timedelta(minutes=3),
    )
    assert len(bars) == 2 and bars[0]["observed_segments"] == 2
    assert bars[0]["open"] == "100" and bars[0]["close"] == "102"
    assert bars[0]["volume"] is None and bars[0]["state"] == "elapsed"


def test_backfill_replaces_overlap_without_summing_and_newer_empty_is_honest(scenario):
    instrument, quote = inputs(scenario)
    candles = LiveCandles()
    candles.observe(quote, instrument, scenario.session)
    rows = candles.drain()
    start, end = quote.timestamp, quote.timestamp + timedelta(minutes=2)
    older = SimpleNamespace(
        id=uuid4(),
        request={"start": start.isoformat(), "end": end.isoformat()},
        payload={
            "status": "available",
            "received_at": end.isoformat(),
            "source": "provider",
            "bars": [
                {
                    "opens_at": start.isoformat(),
                    "open": "98",
                    "high": "105",
                    "low": "96",
                    "close": "104",
                    "volume": 1000,
                    "oi": None,
                    "state": "closed",
                }
            ],
        },
    )
    result = reconciled_bars(rows, [older], start, end, end)
    assert len(result) == 1 and result[0]["volume"] == 1000
    assert result[0]["source"] == "provider" and result[0]["observed_segments"] == 1
    newer = SimpleNamespace(
        id=uuid4(), request=older.request, payload={"status": "empty", "bars": []}
    )
    assert reconciled_bars([], [newer, older], start, end, end) == []
    result = reconciled_bars(rows, [newer, older], start, end, end)
    assert result[0]["source"] == "observed_ltp_snapshots"  # No invented provider bar.


@pytest.mark.integration
def test_restart_persistence_cached_read_gaps_ownership_and_execution_isolation(
    paper, db_engine, scenario, monkeypatch, tmp_path
):
    _, account = paper
    instrument, quote = inputs(scenario)
    store, aggregator = CandleStore(db_engine, account), LiveCandles()
    aggregator.observe(quote, instrument, scenario.session)
    old_rows = aggregator.drain()
    store.save(old_rows)
    newer = tick(quote, 2, 2, 105, 505)
    aggregator.observe(newer, instrument, scenario.session)
    rows = aggregator.drain()
    store.save(rows)
    store.save(rows)  # Retry is idempotent.
    store.save(old_rows)  # A late persistence completion cannot regress the bar.
    other_stream = uuid4()
    # A new worker has no in-memory cursor; use the persisted previous-stream watermark.
    assert (
        store.recovery_start(
            instrument.id, other_stream, scenario.session, quote.timestamp + timedelta(minutes=3)
        )
        == quote.timestamp
    )
    calendar = tmp_path / "calendar.json"
    calendar.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sessions": [
                    {
                        "exchange": "NFO",
                        "session": scenario.session.model_dump(mode="json"),
                        "official_source_url": "https://www.nseindia.com/fixture",
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(api, "MarketSettings", lambda: SimpleNamespace(calendar_file=calendar))
    app.dependency_overrides[account_identity] = lambda: account
    try:
        with TestClient(app) as client:
            production = app.state.engine
            app.state.engine = db_engine
            try:
                params = {
                    "instrument_id": instrument.id,
                    "start": quote.timestamp.isoformat(),
                    "end": (quote.timestamp + timedelta(minutes=2)).isoformat(),
                }
                response = client.get("/api/market/candles", params=params)
                assert response.status_code == 200, response.text
                body = response.json()
                assert len(body["bars"]) == 1 and len(body["gaps"]) == 2
                assert body["sessions"] == [scenario.session.model_dump(mode="json")]
                assert body["bars"][0]["high"] == "105" and body["provider_called"] is False
                with Session(db_engine) as db, db.begin():
                    db.add(
                        MarketHistoryBatch(
                            account_id=account,
                            instrument_id=instrument.id,
                            requested_at=datetime.now(UTC),
                            request={**params, "interval": "ONE_MINUTE"},
                            payload={
                                "status": "available",
                                "source": "isolated-provider-fixture",
                                "received_at": params["end"],
                                "bars": [
                                    {
                                        "opens_at": params["start"],
                                        "open": "100",
                                        "high": "108",
                                        "low": "99",
                                        "close": "107",
                                        "volume": 1234,
                                        "oi": None,
                                        "state": "closed",
                                    }
                                ],
                            },
                        )
                    )
                merged = client.get("/api/market/candles", params=params).json()
                assert len(merged["bars"]) == 1 and merged["bars"][0]["volume"] == 1234
                assert merged["bars"][0]["high"] == "108"
                another = paper[0].create_account(scenario.config, scenario.now)
                app.dependency_overrides[account_identity] = lambda: another
                other = client.get("/api/market/candles", params=params).json()
                assert other["bars"] == []
                app.dependency_overrides[account_identity] = lambda: uuid4()
                assert client.get("/api/market/candles", params=params).status_code == 409
                with Session(db_engine) as db:
                    assert db.scalar(select(func.count()).select_from(LiveCandleSegment)) == 1
                    assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
                    assert db.scalar(select(func.count()).select_from(SnapshotRecord)) == 0
                    assert db.get(Account, account).cash == scenario.config.capital
            finally:
                app.state.engine = production
    finally:
        app.dependency_overrides.pop(account_identity, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_worker_backfill_is_queued_and_chart_failures_do_not_escape(
    paper, db_engine, scenario, monkeypatch
):
    _, account = paper
    instrument, quote = inputs(scenario)
    runtime = TradingRuntime(db_engine, account, MarketSettings(_env_file=None), observe_only=True)
    try:
        runtime.candles.observe(quote, instrument, scenario.session)
        calls = []

        def refresh(query, engine, owner):
            calls.append(query)
            assert query.start == scenario.session.opens_at
            assert owner == account and engine is db_engine

        monkeypatch.setattr("services.worker.runtime.refresh_history", refresh)
        await runtime.recover_candles()
        assert len(calls) == 1 and not runtime.candles.recoveries

        # A same-connection gap queued while history is in flight must survive.
        job = (quote.stream_id, scenario.session, scenario.session.opens_at)
        runtime.candles.recoveries[instrument.id] = job

        def concurrent_gap(query, engine, owner):
            runtime.candles.recoveries[instrument.id] = job

        monkeypatch.setattr("services.worker.runtime.refresh_history", concurrent_gap)
        await runtime.recover_candles()
        assert runtime.candles.recoveries[instrument.id] == job

        # A chart observer fault must not escape into stream delivery.
        runtime.instruments[instrument.id] = instrument

        def broken_observer(*args):
            raise RuntimeError("isolated chart observer failure")

        monkeypatch.setattr(runtime.candles, "observe", broken_observer)
        runtime.observe_candle(quote)

        def broken(rows):
            raise RuntimeError("isolated fixture database failure")

        monkeypatch.setattr(runtime.candle_store, "save", broken)
        await runtime.publish_candles()
        assert runtime.candles.dirty  # Retained for retry; no exception to the exit loop.
    finally:
        await runtime.client.close()
