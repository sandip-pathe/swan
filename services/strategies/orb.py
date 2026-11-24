"""Pure evaluator for the frozen NIFTY opening-range setup definition."""

import hashlib
import json
from datetime import datetime, time, timedelta
from decimal import Decimal

from services.core.contracts import IST, ExchangeSession
from services.strategies.contracts import ORBAssessment, ORBDefinition, ORBSnapshot

ORB_DEFINITION = ORBDefinition()
DEFINITION_FINGERPRINT = hashlib.sha256(
    json.dumps(ORB_DEFINITION.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
ZERO = Decimal("0")
ONE_MINUTE = timedelta(minutes=1)


def evaluate_orb(snapshot: ORBSnapshot, session: ExchangeSession) -> ORBAssessment:
    """Assess an as-of NIFTY index snapshot without I/O or wall-clock access."""
    base: dict[str, object] = dict(
        strategy_id=ORB_DEFINITION.strategy_id,
        version=ORB_DEFINITION.version,
        definition_fingerprint=DEFINITION_FINGERPRINT,
        snapshot_id=snapshot.snapshot_id,
        as_of=snapshot.as_of.astimezone(IST),
        session_key=session.key.isoformat(),
    )
    not_applicable = snapshot.underlying != "NIFTY" or snapshot.exchange != "NSE"
    start = datetime.combine(session.key, time(9, 15), IST)
    range_end = start + timedelta(minutes=15)
    cutoff = datetime.combine(session.key, time(11, 0), IST)
    if (
        not session.verified
        or session.opens_at.astimezone(IST) != start
        or session.closes_at.astimezone(IST) <= range_end
        or snapshot.as_of.astimezone(IST).date() != session.key
    ):
        not_applicable = True
    if not_applicable:
        return ORBAssessment.model_validate({**base, "status": "NOT_APPLICABLE", "reason_codes": ("UNSUPPORTED_SCOPE",)})

    ids = [bar.evidence_id for bar in snapshot.bars]
    if len(set(ids)) != len(ids):
        raise ValueError("Evidence IDs must be unique")
    if any(bar.underlying != snapshot.underlying or bar.exchange != snapshot.exchange for bar in snapshot.bars):
        raise ValueError("Mixed instrument identity")
    if any(bar.source != snapshot.source for bar in snapshot.bars):
        raise ValueError("Mixed evidence source")
    minute_keys = [bar.opens_at.astimezone(IST) for bar in snapshot.bars]
    if len(set(minute_keys)) != len(minute_keys):
        raise ValueError("Duplicate minute bars")
    for bar in snapshot.bars:
        local_open = bar.opens_at.astimezone(IST)
        local_close = bar.closes_at.astimezone(IST)
        if local_open.date() != session.key or local_close.date() != session.key:
            raise ValueError("Bar crosses the declared session")
        if bar.opens_at < session.opens_at or bar.closes_at > session.closes_at:
            raise ValueError("Bar falls outside the declared session")

    now = snapshot.as_of.astimezone(IST)
    excluded = tuple(sorted(
        bar.evidence_id for bar in snapshot.bars
        if not bar.final or bar.closes_at > snapshot.as_of or bar.available_at > snapshot.as_of
    ))
    eligible = sorted(
        (bar for bar in snapshot.bars
         if bar.final and bar.closes_at <= snapshot.as_of and bar.available_at <= snapshot.as_of),
        key=lambda bar: bar.opens_at.astimezone(IST),
    )
    if now < start:
        return ORBAssessment.model_validate({**base, "status": "NOT_READY", "reason_codes": ("BEFORE_SESSION_OPEN",), "excluded_bar_ids": excluded})
    if now < range_end:
        return ORBAssessment.model_validate({**base, "status": "NOT_READY", "reason_codes": ("OPENING_RANGE_IN_PROGRESS",), "excluded_bar_ids": excluded})

    by_open = {bar.opens_at.astimezone(IST): bar for bar in eligible}
    opening_times = [start + i * ONE_MINUTE for i in range(15)]
    missing_open = tuple((t, t + ONE_MINUTE) for t in opening_times if t not in by_open)
    if missing_open:
        return ORBAssessment.model_validate({**base, "status": "UNAVAILABLE", "reason_codes": ("OPENING_RANGE_GAP",),
                             "excluded_bar_ids": excluded, "missing_intervals": missing_open})
    opening = [by_open[t] for t in opening_times]
    high = max(bar.high for bar in opening)
    low = min(bar.low for bar in opening)
    width = high - low
    evidence = [bar.evidence_id for bar in opening]
    common: dict[str, object] = {**base, "excluded_bar_ids": excluded, "evidence_ids": tuple(evidence),
                  "range_high": high, "range_low": low, "range_width": width}
    if width == ZERO:
        return ORBAssessment.model_validate({**common, "status": "NOT_APPLICABLE", "reason_codes": ("ZERO_WIDTH_RANGE",), "buffer": ZERO})
    buffer = width * ORB_DEFINITION.buffer_fraction
    common["buffer"] = buffer
    if now <= cutoff:
        last_close = min(now.replace(second=0, microsecond=0), cutoff)
    else:
        last_close = cutoff
    required = []
    t = range_end
    while t + ONE_MINUTE <= last_close and t + ONE_MINUTE <= cutoff:
        required.append(t)
        t += ONE_MINUTE

    rejects: list[tuple[datetime, str]] = []
    trigger = None
    missing: list[tuple[datetime, datetime]] = []
    for t in required:
        candidate = by_open.get(t)
        if candidate is None:
            missing.append((t, t + ONE_MINUTE))
            break
        bar = candidate
        close = bar.close
        upper = high + width * ORB_DEFINITION.extension_fraction
        lower = low - width * ORB_DEFINITION.extension_fraction
        if high + buffer < close <= upper or lower <= close < low - buffer:
            trigger = bar
            break
        if close > upper:
            rejects.append((bar.closes_at, "BULLISH_OVEREXTENDED"))
        elif close < lower:
            rejects.append((bar.closes_at, "BEARISH_OVEREXTENDED"))
    common["rejected_candidates"] = tuple(rejects)
    if missing:
        return ORBAssessment.model_validate({**common, "status": "UNAVAILABLE", "reason_codes": ("POST_RANGE_GAP",),
                             "missing_intervals": tuple(missing)})
    if trigger is None:
        code = "NO_TRIGGER_YET" if now < cutoff else "NO_TRIGGER_IN_WINDOW"
        return ORBAssessment.model_validate({**common, "status": "NO_SETUP", "reason_codes": (code,)})

    evidence.append(trigger.evidence_id)
    is_bull = trigger.close > high
    expires = trigger.closes_at + ONE_MINUTE
    status = ("EXPIRED" if snapshot.as_of >= expires else "BULLISH_SETUP") if is_bull else (
        "EXPIRED" if snapshot.as_of >= expires else "BEARISH_SETUP"
    )
    return ORBAssessment.model_validate({**common, "evidence_ids": tuple(evidence), "status": status,
        "reason_codes": ("TRIGGER_EXPIRED",) if status == "EXPIRED" else ("BULLISH_TRIGGER",) if is_bull else ("BEARISH_TRIGGER",),
        "trigger_evidence_id": trigger.evidence_id, "trigger_closes_at": trigger.closes_at,
        "trigger_close": trigger.close, "invalidation": high - buffer if is_bull else low + buffer,
        "target": trigger.close + width if is_bull else trigger.close - width, "expires_at": expires})
