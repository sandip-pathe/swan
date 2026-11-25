"""Plan -> retrieve selected saved insights -> answer. No upstream data collection."""

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from services.bot.contracts import ChatPlan
from services.bot.session import market_context
from services.bot.store import Store
from services.market.calendar import SessionCalendar
from services.market.settings import MarketSettings, ProviderError


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

    now = datetime.now(UTC)
    history = [{"role": turn["role"], "content": turn["content"][:1000]} for turn in history[-4:]]
    plan, status = await synthesize(
        store,
        {
            "routing": True,
            "question": question,
            "history": history,
            "has_selected_insight": bool(idea_id),
        },
    )
    if plan is None:
        return {
            "answer": "I couldn't prepare the context for this answer. Please try again.",
            "as_of": now.isoformat(),
            "sources": [],
            "interpretation_status": status,
            "actions_taken": [],
            "order_created": False,
        }
    plan = ChatPlan.model_validate(plan)
    if not plan.sections and plan.direct_answer.strip():
        return {
            "answer": plan.direct_answer,
            "as_of": datetime.now(UTC).isoformat(),
            "sources": [],
            "interpretation_status": status,
            "context_sections": [],
            "routing_status": status,
            "actions_taken": [],
            "order_created": False,
        }
    evidence = await asyncio.to_thread(retrieve, store, plan, datetime.now(UTC), owner, idea_id)
    result = await answer(question, evidence, store, history)
    result["context_sections"] = evidence["retrieved_sections"]
    result["routing_status"] = status
    return result
