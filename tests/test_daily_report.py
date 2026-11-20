"""Daily reporting preserves cost allocation and isolates account records."""

# ruff: noqa: F811
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from test_durable import cycle, durable, observed  # noqa: F401
from test_instrument_search import client_for
from test_manual_amend import amendable  # noqa: F401
from test_manual_execution import human, submit  # noqa: F401

from services.api import daily_report as api
from services.core.contracts import IST
from services.core.models import Account, PaperFill, PaperPosition


def test_cross_day_partial_sales_allocate_rounding_cumulatively():
    start = datetime(2026, 11, 10, tzinfo=UTC)
    buys = [PaperFill(quantity=3, price=Decimal(100), fees=Decimal(1), timestamp=start)]
    sells = [
        PaperFill(
            quantity=1, price=Decimal(price), fees=Decimal(1), timestamp=start + timedelta(days=i)
        )
        for i, price in enumerate((110, 120, 130), 1)
    ]
    results = [
        api.realized_during(buys, sells, start + timedelta(days=i), start + timedelta(days=i + 1))
        for i in (1, 2, 3)
    ]
    assert results == [Decimal("8.67"), Decimal("18.66"), Decimal("28.67")]
    assert sum(results) == Decimal("56.00")


@pytest.mark.integration
def test_report_empty_filled_and_unreconciled(amendable, monkeypatch):
    d = amendable.d
    monkeypatch.setattr(api, "utc_now", lambda: d.clock.now + timedelta(microseconds=1))
    day = d.clock.now.astimezone(IST).date().isoformat()
    with client_for(d.engine, d.account) as client:

        def get():
            response = client.get("/api/paper/daily-report", params={"day": day})
            assert response.status_code == 200, response.text
            return response.json()

        empty = get()
        assert empty["status"] == "RECONCILED"
        assert empty["fill_count"] == 0 and empty["realized_pnl"] == "0.00"
        cycle(d, 300)
        cycle(d, 600, bid="106", ask="106.05")
        cycle(d, 900, bid="106", ask="106.05")
        result = get()
        assert result["fill_count"] >= 2
        assert result["buy_units"] == result["sell_units"] == 25
        assert result["open_units_at_cutoff"] == 0
        with Session(d.engine) as db:
            position = db.query(PaperPosition).filter_by(account_id=d.account).one()
            assert Decimal(result["realized_pnl"]) == position.realized_pnl
        assert len(result["fills"]) == result["fill_count"]
        assert client.get("/api/paper/daily-report?day=2999-01-01").status_code == 422
        assert client.get("/api/paper/daily-report?day=bad").status_code == 422
        with Session(d.engine) as db, db.begin():
            db.get(Account, d.account).cash += Decimal(1)
        broken = get()
        assert broken["status"] == "UNRECONCILED"
        assert all(
            broken[key] is None
            for key in (
                "realized_pnl",
                "fees",
                "cash_opening",
                "cash_at_cutoff",
                "cash_movement",
                "open_units_at_cutoff",
            )
        )
    with client_for(d.engine, uuid4()) as client:
        assert client.get("/api/paper/daily-report", params={"day": day}).status_code == 409
