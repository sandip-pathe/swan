"""Owner-scoped execution projections must not lose old active orders in history."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from services.api.app import workspace
from services.core.models import PaperOrder

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("active_count", [1, 201])
def test_active_orders_are_separate_from_recent_history_and_owner_scoped(
    paper, scenario, db_engine, active_count
):
    engine, identifier = paper
    other = engine.create_account(scenario.config, scenario.now)
    with Session(db_engine) as db, db.begin():
        engine._persist_instrument(db, scenario.instrument)
        for index in range(active_count + 50):
            active = index < active_count
            db.add(
                PaperOrder(
                    account_id=identifier,
                    instrument_id=scenario.instrument.id,
                    idempotency_key=f"isolated-{index}",
                    side="BUY",
                    quantity=25,
                    reason="ISOLATED_API_TEST",
                    timestamp=scenario.now + timedelta(seconds=index),
                    status="OPEN" if active else "CANCELLED",
                )
            )
        foreign = PaperOrder(
            account_id=other,
            instrument_id=scenario.instrument.id,
            idempotency_key="other-owner",
            side="BUY",
            quantity=25,
            reason="OTHER_OWNER",
            timestamp=scenario.now,
            status="OPEN",
        )
        db.add(foreign)
        db.flush()
        foreign_id = str(foreign.id)
    report = workspace(
        SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=db_engine))), identifier
    )
    assert len(report["orders"]) == 50
    assert all(order["status"] == "CANCELLED" for order in report["orders"])
    assert len(report["active_orders"]) == min(active_count, 200)
    assert report["order_summary"] == {
        "active_count": active_count,
        "active_truncated": active_count > 200,
    }
    assert all(
        order["status"] == "OPEN" and order["id"] != foreign_id for order in report["active_orders"]
    )
    assert scenario.instrument.id in report["instruments"]


def test_fills_include_side_instrument_and_precise_money_with_remaining_exposure(
    paper, scenario, db_engine
):
    engine, identifier = paper
    engine.enter(
        identifier,
        scenario.decision,
        scenario.instrument,
        scenario.quote,
        scenario.envelope,
        scenario.session,
        scenario.now,
    )
    report = workspace(
        SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=db_engine))), identifier
    )
    assert len(report["fills"]) == 1
    fill = report["fills"][0]
    assert fill["side"] == "BUY"
    assert fill["instrument_id"] == scenario.instrument.id
    assert isinstance(fill["fees"], str) and isinstance(fill["price"], str)
    position = report["positions"][0]
    assert position["remaining_quantity"] == position["quantity"] - position["closed_quantity"]
    assert report["instruments"][scenario.instrument.id]["lot_size"] == scenario.instrument.lot_size
