"""Chart annotations only expose retained, owned fills and current position settings."""

# ruff: noqa: F811
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_durable import cycle, durable, observed  # noqa: F401
from test_instrument_search import client_for
from test_manual_amend import amendable  # noqa: F401
from test_manual_execution import human, submit  # noqa: F401

from services.api import chart_trades as api
from services.core.contracts import IST
from services.core.models import Account, PaperPosition

pytestmark = pytest.mark.integration


@pytest.fixture
def chart_owner(amendable, monkeypatch):
    monkeypatch.setattr(api, "utc_now", lambda: amendable.d.clock.now)
    return amendable


def read(h, day=None, owner=None, instrument=None):
    d = h.d
    with client_for(d.engine, owner or d.account) as client:
        return client.get(
            "/api/paper/chart-trades",
            params={
                "instrument_id": instrument or d.instrument.id,
                "day": str(day or d.clock.now.astimezone(IST).date()),
            },
        )


def test_exact_contract_owned_fill_position_and_pending_protective_order(chart_owner):
    h, d = chart_owner, chart_owner.d
    cycle(d, 300)
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
    response = read(h)
    assert response.status_code == 200, response.text
    data = response.json()
    assert (
        data["current_day"]
        and len(data["fills"]) == len(data["positions"]) == len(data["exit_orders"]) == 1
    )
    fill, held, exit = data["fills"][0], data["positions"][0], data["exit_orders"][0]
    assert fill["side"] == "BUY" and fill["quantity"] == 25
    assert fill["order_id"] == held["entry_order_id"] == str(h.order)
    assert held["remaining_quantity"] == 25 and exit["position_id"] == held["id"]
    assert exit["order_type"] == "STOP_MARKET" and exit["status"] == "OPEN"
    assert "execution_config" not in response.text and "request_payload" not in response.text
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == revision


def test_historical_date_never_draws_current_position_levels(chart_owner):
    h, d = chart_owner, chart_owner.d
    cycle(d, 300)
    day = d.clock.now.astimezone(IST).date()
    d.clock.now += timedelta(days=1)
    data = read(h, day=day).json()
    assert not data["current_day"] and len(data["fills"]) == 1
    assert data["positions"] == data["exit_orders"] == []
    assert read(h).json()["fills"] == []


def test_closed_position_has_fill_markers_without_current_levels(chart_owner):
    h, d = chart_owner, chart_owner.d
    cycle(d, 300)
    cycle(d, 600, bid="106", ask="106.05")
    cycle(d, 900, bid="106", ask="106.05")
    result = read(h).json()
    assert [fill["side"] for fill in result["fills"]] == ["SELL", "BUY"]
    assert result["positions"] == result["exit_orders"] == []
    with Session(d.engine) as db:
        assert db.scalar(select(PaperPosition)).closed_at is not None


def test_account_contract_date_isolation_and_input_bounds(chart_owner):
    h, d = chart_owner, chart_owner.d
    cycle(d, 300)
    other = d.legacy.create_account(d.scenario.config, d.clock.now)
    for response in [
        read(h, owner=other),
        read(h, instrument="different-contract"),
        read(h, day=d.clock.now.astimezone(IST).date() + timedelta(days=1)),
    ]:
        assert response.status_code == 200 and response.json()["fills"] == []
        assert response.json()["positions"] == []
    assert read(h, instrument="x" * 101).status_code == 422
    assert read(h, day="invalid").status_code == 422
