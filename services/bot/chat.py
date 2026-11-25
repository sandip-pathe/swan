"""Bounded optional interpretation over deterministic facts, with safe fallback."""

import json
import re
from datetime import datetime

from services.bot.store import Store
from services.core.contracts import IST


def reserve(store: Store, day: str, amount: int, limit: int) -> bool:
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        key = f"budget:{day}"
        row = db.execute("SELECT payload FROM documents WHERE key=?", (key,)).fetchone()
        used = json.loads(row[0]) if row else 0
        if used + amount > limit:
            return False
        db.execute(
            "INSERT INTO documents VALUES (?,?) ON CONFLICT(key) DO UPDATE "
            "SET payload=excluded.payload",
            (key, json.dumps(used + amount)),
        )
        return True


async def answer(question: str, context: dict, store: Store, history: list[dict]) -> dict:
    if question.casefold().strip(" .!?,\n\t") in {"hi", "hello", "hey", "good morning"}:
        return {
            "answer": "Hi! What would you like to know about the market?",
            "as_of": context["as_of"],
            "sources": [],
            "actions_taken": [],
            "order_created": False,
        }
    normalized = question.casefold()
    session_question = bool(
        re.search(
            r"(?:\b(?:is|are) (?:the )?(?:market|exchange|sensex|nifty)(?: session)? "
            r"(?:open|closed|active)\b|\bmarket (?:hours|timings?)\b|"
            r"\b(?:when|what time) (?:does|will) (?:the )?market (?:open|close)\b)",
            normalized,
        )
    )
    if session_question:
        name = "NIFTY" if "nifty" in normalized and "sensex" not in normalized else "SENSEX"
        calendar = context.get("calendars", {}).get(name, context.get("calendar", {}))
        now = datetime.fromisoformat(context["as_of"]).astimezone(IST)

        def local_time(value):
            return datetime.fromisoformat(value).astimezone(IST).strftime("%d %b, %I:%M %p IST")

        state = calendar.get("state", "unknown")
        if state == "open":
            text = f"Yes, the {name} regular market session is open as of {now:%I:%M %p IST}."
            if calendar.get("closes_at"):
                text += f" It closes at {local_time(calendar['closes_at'])}."
        elif state == "closed":
            text = f"No, the {name} regular market session is closed as of {now:%I:%M %p IST}."
            if calendar.get("next_verified_open"):
                text += f" Next scheduled opening: {local_time(calendar['next_verified_open'])}."
            elif calendar.get("opens_at") and datetime.fromisoformat(calendar["opens_at"]) > now:
                text += f" Today's opening: {local_time(calendar['opens_at'])}."
            if calendar.get("closure_reason"):
                text += f" {calendar['closure_reason']}."
        else:
            text = "The exchange calendar does not cover the current session, so I cannot confirm whether it is open. Regular cash-market hours are 9:15 AM to 3:30 PM IST on trading days."
        return {
            "answer": text,
            "as_of": context["as_of"],
            "sources": [{"source": "Exchange session calendar"}],
            "interpretation_status": "session_calendar",
            "actions_taken": [],
            "order_created": False,
        }
    from services.bot.research import packet_for, synthesize

    analysis = context["analysis"]
    selected = context.get("selected_idea")
    selected_packet = packet_for(selected, context.get("news", {})) if selected else None
    news = context.get("news", {}).get("items", [])[:4]
    evidence_ids = list(
        dict.fromkeys(
            analysis.get("evidence", [])
            + [row["id"] for row in news]
            + (selected.get("evidence_ids", []) if selected else [])
        )
    )
    result, status = await synthesize(
        store,
        {
            "conversation": True,
            "question": question,
            "history": history[-3:],
            "selected_idea": selected_packet,
            "current_ideas": [
                {
                    key: idea.get(key)
                    for key in (
                        "title",
                        "state",
                        "summary",
                        "trigger",
                        "invalidation",
                        "expires_at",
                    )
                }
                for idea in context.get("current_ideas", [])[:2]
            ],
            "as_of": context["as_of"],
            "calendar": context.get("calendar", {}),
            "facts": analysis,
            "quotes": context["quotes"],
            "weekly": context.get("weekly", {}),
            "news": [
                {key: row.get(key) for key in ("id", "title", "source", "published_at", "excerpt")}
                for row in news
            ],
            "evidence_ids": evidence_ids,
            "research_kind": "Answer the user's question directly using the available evidence. Historical or incomplete candles do not prevent education, session answers, or discussing available news. Do not infer current direction from stale observations.",
        },
    )
    if result:
        narrative = result["answer"]
    else:
        reasons = {
            "AI_NOT_CONFIGURED": "AI answers are not configured on the server.",
            "DAILY_BUDGET_REACHED": "Today's AI budget has been reached.",
            "AI_BUSY": "AI research is busy; please try again shortly.",
        }
        narrative = reasons.get(status, "The AI answer could not complete; please try again.")
        narrative += " I can still answer market-hours questions and show saved insights."
    return {
        "answer": narrative,
        "as_of": context["as_of"],
        "sources": (
            [{"source": row["url"]} for row in news if row["id"] in result["evidence_ids"]]
            + (
                [
                    {
                        "source": "Retained market evidence: "
                        + ", ".join(
                            key
                            for key in result["evidence_ids"]
                            if key not in {row["id"] for row in news}
                        )
                    }
                ]
                if any(key not in {row["id"] for row in news} for key in result["evidence_ids"])
                else []
            )
        )
        if result
        else [],
        "interpretation_status": status,
        "actions_taken": [],
        "order_created": False,
    }
