from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from services.core.contracts import IST, ExchangeSession
from services.market.index_history import (
    INDEX_HISTORY_SOURCE,
    IndexHistoryQuery,
    normalize_index_bars,
)
from services.market.settings import MarketSettings, ProviderError


def stamp(hour: int, minute: int) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=IST)


def session() -> ExchangeSession:
    return ExchangeSession(
        key=date(2026, 11, 20), opens_at=stamp(9, 15), closes_at=stamp(15, 30),
        calendar_source="fixture", verified=True,
    )


def query(end: datetime | None = None) -> IndexHistoryQuery:
    return IndexHistoryQuery(session=session(), start=stamp(9, 15), end=end or stamp(9, 18))


def test_query_uses_configured_nifty_index_token_and_nse():
    body = query().provider_body(MarketSettings(nifty_index_token="fixture-token"), stamp(9, 20))
    assert body == {
        "exchange": "NSE", "symboltoken": "fixture-token", "interval": "ONE_MINUTE",
        "fromdate": "2026-11-20 09:15", "todate": "2026-11-20 09:18",
    }
    with pytest.raises(ProviderError, match="TOKEN_UNAVAILABLE"):
        query().provider_body(MarketSettings.model_construct(nifty_index_token=""), stamp(9, 20))


def test_query_rejects_unsupported_session_and_oversized_window():
    with pytest.raises(ValidationError):
        IndexHistoryQuery(session=ExchangeSession(
            key=date(2026, 11, 20), opens_at=stamp(9, 0), closes_at=stamp(15, 30),
            calendar_source="fixture", verified=True,
        ), start=stamp(9, 15), end=stamp(9, 18))
    assert query(stamp(15, 30)).end == stamp(15, 30)


def test_normalizer_returns_sorted_index_bars_with_receipt_provenance():
    request = query().provider_body(MarketSettings(nifty_index_token="fixture-token"), stamp(9, 20))
    received = stamp(9, 20)
    rows = [
        ["2026-11-20T09:16:00+05:30", 100.5, 101, 100, 100.8, 0],
        ["2026-11-20T09:15:00+05:30", 100, 101, 99.5, 100.5, 0],
    ]
    result = normalize_index_bars(rows, query(), received, request)
    assert result.source == INDEX_HISTORY_SOURCE
    assert result.bars[0].opens_at == stamp(9, 15)
    assert result.bars[0].underlying == "NIFTY" and result.bars[0].exchange == "NSE"
    assert result.bars[0].available_at == received
    assert result.bars[0].final is True and len(result.response_sha256) == 64
    assert len({bar.evidence_id for bar in result.bars}) == 2


def test_normalizer_marks_unclosed_and_late_bars_and_rejects_conflicts():
    rows = [["2026-11-20T09:17:00+05:30", 101, 102, 100, 101, 0]]
    received = datetime(2026, 11, 20, 3, 47, 30, tzinfo=timezone.utc)
    late = normalize_index_bars(rows, query(), received, {})
    assert late.bars[0].final is False
    conflict = rows + [["2026-11-20T09:17:00+05:30", 101, 103, 100, 101, 0]]
    with pytest.raises(ProviderError, match="CONFLICTING_DUPLICATE"):
        normalize_index_bars(conflict, query(), stamp(9, 20), {})


def test_inclusive_provider_end_does_not_enter_half_open_assessment():
    rows = [
        [stamp(9, 17).isoformat(), 100, 102, 99, 101, 0],
        [stamp(9, 18).isoformat(), 101, 103, 100, 102, 0],
    ]
    result = normalize_index_bars(rows, query(), stamp(9, 18), {})
    assert len(result.bars) == 1
    assert result.bars[0].closes_at == query().end
    assert result.response_sha256 != normalize_index_bars(rows[:1], query(), stamp(9, 18), {}).response_sha256
    # An inclusive boundary is not permission to accept arbitrary extra minutes.
    rows[-1][0] = stamp(9, 19).isoformat()
    with pytest.raises(ProviderError, match="INVALID_BAR"):
        normalize_index_bars(rows, query(), stamp(9, 20), {})


def test_inclusive_boundary_must_still_have_valid_ohlc():
    rows = [[stamp(9, 18).isoformat(), 101, 100, 99, 102, 0]]
    with pytest.raises(ProviderError, match="INVALID_BAR"):
        normalize_index_bars(rows, query(), stamp(9, 20), {})
