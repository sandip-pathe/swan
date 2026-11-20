"""Read-only owned histories use actual fills and bounded event pagination."""

# ruff: noqa: F811
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_durable import cycle, durable, observed  # noqa: F401
from test_instrument_search import client_for
from test_manual_amend import amendable, change  # noqa: F401
from test_manual_execution import human, submit  # noqa: F401

from services.core.models import Account, PaperFill, PaperOrder, PaperOrderEvent, PaperPosition

pytestmark = pytest.mark.integration


def test_history_amend_fill_fees_and_owned_related_protection(amendable):
    h, d = amendable, amendable.d
    change(h, uuid4())
    cycle(d, 300)
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
        fill = db.scalar(select(PaperFill).where(PaperFill.order_id == h.order))
        fees = fill.fees
        premium = fill.price * fill.quantity
        position = db.scalar(select(PaperPosition))
        position_id = position.id
        protective = db.scalar(select(PaperOrder).where(PaperOrder.side == "SELL")).id
    with client_for(d.engine, d.account) as client:
        response = client.get(f"/api/paper/orders/{h.order}/history")
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["order"]["status"] == "FILLED" and result["order"]["source"] == "HUMAN"
        assert (
            result["position"]["id"] == str(position_id)
            and result["position"]["remaining_quantity"] == 25
        )
        assert result["related_orders"][0]["id"] == str(protective)
        assert Decimal(result["fills"]["fees"]) == fees
        assert Decimal(result["fills"]["cash_movement"]) == -premium - fees
        events = {event["kind"]: event for event in result["events"]}
        assert set(events) >= {"ACCEPTED", "AMENDED", "FILL"}
        assert Decimal(events["AMENDED"]["detail"]["before"]["entry"]) == 100
        assert Decimal(events["AMENDED"]["detail"]["after"]["entry"]) == 101
        assert events["FILL"]["fill_recorded"]
        assert Decimal(events["FILL"]["detail"]["fees"]) == fees
        exit_data = client.get(f"/api/paper/orders/{protective}/history").json()
        assert exit_data["related_orders"][0]["id"] == str(h.order)
        assert exit_data["position"]["id"] == str(position_id)
        assert exit_data["fills"]["quantity"] == 0 and exit_data["fills"]["average_price"] is None
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == revision
        assert db.scalar(select(func.count()).select_from(PaperFill)) == 1
    cycle(d, 600, bid="107", ask="107.05")
    cycle(d, 900, bid="107", ask="107.05")
    with Session(d.engine) as db:
        exit_id = db.scalar(
            select(PaperOrder.id).where(PaperOrder.side == "SELL", PaperOrder.filled_quantity > 0)
        )
    with client_for(d.engine, d.account) as client:
        closed = client.get(f"/api/paper/orders/{exit_id}/history").json()
        assert closed["position"]["closed"] and closed["position"]["remaining_quantity"] == 0
        assert Decimal(closed["fills"]["cash_movement"]) > 0
        assert any(event["kind"] == "FILL" for event in closed["events"])


def test_keyset_pages_equal_timestamps_no_duplicates_or_payload_leaks(amendable):
    h, d = amendable, amendable.d
    with Session(d.engine) as db, db.begin():
        for _ in range(35):
            db.add(
                PaperOrderEvent(
                    account_id=d.account,
                    order_id=h.order,
                    event_key=str(uuid4()),
                    kind="EXPIRED",
                    timestamp=d.clock.now,
                    payload={"private_config": "NEVER_SEND_ME"},
                )
            )
        all_ids = {
            str(i)
            for i in db.scalars(
                select(PaperOrderEvent.id).where(PaperOrderEvent.order_id == h.order)
            )
        }
    seen = []
    with client_for(d.engine, d.account) as client:
        cursor = None
        while True:
            response = client.get(
                f"/api/paper/orders/{h.order}/history",
                params={"limit": 7, **({"before": cursor} if cursor else {})},
            )
            assert response.status_code == 200
            assert "NEVER_SEND_ME" not in response.text and "request_payload" not in response.text
            data = response.json()
            assert len(data["events"]) <= 7
            seen.extend(event["id"] for event in data["events"])
            cursor = data["next_before"]
            if cursor is None:
                break
        assert (
            client.get(f"/api/paper/orders/{h.order}/history", params={"limit": 101}).status_code
            == 422
        )
    assert set(seen) == all_ids and len(seen) == len(all_ids)


def test_order_and_cursor_owner_isolation_and_strict_ids(amendable):
    h, d = amendable, amendable.d
    other = d.legacy.create_account(d.scenario.config, d.clock.now)
    with Session(d.engine) as db:
        cursor = db.scalar(select(PaperOrderEvent.id).where(PaperOrderEvent.order_id == h.order))
    with client_for(d.engine, other) as client:
        assert client.get(f"/api/paper/orders/{h.order}/history").status_code == 404
    with client_for(d.engine, d.account) as client:
        assert client.get(f"/api/paper/orders/{uuid4()}/history").status_code == 404
        assert (
            client.get(
                f"/api/paper/orders/{h.order}/history", params={"before": str(uuid4())}
            ).status_code
            == 400
        )
        assert (
            client.get(
                f"/api/paper/orders/{h.order}/history", params={"before": "invalid"}
            ).status_code
            == 422
        )
        cycle(d, 300)
        with Session(d.engine) as db:
            protective = db.scalar(select(PaperOrder).where(PaperOrder.side == "SELL")).id
        assert (
            client.get(
                f"/api/paper/orders/{protective}/history", params={"before": str(cursor)}
            ).status_code
            == 400
        )


def test_cancel_ack_history_does_not_hide_filled_trade(amendable):
    h, d = amendable, amendable.d
    cycle(d, 300)
    ledger = h.amender.ledger
    ledger.cancel(d.account, h.order, "late-cancel-request", d.clock.now)
    ledger.cancel(d.account, h.order, "late-cancel-ack", d.clock.now, confirm=True)
    with client_for(d.engine, d.account) as client:
        data = client.get(f"/api/paper/orders/{h.order}/history", params={"limit": 1}).json()
        assert data["order"]["status"] == "FILLED" and data["fills"]["quantity"] == 25
        assert data["next_before"] is not None
        assert Decimal(data["fills"]["fees"]) > 0
