"""A chat session stop blocks entries without becoming a liquidation signal."""

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from services.api.chat_control import router
from services.core.models import Account, AuditEvent
from services.paper.qualification import entry_permission
from services.paper.session_stop import session_entry_stopped, stop_session_entries
from services.worker.models import RuntimeControl


def test_stop_is_durable_idempotent_scoped_and_preserves_protection(scenario):
    engine = create_engine("sqlite://")
    for model in (Account, AuditEvent, RuntimeControl):
        model.__table__.create(engine)
    owner, other, request = uuid4(), uuid4(), uuid4()
    with Session(engine) as db, db.begin():
        db.add(Account(id=owner, cash=100000, config={}, enabled=True, daily_blocked=False,
                       session_key=scenario.session.key, session_opening_equity=100000))
        db.add(RuntimeControl(account_id=owner, resume_requested=True,
                              active_envelope={"id": "protection-policy"}, status="RUNNING"))
    first = stop_session_entries(engine, owner, request, scenario.session, scenario.now)
    again = stop_session_entries(engine, owner, request, scenario.session, scenario.now)
    third = stop_session_entries(engine, owner, uuid4(), scenario.session, scenario.now)
    assert first["duplicate"] is False and again["duplicate"] and third["duplicate"]
    with Session(engine) as db:
        account = db.get(Account, owner)
        assert account.enabled is False and account.daily_blocked is False
        control = db.get(RuntimeControl, owner)
        assert control.resume_requested is False
        assert control.active_envelope == {"id": "protection-policy"}
        assert control.status == "RUNNING"
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 1
        assert session_entry_stopped(db, owner, scenario.now)
        assert not session_entry_stopped(db, other, scenario.now)
        assert not session_entry_stopped(db, owner, scenario.now + timedelta(days=1))
        with pytest.raises(ValueError, match="USER_SESSION_ENTRY_STOP"):
            entry_permission(db, account, scenario.now, "contract")
    engine.dispose()


def test_stop_cannot_target_a_closed_or_different_account_session(scenario):
    engine = create_engine("sqlite://")
    with pytest.raises(ValueError, match="VERIFIED_OPEN_SESSION"):
        stop_session_entries(engine, uuid4(), uuid4(), scenario.session, scenario.session.closes_at)
    for model in (Account, AuditEvent, RuntimeControl):
        model.__table__.create(engine)
    owner = uuid4()
    with Session(engine) as db, db.begin():
        db.add(Account(id=owner, cash=100000, config={}, enabled=False,
                       session_key=scenario.session.key - timedelta(days=1)))
    with pytest.raises(ValueError, match="CURRENT_ACCOUNT_SESSION"):
        stop_session_entries(engine, owner, uuid4(), scenario.session, scenario.now)
    engine.dispose()


def test_chat_mutation_requires_authentication():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post("/api/chat/stop-trading-today", json={"request_id": str(uuid4())})
        assert response.status_code == 401
