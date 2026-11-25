"""Bounded optional interpretation over deterministic facts, with safe fallback."""

import json
import re
from decimal import Decimal, InvalidOperation

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


def facts(context: dict) -> str:
    lines = []
    for row in context["quotes"]:
        quote = row["quote"]
        if quote:
            lines.append(
                f"{row['underlying']}: {quote['last_price']} as observed at "
                f"{quote['timestamp']} ({row['status']})."
            )
    analysis = context["analysis"]
    if analysis.get("last_close"):
        lines.append(
            f"{analysis.get('underlying', 'NIFTY')} completed candle: {analysis['last_close']} at "
            f"{analysis['as_of']} ({analysis['status']})."
        )
        if analysis.get("sma20"):
            lines.append(
                f"The last twenty one-minute closes average {analysis['sma20']}. "
                f"Price is {analysis['trend'].replace('_', ' ')}."
            )
        if analysis.get("range_high"):
            lines.append(
                f"Opening fifteen-minute range: {analysis['range_low']} to "
                f"{analysis['range_high']}; {analysis['range_state'].replace('_', ' ')}."
            )
    if not lines:
        lines.append(
            "I do not have validated market observations yet. Open Insights to check "
            "collection status. I cannot describe the current market without evidence."
        )
    if analysis.get("status") == "partial":
        lines.append(
            "Some candle windows are incomplete; the independent facts above remain available. Only strategies needing the missing windows wait."
        )
    elif analysis.get("status") != "current":
        lines.append(
            "Current candle analysis is unavailable. Saved observations describe their "
            "original times and cannot establish what is happening now."
        )
    return "\n\n".join(lines)


def assessment(context: dict) -> str:
    analysis = context["analysis"]
    name = analysis.get("underlying", "SENSEX")
    if analysis.get("status") == "partial":
        available = []
        if analysis.get("rolling_status") == "complete":
            available.append(
                "The latest twenty-minute window is complete: price is "
                + analysis.get("trend", "unknown").replace("_", " ")
                + "."
            )
        if analysis.get("opening_range_status") == "complete":
            available.append(
                "The opening range is retained: price is "
                + analysis.get("range_state", "unknown").replace("_", " ")
                + "."
            )
        return (
            f"{name}: "
            + " ".join(available)
            + " Range-based entries wait for their required missing window; news and other verified context remain available."
        )
    if analysis.get("status") != "current":
        missing = analysis.get("missing_minutes", [])
        detail = analysis.get("reason", "Current completed-candle evidence is unavailable.")
        return (
            f"{name}: current direction is not established. {detail}"
            + (f" Missing completed minutes: {len(missing)}." if missing else "")
            + " Saved prices are observations at their source times, not a live setup. "
            "A fresh quote alone cannot repair missing candle history."
        )
    trend = analysis.get("trend")
    state = analysis.get("range_state")
    if trend == "warming_up" or state == "warming_up":
        return (
            f"{name}: the session is still warming up; the required completed bars are not ready."
        )
    aligned = (trend, state) in {
        ("above_average", "above_opening_range"),
        ("below_average", "below_opening_range"),
    }
    meaning = (
        "The short-term average and opening range agree on direction."
        if aligned
        else "The short-term average and opening range do not establish an aligned breakout."
    )
    invalidation = (
        "A completed close back inside the opening range weakens that breakout context."
        if state != "inside_range"
        else "A confirmed close outside the opening range would change this range context."
    )
    return (
        f"{name}: {meaning} {invalidation} This describes completed candles, not a forecast. "
        "Index direction does not establish option liquidity, premium behaviour or profit."
    )


async def answer(question: str, context: dict, store: Store, history: list[dict]) -> dict:
    if question.casefold().strip(" .!?,\n\t") in {"hi", "hello", "hey", "good morning"}:
        return {
            "answer": "Hi! Ask me about conditional SENSEX call/put ideas in Insights, entry conditions "
            "or moving averages. I explain evidence and its limitations.",
            "as_of": context["as_of"],
            "sources": [],
            "actions_taken": [],
            "order_created": False,
        }
    # These definitions are available without a provider call or live market context.
    definitions = {
        "vwap": "VWAP is the volume-weighted average traded price. It needs valid traded "
        "volume for the same instrument and session. Index levels do not have traded "
        "volume, so this bot does not calculate an index VWAP. Being above VWAP "
        "alone does not establish a profitable trade.",
        "moving average": "A simple moving average is the arithmetic mean of a fixed number "
        "of completed closes. It describes recent prices and reacts with a "
        "lag. A price crossing it is a change in condition, not proof of a "
        "future trend. Missing candles prevent this bot from claiming "
        "continuous coverage.",
        "opening range": "The opening range is the highest high and lowest low within the "
        "first fifteen completed one-minute candles of the verified session. "
        "A later close outside it describes a breakout condition. Price can "
        "return inside the range; this condition does not predict follow-through.",
    }
    normalized = question.casefold()
    if any(word in normalized for word in ("risk", "loss")) and any(
        word in normalized for word in ("position", "premium")
    ):
        amounts = re.findall(
            r"(?:₹|inr\s*|rs\.?\s*|position(?:\s+value)?\s*[:=]?\s*)([\d,]+(?:\.\d+)?)", normalized
        )
        if len(amounts) == 1:
            try:
                amount = Decimal(amounts[0].replace(",", ""))
                if not Decimal(0) < amount <= Decimal("1000000000"):
                    raise ValueError
                threshold = (amount * Decimal("0.05")).quantize(Decimal("0.01"))
                return {
                    "answer": f"For a position premium of INR {amount}, your stated five-percent "
                    f"reference loss is INR {threshold}. This is a scenario calculation, not an "
                    "order or a guaranteed loss cap. Add applicable charges and slippage; a gap "
                    "can exceed this reference. I do not monitor your holdings or execute exits.",
                    "as_of": context["as_of"],
                    "sources": [],
                    "interpretation_status": "calculation",
                    "actions_taken": [],
                    "order_created": False,
                }
            except (InvalidOperation, ValueError):
                pass
    focus = "NIFTY" if "nifty" in normalized and "sensex" not in normalized else "SENSEX"
    if "analyses" in context:
        context = {
            **context,
            "analysis": context["analyses"][focus],
            "quotes": [row for row in context["quotes"] if row["underlying"] == focus],
        }
    if any(word in normalized for word in ("news", "headline", "report", "catalyst")):
        news = context.get("news", {})
        rows = news.get("items", [])[:5]
        text = "\n\n".join(
            f"{row['title']}\n{row['source']} · published {row['published_at']}\n"
            f"{row.get('excerpt', '')}\n{row['url']}"
            for row in rows
        )
        return {
            "answer": (
                "Attributed feed excerpts, not verified market causality or full research reports.\n\n"
                + text
                if rows
                else "The configured official feeds have not provided usable current items. "
                "This does not mean there is no important news. I cannot invent a current catalyst."
            ),
            "as_of": context["as_of"],
            "sources": [{"source": row["url"]} for row in rows],
            "interpretation_status": "source_excerpts" if rows else "source_unavailable",
            "actions_taken": [],
            "order_created": False,
        }
    ideas = context.get("current_ideas", [])
    if any(word in normalized for word in ("weekly", "swing")):
        ideas = [idea for idea in ideas if idea["horizon"] == "weekly"]
        if not ideas:
            daily = context.get("weekly", {})
            return {
                "answer": "Weekly research: "
                + daily.get("reason", "No verified weekly opportunity yet.")
                + (
                    f" Last verified daily close: {daily['last_close']} at {daily['as_of']}. "
                    + (
                        f"Prior structure: {daily['prior_four_session_low']} to {daily['prior_four_session_high']}."
                        if daily.get("prior_four_session_low")
                        else f"Available {daily.get('available_session_count', 0)}-session range: {daily.get('available_low')} to {daily.get('available_high')}; this is partial history."
                    )
                    if daily.get("last_close")
                    else ""
                )
                + " A weekly idea requires its own history and a contract that outlives the idea; "
                "an intraday signal is not a weekly forecast.",
                "as_of": context["as_of"],
                "sources": [],
                "interpretation_status": "weekly_context",
                "actions_taken": [],
                "order_created": False,
            }
    normalized = re.sub(r"\bsma\b", "moving average", normalized)
    educational = any(
        word in normalized for word in ("explain", "what is", "what does", "understand")
    )
    if educational and not any(
        word in normalized for word in ("today", "latest", "current", "now")
    ):
        for term, definition in definitions.items():
            if term in normalized:
                return {
                    "answer": definition,
                    "as_of": context["as_of"],
                    "sources": [],
                    "interpretation_status": "definition",
                    "actions_taken": [],
                    "order_created": False,
                }
    selected = context.get("selected_idea") or next(
        (idea for idea in ideas if idea["state"] not in {"expired", "invalidated"}), None
    )
    if selected:
        narrative = describe_idea(selected)
        needs = any(
            word in normalized
            for word in ("why", "explain", "research", "compare", "analyse", "analyze")
        )
        research = (selected.get("research") or {}).get("result")
        status = "saved_idea"
        if needs and selected["state"] not in {"expired", "invalidated", "suspended"}:
            from services.bot.research import packet_for, synthesize

            fresh_research, status = await synthesize(
                store,
                {
                    **packet_for(selected, context.get("news", {})),
                    "question": question,
                    "history": history[-3:],
                },
            )
            research = fresh_research or research
        if research:
            narrative += (
                f"\n\nResearch thesis: {research['thesis']}\n\nCounterargument: {research['counterargument']}"
                f"\n\nNext observation: {research['next_observation']}"
            )
        return {
            "answer": narrative,
            "as_of": context["as_of"],
            "sources": [
                {
                    "source": f"Idea {selected['id']}, revision {selected['revision']}; retained evidence."
                }
            ],
            "interpretation_status": status,
            "actions_taken": [],
            "order_created": False,
        }
    needs_interpretation = any(
        word in normalized
        for word in ("why", "explain", "interpret", "compare", "analyse", "analyze", "research")
    )
    interpretation, status = "", "deterministic"
    if needs_interpretation and context["analysis"].get("status") in {"current", "partial"}:
        from services.bot.research import synthesize

        analysis = context["analysis"]
        result, status = await synthesize(
            store,
            {
                "question": question,
                "history": history[-3:],
                "facts": analysis,
                "evidence_ids": analysis.get("evidence", []),
                "research_kind": "conditional hypothesis; not a verified trade idea",
            },
        )
        if result:
            interpretation = (
                f"Research hypothesis: {result['thesis']}\n\nCounterargument: {result['counterargument']}"
                f"\n\nNext observation: {result['next_observation']}"
            )
    narrative = assessment(context)
    if interpretation:
        narrative += "\n\n" + interpretation
    return {
        "answer": narrative + "\n\n" + facts(context),
        "as_of": context["as_of"],
        "sources": [{"source": "Saved Angel One observations; source times shown above"}],
        "interpretation_status": status,
        "actions_taken": [],
        "order_created": False,
    }


def describe_idea(idea: dict) -> str:
    text = (
        f"{idea['title']} — {idea['state'].replace('_', ' ')}; {idea['horizon']}.\n\n"
        f"{idea['summary']}\n\nEntry condition: {idea['trigger']}\n\n"
        f"Invalidation: {idea['invalidation']}\n\nUnderlying target scenario: {idea['target_level']}. "
        f"Valid until {idea['expires_at']}.\n\n"
    )
    if idea.get("reasons"):
        text += (
            "Checks still needed: "
            + ", ".join(reason.replace("_", " ").lower() for reason in idea["reasons"])
            + ".\n\n"
        )
    contract, economics = idea.get("contract"), idea.get("economics")
    if contract:
        text += f"Contract: {contract['underlying']} {contract['strike']} {contract['option_type']}, expiry {contract['expiry']}, lot {contract['lot_size']}.\n\n"
    if economics:
        text += (
            f"One-lot premium required: INR {economics['premium_required']}. Observed ask/bid: "
            f"{economics['entry_ask']} / {economics['exit_bid']} at {economics['quote_at']}. "
            f"Estimated net downside/upside scenarios: INR {economics['estimated_net_loss']} / "
            f"{economics['estimated_net_gain']}; five-percent reference INR {economics['loss_reference']}. "
            "These are conditional scenarios, not predicted profits or guaranteed fills.\n\n"
        )
    return text + idea["limitation"] + " No orders are placed or exits executed by this assistant."
