"""Evidence is explicit, owned, historical and safely projected."""

# ruff: noqa: F811
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_durable import durable, observed  # noqa: F401
from test_instrument_search import client_for

from services.agents.contracts import Analysis
from services.agents.pipeline import AgentPipeline
from services.agents.provider import StructuredProvider
from services.core.models import Account, AuditEvent

pytestmark = pytest.mark.integration


def save(d, kind, details, owner=None):
    with Session(d.engine) as db, db.begin():
        row = AuditEvent(
            account_id=owner or d.account, kind=kind, timestamp=d.clock.now, details=details
        )
        db.add(row)
        db.flush()
        return row.id


def read(d, event):
    with client_for(d.engine, d.account) as client:
        return client.get(f"/api/paper/agent-activity/{event}/evidence")


def output(quote):
    return {
        "outlook": "UNCERTAIN",
        "rationale": "Insufficient evidence",
        "evidence_ids": [str(quote.id)],
        "news_ids": ["headline"],
        "concerns": [],
    }


def test_future_output_links_persisted_context_and_only_cited_values(durable, monkeypatch):
    d = durable
    quote = observed(d)
    settings = SimpleNamespace(
        ready=lambda: True,
        openai_model="test-model",
        swan_ai_daily_token_budget=1000000,
        swan_ai_max_output_tokens=1000,
        swan_ai_timeout_seconds=10,
        openai_api_key=SecretStr("test-only"),
    )
    provider = StructuredProvider(d.engine, d.account, settings)
    pipeline = AgentPipeline.__new__(AgentPipeline)
    pipeline.provider = provider
    context = {
        "quotes": [quote.model_dump(mode="json")],
        "instruments": [d.instrument.model_dump(mode="json")],
        "headlines": [
            {
                "id": "headline",
                "title": "Recorded headline",
                "source": "Source",
                "url": "javascript:unsafe",
                "published_at": d.clock.now.isoformat(),
                "fetched_at": d.clock.now.isoformat(),
                "provider_delay_seconds": 43200,
            }
        ],
        "risk": {"private": "not-for-client"},
    }
    context["context_id"] = str(pipeline.persist_context(context))
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "status": "completed",
                "id": "private-response",
                "usage": {"total_tokens": 30},
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": Analysis.model_validate(output(quote)).model_dump_json(),
                            }
                        ],
                    }
                ],
            },
        )
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=transport))
    asyncio.run(provider.generate("analysis", context, Analysis))
    with Session(d.engine) as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.kind == "AI_OUTPUT"))
        assert event.details["context_id"] == context["context_id"]
        event_id = event.id
    result = read(d, event_id)
    assert result.status_code == 200
    data = result.json()
    assert data["available"] and data["missing"] == 0
    assert data["quotes"][0]["bid"] == str(quote.bid)
    assert "NIFTY" in data["quotes"][0]["instrument"]
    assert data["headlines"][0]["provider_delay_seconds"] == 43200
    assert (
        "javascript" not in result.text
        and "private-response" not in result.text
        and "not-for-client" not in result.text
    )


def test_legacy_wrong_owner_and_wrong_kind_never_time_join(durable):
    d = durable
    quote = observed(d)
    context = save(d, "AI_CONTEXT", {"quotes": [quote.model_dump(mode="json")]})
    old = save(d, "AI_OUTPUT", {"role": "analysis", "output": output(quote)})
    assert not read(d, old).json()["available"]
    assert read(d, context).status_code == 404
    assert read(d, uuid4()).status_code == 404
    with Session(d.engine) as db, db.begin():
        other = Account(cash=0, config={})
        db.add(other)
        db.flush()
        owner = other.id
    foreign = save(d, "AI_CONTEXT", {"quotes": [quote.model_dump(mode="json")]}, owner)
    event = save(
        d, "AI_OUTPUT", {"role": "analysis", "context_id": str(foreign), "output": output(quote)}
    )
    assert not read(d, event).json()["available"]
    foreign_event = save(d, "AI_OUTPUT", {}, owner)
    assert read(d, foreign_event).status_code == 404


def test_invalid_or_missing_observations_are_reported(durable):
    d = durable
    quote = observed(d)
    context = save(d, "AI_CONTEXT", {"quotes": [{"invalid": True}], "headlines": None})
    event = save(
        d, "AI_OUTPUT", {"role": "analysis", "context_id": str(context), "output": output(quote)}
    )
    data = read(d, event).json()
    assert data["available"] and data["missing"] == 2
    assert data["quotes"] == data["headlines"] == []
