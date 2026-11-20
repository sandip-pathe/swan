"""Check events reflect executed validation, including early returns and failures."""

# ruff: noqa: F811
import asyncio
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_agent_run import read, save, slot
from test_durable import durable, observed  # noqa: F401

from services.agents import pipeline as module
from services.agents.contracts import Analysis, Proposal, Review
from services.agents.pipeline import AgentPipeline
from services.market.settings import ProviderError

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "case,states,reason",
    [
        ("wait", ["PASSED", "PASSED"], None),
        ("bad_citation", ["FAILED"], "Market citations"),
        ("bad_news", ["FAILED"], "news citation"),
        ("invalid_wait", ["PASSED", "FAILED"], "wait proposal"),
        ("incomplete", ["PASSED", "FAILED"], "missing required"),
        ("review_rejected", ["PASSED", "PASSED", "PASSED"], None),
        ("review_missing", ["PASSED", "PASSED", "FAILED"], "every proposal citation"),
        ("expired", ["PASSED", "PASSED", "PASSED", "FAILED"], "expired"),
        ("accepted", ["PASSED", "PASSED", "PASSED", "PASSED"], None),
        ("provider_error", ["FAILED"], "could not complete"),
        ("invalid_response", ["FAILED"], "format or contract"),
        ("interrupted", ["INTERRUPTED"], "interrupted"),
    ],
)
def test_recorded_stage_checks_match_real_control_flow(durable, monkeypatch, case, states, reason):
    d = durable
    key = slot(d)
    quote = observed(d)
    second = quote.model_copy(update={"id": uuid4()})
    pipeline = AgentPipeline.__new__(AgentPipeline)
    pipeline.settings = SimpleNamespace(ready=lambda: True)

    async def news():
        return []

    pipeline.news = SimpleNamespace(read=news)
    calls = []

    async def generate(role, context, model):
        calls.append(role)
        ids = [str(quote.id), str(second.id)]
        if case == "provider_error":
            raise ProviderError("AI_HTTP_429")
        if case == "invalid_response":
            raise ValueError("private provider body")
        if case == "interrupted":
            raise asyncio.CancelledError()
        if role == "analysis":
            value = Analysis(
                outlook="UNCERTAIN",
                rationale="Recorded analysis",
                evidence_ids=[str(uuid4())] if case == "bad_citation" else ids,
                news_ids=["unknown"] if case == "bad_news" else [],
                concerns=[],
            )
        elif role == "proposal":
            waiting = case in ("wait", "invalid_wait")
            value = Proposal(
                action="WAIT" if waiting else "BUY_" + d.instrument.option_type,
                instrument_id=None if waiting else d.instrument.id,
                min_entry="100" if not waiting or case == "invalid_wait" else None,
                max_entry=None if waiting or case == "incomplete" else "101",
                stop_loss=None if waiting else "95",
                target=None if waiting else "107",
                rationale="Recorded proposal",
                evidence_ids=ids,
            )
        else:
            value = Review(
                approved=case != "review_rejected",
                rationale="Recorded review",
                evidence_ids=ids[:1] if case == "review_missing" else ids,
            )
        save(d, key, role, value.model_dump(mode="json"))
        return value

    pipeline.provider = SimpleNamespace(engine=d.engine, account_id=d.account, generate=generate)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            point = d.clock.now if case != "expired" else d.clock.now.replace(year=2027)
            return point.astimezone(tz) if tz else point.replace(tzinfo=None)

    monkeypatch.setattr(module, "datetime", FixedDatetime)

    async def execute():
        return await pipeline.evaluate(
            {d.instrument.id: d.instrument},
            [quote, second],
            d.scenario.session,
            d.scenario.config,
            key,
        )

    if reason:
        with pytest.raises((ProviderError, ValueError, asyncio.CancelledError)):
            asyncio.run(execute())
    else:
        envelope = asyncio.run(execute())
        assert (envelope is not None) == (case == "accepted")
    event = save(d, key, kind="AGENT_EVALUATION")
    result = read(d, event).json()
    checks = {check["stage"]: check for check in result["checks"]}
    assert [
        checks[stage]["state"]
        for stage in ("analysis", "proposal", "review", "strategy")
        if stage in checks
    ] == states
    assert len(result["checks"]) == len(states)
    assert len(calls) == min(len(states), 3)
    if reason:
        assert (
            reason.lower()
            in next(
                check["summary"] for check in result["checks"] if check["state"] != "PASSED"
            ).lower()
        )
    assert "private provider body" not in str(result)


def test_history_bounds_and_sanitizes_check_records(durable):
    from sqlalchemy.orm import Session

    from services.core.models import AuditEvent

    d = durable
    key = slot(d)
    event = save(d, key, kind="AGENT_EVALUATION")
    with Session(d.engine) as db, db.begin():
        for index in range(21):
            db.add(
                AuditEvent(
                    account_id=d.account,
                    kind="AI_STAGE_CHECK",
                    timestamp=d.clock.now,
                    details={
                        "evaluation_id": str(key),
                        "stage": "private-stage",
                        "state": "PASSED" if index % 2 else "private-state",
                        "reason": "private-reason",
                        "raw": "secret-context",
                    },
                )
            )
    result = read(d, event).json()
    assert result["checks_truncated"] and len(result["checks"]) == 20
    assert all(
        check["stage"] == "unknown" and check["state"] == "UNKNOWN" for check in result["checks"]
    )
    assert "private-" not in str(result) and "secret-context" not in str(result)
