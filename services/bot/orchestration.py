"""Plan -> retrieve selected saved insights -> answer. No upstream data collection."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException

from services.bot.contracts import ChatPlan
from services.bot.session import market_context
from services.bot.store import Store
from services.market.calendar import SessionCalendar
from services.market.settings import MarketSettings, ProviderError

logger = logging.getLogger(__name__)


def failed_response(run_id: str, status: str) -> dict:
    return {
        "answer": "SWAN couldn't finish this answer. Your question is saved; you can retry.",
        "as_of": datetime.now(UTC).isoformat(),
        "sources": [],
        "interpretation_status": status,
        "routing_status": status,
        "run_id": run_id,
        "actions_taken": [],
        "order_created": False,
    }


def retrieve(store: Store, plan: ChatPlan, now: datetime, owner: str, idea_id: str | None) -> dict:
    sections = set(plan.sections)
    if sections & {"market", "ideas"}:
        sections.add("session")
    result = {"as_of": now.isoformat()}
    calendars = {}
    if "session" in sections:
        try:
            calendar = SessionCalendar(MarketSettings().calendar_file)
            calendars = {
                name: market_context(calendar, now, "BFO" if name == "SENSEX" else "NFO")
                for name in plan.instruments
            }
        except ProviderError:
            calendars = {name: {"state": "unknown"} for name in plan.instruments}
        result["calendars"] = calendars
    if "market" in sections:
        result.update(analyses={}, quotes=[])
        for name in plan.instruments:
            quote = store.read("quote:" + name)
            age = (
                (now - datetime.fromisoformat(quote["timestamp"])).total_seconds()
                if quote
                else None
            )
            result["quotes"].append(
                {
                    "underlying": name,
                    "quote": quote,
                    "status": "unavailable"
                    if quote is None
                    else "current"
                    if calendars[name].get("state") == "open" and 0 <= age <= 90
                    else "historical",
                }
            )
            analysis = store.read("analysis:" + name, {"status": "unavailable"})
            analysis = {
                key: value
                for key, value in analysis.items()
                if key not in {"raw_bars", "missing_minutes"}
            }
            if analysis.get("status") in {"current", "partial"}:
                at = analysis.get("as_of")
                if (
                    not at
                    or calendars[name].get("state") != "open"
                    or not timedelta(0) <= now - datetime.fromisoformat(at) <= timedelta(minutes=3)
                ):
                    analysis["status"] = "historical"
            result["analyses"][name] = analysis
    if "news" in sections:
        news = store.read("news", {"sources": [], "items": []})
        result["news"] = {
            "sources": news.get("sources", []),
            "items": [
                {
                    key: (str(row.get(key, ""))[:800] if key == "excerpt" else row.get(key))
                    for key in ("id", "title", "source", "published_at", "excerpt", "url")
                }
                for row in news.get("items", [])[:4]
            ],
        }
    if "weekly" in sections:
        result["weekly"] = store.read("weekly", {"status": "unavailable"})
    if "ideas" in sections:
        from services.bot.app import idea_view

        if idea_id:
            selected = store.idea(idea_id)
            if not selected or selected.get("kind") != "idea":
                raise HTTPException(404, "IDEA_NOT_FOUND")
            name = selected["contract"]["underlying"] if selected.get("contract") else "SENSEX"
            if name not in calendars:
                try:
                    calendars[name] = market_context(
                        SessionCalendar(MarketSettings().calendar_file),
                        now,
                        "BFO" if name == "SENSEX" else "NFO",
                    )
                except ProviderError:
                    calendars[name] = {"state": "unknown"}
            result["selected_idea"] = idea_view(
                store,
                selected,
                now,
                calendars.get(name, {}).get("state") == "open",
                owner,
            )
        else:
            ideas = [
                idea
                for idea in store.ideas(30)
                if idea.get("state") not in {"expired", "invalidated"}
                and datetime.fromisoformat(idea["expires_at"]) > now
                and (idea.get("contract") or {}).get("underlying", "SENSEX") in plan.instruments
            ]
            result["current_ideas"] = [
                {
                    key: value
                    for key, value in idea_view(
                        store,
                        idea,
                        now,
                        calendars.get(
                            (idea.get("contract") or {}).get("underlying", "SENSEX"), {}
                        ).get("state")
                        == "open",
                        owner,
                    ).items()
                    if key
                    in {
                        "id",
                        "title",
                        "state",
                        "summary",
                        "trigger",
                        "invalidation",
                        "expires_at",
                        "reasons",
                    }
                }
                for idea in ideas[:2]
            ]
    result["retrieved_sections"] = sorted(sections)
    return result


async def respond(
    question: str, history: list[dict], store: Store, owner: str, idea_id: str | None
) -> dict:
    from services.bot.chat import answer
    from services.bot.research import synthesize

    run_id = str(uuid4())
    history = [{"role": turn["role"], "content": turn["content"][:1000]} for turn in history[-4:]]
    store.record_chat_event(run_id, owner, "started", "RUNNING")
    plan, status = await synthesize(
        store,
        {
            "routing": True,
            "question": question,
            "history": history,
            "has_selected_insight": bool(idea_id),
        },
        insight_call_limit=None,
        wait_for_lease=2,
        operation_timeout_seconds=22,
    )
    if plan is None:
        logger.warning("chat_plan_unavailable status=%s", status)
        store.record_chat_event(run_id, owner, "route", status)
        store.record_chat_event(run_id, owner, "complete", "FAILED")
        return failed_response(run_id, status)
    plan = ChatPlan.model_validate(plan)
    route_status = (
        "AI_EMPTY_DIRECT_ANSWER"
        if not plan.sections and not plan.direct_answer.strip()
        else status
    )
    store.record_chat_event(
        run_id, owner, "route", route_status, {"selected_tools": plan.sections}
    )
    if not plan.sections:
        if not plan.direct_answer.strip():
            logger.warning("chat_plan_unavailable status=AI_EMPTY_DIRECT_ANSWER")
            store.record_chat_event(run_id, owner, "complete", "FAILED")
            return failed_response(run_id, "AI_EMPTY_DIRECT_ANSWER")
        store.record_chat_event(run_id, owner, "complete", "SUCCEEDED")
        return {
            "answer": plan.direct_answer,
            "as_of": datetime.now(UTC).isoformat(),
            "sources": [],
            "interpretation_status": status,
            "context_sections": [],
            "routing_status": status,
            "run_id": run_id,
            "actions_taken": [],
            "order_created": False,
        }
    store.record_chat_event(run_id, owner, "tools", "RUNNING", {"selected_tools": plan.sections})
    try:
        evidence = await asyncio.to_thread(retrieve, store, plan, datetime.now(UTC), owner, idea_id)
        store.record_chat_event(
            run_id, owner, "tools", "SUCCEEDED", {"retrieved_sections": evidence["retrieved_sections"]}
        )
    except Exception as error:
        logger.warning("chat_tools_failed run_id=%s type=%s", run_id, type(error).__name__)
        store.record_chat_event(run_id, owner, "tools", "FAILED", {"error_type": type(error).__name__})
        store.record_chat_event(run_id, owner, "complete", "FAILED")
        return failed_response(run_id, "TOOL_EXECUTION_FAILED")
    try:
        result = await answer(question, evidence, store, history)
        answer_status = result.get("interpretation_status", "UNKNOWN")
        store.record_chat_event(run_id, owner, "answer", answer_status)
    except Exception as error:
        logger.warning("chat_answer_failed run_id=%s type=%s", run_id, type(error).__name__)
        store.record_chat_event(run_id, owner, "answer", "FAILED", {"error_type": type(error).__name__})
        store.record_chat_event(run_id, owner, "complete", "FAILED")
        return failed_response(run_id, "AI_RESPONSE_FAILED")
    result["context_sections"] = evidence["retrieved_sections"]
    result["routing_status"] = status
    result["run_id"] = run_id
    store.record_chat_event(
        run_id,
        owner,
        "complete",
        "SUCCEEDED" if answer_status in {"VALIDATED", "CACHED"} else "FAILED",
    )
    return result
