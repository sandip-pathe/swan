from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from services.core.contracts import IST, ExchangeSession
from services.strategies.contracts import IndexBar, ORBSnapshot
from services.strategies.orb import evaluate_orb


def dt(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 11, 20, hour, minute, second, tzinfo=IST)


def make_bar(i: int, close: str = "101", *, final: bool = True, available=None) -> IndexBar:
    opened = dt(9, 15) + timedelta(minutes=i)
    c = Decimal(close)
    return IndexBar(
        evidence_id=f"bar-{i}", underlying="NIFTY", exchange="NSE", source="unit",
        opens_at=opened, closes_at=opened + timedelta(minutes=1),
        available_at=available or opened + timedelta(minutes=1), final=final,
        open=min(Decimal("100"), c), high=max(Decimal("102"), c), low=min(Decimal("99"), c), close=c,
    )


def setup(bars, as_of):
    session = ExchangeSession(key=date(2026, 11, 20), opens_at=dt(9, 15), closes_at=dt(15, 30),
                              calendar_source="unit", verified=True)
    snapshot = ORBSnapshot(snapshot_id="snap", source="unit", underlying="NIFTY", exchange="NSE",
                           as_of=as_of, bars=tuple(bars))
    return evaluate_orb(snapshot, session)


def opening():
    # Range H=102, L=99, W=3, buffer=.15. Keep the opening bars uniform.
    return [make_bar(i, "101") for i in range(15)]


def test_bullish_exact_levels_first_trigger_and_expiry():
    bars = opening() + [make_bar(15, "102.2"), make_bar(16, "102.2")]
    result = setup(bars, dt(9, 31, 59))
    assert result.status == "BULLISH_SETUP"
    assert result.range_high == Decimal("102") and result.range_low == Decimal("99")
    assert result.range_width == Decimal("3") and result.buffer == Decimal("0.15")
    assert result.invalidation == Decimal("101.85") and result.target == Decimal("105.2")
    assert result.trigger_evidence_id == "bar-15"
    expired = setup(bars, dt(9, 32, 1))
    assert expired.status == "EXPIRED" and expired.trigger_evidence_id == "bar-15"


def test_bearish_levels_and_strict_threshold_equality():
    # Close exactly at L-buffer is not a break; next close is bearish.
    bars = opening() + [make_bar(15, "98.85"), make_bar(16, "98.8")]
    result = setup(bars, dt(9, 32))
    assert result.status == "BEARISH_SETUP"
    assert result.trigger_evidence_id == "bar-16"
    assert result.invalidation == Decimal("99.15") and result.target == Decimal("95.8")


def test_bullish_buffer_equality_is_not_a_break():
    result = setup(opening() + [make_bar(15, "102.15"), make_bar(16, "102.16")], dt(9, 32))
    assert result.status == "BULLISH_SETUP" and result.trigger_evidence_id == "bar-16"


def test_extension_boundary_included_and_overextension_rejected():
    bars = opening() + [make_bar(15, "102.75"), make_bar(16, "102.76"), make_bar(17, "102.2")]
    result = setup(bars, dt(9, 33))
    assert result.trigger_evidence_id == "bar-15"
    rejected = setup(opening() + [make_bar(15, "102.76"), make_bar(16, "101")], dt(9, 32))
    assert rejected.status == "NO_SETUP"
    assert rejected.rejected_candidates == ((dt(9, 31), "BULLISH_OVEREXTENDED"),)


def test_no_setup_gap_delay_and_excluded_observations():
    no_setup = setup(opening(), dt(9, 30))
    assert no_setup.status == "NO_SETUP" and no_setup.reason_codes == ("NO_TRIGGER_YET",)
    gap = setup(opening()[:-1], dt(9, 30))
    assert gap.status == "UNAVAILABLE"
    late = make_bar(15, "102.2", available=dt(9, 32))
    result = setup(opening() + [late], dt(9, 31))
    assert result.status == "UNAVAILABLE" and result.excluded_bar_ids == ("bar-15",)
    provisional = make_bar(15, "102.2", final=False)
    result = setup(opening() + [provisional], dt(9, 31))
    assert result.status == "UNAVAILABLE" and "bar-15" in result.excluded_bar_ids


def test_cutoff_includes_1059_bar_and_does_not_require_later_coverage():
    bars = opening() + [make_bar(i, "102.2" if i == 104 else "101") for i in range(15, 105)]
    result = setup(bars, dt(11, 0))
    assert result.status == "BULLISH_SETUP" and result.trigger_evidence_id == "bar-104"


def test_before_open_flat_range_and_schema_validation():
    assert setup([], dt(9, 0)).status == "NOT_READY"
    assert setup([], dt(9, 29)).status == "NOT_READY"
    flat = [bar.model_copy(update={"open": Decimal("101"), "high": Decimal("101"),
                                   "low": Decimal("101"), "close": Decimal("101")}) for bar in opening()]
    assert setup(flat, dt(9, 30)).status == "NOT_APPLICABLE"
    invalid = make_bar(0, "101").model_dump()
    invalid["high"] = Decimal("1")
    with pytest.raises(ValidationError):
        IndexBar.model_validate(invalid)


def test_duplicate_ids_or_minutes_and_collection_bound_rejected():
    with pytest.raises(ValueError, match="unique|Duplicate minute"):
        setup(opening() + [opening()[0]], dt(9, 30))
    with pytest.raises(ValidationError):
        ORBSnapshot(snapshot_id="x", source="unit", underlying="NIFTY", exchange="NSE",
                    as_of=dt(9, 30), bars=tuple(opening() * 27))
    duplicate_minute = opening()[0].model_dump()
    duplicate_minute["evidence_id"] = "different-id"
    with pytest.raises(ValueError, match="unique|Duplicate minute"):
        setup(opening() + [IndexBar.model_validate(duplicate_minute)], dt(9, 30))


def test_mixed_identity_and_source_rejected():
    with pytest.raises(ValueError, match="identity"):
        setup(opening()[:14] + [opening()[14].model_copy(update={"underlying": "SENSEX"})], dt(9, 30))
    with pytest.raises(ValueError, match="source"):
        setup(opening()[:14] + [opening()[14].model_copy(update={"source": "other"})], dt(9, 30))


def test_future_bar_is_excluded_without_changing_past_calculation():
    bars = opening() + [make_bar(15, "102.2")]
    known = setup(bars, dt(9, 31))
    future = make_bar(16, "999")
    with_future = setup(bars + [future], dt(9, 31))
    assert known.status == with_future.status == "BULLISH_SETUP"
    assert known.trigger_evidence_id == with_future.trigger_evidence_id
    assert known.target == with_future.target
    assert with_future.excluded_bar_ids == ("bar-16",)


def test_unsupported_session_and_underlying_are_not_applicable():
    bars = opening()
    session = ExchangeSession(key=date(2026, 11, 20), opens_at=dt(9, 0), closes_at=dt(15, 30),
                              calendar_source="unit", verified=True)
    snapshot = ORBSnapshot(snapshot_id="snap", source="unit", underlying="NIFTY", exchange="NSE",
                           as_of=dt(9, 30), bars=tuple(bars))
    assert evaluate_orb(snapshot, session).status == "NOT_APPLICABLE"
    wrong = snapshot.model_copy(update={"underlying": "SENSEX"})
    assert evaluate_orb(wrong, ExchangeSession(key=date(2026, 11, 20), opens_at=dt(9, 15),
        closes_at=dt(15, 30), calendar_source="unit", verified=True)).status == "NOT_APPLICABLE"


def test_timezone_equivalence_and_order_independence():
    from datetime import timezone

    bars = opening() + [make_bar(15, "102.2")]
    a = setup(bars, dt(9, 31))
    b = setup(list(reversed(bars)), dt(4, 1).replace(tzinfo=timezone.utc))
    assert a.model_dump(mode="json") == b.model_dump(mode="json")
