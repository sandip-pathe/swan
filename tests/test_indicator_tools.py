from datetime import datetime, timedelta
from decimal import Decimal

from services.core.contracts import IST
from services.market.indicators import indicator_series


def fixture(count=20):
    start = datetime(2026, 11, 23, 9, 15, tzinfo=IST)
    return {"as_of": (start + timedelta(minutes=count)).isoformat(),
            "sessions": [{"verified": True, "opens_at": start.isoformat(),
                          "closes_at": (start + timedelta(minutes=375)).isoformat()}],
            "bars": [{"opens_at": (start + timedelta(minutes=i)).isoformat(),
                      "high": str(i + 3), "low": str(i + 1), "close": str(i + 2),
                      "volume": 10, "state": "closed"} for i in range(count)]}


def test_vwap_weighted_hlc3_and_dema_warmup_on_linear_prices():
    result = indicator_series(fixture())
    assert Decimal(result["vwap"][-1]["value"]) == Decimal("11.5")
    assert len(result["dema"]) == 4  # first value follows 17 complete bars
    assert Decimal(result["dema"][-1]["value"]) == Decimal(21)
    weighted = fixture(2)
    weighted["bars"][1]["volume"] = 30
    assert Decimal(indicator_series(weighted)["vwap"][-1]["value"]) == Decimal("2.75")


def test_missing_bar_invalidates_session_vwap_and_restarts_dema():
    data = fixture(40)
    del data["bars"][10]
    result = indicator_series(data)
    assert len(result["vwap"]) == 10
    assert result["latest"]["vwap"]["value"] is None
    assert result["latest"]["dema"]["status"] == "AVAILABLE"
    assert result["dema"][0]["time"] == int(datetime.fromisoformat(data["bars"][26]["opens_at"]).timestamp())
    data = fixture()
    data["bars"][0]["volume"] = None
    assert indicator_series(data)["vwap"] == []
    assert len(indicator_series(data)["dema"]) == 4


def test_five_minute_tool_requires_complete_buckets():
    data = fixture(90)
    result = indicator_series(data, minutes=5)
    assert len(result["vwap"]) == 18 and len(result["dema"]) == 2
    del data["bars"][2]
    assert indicator_series(data, minutes=5)["vwap"] == []
