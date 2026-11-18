"""Isolated permission contracts, never actual-market qualification evidence."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_durable import admit, cycle, observed
from test_durable import durable as durable_fixture

from services.api.app import app
from services.api.auth import account_identity
from services.core.models import (
    Account,
    AuditEvent,
    PaperArm,
    PaperOrder,
    PaperQualification,
    PaperValidation,
)
from services.paper import qualification as module
from services.paper.qualification import (
    MATRIX_VERSION,
    ArmRequest,
    QualificationService,
    ReviewRequest,
    entry_permission,
)
from services.worker import supervisor
from services.worker.models import LatestMarketQuote, RuntimeControl
from services.worker.store import RuntimeStore

durable = durable_fixture  # Register the existing disposable-schema fixture.


@pytest.fixture
def armed_setup(durable, monkeypatch):
    d = durable
    now = d.clock.now
    monkeypatch.setattr(module, "qualification_binding", lambda account: "fixture-release")
    report = {
        "configuration_complete": True,
        "connections_verified": True,
        "worker_online": True,
        "checks": [{"diagnostic": "broker", "checked_at": now.isoformat()}],
    }
    monkeypatch.setattr(module, "readiness", lambda *args, **kwargs: report)
    monkeypatch.setattr(
        module,
        "MarketSettings",
        lambda: SimpleNamespace(
            calendar_file=None,
            session_file=None,
            client_code=SimpleNamespace(get_secret_value=lambda: "fixture"),
        ),
    )
    monkeypatch.setattr(
        module,
        "SessionCalendar",
        lambda path: SimpleNamespace(get=lambda *args: d.scenario.session),
    )
    monkeypatch.setattr(
        module,
        "SessionStore",
        lambda *args: SimpleNamespace(
            load=lambda: SimpleNamespace(expires_at=now + timedelta(hours=1))
        ),
    )
    identifier = uuid4()
    with Session(d.engine) as db, db.begin():
        lease = db.scalar(select(PaperValidation))
        lease.status, lease.stopped_at = "STOPPED", now
        account = db.get(Account, d.account)
        account.enabled = False
        control = db.get(RuntimeControl, d.account)
        control.mode, control.resume_requested, control.active_envelope = "AUTONOMOUS", False, None
        db.add(
            PaperQualification(
                id=identifier,
                account_id=d.account,
                binding="fixture-release",
                matrix_version=MATRIX_VERSION,
                created_at=now,
                valid_until=now + timedelta(days=1),
                evidence={"isolated_fixture": True},
                request={},
                scope={
                    "instruments": [
                        {
                            "instrument_id": d.instrument.id,
                            "exchange": "NFO",
                            "max_quantity": d.instrument.lot_size,
                            "expiry": d.instrument.expiry.isoformat(),
                            "strategy_version": d.scenario.envelope.version,
                            "instrument": d.instrument.model_dump(
                                mode="json", exclude={"verified_at"}
                            ),
                        }
                    ]
                },
            )
        )
        quote = observed(d)
        db.add(
            LatestMarketQuote(
                instrument_id=d.instrument.id, timestamp=now, payload=quote.model_dump(mode="json")
            )
        )
        revision = account.revision
    request = ArmRequest(
        request_id=uuid4(), expected_revision=revision, qualification_id=identifier
    )
    return SimpleNamespace(
        d=d, service=QualificationService(d.engine, d.account), request=request, report=report
    )


def test_completed_or_edited_outcome_is_not_qualification(durable, monkeypatch):
    d = durable
    monkeypatch.setattr(module, "qualification_binding", lambda account: "fixture-release")
    with Session(d.engine) as db, db.begin():
        lease = db.scalar(select(PaperValidation))
        lease.status, lease.stopped_at = "STOPPED", d.clock.now
        lease.outcome = {
            "reconciled": True,
            "autonomous_qualified": True,
            "result": "RECORDED_FILLS",
        }
        account = db.get(Account, d.account)
        account.enabled = False
        request = ReviewRequest(
            request_id=uuid4(), expected_revision=account.revision, session_ids=[lease.id]
        )
    service = QualificationService(d.engine, d.account)
    status = service.status(d.clock.now)
    assert status["qualification"] is None and status["assessment"]["passed"] is False
    assert all(not check["passed"] for check in status["assessment"]["checks"])
    with pytest.raises(ValueError, match="EVIDENCE_INCOMPLETE"):
        service.review(request, d.clock.now)
    with Session(d.engine) as db:
        assert not list(db.scalars(select(PaperQualification)))


def test_arm_is_explicit_idempotent_and_scoped_to_actual_lot(armed_setup):
    v, d = armed_setup, armed_setup.d
    result = v.service.arm(v.request, d.clock.now)
    assert result["status"] == "ACTIVE" and v.service.arm(v.request, d.clock.now) == result
    with Session(d.engine) as db, db.begin():
        account = db.get(Account, d.account)
        assert not account.enabled
        permission = entry_permission(
            db, account, d.clock.now, d.instrument.id, 25, strategy_version="test"
        )
        assert permission.arm_id == v.request.request_id and permission.validation_id is None
        for instrument, quantity, version in (
            ("other", 1, "test"),
            (d.instrument.id, 50, "test"),
            (d.instrument.id, 25, "other"),
        ):
            with pytest.raises(ValueError, match="SCOPE_EXCEEDED"):
                entry_permission(
                    db, account, d.clock.now, instrument, quantity, strategy_version=version
                )
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        v.service.arm(v.request.model_copy(update={"qualification_id": uuid4()}), d.clock.now)


def test_autonomous_permission_reaches_coordinator_and_frozen_exit_path(armed_setup):
    v, d = armed_setup, armed_setup.d
    v.service.arm(v.request, d.clock.now)
    store = RuntimeStore(d.engine, d.account)
    slot = store.save_evaluation(
        d.scenario.session,
        d.clock.now,
        {d.instrument.id: d.instrument},
        [d.scenario.quote],
        d.clock.now,
    )
    store.finish_evaluation(slot, "STRATEGY_APPROVED", 0, d.scenario.envelope, d.clock.now)
    assert store.enable_requested(d.scenario.envelope.id, 0, d.clock.now)
    order_id = admit(d)
    with Session(d.engine) as db:
        order = db.get(PaperOrder, order_id)
        assert (
            order.arm_id == v.request.request_id
            and order.validation_id is None
            and order.quantity == 25
        )
    cycle(d, 300)
    v.service.tick(d.clock.now, "USER_DISARM")
    cycle(d, 600)
    cycle(d, 900)
    with Session(d.engine) as db:
        orders = list(db.scalars(select(PaperOrder)))
        assert any(
            o.side == "SELL" and o.status == "FILLED" and o.arm_id == v.request.request_id
            for o in orders
        )
        assert not db.get(Account, d.account).enabled


@pytest.mark.parametrize(
    "change", ["release", "stream", "heartbeat", "expiry", "preflight", "restart"]
)
def test_invalidation_blocks_pending_buy_fill(armed_setup, monkeypatch, change):
    v, d = armed_setup, armed_setup.d
    v.service.arm(v.request, d.clock.now)
    with Session(d.engine) as db, db.begin():
        db.get(RuntimeControl, d.account).active_envelope = d.scenario.envelope.model_dump(
            mode="json"
        )
        db.get(Account, d.account).enabled = True
    order_id = admit(d)
    if change == "release":
        monkeypatch.setattr(module, "qualification_binding", lambda account: "changed")
    elif change == "stream":
        with Session(d.engine) as db, db.begin():
            db.get(RuntimeControl, d.account).stream_generation += 1
    elif change == "heartbeat":
        with Session(d.engine) as db, db.begin():
            db.get(RuntimeControl, d.account).heartbeat -= timedelta(seconds=11)
    elif change == "expiry":
        with Session(d.engine) as db, db.begin():
            db.get(PaperArm, v.request.request_id).expires_at = d.clock.now
    elif change == "preflight":
        v.report["connections_verified"] = False
    else:
        RuntimeStore(d.engine, d.account).initialize(d.clock.now, "AUTONOMOUS")
    v.service.tick(d.clock.now)
    cycle(d, 300)
    with Session(d.engine) as db:
        assert db.get(PaperArm, v.request.request_id).status == "STOPPED"
        assert db.get(PaperOrder, order_id).filled_quantity == 0
        assert not db.get(RuntimeControl, d.account).resume_requested


def test_old_analysis_cannot_rearm_after_restart(armed_setup):
    v, d = armed_setup, armed_setup.d
    v.service.arm(v.request, d.clock.now)
    store = RuntimeStore(d.engine, d.account)
    slot = store.save_evaluation(
        d.scenario.session,
        d.clock.now,
        {d.instrument.id: d.instrument},
        [d.scenario.quote],
        d.clock.now,
    )
    store.initialize(d.clock.now, "AUTONOMOUS")
    store.finish_evaluation(slot, "STRATEGY_APPROVED", 0, d.scenario.envelope, d.clock.now)
    assert not store.enable_requested(d.scenario.envelope.id, 0, d.clock.now)
    with Session(d.engine) as db:
        assert db.get(RuntimeControl, d.account).active_envelope is None


def test_revocation_invalidates_old_permission_and_keeps_history(armed_setup):
    v, d = armed_setup, armed_setup.d
    v.service.arm(v.request, d.clock.now)
    v.service.revoke(v.request.qualification_id, d.clock.now)
    with Session(d.engine) as db, db.begin():
        account = db.get(Account, d.account)
        row = db.get(PaperQualification, v.request.qualification_id)
        assert row.revoked_at is not None
        assert not module.qualified(db, account, row, d.clock.now)
        assert db.get(PaperArm, v.request.request_id).status == "STOPPED"
        with pytest.raises(ValueError, match="ARM_REQUIRED"):
            entry_permission(db, account, d.clock.now, d.instrument.id)


def test_supervisor_only_launches_fixed_mode_for_flat_enrolled_owner(armed_setup, monkeypatch):
    v, d = armed_setup, armed_setup.d
    with Session(d.engine) as db, db.begin():
        db.add(
            AuditEvent(
                account_id=d.account, kind="LOCAL_OWNER_ENROLLED", timestamp=d.clock.now, details={}
            )
        )
    calls = []

    def launch_fixture(mode):
        from datetime import UTC, datetime

        calls.append(mode)
        RuntimeStore(d.engine, d.account).initialize(datetime.now(UTC), mode)

    monkeypatch.setattr(supervisor, "launch", launch_fixture)
    response = supervisor.prepare(d.engine, d.account, "VALIDATION", v.request.expected_revision)
    assert response["status"] == "PREPARATION_REQUESTED" and calls == ["VALIDATION"]
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
    with pytest.raises(ValueError, match="INVALID_WORKER_MODE"):
        supervisor.prepare(d.engine, d.account, "VALIDATION; arbitrary-command", revision)
    with Session(d.engine) as db, db.begin():
        db.get(Account, d.account).enabled = True
    with pytest.raises(ValueError, match="REQUIRES_FLAT_PAUSED"):
        supervisor.prepare(d.engine, d.account, "OBSERVATION", revision)
    assert calls == ["VALIDATION"]


def test_paper_control_api_owner_and_loopback_boundary(armed_setup):
    v, d = armed_setup, armed_setup.d
    app.state.engine = d.engine
    app.dependency_overrides[account_identity] = lambda: d.account
    client = TestClient(app)
    try:
        assert client.get("/api/paper/qualification").status_code == 200
        assert (
            client.post(
                "/api/worker/prepare", json={"mode": "VALIDATION", "expected_revision": 0}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/worker/prepare", json={"mode": "arbitrary", "expected_revision": 0}
            ).status_code
            == 422
        )
        stranger = d.legacy.create_account(d.scenario.config, d.clock.now)
        app.dependency_overrides[account_identity] = lambda: stranger
        assert client.get("/api/paper/qualification").json()["qualification"] is None
        with Session(d.engine) as db, db.begin():
            db.add(RuntimeControl(account_id=stranger, mode="AUTONOMOUS", heartbeat=d.clock.now))
        request = v.request.model_copy(update={"expected_revision": 0})
        response = client.post("/api/paper/arm", json=request.model_dump(mode="json"))
        assert (
            response.status_code == 409
            and response.json()["detail"] == "PAPER_QUALIFICATION_REQUIRED"
        )
        assert (
            client.post(f"/api/paper/qualification/{v.request.qualification_id}/revoke").status_code
            == 404
        )
    finally:
        app.dependency_overrides.pop(account_identity, None)
    assert client.get("/api/paper/qualification").status_code == 401


def test_facts_inspect_original_fills_and_agent_links_and_reject_fixture_provenance(
    durable, monkeypatch
):
    import test_durable as lifecycle

    from services.core.contracts import StrategyEnvelope
    from services.core.models import SnapshotRecord, StrategyRecord
    from services.paper.validation import ValidationService
    from services.worker.models import EvaluationSlot

    d = durable
    original = lifecycle.observed
    monkeypatch.setattr(
        lifecycle,
        "observed",
        lambda *args, **kwargs: original(*args, **kwargs).model_copy(
            update={"source": "angelone-websocket-v2:snapquote"}
        ),
    )
    with Session(d.engine) as db, db.begin():
        row = db.scalar(select(PaperValidation))
        row.qualification_binding = "isolated-binding"
        row.preflight = {
            "configuration_complete": True,
            "connections_verified": True,
            "worker_online": True,
            "instrument": d.instrument.model_dump(mode="json"),
        }
        row.max_quantity = d.instrument.lot_size
        identifier = row.id
    order_id = admit(d)
    with Session(d.engine) as db, db.begin():
        order = db.get(PaperOrder, order_id)
        from services.core.models import DecisionRecord

        decision = db.get(DecisionRecord, order.decision_id)
        envelope = StrategyEnvelope.model_validate(
            db.get(StrategyRecord, decision.payload["strategy_id"]).payload
        )
        slot = EvaluationSlot(
            account_id=d.account,
            validation_id=identifier,
            session_key=d.scenario.session.key,
            slot_at=d.clock.now,
            status="STRATEGY_APPROVED",
            evidence_ids=list(map(str, envelope.evidence_ids)),
        )
        db.add(slot)
        db.flush()
        db.add(
            AuditEvent(
                account_id=d.account,
                kind="AGENT_EVALUATION",
                timestamp=d.clock.now,
                details={
                    "evaluation_id": str(slot.id),
                    "envelope": envelope.model_dump(mode="json"),
                },
            )
        )
        db.add(
            AuditEvent(
                account_id=d.account,
                kind="AI_OUTPUT",
                timestamp=d.clock.now,
                details={
                    "role": "review",
                    "response_id": "isolated-response",
                    "output": {
                        "approved": True,
                        "evidence_ids": list(map(str, envelope.evidence_ids)),
                    },
                },
            )
        )
    cycle(d, 300)
    cycle(d, 600, bid="106.00", ask="106.05")
    cycle(d, 900, bid="106.00", ask="106.05")
    ValidationService(d.engine, d.account).tick(d.clock.now)
    with Session(d.engine) as db, db.begin():
        row, account = db.get(PaperValidation, identifier), db.get(Account, d.account)
        facts = module.session_facts(db, account, row, "isolated-binding")
        assert {"round_trip", "protective_order", "target_exit"} <= set(facts["checks"])
        assert "stop_exit" not in facts["checks"]
        report = module.assess(db, account, [row], "isolated-binding")
        assert not report["passed"]  # One fixture round trip cannot satisfy the full matrix.
        snapshot = db.get(SnapshotRecord, envelope.evidence_ids[0])
        snapshot.payload = {**snapshot.payload, "source": "isolated-fixture"}
        assert module.session_facts(db, account, row, "isolated-binding")["checks"] == []


def test_matrix_requires_both_venues_every_scenario_and_two_sessions(durable, monkeypatch):
    d = durable
    rows = [
        PaperValidation(
            id=uuid4(),
            account_id=d.account,
            session_key=d.scenario.session.key + timedelta(days=index),
            exchange=venue,
        )
        for index, venue in enumerate(module.VENUES)
    ]
    facts = [
        {
            "session_id": str(row.id),
            "exchange": row.exchange,
            "checks": list(module.CRITERIA),
            "scope": {"isolated": True},
        }
        for row in rows
    ]
    monkeypatch.setattr(
        module,
        "session_facts",
        lambda db, account, row, binding: next(f for f in facts if f["session_id"] == str(row.id)),
    )
    with Session(d.engine) as db, db.begin():
        db.add(
            AuditEvent(
                account_id=d.account,
                kind="SESSION_STARTED",
                timestamp=d.clock.now + timedelta(days=1),
                details={"session": rows[1].session_key.isoformat()},
            )
        )
        account = db.get(Account, d.account)
        assert module.assess(db, account, rows, "isolated")["passed"] is True
        facts[1]["checks"].remove("restart_recovery")
        assert module.assess(db, account, rows, "isolated")["passed"] is False


def test_release_binding_ignores_daily_session_contents_but_detects_policy_and_key_changes(
    tmp_path, scenario, monkeypatch
):
    from pydantic import SecretStr

    from services.market.settings import MarketSettings
    from services.paper import bindings

    root = tmp_path / "root"
    (root / "services").mkdir(parents=True)
    (root / "services" / "worker.py").write_text("# isolated code", encoding="utf-8")
    (root / "uv.lock").write_text("# isolated dependency lock", encoding="utf-8")
    monkeypatch.setattr(bindings, "ROOT", root)
    monkeypatch.setattr(bindings, "connection_fingerprint", lambda name: name)
    for name in bindings.CONFIG_FILES:
        path = tmp_path / (name + ".json")
        path.write_text("{}", encoding="utf-8")
        monkeypatch.setitem(bindings.CONFIG_FILES, name, path)
    settings = MarketSettings(
        _env_file=None, api_key=SecretStr("isolated-key"), session_file=tmp_path / "session.json"
    )
    monkeypatch.setattr(bindings, "MarketSettings", lambda: settings)
    account = Account(config=scenario.config.model_dump(mode="json"))
    initial = bindings.qualification_binding(account)
    settings.session_file.write_text("daily-token-renewed", encoding="utf-8")
    assert bindings.qualification_binding(account) == initial
    settings.api_key = SecretStr("changed-isolated-key")
    assert bindings.qualification_binding(account) != initial
    settings.api_key = SecretStr("isolated-key")
    account.config = {**account.config, "version": "changed"}
    assert bindings.qualification_binding(account) != initial


def test_review_persists_server_assessment_without_arming_and_is_idempotent(
    armed_setup, monkeypatch
):
    """Assessment is the seam here; its original-record checks are tested separately."""
    v, d = armed_setup, armed_setup.d
    with Session(d.engine) as db:
        scope = db.get(PaperQualification, v.request.qualification_id).scope["instruments"]
        lease_id = db.scalar(select(PaperValidation.id))
    report = {"matrix_version": MATRIX_VERSION, "passed": True, "checks": [], "scope": scope}
    monkeypatch.setattr(module, "assess", lambda *args: report)
    request = ReviewRequest(
        request_id=uuid4(), expected_revision=v.request.expected_revision, session_ids=[lease_id]
    )
    result = v.service.review(request, d.clock.now)
    assert result == v.service.review(request, d.clock.now)
    with Session(d.engine) as db:
        row = db.get(PaperQualification, request.request_id)
        assert row.evidence == report and row.binding == "fixture-release"
        assert not db.get(Account, d.account).enabled
        assert not db.get(RuntimeControl, d.account).resume_requested
        assert not list(db.scalars(select(PaperArm)))
    with pytest.raises(ValueError):
        ReviewRequest.model_validate({**request.model_dump(mode="json"), "qa_complete": True})


def test_supervisor_failure_is_audited_and_leaves_entries_disabled(armed_setup, monkeypatch):
    v, d = armed_setup, armed_setup.d
    with Session(d.engine) as db, db.begin():
        db.add(
            AuditEvent(
                account_id=d.account, kind="LOCAL_OWNER_ENROLLED", timestamp=d.clock.now, details={}
            )
        )

    def fail(mode):
        raise ValueError("isolated launch failure")

    monkeypatch.setattr(supervisor, "launch", fail)
    with pytest.raises(ValueError, match="WORKER_PREPARATION_FAILED"):
        supervisor.prepare(d.engine, d.account, "OBSERVATION", v.request.expected_revision)
    with Session(d.engine) as db:
        control = db.get(RuntimeControl, d.account)
        assert control.status == "WORKER_PREPARATION_FAILED" and not control.resume_requested
        assert not db.get(Account, d.account).enabled
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.kind == "WORKER_MODE_FAILED"))


@pytest.mark.asyncio
async def test_prepared_autonomous_worker_is_idle_without_explicit_arm(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock

    from services.market.settings import MarketSettings
    from services.worker import runtime as worker

    agents = SimpleNamespace(evaluate=AsyncMock())
    monkeypatch.setattr(worker, "AgentPipeline", lambda *args: agents)
    runtime = worker.TradingRuntime(
        None, None, MarketSettings(_env_file=None, calendar_file=tmp_path / "missing")
    )
    runtime.qualification.scope = lambda now: None
    await runtime.evaluation_slot()
    agents.evaluate.assert_not_called()
    await runtime.client.close()
