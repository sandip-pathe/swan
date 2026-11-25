"""Completed-bar calculations; no model-generated prices or trading decisions."""

import hashlib
from datetime import datetime, timedelta
from decimal import Decimal

from services.strategies.contracts import IndexBar


def analyze(
    bars: list[IndexBar], now: datetime, session_open: datetime, underlying: str = "NIFTY"
) -> dict:
    if not bars:
        return {"status": "insufficient", "reason": "No completed candles received."}
    ordered = sorted(bars, key=lambda bar: bar.opens_at)
    if len({bar.opens_at for bar in ordered}) != len(ordered):
        raise ValueError("DUPLICATE_BAR")
    if any(
        not bar.final
        or bar.closes_at > now
        or bar.available_at > now
        or bar.underlying != underlying
        or bar.opens_at < session_open
        for bar in ordered
    ):
        raise ValueError("INVALID_ANALYSIS_INPUT")
    if ordered[0].opens_at != session_open or any(
        right.opens_at != left.closes_at for left, right in zip(ordered, ordered[1:])
    ):
        missing = []
        present = {bar.opens_at for bar in ordered}
        minute = session_open
        while minute < ordered[-1].closes_at:
            if minute not in present:
                missing.append(minute.isoformat())
            minute += timedelta(minutes=1)
        return {
            "status": "insufficient",
            "reason": "Candle coverage has gaps; scans withheld.",
            "underlying": underlying,
            "missing_minutes": missing,
            "bars": len(ordered),
            "as_of": ordered[-1].closes_at.isoformat(),
            "last_close": str(ordered[-1].close),
            "source": ordered[-1].source,
        }
    last = ordered[-1]
    if now - last.closes_at > timedelta(minutes=3):
        return {
            "status": "historical",
            "reason": "Latest completed candle is too old for scans.",
            "as_of": last.closes_at.isoformat(),
            "underlying": underlying,
            "last_close": str(last.close),
            "source": last.source,
        }
    closes = [bar.close for bar in ordered]
    result = {
        "status": "current",
        "underlying": underlying,
        "as_of": last.closes_at.isoformat(),
        "last_close": str(last.close),
        "bars": len(ordered),
        "trend": "warming_up",
        "range_state": "warming_up",
        "sma20": None,
        "range_high": None,
        "range_low": None,
        "evidence": [bar.evidence_id for bar in ordered[-20:]],
        "rule": f"{underlying.lower()}-range15-sma20-v1",
        "source": last.source,
    }
    if len(ordered) >= 20:
        average = sum(closes[-20:]) / Decimal(20)
        result.update(
            sma20=str(average),
            trend=(
                "above_average"
                if last.close > average
                else "below_average"
                if last.close < average
                else "at_average"
            ),
        )
    if len(ordered) > 15:
        high = max(bar.high for bar in ordered[:15])
        low = min(bar.low for bar in ordered[:15])
        result.update(
            range_high=str(high),
            range_low=str(low),
            range_state=(
                "above_opening_range"
                if last.close > high
                else "below_opening_range"
                if last.close < low
                else "inside_range"
            ),
        )
    return result


def insight_for(analysis: dict, previous: dict | None, session: str) -> dict | None:
    if analysis.get("status") != "current" or analysis["trend"] == "warming_up":
        return None
    state = (analysis["trend"], analysis["range_state"])
    if (
        previous
        and previous.get("session") == session
        and state == (previous.get("trend"), previous.get("range_state"))
    ):
        return None
    identity = f"{session}:{analysis['as_of']}:{analysis['rule']}:{state}"
    underlying = analysis.get("underlying", "NIFTY")
    return {
        "id": hashlib.sha256(identity.encode()).hexdigest(),
        "session": session,
        "as_of": analysis["as_of"],
        "title": f"{underlying} context changed" if previous else f"{underlying} session context",
        "facts": analysis,
        "summary": f"The completed candle closed {analysis['trend'].replace('_', ' ')} "
        f"and {analysis['range_state'].replace('_', ' ')}.",
        "limitation": "A descriptive condition, not a prediction. Reassess on the next "
        "completed candle; gaps or stale data invalidate current context.",
    }
