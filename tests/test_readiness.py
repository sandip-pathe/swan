"""Readiness never equates a saved login or a running website with safe execution."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from services.market import readiness as diagnostics
from services.market.settings import MarketSettings


@pytest.mark.parametrize(
    ("session_offset", "expected"),
    [(None, "NOT_CONFIGURED"), (-1, "EXPIRED"), (0, "EXPIRED"), (60, "SAVED")],
)
def test_readiness_session_expiry_and_execution_gate(tmp_path, monkeypatch, session_offset, expected):
    now = datetime(2026, 11, 18, 6, tzinfo=UTC)
    session_file = tmp_path / "session.json"
    calendar_file = tmp_path / "calendar.json"
    calendar_file.write_text('{"schema_version":1,"sessions":[]}', encoding="utf-8")
    settings = MarketSettings(
        _env_file=None,
        client_code=SecretStr("test-client"),
        api_key=SecretStr("test-api-key"),
        session_file=session_file,
        calendar_file=calendar_file,
    )
    if session_offset is not None:
        session_file.write_text(json.dumps({
            "jwt": "test-private-jwt", "refresh": "test-private-refresh",
            "feed": "test-private-feed", "client_code": "test-client",
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "expires_at": (now + timedelta(seconds=session_offset)).isoformat(),
        }), encoding="utf-8")
    monkeypatch.setattr(diagnostics, "MarketSettings", lambda: settings)
    result = diagnostics.readiness(now)
    assert result["broker_session"] == expected
    assert result["calendar_exchanges_today"] == []
    assert result["live_connection_checked"] is False
    assert result["paper_execution"]["engine_ready"] is False
    assert "FINAL_CONNECTED_QA_PENDING" in result["paper_execution"]["blockers"]
    serialized = json.dumps(result)
    assert "test-private" not in serialized
    assert "test-client" not in serialized
    assert "test-api-key" not in serialized


def test_readiness_invalid_local_files_do_not_break_account_view(tmp_path, monkeypatch):
    settings = MarketSettings(
        _env_file=None, session_file=tmp_path / "session", calendar_file=tmp_path / "calendar",
    )
    settings.session_file.write_text("invalid", encoding="utf-8")
    settings.calendar_file.write_text("invalid", encoding="utf-8")
    monkeypatch.setattr(diagnostics, "MarketSettings", lambda: settings)
    result = diagnostics.readiness(datetime.now(UTC))
    assert result["broker_session"] == "NOT_CONFIGURED"
    assert result["calendar_exchanges_today"] == []


@pytest.mark.integration
def test_workspace_reports_readiness_and_resume_stays_blocked(db_engine, scenario, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    from services.api.app import app
    from services.api.auth import account_identity
    from services.core.models import Account
    from services.paper.engine import PaperEngine
    from services.worker.models import RuntimeControl

    account = PaperEngine(db_engine).create_account(scenario.config, scenario.now)
    with Session(db_engine) as db, db.begin():
        db.add(RuntimeControl(account_id=account, heartbeat=datetime.now(UTC), status="PAUSED"))
    monkeypatch.setattr(app.state, "engine", db_engine, raising=False)
    app.dependency_overrides[account_identity] = lambda: account
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            # The app lifespan owns its production connection. Replace it after startup
            # so every request below uses only the disposable test schema.
            production_engine = app.state.engine
            app.state.engine = db_engine
            try:
                response = client.get("/api/workspace")
                assert response.status_code == 200
                assert response.json()["readiness"]["paper_execution"]["engine_ready"] is False
                response = client.post("/api/control/resume")
                assert response.status_code == 409
                assert response.json()["detail"] == "USE_EXPLICIT_PAPER_ARMING"
                with Session(db_engine) as db:
                    assert db.get(Account, account).enabled is False
                    assert db.get(RuntimeControl, account).resume_requested is False
            finally:
                app.state.engine = production_engine
    finally:
        app.dependency_overrides.pop(account_identity, None)
