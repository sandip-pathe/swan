"""Manual intent uses the real paper ledger; fixtures never qualify a live account."""

# Imported pytest fixtures are injected by name.
# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_durable import cycle, durable, observed, validation_start  # noqa: F401

from services.core.models import (
    Account,
    DecisionRecord,
    ManualIntentRecord,
    ManualPaperPlan,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PaperValidation,
    StrategyRecord,
)
from services.paper import coordinator, manual
from services.paper.accounting import reconcile_account
from services.paper.contracts import OrderRequest
from services.paper.manual import ManualPaperService
from services.paper.qualification import entry_permission, session_facts
from services.paper.validation import ValidationService
from services.worker.models import RuntimeControl
from services.worker.store import RuntimeStore

pytestmark = pytest.mark.integration


@pytest.fixture
def human(durable, monkeypatch):
    d = durable
    monkeypatch.setattr(manual, "DEFAULT_CONFIG", coordinator.DEFAULT_CONFIG)
    plan_id, request_id = uuid4(), uuid4()
    with Session(d.engine) as db, db.begin():
        lease = db.scalar(select(PaperValidation))
        lease.request = {"entry_source": "HUMAN"}
        lease.max_quantity = d.instrument.lot_size
        lease_id = lease.id
        control = db.get(RuntimeControl, d.account)
        control.active_envelope = None
        control.resume_requested = True
        account = db.get(Account, d.account)
        account.enabled = False
        db.add(
            ManualPaperPlan(
                id=plan_id,
                account_id=d.account,
                instrument_id=d.instrument.id,
                idempotency_key=uuid4(),
                created_at=d.clock.now,
                request_payload=dict(
                    instrument_id=d.instrument.id, lots=1, entry="100", stop_loss="96", target="106"
                ),
                instrument_payload=d.instrument.model_dump(mode="json"),
                preview_payload={},
            )
        )
    store = RuntimeStore(d.engine, d.account)
    assert store.enable_manual_requested(lease_id, 0, d.clock.now)
    with Session(d.engine) as db:
        revision = db.get(Account, d.account).revision
    return SimpleNamespace(
        d=d,
        service=ManualPaperService(d.engine, d.account, clock=lambda: d.clock.now),
        plan=plan_id,
        request=request_id,
        revision=revision,
        lease=lease_id,
        store=store,
    )


def submit(h, **kwargs):
    d = h.d
    quote = observed(d)
    return h.service.submit(
        h.plan,
        h.request,
        h.revision,
        kwargs.get("quote", quote),
        kwargs.get("session", d.scenario.session),
        {d.instrument.id: quote},
    )


def assert_clean(d):
    with Session(d.engine) as db:
        assert reconcile_account(db, db.get(Account, d.account)) == []
        assert db.scalar(select(func.count()).select_from(DecisionRecord)) == 0
        assert db.scalar(select(func.count()).select_from(StrategyRecord)) == 0


def test_human_entry_latency_protection_target_and_retry(human):
    h, d = human, human.d
    result = submit(h)
    identifier = UUID(result["order_id"])
    assert result["status"] == "OPEN" and result["quantity"] == d.instrument.lot_size
    assert submit(h)["order_id"] == str(identifier)
    cycle(d, 100)
    with Session(d.engine) as db:
        assert db.get(PaperOrder, identifier).filled_quantity == 0
    cycle(d, 300)
    with Session(d.engine) as db:
        entry = db.get(PaperOrder, identifier)
        assert entry.manual_intent_id == h.request and entry.decision_id is None
        assert entry.status == "FILLED"
        position = db.scalar(select(PaperPosition))
        assert position.stop_loss == 96 and position.target == 106
        assert position.max_holding_seconds == d.scenario.config.max_holding_seconds
        assert (
            db.scalar(select(PaperOrder).where(PaperOrder.side == "SELL")).reason
            == "PROTECTIVE_STOP"
        )
    cycle(d, 600, bid="106", ask="106.05")
    cycle(d, 900, bid="106", ask="106.05")
    with Session(d.engine) as db:
        assert db.scalar(select(PaperPosition)).closed_at is not None
        assert db.scalar(select(func.count()).select_from(PaperFill)) == 2
    assert submit(h)["order_id"] == str(identifier)  # Retry after the account revision changed.
    assert_clean(d)


def test_concurrent_human_retries_and_conflicting_identity(human):
    h = human
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(h), range(2)))
    assert results[0]["order_id"] == results[1]["order_id"]
    with pytest.raises(ValueError, match="MANUAL_REQUEST_CONFLICT"):
        h.service.submit(uuid4(), h.request, h.revision, observed(h.d), h.d.scenario.session, {})
    with Session(h.d.engine) as db:
        assert db.scalar(select(func.count()).select_from(ManualIntentRecord)) == 1
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 1
    assert_clean(h.d)


@pytest.mark.parametrize(
    "problem",
    [
        "paused",
        "source",
        "envelope",
        "stale",
        "cash",
        "risk",
        "depth",
        "revision",
        "archived",
        "expiry",
    ],
)
def test_human_admission_rejects_without_creating_orders(human, problem):
    h, d = human, human.d
    quote = observed(d)
    with Session(d.engine) as db, db.begin():
        account = db.get(Account, d.account)
        lease = db.get(PaperValidation, h.lease)
        plan = db.get(ManualPaperPlan, h.plan)
        if problem == "paused":
            account.enabled = False
        elif problem == "source":
            lease.request = {"entry_source": "AI"}
        elif problem == "envelope":
            db.get(RuntimeControl, d.account).active_envelope = d.scenario.envelope.model_dump(
                mode="json"
            )
        elif problem == "cash":
            plan.request_payload = {**plan.request_payload, "entry": "10000", "target": "10001"}
        elif problem == "risk":
            plan.request_payload = {**plan.request_payload, "stop_loss": "1"}
        elif problem == "revision":
            account.revision += 1
        elif problem == "archived":
            plan.archived_at = d.clock.now
        elif problem == "expiry":
            lease.expires_at = d.clock.now
    if problem == "stale":
        quote = quote.model_copy(update={"timestamp": d.clock.now - timedelta(seconds=10)})
    if problem == "depth":
        quote = observed(d, depth=25)
    try:
        result = submit(h, quote=quote)
        assert result["status"] == "REJECTED"
    except ValueError:
        pass
    with Session(d.engine) as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
    assert_clean(d)


@pytest.mark.parametrize("change", ["pause", "source", "stream", "lease", "mode", "below_stop"])
def test_human_fill_rechecks_permission(human, change):
    h, d = human, human.d
    order = UUID(submit(h)["order_id"])
    with Session(d.engine) as db, db.begin():
        control = db.get(RuntimeControl, d.account)
        if change == "pause":
            db.get(Account, d.account).enabled = False
        elif change == "source":
            db.get(PaperValidation, h.lease).request = {"entry_source": "AI"}
        elif change == "stream":
            control.stream_generation += 1
        elif change == "lease":
            db.get(PaperValidation, h.lease).status = "STOPPING"
        elif change == "mode":
            control.mode = "AUTONOMOUS"
    cycle(d, 300, bid="95.95", ask="96") if change == "below_stop" else cycle(d, 300)
    with Session(d.engine) as db:
        entry = db.get(PaperOrder, order)
        assert entry.filled_quantity == 0
        assert entry.status == "CANCELLED"
        assert entry.reserved_cash == entry.reserved_risk == 0
    assert_clean(d)


def test_manual_pause_restart_drains_protection_and_not_ai_qualification(human):
    h, d = human, human.d
    submit(h)
    cycle(d, 300)
    assert d.service.ledger.recover(d.account, d.clock.now)["reconciled"]
    ValidationService(d.engine, d.account).stop(h.lease, d.clock.now)
    d.service = coordinator.PaperCoordinator(d.engine, d.account, clock=lambda: d.clock.now)
    cycle(d, 600, bid="99.95", ask="100")
    cycle(d, 900, bid="99.95", ask="100")
    ValidationService(d.engine, d.account).tick(d.clock.now)
    with Session(d.engine) as db:
        assert db.scalar(select(PaperPosition)).closed_at is not None
        account = db.get(Account, d.account)
        assert not account.enabled
        lease = db.get(PaperValidation, h.lease)
        assert lease.status == "STOPPED"
        assert session_facts(db, account, lease, lease.binding)["checks"] == []
    assert_clean(d)


def test_human_and_ai_permissions_are_exclusive_and_pause_wins(human):
    h, d = human, human.d
    with Session(d.engine) as db, db.begin():
        with pytest.raises(ValueError, match="ENTRY_SOURCE_MISMATCH"):
            entry_permission(db, db.get(Account, d.account), d.clock.now, d.instrument.id)
        control = db.get(RuntimeControl, d.account)
        control.resume_requested = False
        db.get(Account, d.account).enabled = False
    assert not h.store.enable_manual_requested(h.lease, 0, d.clock.now)
    with pytest.raises(ValidationError):
        OrderRequest(
            idempotency_key="bad",
            instrument_id=d.instrument.id,
            side="BUY",
            quantity=25,
            submitted_at=d.clock.now,
            expires_at=d.clock.now + timedelta(seconds=1),
            cash_budget="100",
            risk_budget="10",
            reason="invalid",
            decision_id=uuid4(),
            manual_intent_id=uuid4(),
        )


def test_explicit_human_validation_start_retains_shared_gates(validation_start):
    v = validation_start
    request = v.request.model_copy(update={"entry_source": "HUMAN"})
    result = v.service.start(request, v.d.clock.now)
    assert result["entry_source"] == "HUMAN" and result["max_quantity"] == v.d.instrument.lot_size
    with Session(v.d.engine) as db:
        assert not db.get(Account, v.d.account).enabled
        assert db.get(RuntimeControl, v.d.account).status == "MANUAL_AWAITING_ENTRY"


def test_human_partial_fill_cancels_remainder_and_keeps_protection(human):
    h, d = human, human.d
    execution = d.execution.model_copy(
        update={
            "execution": d.execution.execution.model_copy(
                update={"partial_fill_granularity": "units"}
            )
        }
    )
    manual.DEFAULT_CONFIG.write_text(execution.model_dump_json(), encoding="utf-8")
    order_id = UUID(submit(h)["order_id"])
    cycle(d, 300, depth=30)
    with Session(d.engine) as db:
        entry = db.get(PaperOrder, order_id)
        position = db.scalar(select(PaperPosition))
        assert entry.status == "CANCELLED" and entry.filled_quantity == 15
        assert position.quantity == 15 and position.stop_loss == 96
        assert entry.reserved_cash == entry.reserved_risk == 0
        exits = list(db.scalars(select(PaperOrder).where(PaperOrder.side == "SELL")))
        assert len(exits) == 1 and exits[0].quantity == 15
        revision = db.get(Account, d.account).revision
    with pytest.raises(ValueError, match="VALIDATION_ENTRY_LIMIT"):
        h.service.submit(h.plan, uuid4(), revision, observed(d), d.scenario.session, {})
    assert_clean(d)


def test_pause_between_risk_approval_and_ledger_admission_wins(human, monkeypatch):
    h, d = human, human.d
    original = h.service.ledger.submit

    def paused(*args, **kwargs):
        d.legacy.set_enabled(d.account, False, d.clock.now)
        return original(*args, **kwargs)

    monkeypatch.setattr(h.service.ledger, "submit", paused)
    with pytest.raises(ValueError, match="paused"):
        submit(h)
    with Session(d.engine) as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
        assert not db.get(Account, d.account).enabled
    assert_clean(d)


def test_manual_intent_owner_isolation(human):
    h, d = human, human.d
    other = d.legacy.create_account(d.scenario.config, d.clock.now)
    foreign = ManualPaperService(d.engine, other, clock=lambda: d.clock.now)
    with pytest.raises(ValueError, match="PAPER_PLAN_NOT_FOUND"):
        foreign.submit(h.plan, uuid4(), 0, observed(d), d.scenario.session, {})
    submit(h)
    with pytest.raises(ValueError, match="MANUAL_REQUEST_CONFLICT"):
        foreign.submit(h.plan, h.request, h.revision, observed(d), d.scenario.session, {})
    assert_clean(d)


@pytest.mark.parametrize("reason", ["STOP_LOSS", "FEED_UNAVAILABLE"])
def test_manual_protection_exits_without_ai_envelope(human, reason):
    h, d = human, human.d
    submit(h)
    cycle(d, 300)
    d.clock.now = d.scenario.now + timedelta(milliseconds=600)
    quote = observed(
        d,
        elapsed=600,
        bid="95.95" if reason == "STOP_LOSS" else "99.95",
        ask="96" if reason == "STOP_LOSS" else "100",
    )
    d.service.cycle(
        {d.instrument.id: quote}, {"NFO": d.scenario.session}, healthy=reason != "FEED_UNAVAILABLE"
    )
    with Session(d.engine) as db:
        position = db.scalar(select(PaperPosition))
        assert position.pending_exit == reason
        exit_order = db.scalar(
            select(PaperOrder).where(PaperOrder.side == "SELL", PaperOrder.status == "OPEN")
        )
        assert exit_order.reason == reason
    cycle(
        d,
        900,
        bid="95.95" if reason == "STOP_LOSS" else "99.95",
        ask="96" if reason == "STOP_LOSS" else "100",
    )
    with Session(d.engine) as db:
        assert db.scalar(select(PaperPosition)).closed_at is not None
    assert_clean(d)


def test_accepted_manual_retry_survives_configuration_unavailability(human, monkeypatch):
    h = human
    first = submit(h)
    monkeypatch.setattr(
        manual, "DEFAULT_CONFIG", manual.DEFAULT_CONFIG.parent / "missing-config.json"
    )
    assert submit(h) == first


@pytest.mark.asyncio
async def test_human_worker_enables_only_requested_source_without_agents(
    human, monkeypatch, tmp_path
):
    import asyncio
    from datetime import datetime
    from unittest.mock import AsyncMock

    from services.market.settings import MarketSettings
    from services.worker import runtime as worker

    d = human.d
    now = d.clock.now

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    agents = SimpleNamespace(evaluate=AsyncMock())
    monkeypatch.setattr(worker, "datetime", FixedDatetime)
    monkeypatch.setattr(worker, "AgentPipeline", lambda *args: agents)
    runtime = worker.TradingRuntime(
        d.engine,
        d.account,
        MarketSettings(_env_file=None, calendar_file=tmp_path / "missing"),
        validation_only=True,
    )
    runtime.current_session = lambda *args: d.scenario.session
    runtime.instruments = {d.instrument.id: d.instrument}
    runtime.cache.connected, runtime.cache.problem = True, None
    runtime.cache.quotes[d.instrument.id] = observed(d)
    runtime.last_candle_publication = runtime.last_publication = asyncio.get_running_loop().time()
    with Session(d.engine) as db, db.begin():
        db.get(Account, d.account).enabled = False
    try:
        await runtime.evaluation_slot()
        await runtime.cycle()
        agents.evaluate.assert_not_called()
        with Session(d.engine) as db:
            assert db.get(Account, d.account).enabled
            assert db.get(RuntimeControl, d.account).active_envelope is None
            assert db.get(RuntimeControl, d.account).status == "MANUAL_READY"
    finally:
        await runtime.client.close()
