"""Deterministic HLC3 session VWAP and SMA-seeded DEMA. No trade authority."""

from datetime import datetime, timedelta
from decimal import Decimal


def indicator_series(data: dict, minutes: int = 1, period: int = 9) -> dict:
    if minutes not in (1, 5, 15) or not 2 <= period <= 200:
        raise ValueError("UNSUPPORTED_INDICATOR_PARAMETERS")
    now = datetime.fromisoformat(data["as_of"])
    by_time = {datetime.fromisoformat(b["opens_at"]): b for b in data["bars"]}
    vwap, dema = [], []
    latest_expected = None
    reasons: set[str] = set()
    for session in data.get("sessions", []):
        if not session["verified"]:
            reasons.add("UNVERIFIED_SESSION")
            continue
        opening = datetime.fromisoformat(session["opens_at"])
        closing = datetime.fromisoformat(session["closes_at"])
        cursor = opening
        total_value, total_volume = Decimal(0), Decimal(0)
        vwap_valid = True
        first: list[Decimal] = []
        second: list[Decimal] = []
        ema1: Decimal | None = None
        ema2: Decimal | None = None
        alpha = Decimal(2) / (period + 1)
        while cursor + timedelta(minutes=minutes) <= min(now, closing):
            latest_expected = int(cursor.timestamp())
            parts = [by_time.get(cursor + timedelta(minutes=i)) for i in range(minutes)]
            if any(p is None or p["state"] == "provisional" for p in parts):
                vwap_valid = False
                first, second, ema1, ema2 = [], [], None, None
                reasons.add("MISSING_OR_FORMING_BAR")
                cursor += timedelta(minutes=minutes)
                continue
            rows = [p for p in parts if p is not None]
            high = max(Decimal(p["high"]) for p in rows)
            low = min(Decimal(p["low"]) for p in rows)
            close = Decimal(rows[-1]["close"])
            point = int(cursor.timestamp())
            if any(p.get("volume") is None for p in rows):
                vwap_valid = False
                reasons.add("VOLUME_UNAVAILABLE")
            if vwap_valid:
                volume = sum((Decimal(p["volume"]) for p in rows), Decimal(0))
                total_volume += volume
                total_value += (high + low + close) / 3 * volume
                if total_volume:
                    vwap.append({"time": point, "value": str(total_value / total_volume)})
            first.append(close)
            if ema1 is None and len(first) >= period:
                ema1 = sum(first[-period:], Decimal(0)) / period
            elif ema1 is not None:
                ema1 += alpha * (close - ema1)
            if ema1 is not None:
                second.append(ema1)
                if ema2 is None and len(second) >= period:
                    ema2 = sum(second[-period:], Decimal(0)) / period
                elif ema2 is not None:
                    ema2 += alpha * (ema1 - ema2)
                if ema2 is not None:
                    dema.append({"time": point, "value": str(2 * ema1 - ema2)})
            cursor += timedelta(minutes=minutes)
    latest = {}
    for name, series in (("vwap", vwap), ("dema", dema)):
        current = bool(series and series[-1]["time"] == latest_expected)
        latest[name] = {
            "status": "AVAILABLE" if current else "UNAVAILABLE",
            "value": series[-1]["value"] if current else None,
            "last_point_time": series[-1]["time"] if series else None,
            "reason": None if current else "INCOMPLETE_COVERAGE_OR_WARMUP",
        }
    return {
        "as_of": data["as_of"], "minutes": minutes, "period": period,
        "latest": latest,
        "vwap": vwap, "dema": dema, "issues": sorted(reasons),
        "method": "HLC3 session VWAP; DEMA=2*EMA(close)-EMA(EMA(close)), SMA seeds",
        "semantics": "Completed bars only. VWAP requires full session coverage and volume. "
        "DEMA warms up for 2*period-1 contiguous bars and resets each session or gap. "
        "These are observations, not stop, target or trade instructions.",
    }
