# ruff: noqa: F811
import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_durable import durable  # noqa: F401

from services.agents import chat
from services.api.chat import ChatRequest
from services.core.models import AuditEvent, PaperOrder


@pytest.mark.integration
def test_chat_reads_real_owned_tools_and_cannot_create_orders(durable, monkeypatch):
    d = durable

    class Provider:
        def __init__(self, *args):
            pass

        async def generate(self, role, context, schema):
            if role == "chat_tool_planner":
                return chat.ChatPlan(tools=["account", "market", "strategies", "indicators"],
                                     underlying="NIFTY", instrument_id=d.instrument.id)
            assert len(context["tool_results"]) == 4
            for row in context["tool_results"]:
                assert row["data"].get("reason") != "TOOL_READ_FAILED", row["tool"]
            return chat.ChatAnswer(answer="The tools supplied current records; no trade was placed.",
                                   evidence_ids=[row["id"] for row in context["tool_results"]])

    monkeypatch.setattr(chat, "StructuredProvider", Provider)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=d.engine)))
    with Session(d.engine) as db:
        before = db.scalar(select(func.count()).select_from(PaperOrder))
    result = asyncio.run(chat.answer_question(request, d.account, "Explain the market and my risk", []))
    assert len(result["sources"]) == 4 and result["actions_taken"] == []
    with Session(d.engine) as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == before
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.kind == "CHAT_TOOL_CONTEXT"))


def test_tool_allowlist_and_request_bounds():
    with pytest.raises(ValidationError):
        chat.ChatPlan(tools=["place_order"], underlying="NIFTY", instrument_id=None)
    with pytest.raises(ValidationError):
        ChatRequest(question="hello", history=[], arm=True)
    with pytest.raises(ValueError, match="CHAT_TOOL_NOT_ALLOWED"):
        chat.read_tool("shell", SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=None))), None,
                       chat.ChatPlan(tools=["account"], underlying="NIFTY", instrument_id=None))
