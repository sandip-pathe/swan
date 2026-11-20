"""Version records bind to sent requests, owned contexts and unique responses."""

# ruff: noqa: F811
import asyncio
import json
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_agent_run import read, save, slot
from test_durable import durable  # noqa: F401

from services.agents.contracts import Analysis
from services.agents.pipeline import PIPELINE_SHA256, STRATEGY_VERSION, AgentPipeline
from services.agents.provenance import fingerprint
from services.agents.provider import StructuredProvider
from services.core.models import Account, AuditEvent
from services.market.settings import ProviderError

pytestmark = pytest.mark.integration


def prepare(d, monkeypatch, model="provider-model", status=200):
    key = slot(d)
    settings = SimpleNamespace(
        ready=lambda: True,
        openai_model="requested-model",
        swan_ai_daily_token_budget=1000000,
        swan_ai_max_output_tokens=1000,
        swan_ai_timeout_seconds=10,
        openai_api_key=SecretStr("test-only"),
    )
    provider = StructuredProvider(d.engine, d.account, settings)
    pipeline = AgentPipeline.__new__(AgentPipeline)
    pipeline.provider = provider
    context = {
        "evaluation_id": str(key),
        "implementation": {
            "strategy_version": STRATEGY_VERSION,
            "pipeline_sha256": PIPELINE_SHA256,
        },
    }
    context["context_id"] = str(pipeline.persist_context(context))
    sent = []
    result = Analysis(
        outlook="UNCERTAIN", rationale="Uncertain", evidence_ids=[], news_ids=[], concerns=[]
    )

    def handle(request):
        sent.append(json.loads(request.content))
        return httpx.Response(
            status,
            json={
                "model": model,
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": result.model_dump_json()}],
                    }
                ],
            },
        )

    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(handle))
    )
    return key, provider, context, sent


@pytest.mark.parametrize("model", ["provider-model", None])
def test_saved_metadata_matches_actual_sent_request_and_not_current_settings(
    durable, monkeypatch, model
):
    d = durable
    key, provider, context, sent = prepare(d, monkeypatch, model)
    asyncio.run(provider.generate("analysis", context, Analysis))
    with Session(d.engine) as db:
        reservation = db.scalar(select(AuditEvent).where(AuditEvent.kind == "AI_RESERVATION"))
        assert (
            reservation.details["daily_allowance"] == provider.settings.swan_ai_daily_token_budget
        )
    provider.settings.openai_model = "changed-after-request"
    event = save(d, key, kind="AGENT_EVALUATION")
    result = read(d, event).json()["versions"]["rows"][0]
    assert result["requested_model"] == sent[0]["model"] == "requested-model"
    assert result["reported_model"] == model
    assert result["strategy_version"] == STRATEGY_VERSION and result["rules_recorded"]
    assert result["fingerprints"] == {
        "prompt": fingerprint(sent[0]["instructions"]),
        "schema": fingerprint(sent[0]["text"]["format"]["schema"]),
        "pipeline": PIPELINE_SHA256,
    }
    assert "test-only" not in str(result) and "changed-after-request" not in str(result)


def test_failed_request_retains_requested_model_without_invented_response(durable, monkeypatch):
    d = durable
    key, provider, context, sent = prepare(d, monkeypatch, status=429)
    with pytest.raises(ProviderError):
        asyncio.run(provider.generate("analysis", context, Analysis))
    event = save(d, key, kind="AGENT_EVALUATION")
    result = read(d, event).json()["versions"]["rows"][0]
    assert result["requested_model"] == "requested-model" and result["reported_model"] is None
    assert result["rules_recorded"]


def test_duplicate_responses_and_foreign_context_do_not_get_merged(durable, monkeypatch):
    d = durable
    key, provider, context, sent = prepare(d, monkeypatch)
    asyncio.run(provider.generate("analysis", context, Analysis))
    event = save(d, key, kind="AGENT_EVALUATION")
    with Session(d.engine) as db, db.begin():
        original = db.scalar(select(AuditEvent).where(AuditEvent.kind == "AI_OUTPUT"))
        db.add(
            AuditEvent(
                account_id=d.account,
                kind="AI_OUTPUT",
                timestamp=d.clock.now,
                details=dict(original.details),
            )
        )
        other = Account(cash=0, config={})
        db.add(other)
        db.flush()
        db.add(
            AuditEvent(
                account_id=other.id,
                kind="AI_RESERVATION",
                timestamp=d.clock.now,
                details={"request": {"evaluation_id": str(key), "model": "foreign-model"}},
            )
        )
        saved_context = db.get(AuditEvent, UUID(context["context_id"]))
        saved_context.account_id = other.id
    result = read(d, event).json()["versions"]
    assert len(result["rows"]) == 1 and result["rows"][0]["reported_model"] is None
    assert result["rows"][0]["strategy_version"] is None
    assert not result["rows"][0]["rules_recorded"]
    assert "foreign-model" not in str(result)


def test_legacy_invalid_and_bounded_records_stay_explicit(durable):
    d = durable
    key = slot(d)
    event = save(d, key, kind="AGENT_EVALUATION")
    assert read(d, event).json()["versions"]["rows"] == []
    with Session(d.engine) as db, db.begin():
        for _ in range(21):
            db.add(
                AuditEvent(
                    account_id=d.account,
                    kind="AI_RESERVATION",
                    timestamp=d.clock.now,
                    details={
                        "role": "analysis",
                        "request": {
                            "evaluation_id": str(key),
                            "model": "unsafe<model>",
                            "prompt_sha256": "private-invalid",
                        },
                    },
                )
            )
    result = read(d, event).json()["versions"]
    assert result["truncated"] and len(result["rows"]) == 20
    assert all(
        row["requested_model"] is None and not row["rules_recorded"] for row in result["rows"]
    )
    assert "private-invalid" not in str(result)
