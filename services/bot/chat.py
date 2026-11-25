"""Bounded optional interpretation over deterministic facts, with safe fallback."""

import json

from services.bot.store import Store


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
    from services.bot.research import packet_for, synthesize

    selected = context.get("selected_idea")
    news = context.get("news", {}).get("items", [])[:4]
    selected_packet = packet_for(selected, context.get("news", {})) if selected else None
    evidence_ids = list(
        dict.fromkeys(
            [
                key
                for analysis in context.get("analyses", {}).values()
                for key in analysis.get("evidence", [])
            ]
            + [row["id"] for row in news]
            + (selected.get("evidence_ids", []) if selected else [])
        )
    )
    packet = {key: value for key, value in context.items() if key != "selected_idea"}
    packet.update(
        conversation=True,
        question=question,
        history=history[-4:],
        selected_idea=selected_packet,
        evidence_ids=evidence_ids,
    )
    result, status = await synthesize(store, packet)
    if result:
        narrative = result["answer"]
    else:
        reasons = {
            "AI_NOT_CONFIGURED": "AI answers are not configured on the server.",
            "DAILY_BUDGET_REACHED": "Today's AI budget has been reached.",
            "AI_BUSY": "AI research is busy; please try again shortly.",
        }
        narrative = reasons.get(status, "The AI answer could not complete; please try again.")
        narrative += " Your saved insights are still available in Insights."
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
