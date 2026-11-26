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
from services.bot.chat import answer
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
        assert client.get("/api/chat/runs/00000000-0000-0000-0000-000000000001").status_code == 401
    paths = {route.path for route in app.routes}
    assert {"/health", "/api/bot/insights", "/api/chat/messages",
            "/api/bot/insights/{insight_id}/evidence"} <= paths


def test_no_data_chat_explains_concepts_without_claiming_market(tmp_path, monkeypatch):
    from services.bot import research

    store = Store(str(tmp_path / "bot.sqlite3"))
    context = {"as_of": datetime.now(UTC).isoformat(), "quotes": [],
               "analysis": {"status": "insufficient"}}

    async def complete(*_args, **_kwargs):
        return {"answer": "The opening range is the high and low during a chosen early-session period.",
                "evidence_ids": []}, "VALIDATED"

    monkeypatch.setattr(research, "synthesize", complete)
    result = asyncio.run(answer("Explain the opening range", context, store, []))
    assert "high and low" in result["answer"] and result["actions_taken"] == []
    result = asyncio.run(answer("hello", context, store, []))
    assert result["sources"] == [] and result["order_created"] is False


def test_chat_waits_briefly_for_shared_ai_lease(tmp_path, monkeypatch):
    from services.bot import research

    store = Store(str(tmp_path / "bot.sqlite3"))
    with store.connect() as db:
        db.execute(
            "INSERT INTO documents VALUES ('ai_lease:chat',?)",
            (json.dumps({"owner": "worker", "until": (datetime.now(UTC) + timedelta(seconds=2)).isoformat()}),),
        )
    calls = 0

    async def complete(_store, _packet, _insight_call_limit, _timeout):
        nonlocal calls
        calls += 1
        return {"sections": [], "direct_answer": "Hello!"}, "VALIDATED"

    monkeypatch.setattr(research, "_synthesize", complete)
    result = asyncio.run(research.synthesize(
        store, {"routing": True}, insight_call_limit=None, wait_for_lease=3
    ))
    assert result == ({"sections": [], "direct_answer": "Hello!"}, "VALIDATED")
    assert calls == 1


def test_chat_reports_and_logs_router_failure(tmp_path, monkeypatch, caplog):
    from services.bot import research
    from services.bot.orchestration import respond

    store = Store(str(tmp_path / "bot.sqlite3"))

    async def unavailable(*_args, **_kwargs):
        return None, "AI_PROVIDER_UNAVAILABLE"

    monkeypatch.setattr(research, "synthesize", unavailable)
    result = asyncio.run(respond("what should I do?", [], store, "owner", None))
    assert result["routing_status"] == "AI_PROVIDER_UNAVAILABLE"
    assert result["interpretation_status"] == "AI_PROVIDER_UNAVAILABLE"
    assert "chat_plan_unavailable status=AI_PROVIDER_UNAVAILABLE" in caplog.text


def test_chat_skips_retrieval_when_router_selects_no_tools(tmp_path, monkeypatch):
    from services.bot import orchestration, research

    store = Store(str(tmp_path / "bot.sqlite3"))
    received = {}

    async def direct(*_args, **kwargs):
        received.update(kwargs)
        return {"sections": [], "instruments": ["SENSEX"], "direct_answer": "Hey!"}, "VALIDATED"

    def unexpected_retrieval(*_args, **_kwargs):
        raise AssertionError("direct answers must not load research context")

    monkeypatch.setattr(research, "synthesize", direct)
    monkeypatch.setattr(orchestration, "retrieve", unexpected_retrieval)
    result = asyncio.run(orchestration.respond("hello", [], store, "owner", None))
    assert result["answer"] == "Hey!"
    assert result["context_sections"] == []
    assert received["insight_call_limit"] is None
    run = store.chat_run(result["run_id"], "owner")
    assert [event["stage"] for event in run["events"]] == ["started", "route", "complete"]
    assert run["events"][1]["details"]["selected_tools"] == []


def test_chat_run_trace_is_private_to_its_owner(tmp_path):
    store = Store(str(tmp_path / "bot.sqlite3"))
    run_id = "trace-123"
    store.record_chat_event(run_id, "owner-a", "started", "RUNNING")
    store.record_chat_event(run_id, "owner-a", "route", "VALIDATED", {"selected_tools": ["news"]})
    trace = store.chat_run(run_id, "owner-a")
    assert len(trace["events"]) == 2
    assert store.chat_run(run_id, "owner-b") is None


def test_background_insight_lease_does_not_block_chat(tmp_path, monkeypatch):
    from services.bot import research

    store = Store(str(tmp_path / "bot.sqlite3"))
    with store.connect() as db:
        db.execute(
            "INSERT INTO documents VALUES ('ai_lease:insights',?)",
            (json.dumps({"owner": "worker", "until": (datetime.now(UTC) + timedelta(minutes=1)).isoformat()}),),
        )
    calls = 0

    async def complete(_store, _packet, _limit, _timeout):
        nonlocal calls
        calls += 1
        return {"sections": [], "direct_answer": "Hello!"}, "VALIDATED"

    monkeypatch.setattr(research, "_synthesize", complete)
    result = asyncio.run(research.synthesize(
        store, {"routing": True}, insight_call_limit=None, operation_timeout_seconds=1
    ))
    assert result[1] == "VALIDATED" and calls == 1


def test_chat_tool_failure_is_retryable_and_traced(tmp_path, monkeypatch):
    from services.bot import orchestration, research

    store = Store(str(tmp_path / "bot.sqlite3"))

    async def select_news(*_args, **_kwargs):
        return {"sections": ["news"], "instruments": ["SENSEX"], "direct_answer": ""}, "VALIDATED"

    def unavailable(*_args, **_kwargs):
        raise OSError("private backend detail")

    monkeypatch.setattr(research, "synthesize", select_news)
    monkeypatch.setattr(orchestration, "retrieve", unavailable)
    result = asyncio.run(orchestration.respond("what is in the news?", [], store, "owner", None))
    assert result["routing_status"] == "TOOL_EXECUTION_FAILED"
    assert result["run_id"]
    events = store.chat_run(result["run_id"], "owner")["events"]
    assert events[-2]["stage"] == "tools" and events[-2]["status"] == "FAILED"
    assert events[-2]["details"] == {"error_type": "OSError"}


def test_chat_has_no_daily_token_budget_but_insights_keep_call_cap(tmp_path, monkeypatch):
    from services.bot import research

    store = Store(str(tmp_path / "bot.sqlite3"))
    policy = SimpleNamespace(
        ready=lambda: True,
        swan_ai_daily_token_budget=0,
        openai_model="isolated-model",
        swan_ai_timeout_seconds=2,
        swan_ai_max_output_tokens=1000,
        openai_api_key=SimpleNamespace(get_secret_value=lambda: "fixture"),
    )
    monkeypatch.setattr(research, "AgentSettings", lambda: policy)
    calls = 0

    def respond(request):
        nonlocal calls
        calls += 1
        request_body = json.loads(request.content)
        packet = json.loads(request_body["input"])
        routing = packet.get("routing", False)
        output = ({"direct_answer": "Hello!", "sections": [], "instruments": ["SENSEX"]}
                  if routing else {"answer": "Hello!", "evidence_ids": []}
                  if packet.get("conversation") else {
                      "thesis": "Conditions are mixed.",
                      "counterargument": "The evidence may be incomplete.",
                      "next_observation": "Check the next observation.",
                      "evidence_ids": ["source"],
                      "abstain": False,
                  })
        return httpx.Response(200, json={"status": "completed", "output": [{
            "type": "message", "content": [{"type": "output_text", "text": json.dumps(output)}]
        }]})

    transport = httpx.MockTransport(respond)
    client = httpx.AsyncClient
    monkeypatch.setattr(
        research.httpx,
        "AsyncClient",
        lambda **kwargs: client(transport=transport, **kwargs),
    )
    chat_plan, plan_status = asyncio.run(research.synthesize(
        store,
        {"routing": True, "question": "hello"},
        insight_call_limit=None,
    ))
    chat_answer, answer_status = asyncio.run(research.synthesize(
        store,
        {"conversation": True, "question": "hello", "evidence_ids": []},
        insight_call_limit=None,
    ))
    assert plan_status == answer_status == "VALIDATED"
    assert chat_plan["direct_answer"] == chat_answer["answer"] == "Hello!"
    assert calls == 2

    policy.swan_ai_daily_token_budget = 100000
    first, first_status = asyncio.run(research.synthesize(
        store,
        {"idea_id": "idea-one", "evidence_ids": ["source"]},
        insight_call_limit=1,
    ))
    second, second_status = asyncio.run(research.synthesize(
        store,
        {"idea_id": "idea-two", "evidence_ids": ["source"]},
        insight_call_limit=1,
    ))
    assert first and first_status == "VALIDATED"
    assert second is None and second_status == "DAILY_INSIGHT_CALL_LIMIT"
    assert calls == 3


@pytest.mark.parametrize("citation,expected", [("source-a", "VALIDATED"),
    ("invented-source", "AI_UNKNOWN_EVIDENCE")])
def test_chat_answer_rejects_unknown_evidence_ids(tmp_path, monkeypatch, citation, expected):
    from services.bot import research

    store = Store(str(tmp_path / "bot.sqlite3"))
    context = {"as_of": datetime.now(UTC).isoformat(), "quotes": [], "analyses": {
        "SENSEX": {"status": "current", "evidence": ["source-a"]}}}
    policy = SimpleNamespace(ready=lambda: True, swan_ai_daily_token_budget=30000,
                             openai_model="isolated-model", swan_ai_timeout_seconds=2,
                             swan_ai_max_output_tokens=1000,
                             openai_api_key=SimpleNamespace(get_secret_value=lambda: "fixture"))
    monkeypatch.setattr(research, "AgentSettings", lambda: policy)
    output = {"answer": "This condition describes the supplied observation.",
              "evidence_ids": [citation]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "status": "completed", "output": [{"type": "message", "content": [{
            "type": "output_text", "text": json.dumps(output)}]}]}))
    client = httpx.AsyncClient
    monkeypatch.setattr(research.httpx, "AsyncClient", lambda **kwargs: client(transport=transport))
    result = asyncio.run(answer("Explain latest observations", context, store, []))
    assert result["interpretation_status"] == expected
    if expected != "VALIDATED":
        assert "please try again" in result["answer"]
