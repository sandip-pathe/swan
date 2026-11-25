"""At most five qualified daily insights; no publication target or scheduled filler."""

import json
from datetime import datetime
from decimal import Decimal

from services.core.contracts import IST


def claim(store, now: datetime, insight_id: str) -> bool:
    key = f"curation:{now.astimezone(IST).date()}"
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT payload FROM documents WHERE key=?", (key,)).fetchone()
        used = json.loads(row[0]) if row else []
        if insight_id in used:
            return True
        if len(used) >= 5:
            return False
        db.execute(
            "INSERT INTO documents VALUES (?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",
            (key, json.dumps(used + [insight_id])),
        )
    return True


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
