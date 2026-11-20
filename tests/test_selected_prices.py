"""Exact display quotes and subscription bounds; provider calls are isolated fixtures."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_instrument_search import client_for, instruments, save

from services.api import market as api
from services.core.models import AuditEvent, DisplaySelection
from services.market.catalog import InstrumentCatalog
from services.market.settings import AuthenticationRequired, ProviderError
from services.market.subscriptions import add_display_contracts
from services.worker.store import RuntimeStore


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [None, "venue", "duplicate", "future"])
async def test_exact_fetch_preserves_exchange_time_and_rejects_identity(
    scenario, monkeypatch, invalid
):
    item = instruments(scenario)[0]
    stamp = datetime.now(UTC) - timedelta(days=1)
    calls = []
    closed = []

    class Client:
        def __init__(self, settings):
            pass

        async def quotes(self, tokens):
            calls.append(tokens)
            row = {
                "exchange": "BFO" if invalid == "venue" else item.exchange,
                "symbolToken": item.provider_token,
                "ltp": "100",
                "exchFeedTime": (
                    datetime.now(UTC) + timedelta(hours=1) if invalid == "future" else stamp
                ).isoformat(),
            }
            return [row, row] if invalid == "duplicate" else [row]

        async def close(self):
            closed.append(True)

    monkeypatch.setattr(api, "AngelOneClient", Client)
    if invalid:
        with pytest.raises(ProviderError):
            await api.fetch_selected_quotes([item])
    else:
        result = await api.fetch_selected_quotes([item])
        assert result[0].timestamp == stamp
    assert calls == [{item.exchange: [item.provider_token]}] and closed == [True]


@pytest.mark.integration
def test_selected_refresh_missing_stale_shared_throttle_and_bounds(
    paper, db_engine, scenario, monkeypatch
):
    _, owner = paper
    items = instruments(scenario, 2)
    save(db_engine, items)
    calls = []

    async def quotes(requested):
        calls.append(requested)
        return []

    monkeypatch.setattr(api, "fetch_selected_quotes", quotes)
    with client_for(db_engine, owner) as client:
        path = "/api/market/quotes/selected/refresh"
        for ids in [[], [items[0].id] * 2, [str(i) for i in range(51)]]:
            assert client.post(path, json={"instrument_ids": ids}).status_code == 422
        assert client.post(path, json={"instrument_ids": ["unknown"]}).status_code == 404
        result = client.post(path, json={"instrument_ids": [i.id for i in items]})
        assert result.status_code == 200
        assert result.json()["missing_instrument_ids"] == sorted(i.id for i in items)
        assert result.json()["fresh_quotes"] == 0 and result.json()["newest_exchange_at"] is None
        assert (
            client.post("/api/market/quotes/refresh", json={"underlying": "NIFTY"}).status_code
            == 429
        )
        assert calls == [items]


@pytest.mark.integration
def test_selected_login_failure_and_expiring_owner_interest(
    paper, db_engine, scenario, monkeypatch
):
    _, owner = paper
    items = instruments(scenario, 2)
    save(db_engine, items)

    async def unavailable(requested):
        raise AuthenticationRequired("DAILY_BROKER_LOGIN_REQUIRED")

    monkeypatch.setattr(api, "fetch_selected_quotes", unavailable)
    with client_for(db_engine, owner) as client:
        response = client.post(
            "/api/market/quotes/selected/refresh", json={"instrument_ids": [items[0].id]}
        )
        assert response.status_code == 409 and response.json()["detail"] == "BROKER_LOGIN_REQUIRED"
        for item in items:
            assert (
                client.post(
                    "/api/market/subscriptions/selected", json={"instrument_id": item.id}
                ).status_code
                == 200
            )
    now = datetime.now(UTC)
    store = RuntimeStore(db_engine, owner)
    assert [i.id for i in store.display_instruments(now)] == [items[1].id]
    assert store.display_instruments(now + timedelta(seconds=91)) == []
    assert RuntimeStore(db_engine, uuid4()).display_instruments(now) == []
    with Session(db_engine) as db:
        assert len(list(db.scalars(select(DisplaySelection)))) == 1
        assert (
            db.scalar(
                select(AuditEvent).where(AuditEvent.kind == "MARKET_QUOTES_REFRESHED")
            ).details["problem"]
            == "BROKER_LOGIN_REQUIRED"
        )


def test_display_budget_never_displaces_protected_and_ignores_changed_expired(scenario):
    now = datetime.now(UTC)
    items = instruments(scenario, 5)
    expired = items[3].model_copy(update={"expiry": now.date() - timedelta(days=1)})
    changed = items[4].model_copy(update={"lot_size": items[4].lot_size + 1})
    catalog = InstrumentCatalog([*items[:3], expired, changed], now, 0)
    result = add_display_contracts([items[0]], [items[1], items[2]], catalog, now, 2)
    assert [i.id for i in result] == [items[0].id, items[1].id]
    assert add_display_contracts([items[0]], items[3:], catalog, now, 5) == [items[0]]
    catalog.fetched_at = now - timedelta(days=1)
    assert add_display_contracts([items[0]], items[1:], catalog, now, 5) == [items[0]]
    with pytest.raises(ValueError):
        add_display_contracts(items[:2], [], catalog, now, 1)


@pytest.mark.asyncio
async def test_runtime_merges_display_without_losing_open_exposure(scenario):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from services.worker.runtime import TradingRuntime

    now = datetime.now(UTC)
    items = instruments(scenario, 4)
    runtime = object.__new__(TradingRuntime)
    runtime.catalog = InstrumentCatalog(items, now, 0)
    runtime.base_instruments = [items[0]]
    runtime.settings = SimpleNamespace(max_subscriptions=3)
    runtime.store = SimpleNamespace(
        display_instruments=lambda now: items[2:], open_instruments=lambda: [items[1]]
    )
    runtime.replace_subscriptions = AsyncMock()
    await runtime.apply_display_subscriptions(now)
    assert runtime.replace_subscriptions.await_args.args[0] == items[:3]
    # Once interest expires, the display slot is removed; exposure stays protected.
    runtime.store.display_instruments = lambda now: []
    await runtime.apply_display_subscriptions(now)
    assert runtime.replace_subscriptions.await_args.args[0] == items[:2]
