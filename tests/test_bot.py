"""Isolated bot contracts; no database server, broker, model or trading calls."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from services.bot.analysis import analyze, insight_for
from services.bot.app import app
from services.bot.chat import answer, reserve
from services.bot.store import Store
from services.strategies.contracts import IndexBar


def bars():
    start = datetime(2026, 11, 25, 3, 45, tzinfo=UTC)
    return [IndexBar(evidence_id=f"source-{i}", underlying="NIFTY", exchange="NSE",
                     source="isolated-test", opens_at=start + timedelta(minutes=i),
                     closes_at=start + timedelta(minutes=i + 1),
                     available_at=start + timedelta(minutes=30), final=True,
                     open=Decimal(100 + i), close=Decimal(101 + i),
                     high=Decimal(102 + i), low=Decimal(99 + i)) for i in range(25)]


def test_analysis_rejects_gap_future_and_duplicates():
    rows = bars()
    now = rows[0].available_at
    # Receipt must not be in the future; use the latest valid completed minute.
    rows = [row.model_copy(update={"available_at": rows[-1].closes_at}) for row in rows]
    now = rows[-1].closes_at
    result = analyze(rows, now, rows[0].opens_at)
    assert result["trend"] == "above_average"
    assert result["range_state"] == "above_opening_range"
    assert Decimal(result["sma20"]) == sum(row.close for row in rows[-20:]) / 20
    assert analyze(rows[1:], now, rows[0].opens_at)["status"] == "insufficient"
    assert analyze(rows[:10] + rows[11:], now, rows[0].opens_at)["status"] == "insufficient"
    assert analyze(rows, now + timedelta(minutes=4), rows[0].opens_at)["status"] == "historical"
    with pytest.raises(ValueError, match="DUPLICATE"):
        analyze(rows + [rows[-1]], now, rows[0].opens_at)
    with pytest.raises(ValueError, match="INVALID"):
        analyze(rows, now - timedelta(minutes=1), rows[0].opens_at)


def test_restart_publication_and_atomic_budget(tmp_path):
    store = Store(str(tmp_path / "bot.sqlite3"))
    analysis = {"status": "current", "trend": "above_average", "range_state": "inside_range",
                "rule": "rule-v1", "as_of": "2026-11-25T04:10:00+00:00"}
    insight = insight_for(analysis, None, "2026-11-25")
    assert store.publish(insight)
    reopened = Store(store.path)
    assert not reopened.publish(insight)
    assert len(reopened.insights()) == 1
    assert insight_for(analysis, {**analysis, "session": "2026-11-25"}, "2026-11-25") is None
    assert reserve(store, "2026-11-25", 80, 100)
    assert not reserve(reopened, "2026-11-25", 30, 100)


def test_large_source_snapshot_is_loaded_only_on_demand(tmp_path):
    store = Store(str(tmp_path / "bot.sqlite3"))
    insight = {"id": "evidence-test", "as_of": "2026-11-25T04:10:00+00:00",
               "source_snapshot": {"bars": [{"close": "123"}]}}
    store.publish(insight)
    assert "source_snapshot" not in store.insights()[0]
    assert store.evidence("evidence-test")["bars"][0]["close"] == "123"


def test_cash_session_does_not_claim_derivatives_late_minutes_are_open():
    from services.bot.session import market_context
    from services.core.contracts import IST

    now = datetime(2026, 11, 25, 15, 35, tzinfo=IST)
    session = SimpleNamespace(opens_at=now.replace(hour=9, minute=15),
                              closes_at=now.replace(hour=15, minute=40), key=now.date())
    calendar = SimpleNamespace(describe=lambda *args: {"state": "open"},
                               get=lambda *args: session)
    result = market_context(calendar, now)
    assert result["state"] == "closed"
    assert datetime.fromisoformat(result["closes_at"]).minute == 30


def test_api_has_no_trading_routes_and_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_DB_PATH", str(tmp_path / "bot.sqlite3"))
    with TestClient(app) as client:
        assert client.get("/health").json()["service"] == "swan-bot"
        assert client.get("/api/bot/insights").status_code == 401
        assert client.post("/api/chat/messages", json={"question": "hello"}).status_code == 401
        assert client.post("/api/paper/orders/preview", json={}).status_code == 404
        assert client.post("/api/paper/arm", json={}).status_code == 404
    paths = {route.path for route in app.routes}
    assert paths == {"/health", "/api/bot/insights", "/api/chat/messages",
                     "/api/bot/insights/{insight_id}/evidence"}


def test_no_data_chat_explains_concepts_without_claiming_market(tmp_path):
    store = Store(str(tmp_path / "bot.sqlite3"))
    context = {"as_of": datetime.now(UTC).isoformat(), "quotes": [],
               "analysis": {"status": "insufficient"}}
    result = asyncio.run(answer("Explain the opening range", context, store, []))
    assert "fifteen" in result["answer"] and result["actions_taken"] == []
    result = asyncio.run(answer("hello", context, store, []))
    assert result["sources"] == [] and result["order_created"] is False


@pytest.mark.parametrize("numeric,citation,expected", [(False, "source-a", "available"),
    (True, "source-a", "validation_failed"), (False, "invented-source", "validation_failed")])
def test_model_validation_and_failure_fallback(tmp_path, monkeypatch, numeric, citation, expected):
    from services.bot import chat

    store = Store(str(tmp_path / "bot.sqlite3"))
    context = {"as_of": datetime.now(UTC).isoformat(), "quotes": [], "analysis": {
        "status": "current", "evidence": ["source-a"]}}
    policy = SimpleNamespace(ready=lambda: True, swan_ai_daily_token_budget=30000,
                             openai_model="isolated-model",
                             openai_api_key=SimpleNamespace(get_secret_value=lambda: "fixture"))
    monkeypatch.setattr(chat, "AgentSettings", lambda: policy)
    output = {"interpretation": "Price might reach 123" if numeric else
              "This condition describes recent prices and may reverse.",
              "limitation": "No prediction is established.", "evidence_ids": [citation]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "status": "completed", "output": [{"type": "message", "content": [{
            "type": "output_text", "text": json.dumps(output)}]}]}))
    client = httpx.AsyncClient
    monkeypatch.setattr(chat.httpx, "AsyncClient", lambda **kwargs: client(transport=transport))
    result = asyncio.run(answer("Explain latest observations", context, store, []))
    assert result["interpretation_status"] == expected
    assert "123" not in result["answer"]
    if expected != "available":
        assert "unavailable" in result["answer"]
