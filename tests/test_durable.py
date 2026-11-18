"""Durable lifecycle contracts in disposable schemas; no live provider qualification.

Value: protects=depth fills, protection and reconciliation; fails_when=durable wiring
breaks; why_new=existing paper suite exercises legacy fills; seam=none;
no_claim=real provider acceptance, rates or activation (isolated test inputs).
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from services.api.app import app
from services.api.auth import account_identity
from services.core.contracts import DepthLevel, Quote
from services.core.execution import PaperExecutionConfig
from services.core.models import (
    Account,
    PaperFill,
    PaperFundsHold,
    PaperOrder,
    PaperPosition,
    PaperValidation,
)
from services.paper import coordinator as module
from services.paper import validation
from services.paper.accounting import reconcile_account
from services.paper.coordinator import PaperCoordinator
from services.paper.validation import ValidationRequest, ValidationService, entry_lease
from services.worker.models import EvaluationSlot, LatestMarketQuote, RuntimeControl
from services.worker.store import RuntimeStore

pytestmark = pytest.mark.integration


@pytest.fixture
def durable(paper, scenario, db_engine, tmp_path, monkeypatch):
    legacy, account_id = paper
    clock = SimpleNamespace(now=scenario.now)
    source = {
        "url": "https://example.test/isolated-fixture",
        "checked_at": scenario.now.isoformat(),
        "finding": "Test arithmetic only, not an actual fee or provider assertion",
        "status": "documented",
    }
    rules = [
        {
            "code": code,
            "sides": ["BUY", "SELL"],
            "calculation": "flat_per_order",
            "amount": "1.00" if code == "BROKERAGE" else "0.00",
            "rounding_increment": "0.01",
            "rounding_mode": "HALF_UP",
            "rounding_scope": "cumulative_order",
            "sources": [source],
        }
        for code in ("BROKERAGE", "EXCHANGE", "STT", "SEBI", "STAMP", "GST", "IPFT", "CLEARING")
    ]
    execution = PaperExecutionConfig.model_validate(
        {
            "version": "isolated-depth-v1",
            "execution": {
                "version": "isolated-policy-v1",
                "reviewed": True,
                "assumed_latency_ms": 250,
                "displayed_participation": "0.5",
                "extra_adverse_slippage_bps": "0",
                "market_protection_bps": "100",
                "quote_max_age_ms": 2000,
                "pending_entry_lifetime_ms": 5000,
                "quantity_unit": "units",
                "quantity_unit_sources": [source],
                "partial_fill_granularity": "lots",
                "notes": "Isolated test assumptions",
            },
            "fee_schedules": [
                {
                    "version": "isolated-fees-" + venue,
                    "exchange": venue,
                    "effective_from": "2026-01-01",
                    "reviewed": True,
                    "account_pricing_verified": True,
                    "rules": rules,
                    "notes": "Test-only arithmetic",
                }
                for venue in ("NFO", "BFO")
            ],
        }
    )
    path = tmp_path / "execution.json"
    path.write_text(execution.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(module, "DEFAULT_CONFIG", path)
    monkeypatch.setitem(validation.CONFIG_FILES, "execution", path)
    # Isolate the deliberately closed activation gate while testing downstream
    # contracts; this is test-only and does not qualify or alter production.
    monkeypatch.setattr(validation, "input_binding", lambda account: "isolated-fixture")
    instrument = scenario.instrument.model_copy(update={"exchange": "NFO"})
    service = PaperCoordinator(db_engine, account_id, clock=lambda: clock.now)
    with Session(db_engine) as db, db.begin():
        legacy._persist_instrument(db, instrument)
        db.add(
            PaperValidation(
                id=uuid4(),
                account_id=account_id,
                instrument_id=instrument.id,
                exchange="NFO",
                session_key=scenario.session.key,
                status="ACTIVE",
                max_quantity=200,
                stream_generation=0,
                binding="isolated-fixture",
                started_at=scenario.now,
                expires_at=scenario.now + timedelta(minutes=5),
                request={},
                preflight={},
            )
        )
        db.add(
            RuntimeControl(
                account_id=account_id,
                mode="VALIDATION",
                heartbeat=scenario.now,
                status="PAUSED",
                active_envelope=scenario.envelope.model_dump(mode="json"),
            )
        )
    return SimpleNamespace(
        service=service,
        account=account_id,
        clock=clock,
        instrument=instrument,
        execution=execution,
        legacy=legacy,
        scenario=scenario,
        engine=db_engine,
    )


def observed(d, *, elapsed=0, bid="99.95", ask="100.00", depth=200):
    stamp = d.scenario.now + timedelta(milliseconds=elapsed)
    return Quote(
        instrument_id=d.instrument.id,
        timestamp=stamp,
        received_at=stamp,
        source="isolated-fixture",
        market_event_id="fixture:" + str(uuid4()),
        sequence=elapsed,
        timestamp_basis="exchange_feed",
        quantity_unit="units",
        quantity_unit_source="isolated-fixture",
        depth_kind="best_five",
        bid=bid,
        ask=ask,
        bid_quantity=depth,
        ask_quantity=depth,
        bid_depth=(DepthLevel(price=bid, quantity=depth),),
        ask_depth=(DepthLevel(price=ask, quantity=depth),),
        volume=1000,
        oi=2000,
    )


def admit(d):
    quote = observed(d)
    result = d.service.admit(
        d.scenario.decision.model_copy(update={"snapshot_ids": (quote.id,)}),
        d.instrument,
        quote,
        d.scenario.envelope.model_copy(update={"evidence_ids": (quote.id,)}),
        d.scenario.session,
        {d.instrument.id: quote},
    )
    assert result["status"] == "OPEN", result
    assert result["filled_quantity"] == 0
    return UUID(result["order_id"])


def cycle(d, elapsed, **kwargs):
    d.clock.now = d.scenario.now + timedelta(milliseconds=elapsed)
    quote = observed(d, elapsed=elapsed, **kwargs)
    d.service.cycle({d.instrument.id: quote}, {"NFO": d.scenario.session}, healthy=True)
    return quote


@pytest.fixture
def validation_start(durable, monkeypatch):
    """Provider boundaries only are isolated; admission uses the real DB/ledger."""
    d = durable
    now = d.clock.now
    with Session(d.engine) as db, db.begin():
        db.execute(delete(PaperValidation))
        account = db.get(Account, d.account)
        account.enabled = False
        control = db.get(RuntimeControl, d.account)
        control.resume_requested = False
        quote = observed(d).model_copy(update={"source": "angelone-websocket-v2:snapquote"})
        db.add(
            LatestMarketQuote(
                instrument_id=d.instrument.id, timestamp=now, payload=quote.model_dump(mode="json")
            )
        )
        revision = account.revision
    report = {
        "configuration_complete": True,
        "connections_verified": True,
        "worker_online": True,
        "checks": [{"diagnostic": "broker", "checked_at": now.isoformat()}],
    }
    monkeypatch.setattr(validation, "readiness", lambda *args, **kwargs: report)
    monkeypatch.setattr(
        validation,
        "MarketSettings",
        lambda: SimpleNamespace(
            calendar_file=None,
            session_file=None,
            client_code=SimpleNamespace(get_secret_value=lambda: "test"),
        ),
    )
    monkeypatch.setattr(
        validation,
        "SessionCalendar",
        lambda path: SimpleNamespace(get=lambda venue, day: d.scenario.session),
    )
    monkeypatch.setattr(
        validation,
        "SessionStore",
        lambda *args: SimpleNamespace(
            load=lambda: SimpleNamespace(expires_at=now + timedelta(hours=1))
        ),
    )
    request = ValidationRequest(
        request_id=uuid4(),
        expected_revision=revision,
        instrument_id=d.instrument.id,
        duration_seconds=300,
    )
    return SimpleNamespace(
        d=d, service=ValidationService(d.engine, d.account), request=request, report=report
    )


def test_validation_start_is_idempotent_bound_and_one_actual_lot(validation_start):
    v = validation_start
    result = v.service.start(v.request, v.d.clock.now)
    assert result["max_quantity"] == v.d.instrument.lot_size
    assert result["autonomous_qualified"] is False
    assert v.service.start(v.request, v.d.clock.now) == result
    with Session(v.d.engine) as db, db.begin():
        account = db.get(Account, v.d.account)
        assert account.enabled is False  # A real approved strategy is still required.
        assert db.get(RuntimeControl, account.id).resume_requested is True
        with pytest.raises(ValueError, match="SCOPE_EXCEEDED"):
            entry_lease(db, account, v.d.clock.now, v.d.instrument.id, v.d.instrument.lot_size * 2)
        with pytest.raises(ValueError, match="SCOPE_EXCEEDED"):
            entry_lease(db, account, v.d.clock.now, "other-contract")
    conflict = v.request.model_copy(update={"duration_seconds": 120})
    with pytest.raises(ValueError, match="REQUEST_CONFLICT"):
        v.service.start(conflict, v.d.clock.now)


@pytest.mark.parametrize(
    "check", ["configuration_complete", "connections_verified", "worker_online"]
)
def test_validation_start_requires_every_shared_preflight(validation_start, check):
    v = validation_start
    v.report[check] = False
    with pytest.raises(ValueError, match="PREFLIGHT_INCOMPLETE"):
        v.service.start(v.request, v.d.clock.now)
    with Session(v.d.engine) as db:
        assert not list(db.scalars(select(PaperValidation)))
        assert not db.get(RuntimeControl, v.d.account).resume_requested


def test_validation_start_rejects_observation_stale_revision_and_stale_depth(validation_start):
    v = validation_start
    with Session(v.d.engine) as db, db.begin():
        db.get(RuntimeControl, v.d.account).mode = "OBSERVATION"
    with pytest.raises(ValueError, match="WORKER_REQUIRED"):
        v.service.start(v.request, v.d.clock.now)
    with Session(v.d.engine) as db, db.begin():
        db.get(RuntimeControl, v.d.account).mode = "VALIDATION"
    with pytest.raises(ValueError, match="SETTINGS_CHANGED"):
        v.service.start(v.request.model_copy(update={"expected_revision": 999}), v.d.clock.now)
    with Session(v.d.engine) as db, db.begin():
        row = db.get(LatestMarketQuote, v.d.instrument.id)
        row.payload = {
            **row.payload,
            "timestamp": (v.d.clock.now - timedelta(seconds=3)).isoformat(),
        }
    with pytest.raises(ValueError, match="FRESH_DEPTH_REQUIRED"):
        v.service.start(v.request, v.d.clock.now)


def test_validation_no_trade_expiry_is_reconciled_and_never_qualifies(validation_start):
    v = validation_start
    v.service.start(v.request, v.d.clock.now)
    result = v.service.tick(v.d.clock.now + timedelta(minutes=5))
    assert result["status"] == "STOPPED"
    assert result["stop_reason"] == "VALIDATION_EXPIRED"
    assert result["outcome"]["result"] == "NO_TRADE_OBSERVED"
    assert result["outcome"]["reconciled"] is True
    assert result["outcome"]["autonomous_qualified"] is False
    assert v.service.stop(v.request.request_id, v.d.clock.now + timedelta(minutes=6)) == result


@pytest.mark.parametrize("reason", ["stop", "inputs", "generation", "restart"])
def test_validation_invalidation_prevents_pending_fill_and_reconciles(durable, monkeypatch, reason):
    d = durable
    order_id = admit(d)
    service = ValidationService(d.engine, d.account)
    if reason == "stop":
        with Session(d.engine) as db:
            identifier = db.scalar(select(PaperValidation.id))
        result = service.stop(identifier, d.clock.now)
    elif reason == "inputs":
        monkeypatch.setattr(validation, "input_binding", lambda account: "changed")
        result = service.tick(d.clock.now)
    elif reason == "generation":
        with Session(d.engine) as db, db.begin():
            db.get(RuntimeControl, d.account).stream_generation += 1
        result = service.tick(d.clock.now)
    else:
        RuntimeStore(d.engine, d.account).initialize(d.clock.now, "VALIDATION")
        with Session(d.engine) as db:
            result = validation.view(db.scalar(select(PaperValidation)))
    assert result["status"] == "STOPPING"  # Pending order must first be acknowledged cancelled.
    cycle(d, 300)
    result = service.tick(d.clock.now)
    assert result["status"] == "STOPPED"
    with Session(d.engine) as db:
        assert db.get(PaperOrder, order_id).filled_quantity == 0
        assert not list(db.scalars(select(PaperFill)))
        assert not db.get(Account, d.account).enabled


def test_stopped_validation_drains_real_ledger_exposure_before_reporting(durable):
    d = durable
    admit(d)
    cycle(d, 300)
    service = ValidationService(d.engine, d.account)
    with Session(d.engine) as db:
        identifier = db.scalar(select(PaperValidation.id))
    assert service.stop(identifier, d.clock.now)["status"] == "STOPPING"
    cycle(d, 600)
    cycle(d, 900)
    result = service.tick(d.clock.now)
    assert result["status"] == "STOPPED"
    assert result["outcome"]["result"] == "RECORDED_FILLS"
    assert len(result["outcome"]["fills"]) == 2
    assert {o["side"] for o in result["outcome"]["orders"]} == {"BUY", "SELL"}
    assert result["outcome"]["reconciled"] is True


def test_validation_one_entry_attempt_cannot_be_reused(durable):
    d = durable
    admit(d)
    with Session(d.engine) as db, db.begin():
        account = db.get(Account, d.account)
        with pytest.raises(ValueError, match="ENTRY_LIMIT"):
            entry_lease(db, account, d.clock.now, d.instrument.id)


def test_started_validation_uses_real_risk_cap_and_collects_actual_fill_references(
    validation_start,
):
    v = validation_start
    d = v.d
    v.service.start(v.request, d.clock.now)
    store = RuntimeStore(d.engine, d.account)
    slot = store.save_evaluation(
        d.scenario.session,
        d.clock.now,
        {d.instrument.id: d.instrument},
        [d.scenario.quote],
        d.clock.now,
    )
    store.finish_evaluation(slot, "STRATEGY_APPROVED", 0, d.scenario.envelope, d.clock.now)
    assert RuntimeStore(d.engine, d.account).enable_requested(
        d.scenario.envelope.id, 0, d.clock.now
    )
    order_id = admit(d)
    with Session(d.engine) as db:
        order = db.get(PaperOrder, order_id)
        assert order.quantity == d.instrument.lot_size
        assert order.validation_id == v.request.request_id
    cycle(d, 300)
    cycle(d, 600, bid="106.00", ask="106.05")
    cycle(d, 900, bid="106.00", ask="106.05")
    result = v.service.tick(d.clock.now)
    assert result["status"] == "STOPPED"
    assert result["outcome"]["entry_attempts"] == 1
    assert len(result["outcome"]["fills"]) == 2
    assert all(f["snapshot_id"] and f["market_event_id"] for f in result["outcome"]["fills"])
    assert result["autonomous_qualified"] is False


def test_validation_api_owner_scope_and_pause_cancels_session(durable):
    d = durable
    app.state.engine = d.engine
    app.dependency_overrides[account_identity] = lambda: d.account
    client = TestClient(app)
    try:
        response = client.get("/api/validation")
        assert response.status_code == 200
        identifier = response.json()["sessions"][0]["id"]
        stranger = d.legacy.create_account(d.scenario.config, d.clock.now)
        app.dependency_overrides[account_identity] = lambda: stranger
        assert client.get("/api/validation").json()["sessions"] == []
        assert client.post(f"/api/validation/{identifier}/stop").status_code == 404
        app.dependency_overrides[account_identity] = lambda: d.account
        assert client.post("/api/control/pause").status_code == 200
        result = client.get("/api/validation").json()["sessions"][0]
        assert result["status"] == "STOPPED"
        assert result["stop_reason"] == "USER_PAUSE"
    finally:
        app.dependency_overrides.pop(account_identity, None)
    assert client.get("/api/validation").status_code in {401, 503}


@pytest.mark.parametrize("action", ["stop", "observer_restart"])
def test_late_agent_result_after_stop_cannot_restore_entry_intent(durable, action):
    d = durable
    with Session(d.engine) as db, db.begin():
        identifier = db.scalar(select(PaperValidation.id))
        slot = EvaluationSlot(
            validation_id=identifier,
            account_id=d.account,
            session_key=d.scenario.session.key,
            slot_at=d.clock.now,
            status="AWAITING_AGENT",
            evidence_ids=list(map(str, d.scenario.envelope.evidence_ids)),
        )
        db.add(slot)
        db.flush()
        slot_id = slot.id
    if action == "stop":
        ValidationService(d.engine, d.account).stop(identifier, d.clock.now)
    else:
        RuntimeStore(d.engine, d.account).initialize(d.clock.now, "OBSERVATION")
    RuntimeStore(d.engine, d.account).finish_evaluation(
        slot_id, "STRATEGY_APPROVED", 0, d.scenario.envelope, d.clock.now
    )
    with Session(d.engine) as db:
        control = db.get(RuntimeControl, d.account)
        assert control.active_envelope is None
        assert control.resume_requested is False
        assert db.get(EvaluationSlot, slot_id).status == "INVALIDATED_DURING_ANALYSIS"


@pytest.mark.asyncio
async def test_idle_validation_worker_does_not_generate_agents(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock

    from services.market.settings import MarketSettings
    from services.worker import runtime as worker

    agents = SimpleNamespace(evaluate=AsyncMock())
    monkeypatch.setattr(worker, "AgentPipeline", lambda *args: agents)
    runtime = worker.TradingRuntime(
        None,
        None,
        MarketSettings(_env_file=None, calendar_file=tmp_path / "missing"),
        validation_only=True,
    )
    runtime.validation.active_scope = lambda now: None
    await runtime.evaluation_slot()
    agents.evaluate.assert_not_called()
    await runtime.client.close()


def test_analysis_from_previous_session_cannot_arm_new_session(durable):
    d = durable
    store = RuntimeStore(d.engine, d.account)
    slot = store.save_evaluation(
        d.scenario.session,
        d.clock.now,
        {d.instrument.id: d.instrument},
        [d.scenario.quote],
        d.clock.now,
    )
    with Session(d.engine) as db:
        identifier = db.scalar(select(PaperValidation.id))
    ValidationService(d.engine, d.account).stop(identifier, d.clock.now)
    with Session(d.engine) as db, db.begin():
        db.add(
            PaperValidation(
                id=uuid4(),
                account_id=d.account,
                instrument_id=d.instrument.id,
                exchange="NFO",
                session_key=d.scenario.session.key,
                status="ACTIVE",
                max_quantity=25,
                stream_generation=0,
                binding="isolated-fixture",
                started_at=d.clock.now,
                expires_at=d.clock.now + timedelta(minutes=5),
                request={},
                preflight={},
            )
        )
        db.get(RuntimeControl, d.account).resume_requested = True
    store.finish_evaluation(slot, "STRATEGY_APPROVED", 0, d.scenario.envelope, d.clock.now)
    with Session(d.engine) as db:
        assert db.get(RuntimeControl, d.account).active_envelope is None
        assert db.get(EvaluationSlot, slot).status == "INVALIDATED_DURING_ANALYSIS"
    assert not store.enable_requested(d.scenario.envelope.id, 0, d.clock.now)


def test_durable_entry_protection_target_exit_and_reconciliation(durable):
    d = durable
    order_id = admit(d)
    cycle(d, 100)  # Latency is enforced, no immediate fill.
    with Session(d.engine) as db:
        assert db.get(PaperOrder, order_id).filled_quantity == 0
    cycle(d, 300)
    with Session(d.engine) as db:
        entry = db.get(PaperOrder, order_id)
        assert entry.status == "FILLED"
        position = db.scalar(select(PaperPosition))
        assert position is not None and position.quantity == entry.quantity
        exits = list(db.scalars(select(PaperOrder).where(PaperOrder.side == "SELL")))
        assert len(exits) == 1 and exits[0].order_type == "STOP_MARKET"
        assert exits[0].reason == "PROTECTIVE_STOP"
    cycle(d, 600, bid="106.00", ask="106.05")
    cycle(d, 900, bid="106.00", ask="106.05")
    with Session(d.engine) as db:
        account = db.get(Account, d.account)
        position = db.scalar(select(PaperPosition))
        assert position.closed_at is not None
        fills = list(db.scalars(select(PaperFill)))
        sides = {o.id: o.side for o in db.scalars(select(PaperOrder))}
        assert len(fills) == 2
        assert all(f.fee_breakdown["BROKERAGE"] == "1.00" for f in fills)
        assert account.cash == Decimal("100000") + sum(
            (
                f.price * f.quantity * (1 if sides[f.order_id] == "SELL" else -1) - f.fees
                for f in fills
            ),
            Decimal(0),
        )
        assert reconcile_account(db, account) == []
        assert list(db.scalars(select(PaperFundsHold)))  # Sale proceeds remain restricted.


def test_first_partial_entry_cancels_remainder_and_installs_protection(durable):
    d = durable
    order_id = admit(d)
    cycle(d, 300, depth=50)
    with Session(d.engine) as db:
        entry = db.get(PaperOrder, order_id)
        assert entry.status == "CANCELLED"
        assert entry.filled_quantity == 25 < entry.quantity
        assert entry.reserved_cash == entry.reserved_risk == 0
        exits = list(db.scalars(select(PaperOrder).where(PaperOrder.side == "SELL")))
        assert len(exits) == 1 and exits[0].quantity == 25
        assert reconcile_account(db, db.get(Account, d.account)) == []


def test_pausing_cancels_unfilled_durable_entry_without_exposure(durable):
    d = durable
    order_id = admit(d)
    d.legacy.set_enabled(d.account, False, d.clock.now)
    cycle(d, 300)
    with Session(d.engine) as db:
        entry = db.get(PaperOrder, order_id)
        assert entry.status == "CANCELLED"
        assert entry.filled_quantity == 0
        assert not list(db.scalars(select(PaperPosition)))
        assert db.get(Account, d.account).cash == Decimal("100000")
        assert reconcile_account(db, db.get(Account, d.account)) == []


def test_restart_and_repeated_quote_do_not_duplicate_fills_and_paused_stop_still_exits(durable):
    d = durable
    admit(d)
    quote = cycle(d, 300)
    d.legacy.set_enabled(d.account, False, d.clock.now)
    # Reconstruct the service from durable state; repeat the exact observation.
    d.service = PaperCoordinator(d.engine, d.account, clock=lambda: d.clock.now)
    d.service.cycle({d.instrument.id: quote}, {"NFO": d.scenario.session}, healthy=True)
    with Session(d.engine) as db:
        assert len(list(db.scalars(select(PaperFill)))) == 1
        assert db.get(Account, d.account).enabled is False
    cycle(d, 600, bid="95.00", ask="95.05")
    cycle(d, 900, bid="94.90", ask="94.95")
    with Session(d.engine) as db:
        assert db.scalar(select(PaperPosition)).closed_at is not None
        assert len(list(db.scalars(select(PaperFill)))) == 2
        account = db.get(Account, d.account)
        assert account.enabled is False
        assert reconcile_account(db, account) == []


@pytest.mark.parametrize("held", [False, True])
def test_unresolved_durable_orders_or_positions_prevent_daily_baseline_reset(durable, held):
    d = durable
    admit(d)
    if held:
        cycle(d, 300)
    with Session(d.engine) as db, db.begin():
        db.get(Account, d.account).daily_blocked = True
    next_day = d.scenario.now + timedelta(days=1)
    session = d.scenario.session.model_copy(
        update={
            "key": next_day.date(),
            "opens_at": next_day.replace(hour=9, minute=15),
            "closes_at": next_day.replace(hour=15, minute=30),
        }
    )
    with pytest.raises(ValueError, match="Unresolved"):
        d.legacy.start_session(d.account, session, next_day)
    with Session(d.engine) as db:
        account = db.get(Account, d.account)
        assert account.daily_blocked is True
        assert account.session_key == d.scenario.session.key
        assert reconcile_account(db, account) == []
