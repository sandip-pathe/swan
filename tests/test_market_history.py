"""Provider decoding and history isolation; all provider data is isolated fixture input."""

import struct
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api import history as api
from services.api.app import app
from services.api.auth import account_identity
from services.core.contracts import IST
from services.core.models import (
    Account,
    InstrumentRecord,
    MarketHistoryBatch,
    PaperOrder,
    SnapshotRecord,
)
from services.market.analysis import normalize_rest_quote
from services.market.angelone import CANDLES, AngelOneClient
from services.market.evidence import identify_quote
from services.market.history import HistoryQuery, normalize_bars
from services.market.settings import MarketSettings, ProviderError
from services.market.stream import decode_quote


def test_rest_retains_display_prices_without_replenishing_liquidity(scenario):
    instrument = scenario.instrument.model_copy(update={"exchange": "NFO"})
    row = {
        "symbolToken": instrument.provider_token,
        "exchange": "NFO",
        "exchFeedTime": scenario.now.isoformat(),
        "ltp": "101.25",
        "open": "99.1",
        "high": "105",
        "low": "98",
        "close": "100",
        "avgPrice": "102",
        "lastTradeQty": 25,
        "exchTradeTime": scenario.now.isoformat(),
        "depth": {
            "buy": [{"price": "101", "quantity": 50, "orders": 2}],
            "sell": [{"price": "101.5", "quantity": 75, "orders": 3}],
        },
    }
    quote = normalize_rest_quote(row, instrument, scenario.now)
    assert quote.last_price == Decimal("101.25")
    assert quote.previous_close == 100 and quote.session_open == Decimal("99.1")
    assert quote.last_trade_at == scenario.now and quote.last_trade_quantity == 25
    assert quote.bid == 101 and quote.ask == Decimal("101.5")
    changed = normalize_rest_quote({**row, "ltp": "103", "high": "106"}, instrument, scenario.now)
    assert changed.market_event_id == quote.market_event_id
    missing = normalize_rest_quote(
        {**row, "ltp": 0, "avgPrice": "NaN", "exchTradeTime": "bad"}, instrument, scenario.now
    )
    assert missing.last_price is None and missing.average_price is None
    assert missing.last_trade_at is None and missing.bid == quote.bid


def test_snapquote_retains_price_offsets_and_depth(scenario):
    instrument = scenario.instrument.model_copy(update={"exchange": "NFO", "provider_token": "42"})
    packet = bytearray(379)
    packet[0], packet[1] = 3, 2
    packet[2:4] = b"42"
    struct.pack_into("<q", packet, 27, 10)
    struct.pack_into("<q", packet, 35, int(scenario.now.timestamp() * 1000))
    for offset, value in {
        43: 10125,
        51: 25,
        59: 10200,
        67: 500,
        91: 9900,
        99: 10500,
        107: 9800,
        115: 10000,
        131: 1000,
    }.items():
        struct.pack_into("<q", packet, offset, value)
    struct.pack_into("<HqqH", packet, 147, 1, 50, 10100, 2)
    struct.pack_into("<HqqH", packet, 247, 0, 75, 10150, 3)
    quote = decode_quote(bytes(packet), {(2, "42"): instrument}, scenario.now)
    assert quote.last_price == Decimal("101.25")
    assert quote.session_low == 98 and quote.previous_close == 100
    assert quote.volume == 500 and quote.oi == 1000 and quote.bid == 101
    assert (
        identify_quote(quote.model_copy(update={"last_price": Decimal("110")})).market_event_id
        == quote.market_event_id
    )


def query(now):
    return HistoryQuery(
        instrument_id="fixture", interval="ONE_MINUTE", start=now - timedelta(minutes=3), end=now
    )


def test_history_contract_deduplicates_sorts_keeps_gaps_and_provisional_state():
    now = datetime(2026, 11, 18, 10, 0, tzinfo=IST)
    request = query(now)
    first = [(now - timedelta(minutes=3)).isoformat(), 100, 103, 99, 102, 25]
    last = [now.isoformat(), 102, 104, 101, 103, 0]
    bars = normalize_bars([last, first, first], request, now + timedelta(seconds=10))
    assert len(bars) == 2 and bars[0]["state"] == "closed"
    assert bars[1]["state"] == "provisional" and bars[1]["volume"] == 0
    assert bars[0]["oi"] is None
    with pytest.raises(ProviderError, match="CONFLICTING_DUPLICATE"):
        normalize_bars([first, [*first[:5], 30]], request, now)
    for bad in (
        [first[0], 100, 99, 98, 102, 1],
        [first[0], 100, 103, 99, 102, -1],
        [first[0], True, 103, 99, 102, 1],
        [first[0].replace("+05:30", ""), 100, 103, 99, 102, 1],
    ):
        with pytest.raises(ProviderError, match="INVALID_BAR"):
            normalize_bars([bad], request, now)
    assert normalize_bars([], request, now) == []


def test_history_rejects_unbounded_future_expired_and_wrong_instrument(scenario):
    now = scenario.now.replace(second=0, microsecond=0)
    request = query(now)
    with pytest.raises(ValueError):
        HistoryQuery.model_validate({**request.model_dump(), "start": now - timedelta(days=5)})
    instrument = scenario.instrument.model_copy(update={"id": "fixture", "exchange": "NFO"})
    assert request.provider_body(instrument, now)["fromdate"].endswith("09:27")
    with pytest.raises(ProviderError, match="FUTURE"):
        request.provider_body(instrument, now - timedelta(minutes=1))
    with pytest.raises(ProviderError, match="AFTER_EXPIRY"):
        request.provider_body(
            instrument.model_copy(update={"expiry": now.date() - timedelta(days=1)}), now
        )


@pytest.mark.asyncio
async def test_candle_client_uses_allowlisted_read_only_route_and_normalizes(scenario, monkeypatch):
    now = scenario.now.replace(second=0, microsecond=0)
    body = query(now)
    instrument = scenario.instrument.model_copy(update={"id": "fixture", "exchange": "NFO"})
    settings = MarketSettings(_env_file=None)
    client = AngelOneClient(settings)
    await client.http.aclose()
    requests = []

    def response(request):
        requests.append(request)
        return httpx.Response(
            200, json={"status": True, "data": [[body.start.isoformat(), 100, 103, 99, 102, 25]]}
        )

    client.http = httpx.AsyncClient(
        base_url="https://apiconnect.angelone.in", transport=httpx.MockTransport(response)
    )

    async def session():
        return None

    monkeypatch.setattr(client, "session", session)
    monkeypatch.setattr(client, "_headers", lambda saved: {})
    try:
        result = await client.candles(body, instrument, now)
        assert len(result["bars"]) == 1 and result["raw_rows"][0][-1] == 25
        assert requests[0].url.path == CANDLES and len(requests) == 1
        with pytest.raises(ProviderError, match="ENDPOINT_NOT_ALLOWED"):
            await client._post("/order/placeOrder", {})
        assert len(requests) == 1
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        "Access denied because of exceeding access rate",
        "Too many requests",
        {"status": False, "errorcode": "AB1021", "message": "private"},
    ],
)
async def test_history_403_throttling_does_not_report_invalid_login(monkeypatch, payload):
    client = AngelOneClient(MarketSettings(_env_file=None))
    await client.http.aclose()
    calls = []

    def response(request):
        calls.append(request)
        if isinstance(payload, dict):
            return httpx.Response(403, json=payload)
        return httpx.Response(403, text=payload)

    client.http = httpx.AsyncClient(
        base_url="https://apiconnect.angelone.in", transport=httpx.MockTransport(response)
    )
    monkeypatch.setattr(client, "_headers", lambda saved: {})
    try:
        with pytest.raises(ProviderError, match="^PROVIDER_RATE_LIMITED$"):
            await client._post(CANDLES, {})
        assert len(calls) == 1
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_history_403_without_throttle_evidence_still_requires_auth(monkeypatch):
    from services.market.settings import AuthenticationRequired

    client = AngelOneClient(MarketSettings(_env_file=None))
    await client.http.aclose()
    client.http = httpx.AsyncClient(
        base_url="https://apiconnect.angelone.in",
        transport=httpx.MockTransport(lambda request: httpx.Response(403, text="private")),
    )
    monkeypatch.setattr(client, "_headers", lambda saved: {})
    try:
        with pytest.raises(AuthenticationRequired, match="^BROKER_AUTH_REJECTED$"):
            await client._post(CANDLES, {})
    finally:
        await client.close()


@pytest.mark.integration
def test_history_api_explicit_refresh_cached_read_ownership_throttle_and_no_execution(
    paper,
    db_engine,
    scenario,
    monkeypatch,
):
    _, account_id = paper
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    instrument = scenario.instrument.model_copy(
        update={
            "id": "fixture",
            "exchange": "NFO",
            "verified_at": now,
            "expiry": now.astimezone(IST).date() + timedelta(days=1),
        }
    )
    with Session(db_engine) as db, db.begin():
        db.add(InstrumentRecord(id=instrument.id, payload=instrument.model_dump(mode="json")))
    calls = []

    async def fixture_fetch(body, item, stamp):
        calls.append(body)
        return {
            "bars": [],
            "raw_rows": [],
            "received_at": stamp.isoformat(),
            "provider_request": body.provider_body(item, stamp),
        }

    monkeypatch.setattr(api, "fetch", fixture_fetch)
    app.dependency_overrides[account_identity] = lambda: account_id
    try:
        with TestClient(app) as client:
            production = app.state.engine
            app.state.engine = db_engine
            try:
                url = "/api/market/history?instrument_id=fixture&interval=ONE_MINUTE"
                assert client.get(url).json()["batch"] is None and not calls
                response = client.post(
                    "/api/market/history/refresh", json=query(now).model_dump(mode="json")
                )
                assert response.status_code == 200 and response.json()["batch"]["status"] == "empty"
                assert len(calls) == 1
                assert client.get(url).json()["batch"]["status"] == "empty" and len(calls) == 1
                assert client.get(url.replace("ONE_MINUTE", "FIVE_MINUTE")).json()["batch"] is None
                assert (
                    client.post(
                        "/api/market/history/refresh", json=query(now).model_dump(mode="json")
                    ).status_code
                    == 429
                )
                # A failed read remains auditable and consumes the same refresh budget.
                with Session(db_engine) as db, db.begin():
                    batch = db.scalar(select(MarketHistoryBatch))
                    batch.requested_at = now - timedelta(minutes=1)

                async def rejected_fetch(body, item, stamp):
                    raise ProviderError("BROKER_AUTH_REJECTED")

                monkeypatch.setattr(api, "fetch", rejected_fetch)
                failure = client.post(
                    "/api/market/history/refresh", json=query(now).model_dump(mode="json")
                )
                assert failure.status_code == 409
                assert client.get(url).json()["batch"]["problem"] == "BROKER_AUTH_REJECTED"
                assert (
                    client.post(
                        "/api/market/history/refresh", json=query(now).model_dump(mode="json")
                    ).status_code
                    == 429
                )
                app.dependency_overrides[account_identity] = lambda: uuid4()
                assert client.get(url).status_code == 409
                with Session(db_engine) as db:
                    assert db.scalar(select(func.count()).select_from(MarketHistoryBatch)) == 2
                    assert db.scalar(select(func.count()).select_from(SnapshotRecord)) == 0
                    assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
                    assert db.get(Account, account_id).cash == scenario.config.capital
            finally:
                app.state.engine = production
    finally:
        app.dependency_overrides.pop(account_identity, None)
