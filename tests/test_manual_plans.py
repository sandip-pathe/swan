"""Durable human planning stays separate from AI approval and order execution."""

# Imported pytest fixtures are resolved through test parameter injection.
# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_instrument_search import client_for
from test_order_preview import counts, preview_case  # noqa: F401

from services.api import manual_plans as api
from services.core.models import Account, AuditEvent, ManualPaperPlan


def body(owner, item, engine, key=None):
    with Session(engine) as db:
        revision = db.get(Account, owner).revision
    return dict(
        instrument_id=item.id,
        lots=1,
        entry="100",
        stop_loss="96",
        target="106",
        idempotency_key=str(key or uuid4()),
        expected_account_revision=revision,
    )


@pytest.mark.integration
def test_save_idempotency_canonical_prices_and_no_execution(preview_case, db_engine):
    owner, item, _ = preview_case
    before = counts(db_engine)
    payload = body(owner, item, db_engine)
    with client_for(db_engine, owner) as client:
        first = client.post("/api/paper/plans", json=payload)
        assert first.status_code == 200, first.text
        plan = first.json()
        assert (
            plan["source"] == "human"
            and plan["order_id"] is None
            and plan["submission_ready"] is False
        )
        assert (
            client.post(
                "/api/paper/plans",
                json={**payload, "entry": "100.00", "expected_account_revision": 999},
            ).json()["id"]
            == plan["id"]
        )
        assert client.post("/api/paper/plans", json={**payload, "target": "107"}).status_code == 409
        listed = client.get("/api/paper/plans", params={"instrument_id": item.id}).json()
        assert len(listed["rows"]) == 1 and listed["rows"][0]["inputs"]["entry"] == "100.00"
    assert counts(db_engine)[:-1] == before[:-1]
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(ManualPaperPlan)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.kind == "MANUAL_PAPER_PLAN_SAVED")
            )
            == 1
        )
        assert db.get(Account, owner).revision == payload["expected_account_revision"]


@pytest.mark.integration
def test_saved_plan_ownership_archive_and_capacity(
    preview_case, db_engine, paper, scenario, monkeypatch
):
    owner, item, _ = preview_case
    other = paper[0].create_account(scenario.config, scenario.now)
    monkeypatch.setattr(api, "PLAN_LIMIT", 1)
    payload = body(owner, item, db_engine)
    with client_for(db_engine, owner) as client:
        plan = client.post("/api/paper/plans", json=payload).json()
        assert (
            client.post(
                "/api/paper/plans", json={**payload, "idempotency_key": str(uuid4())}
            ).status_code
            == 409
        )
    with client_for(db_engine, other) as client:
        assert client.get("/api/paper/plans").json()["rows"] == []
        assert client.post(f"/api/paper/plans/{plan['id']}/archive").status_code == 404
    with client_for(db_engine, owner) as client:
        endpoint = f"/api/paper/plans/{plan['id']}/archive"
        assert client.post(endpoint).json()["status"] == "archived"
        assert client.post(endpoint).json()["status"] == "archived"
        assert client.get("/api/paper/plans").json()["rows"] == []
        assert client.post("/api/paper/plans", json=payload).json()["status"] == "archived"
        assert (
            client.post(
                "/api/paper/plans", json={**payload, "idempotency_key": str(uuid4())}
            ).status_code
            == 200
        )
    with Session(db_engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.kind == "MANUAL_PAPER_PLAN_ARCHIVED")
            )
            == 1
        )


@pytest.mark.integration
def test_account_changes_and_untrusted_approval_fields_fail(preview_case, db_engine):
    owner, item, _ = preview_case
    payload = body(owner, item, db_engine)
    with Session(db_engine) as db, db.begin():
        db.get(Account, owner).revision += 1
    with client_for(db_engine, owner) as client:
        assert (
            client.post("/api/paper/plans", json=payload).json()["detail"]
            == "PREVIEW_ACCOUNT_CHANGED"
        )
        for extra in [dict(source="AI"), dict(status="APPROVED"), dict(account_id=str(uuid4()))]:
            assert client.post("/api/paper/plans", json={**payload, **extra}).status_code == 422
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(ManualPaperPlan)) == 0


@pytest.mark.integration
def test_concurrent_retries_create_one_plan(preview_case, db_engine):
    owner, item, _ = preview_case
    payload = body(owner, item, db_engine)
    with client_for(db_engine, owner) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(lambda _: client.post("/api/paper/plans", json=payload), range(2))
            )
        assert all(r.status_code == 200 for r in responses)
        assert responses[0].json()["id"] == responses[1].json()["id"]
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(ManualPaperPlan)) == 1
