"""Isolated quote-refresh fixtures; no provider requests or production seed data."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api import market as api
from services.api.app import app
from services.api.auth import account_identity
from services.core.contracts import IST
from services.core.models import Account, AuditEvent, PaperOrder, SnapshotRecord
from services.market.catalog import InstrumentCatalog
from services.market.selection import display_contracts
from services.market.settings import AuthenticationRequired, ProviderError
from services.worker.models import LatestMarketQuote


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [None, "unknown", "duplicate", "malformed", "future"])
async def test_quote_fetch_checks_provider_identity_and_preserves_old_times(
    scenario, monkeypatch, invalid
):
    now = datetime.now(UTC)
    stamp = now - timedelta(hours=3)
    instrument = scenario.instrument.model_copy(
        update={
            "exchange": "NFO",
            "verified_at": now,
            "expiry": now.astimezone(IST).date() + timedelta(days=1),
        }
    )

    async def catalog():
        return InstrumentCatalog([instrument], now, 0)

    requests = []
    closed = []

    class Client:
        def __init__(self, settings):
            pass

        async def quotes(self, tokens):
            requests.append(tokens)
            if "NSE" in tokens:
                return [
                    {
                        "exchange": "NSE",
                        "symbolToken": "index-fixture",
                        "ltp": "25000",
                        "exchFeedTime": stamp.isoformat(),
                    }
                ]
            row = {
                "exchange": "NFO",
                "symbolToken": instrument.provider_token,
                "ltp": "100",
                "exchFeedTime": stamp.isoformat(),
            }
            if invalid == "unknown":
                row["symbolToken"] = "unrequested-fixture"
            if invalid == "future":
                row["exchFeedTime"] = (now + timedelta(minutes=5)).isoformat()
            return (
                [row, row]
                if invalid == "duplicate"
                else [None]
                if invalid == "malformed"
                else [row]
            )

        async def close(self):
            closed.append(True)

    monkeypatch.setattr(api.InstrumentCatalog, "fetch", catalog)
    monkeypatch.setattr(api, "AngelOneClient", Client)
    monkeypatch.setattr(
        api, "MarketSettings", lambda: SimpleNamespace(nifty_index_token="index-fixture")
    )
    if invalid:
        with pytest.raises(ProviderError):
            await api.fetch_quotes("NIFTY")
    else:
        instruments, quotes, reference_at = await api.fetch_quotes("NIFTY")
        assert instruments == [instrument] and quotes[0].timestamp == stamp
        assert reference_at == stamp and quotes[0].last_price == 100
    assert closed == [True]
    assert requests == [{"NSE": ["index-fixture"]}, {"NFO": [instrument.provider_token]}]


def test_display_selection_uses_listed_nearest_expiry_and_bounds_strikes(scenario):
    now = scenario.now
    instruments = [
        scenario.instrument.model_copy(
            update={
                "id": f"fixture-{days}-{strike}",
                "exchange": "NFO",
                "strike": Decimal(strike),
                "expiry": now.date() + timedelta(days=days),
            }
        )
        for days in (-1, 1, 4, 9)
        for strike in range(24900, 25300, 50)
    ]
    catalog = InstrumentCatalog(instruments, now, 0)
    selected = display_contracts(catalog, "NIFTY", Decimal(25005), now)
    assert len(selected) == 5
    assert {item.expiry for item in selected} == {now.date() + timedelta(days=1)}
    assert {item.strike for item in selected} == {Decimal(v) for v in range(24900, 25150, 50)}
    with pytest.raises(ProviderError, match="NO_ELIGIBLE"):
        display_contracts(catalog, "SENSEX", Decimal(80000), now)
    with pytest.raises(ProviderError, match="REFERENCE_UNAVAILABLE"):
        display_contracts(catalog, "NIFTY", Decimal("NaN"), now)
    with pytest.raises(ProviderError, match="REQUIRES_REFRESH"):
        display_contracts(catalog, "NIFTY", Decimal(25000), now + timedelta(days=1))


@pytest.mark.integration
def test_explicit_after_hours_refresh_is_bounded_and_never_executes(
    paper, db_engine, scenario, monkeypatch
):
    _, identifier = paper
    now = datetime.now(UTC)
    instrument = scenario.instrument.model_copy(
        update={
            "id": "refresh-fixture",
            "exchange": "NFO",
            "verified_at": now,
            "expiry": now.astimezone(IST).date() + timedelta(days=1),
        }
    )
    # Deliberately old exchange time: a new fetch must not make it fresh.
    stamp = now - timedelta(hours=3)
    quote = scenario.quote.model_copy(
        update={
            "instrument_id": instrument.id,
            "timestamp": stamp,
            "received_at": now,
            "source": "angelone-rest:full",
        }
    )
    calls = []

    async def fetched(underlying):
        calls.append(underlying)
        return [instrument], [quote], stamp

    monkeypatch.setattr(api, "fetch_quotes", fetched)
    app.dependency_overrides[account_identity] = lambda: identifier
    try:
        with TestClient(app) as client:
            production = app.state.engine
            app.state.engine = db_engine
            try:
                endpoint = "/api/market/quotes/refresh"
                assert client.post(endpoint, json={"underlying": "OTHER"}).status_code == 422
                assert not calls
                response = client.post(endpoint, json={"underlying": "NIFTY"})
                assert response.status_code == 200
                assert response.json()["quotes"] == 1
                assert response.json()["price_status"].startswith("last_available")
                assert calls == ["NIFTY"]
                assert client.post(endpoint, json={"underlying": "SENSEX"}).status_code == 429
                with Session(db_engine) as db, db.begin():
                    stored = db.get(LatestMarketQuote, instrument.id)
                    assert stored.timestamp == stamp
                    assert stored.payload["received_at"] != stored.payload["timestamp"]
                    event = db.scalar(
                        select(AuditEvent).where(AuditEvent.kind == "MARKET_QUOTES_REFRESHED")
                    )
                    event.timestamp = now - timedelta(minutes=1)

                # An older retry cannot overwrite a newer stored observation.
                quote = quote.model_copy(update={"timestamp": stamp - timedelta(minutes=1)})
                assert client.post(endpoint, json={"underlying": "NIFTY"}).status_code == 200
                with Session(db_engine) as db:
                    assert db.get(LatestMarketQuote, instrument.id).timestamp == stamp
                    assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
                    assert db.scalar(select(func.count()).select_from(SnapshotRecord)) == 0
                    assert db.get(Account, identifier).cash == scenario.config.capital
                app.dependency_overrides[account_identity] = lambda: uuid4()
                assert client.post(endpoint, json={"underlying": "NIFTY"}).status_code == 409
                assert calls == ["NIFTY", "NIFTY"]
            finally:
                app.state.engine = production
    finally:
        app.dependency_overrides.pop(account_identity, None)


@pytest.mark.integration
@pytest.mark.parametrize(
    "error, expected",
    [
        (ProviderError("BROKER_AUTH_REJECTED"), "MARKET_PRICES_UNAVAILABLE"),
        (AuthenticationRequired("DAILY_BROKER_LOGIN_REQUIRED"), "BROKER_LOGIN_REQUIRED"),
    ],
)
def test_provider_failure_is_recorded_and_throttled(paper, db_engine, monkeypatch, error, expected):
    _, identifier = paper

    async def unavailable(underlying):
        raise error

    monkeypatch.setattr(api, "fetch_quotes", unavailable)
    app.dependency_overrides[account_identity] = lambda: identifier
    try:
        with TestClient(app) as client:
            production = app.state.engine
            app.state.engine = db_engine
            try:
                endpoint = "/api/market/quotes/refresh"
                response = client.post(endpoint, json={"underlying": "NIFTY"})
                assert response.status_code == 409 and response.json()["detail"] == expected
                assert client.post(endpoint, json={"underlying": "NIFTY"}).status_code == 429
                with Session(db_engine) as db:
                    event = db.scalar(
                        select(AuditEvent).where(AuditEvent.kind == "MARKET_QUOTES_REFRESHED")
                    )
                    assert event.details["status"] == "unavailable"
                    assert db.scalar(select(func.count()).select_from(LatestMarketQuote)) == 0
            finally:
                app.state.engine = production
    finally:
        app.dependency_overrides.pop(account_identity, None)
