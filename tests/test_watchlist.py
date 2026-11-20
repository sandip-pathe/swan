"""Watchlist tests use disposable schemas, never real broker sessions or account data."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_instrument_search import client_for, instruments
from test_instrument_search import save as seed

from services.api import watchlist as api
from services.api.app import app
from services.api.auth import account_identity
from services.core.models import (
    Account,
    InstrumentRecord,
    ListedInstrument,
    PaperOrder,
    SnapshotRecord,
    WatchlistItem,
)
from services.worker.models import LatestMarketQuote


@pytest.mark.integration
def test_watchlist_is_owned_durable_and_idempotent_without_execution_effects(
    paper, db_engine, scenario
):
    engine, owner = paper
    item = instruments(scenario)[0]
    seed(db_engine, [item])
    another = engine.create_account(scenario.config, scenario.now)
    with client_for(db_engine, owner) as client:
        assert client.get("/api/watchlist").json()["rows"] == []
        body = {"instrument_id": item.id}
        for _ in range(2):
            assert client.post("/api/watchlist/save", json=body).status_code == 200
        saved = client.get("/api/watchlist").json()
        assert len(saved["rows"]) == 1 and not saved["provider_called"]
        assert saved["rows"][0]["quote"] is None
        assert saved["rows"][0]["status"] == "listed"
        app.dependency_overrides[account_identity] = lambda: another
        assert client.get("/api/watchlist").json()["rows"] == []
        assert client.post("/api/watchlist/remove", json=body).status_code == 200
        app.dependency_overrides[account_identity] = lambda: owner
        assert len(client.get("/api/watchlist").json()["rows"]) == 1
    # A fresh client reads the persisted list, without a browser storage dependency.
    with client_for(db_engine, owner) as client:
        assert (
            client.get("/api/watchlist").json()["rows"][0]["saved_at"]
            == saved["rows"][0]["saved_at"]
        )
        for _ in range(2):
            assert client.post("/api/watchlist/remove", json=body).status_code == 200
        assert client.get("/api/watchlist").json()["rows"] == []
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(WatchlistItem)) == 0
        assert db.get(InstrumentRecord, item.id) is not None
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
        assert db.scalar(select(func.count()).select_from(SnapshotRecord)) == 0
        assert db.scalar(select(func.count()).select_from(LatestMarketQuote)) == 0
        assert db.get(Account, owner).cash == scenario.config.capital
        assert db.get(Account, owner).enabled  # Fixture entry state was not changed.


@pytest.mark.integration
def test_expired_removed_and_changed_listings_preserve_saved_identity_and_quote_time(
    paper, db_engine, scenario
):
    _, owner = paper
    items = instruments(scenario, 3)
    seed(db_engine, items)
    with client_for(db_engine, owner) as client:
        for item in items:
            assert (
                client.post("/api/watchlist/save", json={"instrument_id": item.id}).status_code
                == 200
            )
        stamp = datetime.now(UTC) - timedelta(hours=1)
        with Session(db_engine) as db, db.begin():
            db.get(InstrumentRecord, items[0].id).payload = (
                items[0]
                .model_copy(update={"expiry": (datetime.now(UTC) - timedelta(days=2)).date()})
                .model_dump(mode="json")
            )
            db.get(ListedInstrument, items[1].id).catalog_at -= timedelta(days=1)
            db.get(ListedInstrument, items[2].id).payload = (
                items[2].model_copy(update={"strike": Decimal("999")}).model_dump(mode="json")
            )
            quote = scenario.quote.model_copy(
                update={"instrument_id": items[0].id, "timestamp": stamp}
            )
            db.add(
                LatestMarketQuote(
                    instrument_id=items[0].id,
                    timestamp=stamp,
                    payload=quote.model_dump(mode="json"),
                )
            )
        rows = {row["instrument"]["id"]: row for row in client.get("/api/watchlist").json()["rows"]}
        assert rows[items[0].id]["status"] == "expired"
        assert rows[items[0].id]["quote"]["timestamp"] == quote.model_dump(mode="json")["timestamp"]
        assert rows[items[1].id]["status"] == "not_listed"
        assert rows[items[2].id]["status"] == "not_listed"
        assert rows[items[2].id]["instrument"]["strike"] == str(items[2].strike)
        assert (
            client.post("/api/watchlist/save", json={"instrument_id": items[0].id}).status_code
            == 200
        )
        assert (
            client.post("/api/watchlist/remove", json={"instrument_id": items[0].id}).status_code
            == 200
        )


@pytest.mark.integration
def test_concurrent_saves_cannot_exceed_capacity_and_duplicate_retry_still_succeeds(
    paper, db_engine, scenario, monkeypatch
):
    _, owner = paper
    items = instruments(scenario, 3)
    seed(db_engine, items)
    monkeypatch.setattr(api, "LIMIT", 2)
    with client_for(db_engine, owner) as client:
        assert (
            client.post("/api/watchlist/save", json={"instrument_id": items[0].id}).status_code
            == 200
        )
        barrier = Barrier(2)

        def attempt(item):
            barrier.wait(timeout=5)
            return client.post("/api/watchlist/save", json={"instrument_id": item.id}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(attempt, items[1:]))
        assert sorted(statuses) == [200, 409]
        assert len(client.get("/api/watchlist").json()["rows"]) == 2
        assert (
            client.post("/api/watchlist/save", json={"instrument_id": items[0].id}).status_code
            == 200
        )


@pytest.mark.integration
def test_save_requires_current_identity_and_authorized_account(paper, db_engine, scenario):
    _, owner = paper
    item = instruments(scenario)[0]
    seed(db_engine, [item], item.verified_at - timedelta(days=1))
    with client_for(db_engine, owner) as client:
        body = {"instrument_id": item.id}
        assert (
            client.post("/api/watchlist/save", json=body).json()["detail"]
            == "CATALOG_REFRESH_REQUIRED"
        )
        with Session(db_engine) as db, db.begin():
            db.get(ListedInstrument, item.id).catalog_at = item.verified_at
            db.add(
                InstrumentRecord(
                    id=item.id,
                    payload=item.model_copy(update={"strike": Decimal("1")}).model_dump(
                        mode="json"
                    ),
                )
            )
        assert (
            client.post("/api/watchlist/save", json=body).json()["detail"]
            == "INSTRUMENT_IDENTITY_CHANGED"
        )
        assert client.get("/api/watchlist").json()["rows"] == []
        app.dependency_overrides[account_identity] = lambda: uuid4()
        assert client.get("/api/watchlist").status_code == 409
        assert client.post("/api/watchlist/save", json=body).status_code == 409
        assert client.post("/api/watchlist/remove", json=body).status_code == 409
