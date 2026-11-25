"""Five persisted daily editorial slots; deterministic qualification before AI."""

import json
from datetime import datetime, time, timedelta
from decimal import Decimal

from services.core.contracts import IST

SLOTS = (time(9, 35), time(10, 30), time(11, 30), time(13), time(14, 30))


def slot_key(now: datetime) -> str | None:
    local = now.astimezone(IST)
    if local.time() >= time(15, 25):
        return None
    passed = [i for i, stamp in enumerate(SLOTS) if stamp <= local.time()]
    return f"curation:{local.date()}:{passed[-1]}" if passed else None


def claim(store, now: datetime, insight_id: str) -> bool:
    key = slot_key(now)
    if key is None:
        return False
    with store.connect() as db:
        inserted = bool(
            db.execute(
                "INSERT OR IGNORE INTO documents VALUES (?,?)",
                (key, json.dumps(insight_id)),
            ).rowcount
        )
        row = db.execute("SELECT payload FROM documents WHERE key=?", (key,)).fetchone()
        return inserted or bool(row and json.loads(row[0]) == insight_id)


def score(candidate: dict) -> int:
    if candidate["horizon"] == "weekly":
        return 60 if candidate.get("evidence_ids") else 0
    facts = candidate["facts"]
    if facts.get("status") != "current" or candidate["state"] != "trigger_pending":
        return 0
    efficiency = Decimal(facts.get("efficiency20", "0"))
    if candidate["strategy"] != "failed-break-v1" and efficiency < Decimal("0.25"):
        return 0
    return min(
        95, 60 + int(efficiency * 25) + (10 if candidate["strategy"] == "range-retest-v1" else 0)
    )


def briefing(store, now: datetime, market: dict, news: dict):
    key = slot_key(now)
    if key is None:
        return
    held = store.read(key)
    if held and store.idea(held):
        return
    index = int(key.rsplit(":", 1)[1])
    start = datetime.combine(now.astimezone(IST).date(), SLOTS[index], IST)
    # Let supported ideas take this slot first. Never backfill missed slots with stale data.
    if now - start < timedelta(minutes=15):
        return
    ident = key + ":insight"
    at = market.get("as_of")
    usable = (
        at
        and market.get("status") in {"current", "partial"}
        and timedelta(0) <= now - datetime.fromisoformat(at) <= timedelta(minutes=3)
    )
    lines = []
    if usable:
        lines.append(f"SENSEX last completed close: {market.get('last_close')} at {at}.")
        if market.get("trend"):
            lines.append("Recent price is " + market["trend"].replace("_", " ") + ".")
        if market.get("range_high"):
            lines.append(f"Opening range: {market['range_low']} to {market['range_high']}.")
    else:
        lines.append("A fresh completed-price window is unavailable for this update.")
    items = [
        row
        for row in news.get("items", [])
        if row.get("market_relevant")
        and row.get("published_at")
        and timedelta(0) <= now - datetime.fromisoformat(row["published_at"]) <= timedelta(days=1)
    ][:2]
    for row in items:
        lines.append(f"{row['title']} ({row['source']}, {row['published_at']}).")
    lines.append("No setup passed the publication checks in this window.")
    value = {
        "id": ident,
        "kind": "brief",
        "as_of": now.isoformat(),
        "title": "SENSEX market brief",
        "summary": " ".join(lines),
        "limitation": "Source times identify the observations used; this brief is not an entry signal.",
        "facts": {
            "source": market.get("source", "unavailable"),
            "news": [
                {key: row.get(key) for key in ("title", "url", "published_at")} for row in items
            ],
        },
        "ai_used": False,
    }
    if claim(store, now, ident):
        store.publish(value)
