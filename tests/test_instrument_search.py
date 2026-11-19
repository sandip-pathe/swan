"""Discovery fixtures stay in disposable schemas and never call the provider."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from services.api import instruments as api
from services.api.app import app
from services.api.auth import account_identity
from services.core.contracts import IST
from services.core.models import Account, AuditEvent, InstrumentRecord, ListedInstrument, PaperOrder
from services.market.catalog import InstrumentCatalog
from services.market.settings import ProviderError


@contextmanager
def client_for(engine, account):
    app.dependency_overrides[account_identity] = lambda: account
    try:
        with TestClient(app) as client:
            production = app.state.engine
            app.state.engine = engine
            try:
                yield client
            finally:
                app.state.engine = production
    finally:
        app.dependency_overrides.pop(account_identity, None)


def instruments(scenario, count=1):
    now = datetime.now(UTC)
    today = now.astimezone(IST).date()
    return [
        scenario.instrument.model_copy(
            update={
                "id": f"NFO:isolated-{index}",
                "exchange": "NFO",
                "provider_token": f"isolated-{index}",
                "expiry": today + timedelta(days=4),
                "verified_at": now,
                "strike": Decimal(100 + index * 50),
                "option_type": "CALL" if index % 2 == 0 else "PUT",
            }
        )
        for index in range(count)
    ]


def save(engine, items, stamp=None):
    with Session(engine) as db, db.begin():
        for item in items:
            db.add(
                ListedInstrument(
                    id=item.id,
                    catalog_at=stamp or item.verified_at,
                    payload=item.model_dump(mode="json"),
                )
            )


@pytest.mark.integration
def test_search_filters_pagination_literal_terms_and_snapshot_scope(paper, db_engine, scenario):
    _, owner = paper
    items = instruments(scenario, 35)
    save(db_engine, items)
    expired = items[0].model_copy(
        update={"id": "expired", "expiry": datetime.now(IST).date() - timedelta(days=1)}
    )
    old = items[0].model_copy(update={"id": "removed"})
    save(db_engine, [expired])
    save(db_engine, [old], items[0].verified_at - timedelta(days=1))
    with client_for(db_engine, owner) as client:
        path = "/api/market/instruments"
        first = client.get(path).json()
        assert len(first["rows"]) == 30 and first["next_offset"] == 30
        assert first["rows"][0]["strike"] == "100" and not first["provider_called"]
        assert first["expiries"] == [items[0].expiry.isoformat()]
        assert len(client.get(path, params={"offset": 30}).json()["rows"]) == 5
        assert client.get(path, params={"q": "NIFTY 100 CE"}).json()["rows"][0]["id"] == items[0].id
        puts = client.get(
            path, params={"option_type": "PUT", "expiry": items[0].expiry.isoformat()}
        ).json()
        assert len(puts["rows"]) == 17 and all(row["option_type"] == "PUT" for row in puts["rows"])
        assert client.get(path, params={"q": "%"}).json()["rows"] == []
        assert client.get(path, params={"q": "_"}).json()["rows"] == []
        assert client.get(path, params={"underlying": "SENSEX"}).json()["rows"] == []
        assert client.get(path, params={"option_type": "OTHER"}).status_code == 422
        assert client.get(path, params={"offset": -1}).status_code == 422


@pytest.mark.integration
def test_catalog_refresh_is_deliberate_atomic_and_throttles_failures(
    paper, db_engine, scenario, monkeypatch
):
    _, owner = paper
    items, calls = instruments(scenario, 2), []

    async def fetch():
        calls.append(1)
        return InstrumentCatalog(items, items[0].verified_at, 0)

    monkeypatch.setattr(api.InstrumentCatalog, "fetch", fetch)
    with client_for(db_engine, owner) as client:
        assert client.get("/api/market/instruments").json()["catalog_at"] is None and not calls
        response = client.post("/api/market/instruments/refresh")
        assert response.status_code == 200 and response.json()["contracts"] == 2
        assert client.get("/api/market/instruments").json()["rows"] and len(calls) == 1
        assert client.post("/api/market/instruments/refresh").status_code == 429
        with Session(db_engine) as db, db.begin():
            event = db.scalar(select(AuditEvent).where(AuditEvent.kind == "CATALOG_REFRESHED"))
            event.timestamp -= timedelta(minutes=2)

        async def fail():
            raise ProviderError("isolated-provider-failure")

        monkeypatch.setattr(api.InstrumentCatalog, "fetch", fail)
        assert client.post("/api/market/instruments/refresh").status_code == 503
        assert client.post("/api/market/instruments/refresh").status_code == 429
        assert len(client.get("/api/market/instruments").json()["rows"]) == 2


@pytest.mark.integration
def test_selection_preserves_account_and_ledger_and_resolves_unquoted_contract(
    paper, db_engine, scenario
):
    _, owner = paper
    item = instruments(scenario)[0]
    save(db_engine, [item])
    with Session(db_engine) as db:
        enabled = db.get(Account, owner).enabled
    with client_for(db_engine, owner) as client:
        path = "/api/market/instruments/selected"
        assert client.get(path, params={"instrument_id": item.id}).status_code == 404
        for _ in range(2):
            result = client.post(path, json={"instrument_id": item.id})
            assert result.status_code == 200 and result.json()["quote"] is None
        assert (
            client.get(path, params={"instrument_id": item.id}).json()["instrument"]["id"]
            == item.id
        )
        with Session(db_engine) as db:
            assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
            assert db.scalar(select(func.count()).select_from(InstrumentRecord)) == 1
            assert db.get(Account, owner).cash == scenario.config.capital
            assert db.get(Account, owner).enabled == enabled
        app.dependency_overrides[account_identity] = lambda: uuid4()
        assert client.get("/api/market/instruments").status_code == 409
        assert client.post(path, json={"instrument_id": item.id}).status_code == 409


@pytest.mark.integration
def test_stale_expired_reused_identity_and_refresh_lock(paper, db_engine, scenario):
    _, owner = paper
    item = instruments(scenario)[0]
    save(db_engine, [item], item.verified_at - timedelta(days=1))
    path = "/api/market/instruments/selected"
    with client_for(db_engine, owner) as client:
        assert client.get("/api/market/instruments").json()["stale"]
        assert (
            client.post(path, json={"instrument_id": item.id}).json()["detail"]
            == "CATALOG_REFRESH_REQUIRED"
        )
        with Session(db_engine) as db, db.begin():
            listing = db.get(ListedInstrument, item.id)
            listing.catalog_at = item.verified_at
            listing.payload = item.model_copy(
                update={"expiry": datetime.now(IST).date() - timedelta(days=1)}
            ).model_dump(mode="json")
        assert (
            client.post(path, json={"instrument_id": item.id}).json()["detail"]
            == "INSTRUMENT_EXPIRED"
        )
        with Session(db_engine) as db, db.begin():
            db.get(ListedInstrument, item.id).payload = item.model_dump(mode="json")
            db.add(
                InstrumentRecord(
                    id=item.id,
                    payload=item.model_copy(update={"strike": Decimal("1")}).model_dump(
                        mode="json"
                    ),
                )
            )
        assert (
            client.post(path, json={"instrument_id": item.id}).json()["detail"]
            == "INSTRUMENT_IDENTITY_CHANGED"
        )
        with db_engine.connect() as lock, lock.begin():
            lock.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": api.CATALOG_LOCK})
            assert client.post("/api/market/instruments/refresh").status_code == 429
