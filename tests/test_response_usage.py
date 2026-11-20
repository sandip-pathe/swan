"""Rejected responses retain supplied usage without becoming valid outputs."""

# ruff: noqa: F811
import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_durable import durable  # noqa: F401
from test_instrument_search import client_for

from services.agents import provider as module
from services.agents.contracts import Analysis
from services.agents.provider import StructuredProvider
from services.api import agent_usage as api
from services.core.models import AuditEvent
from services.market.settings import ProviderError

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "case,total,valid",
    [
        ("valid", 90, True),
        ("incomplete", 70, False),
        ("invalid_schema", 50, False),
        ("refusal", 30, False),
        ("invalid_blocks", 20, False),
        ("missing", None, False),
        ("invalid_usage", True, False),
        ("zero", 0, False),
    ],
)
def test_response_usage_survives_output_rejection_and_is_not_double_counted(
    durable, monkeypatch, case, total, valid
):
    d = durable

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return d.clock.now.astimezone(tz) if tz else d.clock.now.replace(tzinfo=None)

    monkeypatch.setattr(module, "datetime", FixedDatetime)
    monkeypatch.setattr(api, "utc_now", lambda: d.clock.now + timedelta(seconds=1))
    settings = SimpleNamespace(
        ready=lambda: True,
        openai_model="test-model",
        swan_ai_daily_token_budget=1000000,
        swan_ai_max_output_tokens=1000,
        swan_ai_timeout_seconds=10,
        openai_api_key=SecretStr("test-only"),
    )
    provider = StructuredProvider(d.engine, d.account, settings)
    monkeypatch.setattr(api, "AgentSettings", lambda: settings)
    output = Analysis(
        outlook="UNCERTAIN", rationale="Recorded", evidence_ids=[], news_ids=[], concerns=[]
    )
    part = {
        "type": "output_text",
        "text": output.model_dump_json() if valid else "invalid private output",
    }
    if case == "refusal":
        part = {"type": "refusal", "refusal": "private refusal"}
    body = {
        "status": "completed"
        if case in ("valid", "invalid_schema", "refusal", "invalid_blocks")
        else "incomplete",
        "usage": {
            "total_tokens": total,
            "input_tokens": 10,
            "output_tokens": 20,
            "input_tokens_details": {"cached_tokens": 5, "private": "not-for-audit"},
            "private": "not-for-audit",
        },
        "output": [{"type": "message", "content": [part]}],
    }
    if case == "invalid_blocks":
        body["output"] = [123]
    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
        ),
    )
    if valid:
        asyncio.run(provider.generate("analysis", {}, Analysis))
    else:
        with pytest.raises(ProviderError):
            asyncio.run(provider.generate("analysis", {}, Analysis))
    with Session(d.engine) as db:
        assert db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.kind == "AI_OUTPUT")
        ) == int(valid)
        receipt = db.scalar(select(AuditEvent).where(AuditEvent.kind == "AI_RESPONSE_USAGE"))
        assert receipt is not None
        assert receipt.details["usage"]["input_tokens"] == 10
        assert receipt.details["usage"]["output_tokens"] == 20
        assert receipt.details["usage"]["input_tokens_details"] == {"cached_tokens": 5}
        assert "not-for-audit" not in json.dumps(receipt.details)
    with client_for(d.engine, d.account) as browser:
        result = browser.get("/api/paper/agent-usage").json()
    known = type(total) is int and total >= 0
    assert result["reported_tokens"] == (total if known else 0)
    assert result["reported_calls"] == int(known)
    assert result["unknown_calls"] == int(not known)
    assert result["reported_without_output_calls"] == int(known and not valid)
    assert result["reservation_count"] == 1 and result["reserved_allowance"] > 0
    assert "private" not in json.dumps(result)


def test_unique_receipts_override_legacy_output_without_double_counting_and_duplicates_are_unknown(
    durable, monkeypatch
):
    from test_agent_usage import save

    d = durable
    monkeypatch.setattr(api, "utc_now", lambda: d.clock.now)
    reservation = save(d, "AI_RESERVATION", {"tokens": 100})
    save(d, "AI_OUTPUT", {"reservation_id": reservation, "usage": {"total_tokens": 70}})
    receipt = {"reservation_id": reservation, "usage": {"total_tokens": 70}}
    save(d, "AI_RESPONSE_USAGE", receipt)
    with client_for(d.engine, d.account) as browser:
        assert browser.get("/api/paper/agent-usage").json()["reported_tokens"] == 70
        with Session(d.engine) as db, db.begin():
            output = db.scalar(select(AuditEvent).where(AuditEvent.kind == "AI_OUTPUT"))
            output.details = {"reservation_id": reservation, "usage": {"total_tokens": 50}}
        assert browser.get("/api/paper/agent-usage").json()["unknown_calls"] == 1
        with Session(d.engine) as db, db.begin():
            output = db.scalar(select(AuditEvent).where(AuditEvent.kind == "AI_OUTPUT"))
            output.details = {"reservation_id": reservation, "usage": {"total_tokens": 70}}
        save(d, "AI_RESPONSE_USAGE", receipt)
        result = browser.get("/api/paper/agent-usage").json()
        assert result["reported_tokens"] == 0 and result["unknown_calls"] == 1


@pytest.mark.parametrize(
    "body,status", [("not-json", 200), ('{"usage":{"total_tokens":500}}', 429)]
)
def test_untrusted_or_missing_response_usage_stays_unknown(durable, monkeypatch, body, status):
    from test_agent_versions import prepare

    d = durable
    original = httpx.AsyncClient
    key, provider, context, sent = prepare(d, monkeypatch)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(lambda request: httpx.Response(status, content=body))
        ),
    )
    with pytest.raises(ProviderError):
        asyncio.run(provider.generate("analysis", context, Analysis))
    with Session(d.engine) as db:
        assert not db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.kind == "AI_RESPONSE_USAGE")
        )
