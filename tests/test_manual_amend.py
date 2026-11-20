"""Amendments retain one entry and reprice reservations under the account lock."""

# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_durable import cycle, durable, observed  # noqa: F401
from test_instrument_search import client_for
from test_manual_execution import human, submit  # noqa: F401

from services.api import paper_actions
from services.core.models import (
    Account,
    ManualIntentRecord,
    PaperOrder,
    PaperOrderEvent,
    PaperPosition,
)
from services.paper import manual
from services.paper.accounting import reconcile_account
from services.paper.amend import ManualAmendService
from services.worker.models import LatestMarketQuote

pytestmark = pytest.mark.integration


@pytest.fixture
def amendable(human, monkeypatch):
    h, d = human, human.d
    h.order = UUID(submit(h)["order_id"])
    with Session(d.engine) as db, db.begin():
        quote = observed(d)
        db.merge(
            LatestMarketQuote(
                instrument_id=d.instrument.id,
                payload=quote.model_dump(mode="json"),
                timestamp=quote.timestamp,
            )
        )
        h.amend_revision = db.get(Account, d.account).revision
    monkeypatch.setattr(manual, "load_session", lambda exchange, now: d.scenario.session)
    h.amender = ManualAmendService(d.engine, d.account, clock=lambda: d.clock.now)
    monkeypatch.setattr(
        paper_actions,
        "ManualAmendService",
        lambda engine, owner: ManualAmendService(engine, owner, clock=lambda: d.clock.now),
    )
    return h


def change(h, key=None, **kwargs):
    return h.amender.amend(
        h.order,
        kwargs.get("revision", h.amend_revision),
        Decimal(kwargs.get("entry", "101")),
        Decimal(kwargs.get("stop", "97")),
        Decimal(kwargs.get("target", "107")),
        key,
    )


def test_amend_preview_readonly_then_atomic_retry_and_protection(amendable):
    h, d = amendable, amendable.d
    with Session(d.engine) as db:
        original = db.get(PaperOrder, h.order).request_payload
        expiry = db.get(PaperOrder, h.order).expires_at
    d.clock.now += timedelta(milliseconds=100)
    preview = change(h)
    assert Decimal(preview["before"]["entry"]) == 100 and Decimal(preview["after"]["entry"]) == 101
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == h.amend_revision
        assert db.scalar(select(func.count()).select_from(ManualIntentRecord)) == 1
    key = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: change(h, key), range(2)))
    assert results[0] == results[1] and results[0]["amended"]
    with Session(d.engine) as db:
        order = db.get(PaperOrder, h.order)
        assert order.limit_price == 101 and order.expires_at <= expiry
        assert order.request_payload == original
        assert order.manual_intent_id == key
        assert order.reserved_cash == order.cash_budget
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(PaperOrderEvent)
                .where(PaperOrderEvent.kind == "AMENDED")
            )
            == 1
        )
        assert reconcile_account(db, db.get(Account, d.account)) == []
    assert submit(h)["order_id"] == str(h.order)
    cycle(d, 300)
    with Session(d.engine) as db:
        assert db.get(PaperOrder, h.order).filled_quantity == 0
    cycle(d, 500)
    with Session(d.engine) as db:
        position = db.scalar(select(PaperPosition))
        assert position.stop_loss == 97 and position.target == 107
        assert reconcile_account(db, db.get(Account, d.account)) == []
    d.clock.now += timedelta(days=1)
    assert change(h, key)["status"] == "FILLED"


def test_rejections_leave_order_and_reservations_unchanged(amendable):
    h, d = amendable, amendable.d
    for kwargs, reason in [
        ({"revision": h.amend_revision - 1}, "PREVIEW_ACCOUNT_CHANGED"),
        ({"entry": "100.01"}, "OFF_TICK"),
        ({"stop": "1"}, "RISK_LIMIT"),
    ]:
        with pytest.raises(ValueError, match=reason):
            change(h, uuid4(), **kwargs)
    with Session(d.engine) as db:
        assert db.get(PaperOrder, h.order).limit_price == 100
        assert db.get(Account, d.account).revision == h.amend_revision
        assert db.scalar(select(func.count()).select_from(ManualIntentRecord)) == 1
        assert reconcile_account(db, db.get(Account, d.account)) == []
    cycle(d, 300)
    with pytest.raises(ValueError, match="MANUAL_AMEND_UNAVAILABLE"):
        change(h, uuid4())


def test_api_ownership_strict_input_and_command_identity(amendable):
    h, d = amendable, amendable.d
    body = dict(
        expected_account_revision=h.amend_revision, entry="101", stop_loss="97", target="107"
    )
    other = d.legacy.create_account(d.scenario.config, d.clock.now)
    with client_for(d.engine, other) as client:
        assert (
            client.post(f"/api/paper/orders/{h.order}/amend/preview", json=body).status_code == 404
        )
    with client_for(d.engine, d.account) as client:
        assert (
            client.post(
                f"/api/paper/orders/{h.order}/amend/preview", json={**body, "quantity": 50}
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/paper/orders/{h.order}/amend/preview", json={**body, "stop_loss": "110"}
            ).status_code
            == 422
        )
        assert (
            client.post(f"/api/paper/orders/{h.order}/amend/preview", json=body).status_code == 200
        )
        key = str(uuid4())
        response = client.post(
            f"/api/paper/orders/{h.order}/amend", json={**body, "request_id": key}
        )
        assert response.status_code == 200, response.text
        assert (
            client.post(
                f"/api/paper/orders/{h.order}/amend",
                json={**body, "request_id": key, "target": "108"},
            ).json()["detail"]
            == "MANUAL_REQUEST_CONFLICT"
        )


def test_expired_quote_cancel_and_second_request_cannot_mutate(amendable):
    h, d = amendable, amendable.d
    key = uuid4()
    change(h, key)
    with pytest.raises(ValueError, match="PREVIEW_ACCOUNT_CHANGED"):
        change(h, uuid4())
    d.clock.now += timedelta(seconds=3)
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
    with pytest.raises(ValueError):
        change(h, uuid4(), revision=revision)
    assert change(h, key)["amended"]


@pytest.mark.parametrize("blocked", ["cancel", "pause", "closed", "stale_quote", "config"])
def test_changed_execution_conditions_fail_without_mutation(amendable, monkeypatch, blocked):
    h, d = amendable, amendable.d
    if blocked == "cancel":
        h.amender.ledger.cancel(d.account, h.order, "cancel-before-amend", d.clock.now)
    elif blocked == "pause":
        with Session(d.engine) as db, db.begin():
            db.get(Account, d.account).enabled = False
    elif blocked == "closed":
        monkeypatch.setattr(manual, "load_session", lambda exchange, now: None)
    elif blocked == "stale_quote":
        with Session(d.engine) as db, db.begin():
            row = db.get(LatestMarketQuote, d.instrument.id)
            payload = dict(row.payload)
            payload["timestamp"] = (d.clock.now - timedelta(seconds=30)).isoformat()
            row.payload = payload
    else:
        with Session(d.engine) as db, db.begin():
            order = db.get(PaperOrder, h.order)
            config = dict(order.execution_config)
            config["version"] = "different-frozen-version"
            order.execution_config = config
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
        cash = db.get(PaperOrder, h.order).reserved_cash
    with pytest.raises(ValueError):
        change(h, uuid4(), revision=revision)
    with Session(d.engine) as db:
        order = db.get(PaperOrder, h.order)
        assert order.manual_intent_id == h.request and order.reserved_cash == cash
        assert db.scalar(select(func.count()).select_from(ManualIntentRecord)) == 1
        assert db.get(Account, d.account).revision == revision


def test_workspace_projects_revised_terms_and_keeps_original_plan_link(amendable):
    h, d = amendable, amendable.d
    change(h, uuid4())
    with client_for(d.engine, d.account) as client:
        data = client.get("/api/workspace").json()
        order = next(o for o in data["active_orders"] if o["id"] == str(h.order))
        assert order["can_amend"] is True
        assert Decimal(order["manual_terms"]["entry_limit"]) == 101
        assert Decimal(order["manual_terms"]["stop_loss"]) == 97
        plans = client.get("/api/paper/plans").json()
        assert plans["rows"][0]["order_id"] == str(h.order)
