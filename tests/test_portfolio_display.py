"""Portfolio display never promotes partial/stale valuation to spendable equity."""

# ruff: noqa: F811
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from test_durable import cycle, durable, observed  # noqa: F401
from test_instrument_search import client_for
from test_manual_amend import amendable  # noqa: F401
from test_manual_execution import human, submit  # noqa: F401

from services.api import portfolio as api
from services.core.models import Account, PaperOrder
from services.worker.models import LatestMarketQuote

pytestmark = pytest.mark.integration


@pytest.fixture
def valued(amendable, monkeypatch):
    h = amendable
    monkeypatch.setattr(api, "utc_now", lambda: h.d.clock.now)
    return h


def read(h):
    with client_for(h.d.engine, h.d.account) as client:
        response = client.get("/api/paper/portfolio")
        assert response.status_code == 200, response.text
        return response.json()


def test_flat_reservations_do_not_reduce_equity_or_fake_pnl(valued):
    h, d = valued, valued.d
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
    result = read(h)
    assert result["status"] == "FLAT" and result["reconciled"]
    assert result["fee_basis"] == "no_fills"
    assert Decimal(result["equity"]) == 100000 and Decimal(result["available_cash"]) < 100000
    assert (
        Decimal(result["total_pnl"])
        == Decimal(result["realized_pnl"])
        == Decimal(result["unrealized_pnl"])
        == 0
    )
    assert result["valid_until"] is None
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == revision


def test_estimated_fees_are_reported_from_filled_order_not_other_venue(valued):
    from copy import deepcopy

    h, d = valued, valued.d
    cycle(d, 300)
    with Session(d.engine) as db, db.begin():
        order = db.get(PaperOrder, h.order)
        execution = deepcopy(order.execution_config)
        for schedule in execution["fee_schedules"]:
            if schedule["exchange"] == d.instrument.exchange:
                schedule["calculation_basis"] = "estimated"
                for rule in schedule["rules"]:
                    rule["sources"][0]["status"] = "assumed"
        order.execution_config = execution
    result = read(h)
    assert result["fee_basis"] == "estimated"
    assert result["reconciled"] and result["total_pnl"] is not None


def test_depth_equity_pnl_fees_then_closed_cash_and_restricted_proceeds(valued):
    h, d = valued, valued.d
    cycle(d, 300)
    result = read(h)
    assert result["status"] == "FRESH" and result["open_positions"] == 1
    equity = Decimal(result["equity"])
    assert equity == Decimal(result["cash_balance"]) + Decimal(result["open_position_value"])
    assert Decimal(result["total_pnl"]) == equity - 100000
    assert Decimal(result["unrealized_pnl"]) + Decimal(result["realized_pnl"]) == Decimal(
        result["total_pnl"]
    )
    assert Decimal(result["fees"]) > 0 and Decimal(result["total_pnl"]) < 0
    assert result["valid_until"] and result["session_pnl"] is not None
    cycle(d, 600, bid="106", ask="106.05")
    cycle(d, 900, bid="106", ask="106.05")
    closed = read(h)
    assert closed["status"] == "FLAT" and closed["open_positions"] == 0
    assert Decimal(closed["equity"]) == Decimal(closed["cash_balance"])
    assert Decimal(closed["total_pnl"]) == Decimal(closed["realized_pnl"]) > 0
    assert Decimal(closed["unrealized_pnl"]) == 0
    assert Decimal(closed["available_cash"]) < Decimal(closed["cash_balance"])


@pytest.mark.parametrize("bad", ["stale", "missing", "depth", "malformed", "missing_bid"])
def test_unusable_held_prices_never_return_zero_or_partial_equity(valued, bad):
    h, d = valued, valued.d
    cycle(d, 300)
    if bad == "stale":
        d.clock.now += timedelta(seconds=3)
    else:
        with Session(d.engine) as db, db.begin():
            row = db.get(LatestMarketQuote, d.instrument.id)
            if bad == "missing":
                db.delete(row)
            else:
                payload = dict(row.payload)
                if bad == "missing_bid":
                    payload["bid"] = None
                elif bad == "depth":
                    payload["bid_depth"] = []
                else:
                    payload["last_price"] = "invalid-private-value"
                row.payload = payload
    result = read(h)
    assert result["status"] == ("STALE" if bad == "stale" else "UNAVAILABLE")
    assert (
        result["equity"]
        is result["total_pnl"]
        is result["unrealized_pnl"]
        is result["open_position_value"]
        is None
    )
    assert result["reconciled"] and result["realized_pnl"] is not None
    assert "invalid-private-value" not in str(result)


def test_unreconciled_account_suppresses_money_and_old_session_not_today(valued):
    h, d = valued, valued.d
    with Session(d.engine) as db, db.begin():
        account = db.get(Account, d.account)
        account.session_key -= timedelta(days=1)
    result = read(h)
    assert (
        result["status"] == "FLAT"
        and result["session_pnl"] is None
        and result["session_date"] is None
    )
    with Session(d.engine) as db, db.begin():
        db.get(Account, d.account).cash += 1
    broken = read(h)
    assert broken["status"] == "UNRECONCILED" and broken["reconciled"] is False
    assert all(
        broken[key] is None
        for key in [
            "equity",
            "available_cash",
            "cash_balance",
            "total_pnl",
            "realized_pnl",
            "unrealized_pnl",
            "fees",
        ]
    )


def test_portfolio_is_owned_and_unconfigured_owner_gets_no_other_data(valued):
    d = valued.d
    other = d.legacy.create_account(d.scenario.config, d.clock.now)
    cycle(d, 300)
    with client_for(d.engine, other) as client:
        result = client.get("/api/paper/portfolio").json()
        assert result["status"] == "FLAT" and result["open_positions"] == 0
        assert Decimal(result["fees"]) == 0
    from uuid import uuid4

    with client_for(d.engine, uuid4()) as client:
        assert client.get("/api/paper/portfolio").status_code == 409
