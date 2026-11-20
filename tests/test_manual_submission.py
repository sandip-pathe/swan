"""Owner-scoped submission API with fixed clocks and disposable fixture data."""

# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from test_durable import durable, observed  # noqa: F401
from test_instrument_search import client_for
from test_manual_execution import human  # noqa: F401

from services.api import manual_orders as api
from services.core.models import (
    Account,
    AuditEvent,
    ManualIntentRecord,
    ManualPaperPlan,
    PaperOrder,
    PaperValidation,
    SnapshotRecord,
)
from services.paper import manual
from services.paper.manual import ManualPaperService
from services.worker.models import LatestMarketQuote, RuntimeControl

pytestmark = pytest.mark.integration


@pytest.fixture
def route_case(human, monkeypatch):
    h, d = human, human.d

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return d.clock.now.astimezone(tz) if tz else d.clock.now.replace(tzinfo=None)

    monkeypatch.setattr(api, "datetime", FixedDatetime)
    monkeypatch.setattr(api, "load_session", lambda exchange, now: d.scenario.session)
    monkeypatch.setattr(manual, "load_session", lambda exchange, now: d.scenario.session)
    monkeypatch.setattr(
        api,
        "ManualPaperService",
        lambda engine, owner: ManualPaperService(engine, owner, clock=lambda: d.clock.now),
    )
    quote = observed(d)
    with Session(d.engine) as db, db.begin():
        db.add(
            LatestMarketQuote(
                instrument_id=d.instrument.id,
                timestamp=quote.timestamp,
                payload=quote.model_dump(mode="json"),
            )
        )
    return h


def payload(h):
    return dict(request_id=str(h.request), expected_account_revision=h.revision)


def endpoint(h):
    return f"/api/paper/plans/{h.plan}/submit"


def test_submission_and_concurrent_api_retries_record_one_order(route_case):
    h, d = route_case, route_case.d
    with client_for(d.engine, d.account) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(lambda _: client.post(endpoint(h), json=payload(h)), range(2))
            )
        assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
        result = responses[0].json()
        assert result["order_id"] == responses[1].json()["order_id"]
        assert result["source"] == "HUMAN" and result["plan_id"] == str(h.plan)
        assert result["filled_quantity"] == 0
        status = client.get(
            "/api/paper/manual/status", params={"instrument_id": d.instrument.id}
        ).json()
        assert not status["ready"] and status["reason"] == "MANUAL_ENTRY_USED"
        assert status["order"]["order_id"] == result["order_id"]
        assert status["order"]["instrument_id"] == d.instrument.id
        saved = client.get("/api/paper/plans").json()["rows"][0]
        assert saved["order_id"] == result["order_id"] and saved["last_order_status"] == "OPEN"
    with Session(d.engine) as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 1
        assert db.scalar(select(func.count()).select_from(ManualIntentRecord)) == 1


def test_api_owner_isolation_and_strict_commands(route_case):
    h, d = route_case, route_case.d
    other = d.legacy.create_account(d.scenario.config, d.clock.now)
    with client_for(d.engine, other) as client:
        assert client.post(endpoint(h), json=payload(h)).status_code == 404
    with client_for(d.engine, d.account) as client:
        for change in [
            dict(quantity=25),
            dict(approval={}),
            dict(expected_account_revision=True),
            dict(account_id=str(other)),
        ]:
            assert client.post(endpoint(h), json={**payload(h), **change}).status_code == 422
        assert client.post(f"/api/paper/plans/{uuid4()}/submit", json=payload(h)).status_code == 404
        with Session(d.engine) as db, db.begin():
            db.get(ManualPaperPlan, h.plan).archived_at = d.clock.now
        assert client.post(endpoint(h), json=payload(h)).status_code == 404
    with Session(d.engine) as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0


def test_status_is_read_only_and_checks_market_source_and_pause(route_case, monkeypatch):
    h, d = route_case, route_case.d

    def counts():
        with Session(d.engine) as db:
            return [
                db.scalar(select(func.count()).select_from(m))
                for m in (PaperOrder, ManualIntentRecord, AuditEvent, SnapshotRecord)
            ]

    before = counts()
    with client_for(d.engine, d.account) as client:
        url = "/api/paper/manual/status"
        params = dict(instrument_id=d.instrument.id)
        assert client.get(url, params=params).json()["ready"] is True
        with Session(d.engine) as db, db.begin():
            db.get(Account, d.account).enabled = False
        assert client.get(url, params=params).json()["reason"] == "MANUAL_WAITING"
        with Session(d.engine) as db, db.begin():
            db.get(PaperValidation, h.lease).request = {"entry_source": "AI"}
        assert client.get(url, params=params).json()["reason"] == "ENTRY_SOURCE_MISMATCH"
        monkeypatch.setattr(
            api,
            "load_session",
            lambda *args: d.scenario.session.model_copy(
                update={"closes_at": d.clock.now + timedelta(minutes=10)}
            ),
        )
        assert client.get(url, params=params).json()["reason"] == "MANUAL_ENTRY_CUTOFF"
        monkeypatch.setattr(api, "load_session", lambda *args: None)
        assert client.get(url, params=params).json()["reason"] == "MANUAL_MARKET_CLOSED"
    assert counts() == before


def test_retry_after_close_missing_quotes_and_config_returns_original(route_case, monkeypatch):
    h, d = route_case, route_case.d
    with client_for(d.engine, d.account) as client:
        result = client.post(endpoint(h), json=payload(h)).json()
        with Session(d.engine) as db, db.begin():
            db.execute(delete(LatestMarketQuote))
            db.get(Account, d.account).enabled = False
            db.get(Account, d.account).revision += 1
            db.get(PaperValidation, h.lease).expires_at = d.clock.now - timedelta(seconds=1)
        monkeypatch.setattr(manual, "DEFAULT_CONFIG", manual.DEFAULT_CONFIG.parent / "missing.json")
        monkeypatch.setattr(manual, "load_session", lambda *args: None)
        retry = client.post(endpoint(h), json=payload(h))
        assert retry.status_code == 200 and retry.json()["order_id"] == result["order_id"]
        conflict = client.post(f"/api/paper/plans/{uuid4()}/submit", json=payload(h))
        assert (
            conflict.status_code == 409 and conflict.json()["detail"] == "MANUAL_REQUEST_CONFLICT"
        )


def test_current_risk_rejection_and_unprepared_mode_never_create_order(route_case):
    h, d = route_case, route_case.d
    with Session(d.engine) as db, db.begin():
        plan = db.get(ManualPaperPlan, h.plan)
        plan.request_payload = {**plan.request_payload, "stop_loss": "1"}
    with client_for(d.engine, d.account) as client:
        response = client.post(endpoint(h), json=payload(h))
        assert response.status_code == 409 and response.json()["detail"] == "MANUAL_RISK_LIMIT"
        assert client.post(endpoint(h), json=payload(h)).json() == response.json()
        with Session(d.engine) as db, db.begin():
            db.get(RuntimeControl, d.account).mode = "OBSERVATION"
        other = client.post(endpoint(h), json={**payload(h), "request_id": str(uuid4())})
        assert other.status_code == 409 and other.json()["detail"] == "MANUAL_VALIDATION_REQUIRED"
    with Session(d.engine) as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
