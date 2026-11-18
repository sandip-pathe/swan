"""Configuration and diagnostics use isolated files and disposable account schemas."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app import app
from services.api.auth import account_identity
from services.core.models import Account, AuditEvent
from services.core.setup import CONFIG_FILES, digest, document, save_document
from services.market import diagnostics, readiness
from services.market.calendar import CalendarDocument, SessionCalendar
from services.market.settings import MarketSettings
from services.paper.engine import PaperEngine
from services.worker.models import RuntimeControl


@pytest.fixture
def local_configs(tmp_path, monkeypatch):
    for name in CONFIG_FILES:
        path = tmp_path / f"{name}.json"
        monkeypatch.setitem(CONFIG_FILES, name, path)
    CONFIG_FILES["news"].write_text('{"sources":[]}', encoding="utf-8")
    return tmp_path


def test_calendar_distinguishes_verified_closure_and_missing_day(local_configs):
    path = CONFIG_FILES["calendar"]
    now = datetime(2026, 11, 18, 12, tzinfo=UTC)
    config = {
        "schema_version": 1,
        "sessions": [],
        "closed_days": [
            {
                "exchange": venue,
                "day": "2026-11-18",
                "reason": "Test closure record",
                "official_source_url": "https://www.nseindia.com/test",
            }
            for venue in ("NFO", "BFO")
        ],
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    calendar = SessionCalendar(path)
    assert calendar.state("NFO", now) == "closed"
    assert calendar.state("NFO", now + timedelta(days=1)) == "unknown"
    config["closed_days"][0]["official_source_url"] = "https://nseindia.com.example.test"
    with pytest.raises(ValueError):
        CalendarDocument.model_validate(config)


def test_config_import_is_validated_atomic_and_revision_checked(local_configs):
    before = document("news")
    with pytest.raises(ValueError):
        save_document(
            "news",
            {
                "sources": [
                    {
                        "name": "Unpermitted",
                        "url": "https://example.test",
                        "license_reference": "none",
                        "automation_and_storage_permitted": False,
                    }
                ]
            },
            before["revision"],
        )
    assert document("news") == before
    permitted = {
        "sources": [
            {
                "name": "Test feed",
                "url": "https://example.test/feed",
                "license_reference": "test permission",
                "automation_and_storage_permitted": True,
            }
        ]
    }
    save_document("news", permitted, before["revision"])
    assert document("news")["document"] == {"provider": "rss", **permitted}
    with pytest.raises(ValueError, match="SETTINGS_CHANGED"):
        save_document("news", {"sources": []}, before["revision"])
    assert not list(local_configs.glob("*.tmp"))


@pytest.mark.parametrize(
    "offset, fingerprint, expected",
    [
        (0, "current", "passed"),
        (-901, "current", "not_checked"),
        (1, "current", "not_checked"),
        (0, "old", "not_checked"),
    ],
)
def test_connection_evidence_is_bound_to_time_and_configuration(
    monkeypatch, offset, fingerprint, expected
):
    now = datetime.now(UTC)
    monkeypatch.setattr(readiness, "connection_fingerprint", lambda name: "current")
    result = readiness.readiness(
        now,
        evidence={
            "ai": {
                "status": "passed",
                "detail": "Verified",
                "checked_at": (now + timedelta(seconds=offset)).isoformat(),
                "fingerprint": fingerprint,
            }
        },
    )
    check = next(c for c in result["checks"] if c["code"] == "CONNECTION_AI")
    assert check["status"] == expected
    assert result["connections_verified"] is False


def test_missing_reference_and_changed_policy_cannot_pass(monkeypatch, scenario):
    settings = MarketSettings(_env_file=None)
    monkeypatch.setattr(readiness, "MarketSettings", lambda: settings)
    policy = scenario.config.model_dump(mode="json")
    report = readiness.readiness(
        datetime.now(UTC), account={"config": policy}, risk_review=digest(policy)
    )
    assert "ANGELONE_NIFTY_INDEX_TOKEN" in report["missing_configuration"]
    assert (
        next(c for c in report["checks"] if c["code"] == "RISK_POLICY_REVIEW")["status"] == "passed"
    )
    changed = {**policy, "max_fill_quantity": 150}
    report = readiness.readiness(
        datetime.now(UTC), account={"config": changed}, risk_review=digest(policy)
    )
    assert (
        next(c for c in report["checks"] if c["code"] == "RISK_POLICY_REVIEW")["status"] == "failed"
    )


def test_completed_setup_waits_for_market_without_requiring_after_hours_strategy(
    local_configs, monkeypatch, scenario
):
    from pydantic import SecretStr

    now = datetime.now(UTC)
    from services.core.contracts import IST

    day = now.astimezone(IST).date().isoformat()
    CONFIG_FILES["calendar"].write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sessions": [],
                "closed_days": [
                    {
                        "exchange": venue,
                        "day": day,
                        "reason": "Test closure",
                        "official_source_url": "https://www.nseindia.com/test",
                    }
                    for venue in ("NFO", "BFO")
                ],
            }
        ),
        encoding="utf-8",
    )
    CONFIG_FILES["news"].write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "Test",
                        "url": "https://example.test/feed",
                        "license_reference": "test",
                        "automation_and_storage_permitted": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    settings = SimpleNamespace(
        missing=lambda: [],
        missing_references=lambda: [],
        session_file=local_configs / "session",
        client_code=SecretStr("test"),
        calendar_file=CONFIG_FILES["calendar"],
    )
    monkeypatch.setattr(readiness, "MarketSettings", lambda: settings)
    monkeypatch.setattr(
        readiness.SessionStore,
        "load",
        lambda _: SimpleNamespace(expires_at=now + timedelta(hours=1), created_at=now),
    )
    monkeypatch.setattr(
        readiness,
        "AgentSettings",
        lambda: SimpleNamespace(
            openai_api_key=SecretStr("test"),
            openai_model="test-model",
            swan_ai_daily_token_budget=1,
            swan_news_config=str(CONFIG_FILES["news"]),
        ),
    )
    monkeypatch.setattr(
        readiness,
        "configuration_status",
        lambda _: {
            "configuration_ready": True,
            "engine_ready": False,
            "blockers": ["FINAL_CONNECTED_QA_PENDING"],
        },
    )
    monkeypatch.setattr(readiness, "connection_fingerprint", lambda name: "current")
    evidence = {
        name: {
            "status": "passed",
            "detail": "Test verified",
            "fingerprint": "current",
            "checked_at": now.isoformat(),
        }
        for name in diagnostics.NAMES
    }
    policy = scenario.config.model_dump(mode="json")
    report = readiness.readiness(
        now,
        account={"config": policy},
        runtime={"heartbeat": now},
        evidence=evidence,
        risk_review=digest(policy),
    )
    assert report["configuration_complete"] and report["connections_verified"]
    assert report["title"] == "Setup complete · Market closed"
    assert report["paper_execution"]["engine_ready"] is False
    assert (
        next(c for c in report["checks"] if c["code"] == "FRESH_MARKET_DATA")["status"]
        == "waiting_for_market"
    )


@pytest.fixture
def setup_client(db_engine, scenario, monkeypatch, local_configs):
    identifier = PaperEngine(db_engine).create_account(scenario.config, scenario.now)
    with Session(db_engine) as db, db.begin():
        db.add(
            RuntimeControl(
                account_id=identifier, status="OBSERVATION_ONLY", heartbeat=datetime.now(UTC)
            )
        )
    monkeypatch.setattr(app.state, "engine", db_engine, raising=False)
    app.dependency_overrides[account_identity] = lambda: identifier
    client = TestClient(app)
    try:
        yield SimpleNamespace(client=client, account=identifier, engine=db_engine)
    finally:
        client.close()
        app.dependency_overrides.pop(account_identity, None)


@pytest.mark.integration
def test_full_policy_review_preserves_ledger_capital_and_invalidates_on_edit(setup_client):
    client = setup_client.client
    workspace = client.get("/api/workspace").json()
    policy = workspace["account"]["config"]
    updated = {**policy, "max_fill_quantity": 250}
    response = client.post(
        "/api/settings/risk-policy",
        json={
            "expected_revision": workspace["account"]["revision"],
            "policy": updated,
            "reviewed": True,
        },
    )
    assert response.status_code == 200
    result = client.get("/api/workspace").json()
    assert result["account"]["cash"] == workspace["account"]["cash"]
    assert (
        next(c for c in result["readiness"]["checks"] if c["code"] == "RISK_POLICY_REVIEW")[
            "status"
        ]
        == "passed"
    )
    response = client.post(
        "/api/settings/risk-policy",
        json={
            "expected_revision": result["account"]["revision"],
            "policy": {**updated, "capital": "200000"},
            "reviewed": True,
        },
    )
    assert response.status_code == 409
    # Existing partial-update clients must invalidate a full review rather than inherit it.
    response = client.post(
        "/api/settings/risk",
        json={
            "expected_revision": result["account"]["revision"],
            "max_trade_risk_pct": "0.005",
            "max_daily_loss_pct": "0.02",
            "max_holding_seconds": 200,
        },
    )
    assert response.status_code == 200
    result = client.get("/api/workspace").json()
    assert (
        next(c for c in result["readiness"]["checks"] if c["code"] == "RISK_POLICY_REVIEW")[
            "status"
        ]
        == "failed"
    )


@pytest.mark.integration
def test_import_conflicts_active_entries_and_observation_resume_are_rejected(setup_client):
    client = setup_client.client
    revision = document("news")["revision"]
    assert client.post("/api/control/resume").json()["detail"] == "WORKER_OBSERVATION_ONLY"
    permitted = {
        "sources": [
            {
                "name": "Test",
                "url": "https://example.test/feed",
                "license_reference": "test",
                "automation_and_storage_permitted": True,
            }
        ]
    }
    response = client.post(
        "/api/settings/setup/news", json={"expected_revision": revision, "document": permitted}
    )
    assert response.status_code == 200
    response = client.post(
        "/api/settings/setup/news",
        json={"expected_revision": revision, "document": {"sources": []}},
    )
    assert response.status_code == 409
    with Session(setup_client.engine) as db, db.begin():
        db.get(Account, setup_client.account).enabled = True
    revision = document("news")["revision"]
    response = client.post(
        "/api/settings/setup/news",
        json={"expected_revision": revision, "document": {"sources": []}},
    )
    assert response.status_code == 409
    assert document("news")["document"] == {"provider": "rss", **permitted}


@pytest.mark.integration
def test_diagnostics_persist_account_scoped_evidence_and_throttle(setup_client, monkeypatch):
    calls = []

    async def probe(name):
        calls.append(name)
        return {"status": "passed", "detail": "Test authenticated access", "models": ["test-model"]}

    monkeypatch.setattr(diagnostics, "probe", probe)
    monkeypatch.setattr(diagnostics, "connection_fingerprint", lambda name: "test-fingerprint")
    for _ in range(2):
        response = setup_client.client.post("/api/diagnostics/ai")
        assert response.status_code == 200
        assert "fingerprint" not in response.json()
    assert calls == ["ai"]
    with Session(setup_client.engine) as db:
        events = list(db.scalars(select(AuditEvent).where(AuditEvent.kind == "CONNECTION_CHECK")))
        assert len(events) == 1 and events[0].account_id == setup_client.account
    # A normal workspace refresh must never run a provider test.
    setup_client.client.get("/api/workspace")
    assert calls == ["ai"]


@pytest.mark.integration
def test_setup_and_diagnostics_require_identity(setup_client):
    app.dependency_overrides.pop(account_identity)
    for method, path in (("GET", "/api/settings/setup"), ("POST", "/api/diagnostics/ai")):
        assert setup_client.client.request(method, path).status_code == 401


@pytest.mark.integration
def test_database_failure_does_not_leave_an_unacknowledged_config_change(setup_client, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    before = document("news")
    permitted = {
        "sources": [
            {
                "name": "Test",
                "url": "https://example.test/feed",
                "license_reference": "test",
                "automation_and_storage_permitted": True,
            }
        ]
    }

    def fail_commit(self):
        raise SQLAlchemyError("injected commit failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = setup_client.client.post(
        "/api/settings/setup/news",
        json={"expected_revision": before["revision"], "document": permitted},
    )
    assert response.status_code == 503
    assert document("news") == before


@pytest.mark.asyncio
async def test_observation_worker_does_not_run_agents_or_admit_entries(
    monkeypatch, tmp_path, scenario
):
    from unittest.mock import AsyncMock

    from services.worker.runtime import TradingRuntime

    settings = MarketSettings(_env_file=None, calendar_file=tmp_path / "unavailable-calendar")
    runtime = TradingRuntime(None, None, settings, observe_only=True)
    assert runtime.agents is None
    state = {
        "config": scenario.config,
        "enabled": False,
        "runtime_status": "STARTING",
        "resume_requested": True,
    }
    runtime.store.state = lambda: state
    runtime.store.open_instruments = lambda: []
    changes = []
    runtime.store.update = lambda **kwargs: changes.append(kwargs)
    # A configuration blocker must not overwrite transport health.
    runtime.cache.problem = None
    runtime.paper.set_enabled = lambda *args: None
    runtime.validation.tick = lambda *args, **kwargs: None
    runtime.qualification.tick = lambda *args, **kwargs: None
    await runtime.problem("PAPER_ENGINE_NOT_READY")
    assert runtime.cache.problem is None
    changes.clear()
    runtime.publish_latest = AsyncMock()
    runtime.last_publication = asyncio.get_running_loop().time()
    await runtime.cycle()
    assert changes == [
        {
            "status": "OBSERVATION_ONLY",
            "problem": None,
            "resume_requested": False,
            "active_envelope": None,
        }
    ]
    await runtime.evaluation_slot()
    await runtime.client.close()
