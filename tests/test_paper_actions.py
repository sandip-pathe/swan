"""Paper controls use durable account locks and the real protective fill path."""

# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_durable import admit, cycle, durable, observed  # noqa: F401
from test_instrument_search import client_for
from test_manual_execution import human, submit  # noqa: F401

from services.api import paper_actions as api
from services.core.models import Account, AuditEvent, PaperFill, PaperOrder, PaperPosition
from services.paper.accounting import reconcile_account
from services.paper.user_actions import PaperUserActions
from services.worker.models import RuntimeControl

pytestmark = pytest.mark.integration


@pytest.fixture
def actions(human, monkeypatch):
    h, d = human, human.d
    h.actions = PaperUserActions(d.engine, d.account, clock=lambda: d.clock.now)
    monkeypatch.setattr(
        api,
        "PaperUserActions",
        lambda engine, owner: PaperUserActions(engine, owner, clock=lambda: d.clock.now),
    )
    return h


def test_cancel_entry_retries_release_reservations_and_prevent_later_fill(actions):
    h, d = actions, actions.d
    order = UUID(submit(h)["order_id"])
    key = uuid4()
    with client_for(d.engine, d.account) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(
                    lambda _: client.post(
                        f"/api/paper/orders/{order}/cancel", json={"request_id": str(key)}
                    ),
                    range(2),
                )
            )
        assert all(r.status_code == 200 for r in responses)
        assert responses[0].json()["status"] == "CANCELLED"
    cycle(d, 300)
    with Session(d.engine) as db:
        entry = db.get(PaperOrder, order)
        assert entry.filled_quantity == 0 and entry.reserved_cash == entry.reserved_risk == 0
        assert db.scalar(select(func.count()).select_from(PaperFill)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.kind == "USER_ENTRY_CANCEL")
            )
            == 1
        )
        assert reconcile_account(db, db.get(Account, d.account)) == []


def test_fill_race_before_cancel_ack_preserves_real_position(actions, monkeypatch):
    h, d = actions, actions.d
    order = UUID(submit(h)["order_id"])
    cancel = h.actions.ledger.cancel

    def raced(*args, **kwargs):
        result = cancel(*args, **kwargs)
        if not kwargs.get("confirm"):
            d.clock.now = d.scenario.now.replace(microsecond=300000)
            h.d.service.matcher.match_order(
                d.account, order, d.instrument, observed(d, elapsed=300)
            )
        return result

    monkeypatch.setattr(h.actions.ledger, "cancel", raced)
    result = h.actions.cancel_entry(order, uuid4())
    assert result["status"] == "FILLED" and result["filled_quantity"] == d.instrument.lot_size
    with Session(d.engine) as db:
        assert db.scalar(select(PaperPosition)).quantity == d.instrument.lot_size
        assert reconcile_account(db, db.get(Account, d.account)) == []


def test_exit_signal_is_idempotent_pauses_and_fills_through_protection(actions):
    h, d = actions, actions.d
    submit(h)
    cycle(d, 300)
    with Session(d.engine) as db:
        position = db.scalar(select(PaperPosition)).id
        protective = db.scalar(select(PaperOrder).where(PaperOrder.side == "SELL")).id
    key = uuid4()
    with client_for(d.engine, d.account) as client:
        assert (
            client.post(
                f"/api/paper/orders/{protective}/cancel", json={"request_id": str(uuid4())}
            ).json()["detail"]
            == "PAPER_ENTRY_CANCEL_ONLY"
        )
        response = client.post(
            f"/api/paper/positions/{position}/exit", json={"request_id": str(key)}
        )
        assert response.status_code == 200 and response.json()["status"] == "EXIT_REQUESTED"
        assert response.json()["remaining_quantity"] == d.instrument.lot_size
        assert (
            client.post(
                f"/api/paper/positions/{position}/exit", json={"request_id": str(key)}
            ).json()
            == response.json()
        )
    with Session(d.engine) as db:
        assert not db.get(Account, d.account).enabled
        assert not db.get(RuntimeControl, d.account).resume_requested
        assert db.get(PaperPosition, position).pending_exit == "USER_EXIT"
        assert db.scalar(select(func.count()).select_from(PaperFill)) == 1
    cycle(d, 600)
    cycle(d, 900)
    assert h.actions.exit_position(position, key)["status"] == "CLOSED"
    with Session(d.engine) as db:
        assert db.get(PaperPosition, position).closed_at is not None
        assert db.scalar(select(func.count()).select_from(PaperFill)) == 2
        assert reconcile_account(db, db.get(Account, d.account)) == []


def test_exit_intent_survives_unavailable_session_without_fake_fill(actions):
    h, d = actions, actions.d
    submit(h)
    cycle(d, 300)
    with Session(d.engine) as db:
        position = db.scalar(select(PaperPosition)).id
    h.actions.exit_position(position, uuid4())
    d.service.cycle({}, {}, healthy=False)
    with Session(d.engine) as db:
        held = db.get(PaperPosition, position)
        assert held.closed_at is None and held.pending_exit is not None
        assert db.scalar(select(func.count()).select_from(PaperFill)) == 1
        assert not db.get(Account, d.account).enabled


def test_controls_owned_strict_and_request_identity_bound(actions):
    h, d = actions, actions.d
    order = UUID(submit(h)["order_id"])
    other = d.legacy.create_account(d.scenario.config, d.clock.now)
    with client_for(d.engine, other) as client:
        assert (
            client.post(
                f"/api/paper/orders/{order}/cancel", json={"request_id": str(uuid4())}
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/paper/positions/{uuid4()}/exit", json={"request_id": str(uuid4())}
            ).status_code
            == 404
        )
    key = uuid4()
    h.actions.cancel_entry(order, key)
    with Session(d.engine) as db, db.begin():
        # A second owned, real entry is unnecessary: collision is rejected against another audit kind.
        db.add(
            AuditEvent(
                id=uuid4(), account_id=d.account, kind="OTHER", timestamp=d.clock.now, details={}
            )
        )
    with client_for(d.engine, d.account) as client:
        assert (
            client.post(
                f"/api/paper/orders/{order}/cancel", json={"request_id": str(key), "confirm": True}
            ).status_code
            == 422
        )
        with Session(d.engine) as db:
            collision = db.scalar(select(AuditEvent.id).where(AuditEvent.kind == "OTHER"))
        response = client.post(
            f"/api/paper/orders/{order}/cancel", json={"request_id": str(collision)}
        )
        assert (
            response.status_code == 409
            and response.json()["detail"] == "PAPER_ACTION_REQUEST_CONFLICT"
        )


def test_workspace_links_manual_source_for_entry_position_and_protective_order(actions):
    h, d = actions, actions.d
    entry = UUID(submit(h)["order_id"])
    cycle(d, 300)
    with client_for(d.engine, d.account) as client:
        result = client.get("/api/workspace")
        assert result.status_code == 200, result.text
        data = result.json()
        position = data["positions"][0]
        assert position["entry_source"] == "HUMAN" and position["entry_order_id"] == str(entry)
        assert position["entry_manual_intent_id"] == str(h.request) and position["can_exit"]
        protective = next(o for o in data["active_orders"] if o["side"] == "SELL")
        assert protective["entry_source"] == "HUMAN" and protective["entry_order_id"] == str(entry)
        assert protective["can_cancel"] is False


def test_partial_fill_during_cancel_keeps_filled_units_and_releases_only_remainder(
    durable, monkeypatch
):
    d = durable
    order_id = admit(d)
    actions = PaperUserActions(d.engine, d.account, clock=lambda: d.clock.now)
    cancel = actions.ledger.cancel

    def raced(*args, **kwargs):
        result = cancel(*args, **kwargs)
        if not kwargs.get("confirm"):
            d.clock.now = d.scenario.now.replace(microsecond=300000)
            d.service.matcher.match_order(
                d.account, order_id, d.instrument, observed(d, elapsed=300, depth=50)
            )
        return result

    monkeypatch.setattr(actions.ledger, "cancel", raced)
    result = actions.cancel_entry(order_id, uuid4())
    assert result["status"] == "CANCELLED" and result["filled_quantity"] == 25
    with Session(d.engine) as db:
        order = db.get(PaperOrder, order_id)
        assert order.quantity > order.filled_quantity
        assert order.reserved_cash == order.reserved_risk == 0
        assert db.scalar(select(PaperPosition)).quantity == 25
        assert reconcile_account(db, db.get(Account, d.account)) == []


def test_exit_preserves_higher_priority_reason_and_retry_does_not_pause_again(actions):
    h, d = actions, actions.d
    submit(h)
    cycle(d, 300)
    with Session(d.engine) as db, db.begin():
        position = db.scalar(select(PaperPosition))
        position.pending_exit = "DAILY_LOSS_LIMIT"
        position_id = position.id
    key = uuid4()
    response = h.actions.exit_position(position_id, key)
    assert response["pending_exit"] == "DAILY_LOSS_LIMIT"
    with Session(d.engine) as db, db.begin():
        account = db.get(Account, d.account)
        revision = account.revision
        account.enabled = True
    retry = h.actions.exit_position(position_id, key)
    assert retry["new_entries_paused"] is False
    with Session(d.engine) as db:
        assert db.get(Account, d.account).revision == revision
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.kind == "USER_EXIT_REQUESTED")
            )
            == 1
        )
