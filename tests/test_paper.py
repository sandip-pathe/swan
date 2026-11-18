from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from services.core.export_contracts import artifacts
from services.core.models import (
    Account,
    AuditEvent,
    Base,
    DecisionRecord,
    LedgerEntry,
    PaperFill,
    PaperOrder,
    PaperPosition,
)
from services.paper.engine import ConflictError, PaperEngine

pytestmark = pytest.mark.integration


def enter(paper, s, decision=None):
    engine, account = paper
    return engine.enter(
        account, decision or s.decision, s.instrument, s.quote, s.envelope, s.session, s.now
    )


def quote_at(s, at, bid="106.00", **changes):
    return s.exit_quote.model_copy(
        update={
            "id": uuid4(),
            "timestamp": at,
            "received_at": at,
            "bid": Decimal(bid),
            "ask": Decimal(bid) + Decimal("0.05"),
            **changes,
        }
    )


def test_full_session_matches_golden_ledger(paper, scenario, db_engine):
    engine, account = paper
    entry = enter(paper, scenario)
    assert entry.quantity == scenario.expected["quantity"]
    assert entry.fill_price == scenario.expected["entry_price"]
    exits = engine.monitor(
        account,
        {scenario.instrument.id: scenario.exit_quote},
        scenario.session,
        scenario.exit_quote.timestamp,
    )
    assert len(exits) == 1 and exits[0].reason == "TAKE_PROFIT"
    report = engine.portfolio(account, {}, scenario.exit_quote.timestamp)
    assert report["reconciled"] and report["open_positions"] == 0
    assert report["cash"] == scenario.expected["final_cash"]
    assert report["fees"] == scenario.expected["fees"]
    assert report["realized_pnl"] == scenario.expected["net_pnl"]
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(LedgerEntry)) == 5
        assert db.scalar(select(func.count()).select_from(PaperFill)) == 2


def test_decision_and_exit_retries_are_idempotent(paper, scenario, db_engine):
    engine, account = paper
    first = enter(paper, scenario)
    assert enter(paper, scenario) == first
    engine.monitor(
        account,
        {scenario.instrument.id: scenario.exit_quote},
        scenario.session,
        scenario.exit_quote.timestamp,
    )
    assert (
        engine.monitor(
            account,
            {scenario.instrument.id: scenario.exit_quote},
            scenario.session,
            scenario.exit_quote.timestamp,
        )
        == []
    )
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 2
        assert db.scalar(select(func.count()).select_from(DecisionRecord)) == 1


def test_reusing_decision_id_with_different_contents_is_rejected(paper, scenario):
    enter(paper, scenario)
    with pytest.raises(ConflictError):
        enter(
            paper, scenario, scenario.decision.model_copy(update={"rationale": "Changed payload"})
        )


@pytest.mark.parametrize("same_decision", [True, False])
def test_simultaneous_entries_cannot_duplicate_or_exceed_limit(
    paper, scenario, db_engine, same_decision
):
    barrier = Barrier(2)

    def submit(index):
        decision = (
            scenario.decision
            if same_decision or index == 0
            else scenario.decision.model_copy(update={"id": uuid4()})
        )
        barrier.wait(timeout=10)
        return enter(paper, scenario, decision)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, [0, 1]))
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 1
        assert db.scalar(select(func.count()).select_from(PaperPosition)) == 1
    if same_decision:
        assert results[0].order_id == results[1].order_id
    else:
        assert sorted(r.status for r in results) == ["FILLED", "REJECTED"]


def test_pause_blocks_inflight_proposal_but_does_not_stop_exit(paper, scenario):
    engine, account = paper
    engine.set_enabled(account, False, scenario.now)
    assert enter(paper, scenario).reason == "PAUSED"
    engine.set_enabled(account, True, scenario.now)
    assert (
        enter(paper, scenario, scenario.decision.model_copy(update={"id": uuid4()})).status
        == "FILLED"
    )
    engine.set_enabled(account, False, scenario.now)
    exits = engine.monitor(
        account,
        {scenario.instrument.id: scenario.exit_quote},
        scenario.session,
        scenario.exit_quote.timestamp,
    )
    assert exits[0].status == "FILLED"


def test_gap_stop_fills_available_bid_not_stop_price(paper, scenario):
    engine, account = paper
    enter(paper, scenario)
    quote = quote_at(scenario, scenario.now + timedelta(seconds=30), bid="90")
    result = engine.monitor(
        account, {scenario.instrument.id: quote}, scenario.session, quote.timestamp
    )
    assert result[0].reason == "STOP_LOSS" and result[0].fill_price == "89.95"
    report = engine.portfolio(account, {}, quote.timestamp)
    assert Decimal(report["realized_pnl"]) < -Decimal("500")
    assert report["reconciled"]


def test_daily_loss_blocks_entries_and_survives_recovery(paper, scenario):
    engine, account = paper
    enter(paper, scenario)
    quote = quote_at(scenario, scenario.now + timedelta(seconds=30), bid="70")
    result = engine.monitor(
        account, {scenario.instrument.id: quote}, scenario.session, quote.timestamp
    )
    assert result[0].reason == "DAILY_LOSS_LIMIT"
    assert engine.recover(account, quote.timestamp)
    engine.start_session(account, scenario.session, quote.timestamp)
    report = engine.portfolio(account, {}, quote.timestamp)
    assert report["daily_blocked"] and not report["enabled"]
    assert report["session_opening_equity"] == "100000.00"
    with pytest.raises(ValueError, match="cannot resume"):
        engine.set_enabled(account, True, quote.timestamp)


def test_cutoff_with_missing_quotes_persists_pending_exit(paper, scenario, db_engine):
    engine, account = paper
    enter(paper, scenario)
    cutoff = scenario.session.closes_at - timedelta(minutes=10)
    assert engine.monitor(account, {}, scenario.session, cutoff)[0].status == "PENDING"
    report = engine.portfolio(account, {}, cutoff)
    assert report["equity"] is None and report["open_positions"] == 1
    assert engine.recover(account, cutoff)
    with pytest.raises(ValueError):
        engine.set_enabled(account, True, cutoff)
    quote = quote_at(scenario, cutoff + timedelta(seconds=1), bid="100")
    result = engine.monitor(
        account, {scenario.instrument.id: quote}, scenario.session, quote.timestamp
    )
    assert result[0].status == "FILLED" and result[0].reason == "SESSION_FLATTEN"
    with Session(db_engine) as db:
        assert db.scalar(select(PaperPosition)).pending_exit is None


def test_shallow_exit_is_pending_until_complete_depth_returns(paper, scenario):
    engine, account = paper
    enter(paper, scenario)
    shallow = scenario.exit_quote.model_copy(update={"bid_quantity": 1})
    result = engine.monitor(
        account, {scenario.instrument.id: shallow}, scenario.session, shallow.timestamp
    )
    assert result[0].reason == "INSUFFICIENT_DEPTH"
    # A target-triggered pending exit remains due even if price returns below the target.
    quote = quote_at(scenario, shallow.timestamp + timedelta(seconds=1), bid="101")
    result = engine.monitor(
        account, {scenario.instrument.id: quote}, scenario.session, quote.timestamp
    )
    assert result[0].reason == "TAKE_PROFIT" and result[0].status == "FILLED"


def test_stale_quotes_never_fill_exit(paper, scenario):
    engine, account = paper
    enter(paper, scenario)
    at = scenario.now + timedelta(seconds=300)
    result = engine.monitor(account, {scenario.instrument.id: scenario.quote}, scenario.session, at)
    assert result[0].status == "PENDING" and result[0].reason == "MAX_HOLDING_TIME"


def test_atomic_rollback_after_fill_write(paper, scenario, db_engine, monkeypatch):
    engine, account = paper
    original = engine._record_fill

    def fail_after_write(*args):
        original(*args)
        raise RuntimeError("Injected process failure before transaction commit")

    monkeypatch.setattr(engine, "_record_fill", fail_after_write)
    with pytest.raises(RuntimeError, match="Injected"):
        enter(paper, scenario)
    with Session(db_engine) as db:
        assert db.scalar(select(Account.cash)) == Decimal("100000")
        assert db.scalar(select(func.count()).select_from(PaperFill)) == 0
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
        assert db.scalar(select(func.count()).select_from(DecisionRecord)) == 0
        assert db.scalar(select(func.count()).select_from(LedgerEntry)) == 1
    monkeypatch.setattr(engine, "_record_fill", original)
    assert enter(paper, scenario).status == "FILLED"


def test_corrupt_projection_blocks_new_entries(paper, scenario, db_engine):
    engine, account = paper
    with Session(db_engine) as db, db.begin():
        db.get(Account, account).cash = Decimal("100001")
    assert not engine.recover(account, scenario.now)
    with pytest.raises(ValueError):
        engine.set_enabled(account, True, scenario.now)


def test_recovery_preserves_positions_baseline_and_disables_entries(paper, scenario):
    engine, account = paper
    enter(paper, scenario)
    restarted = PaperEngine(engine.engine)
    assert restarted.recover(account, scenario.now)
    report = restarted.portfolio(account, {scenario.instrument.id: scenario.quote}, scenario.now)
    assert report["open_positions"] == 1 and not report["enabled"]
    assert report["session_opening_equity"] == "100000.00"


def test_unavailable_evidence_rejected_without_fill(paper, scenario, db_engine):
    envelope = scenario.envelope.model_copy(update={"evidence_ids": (uuid4(),)})
    engine, account = paper
    result = engine.enter(
        account,
        scenario.decision,
        scenario.instrument,
        scenario.quote,
        envelope,
        scenario.session,
        scenario.now,
    )
    assert result.reason == "UNAVAILABLE_EVIDENCE"
    with Session(db_engine) as db:
        assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
        assert db.scalar(select(AuditEvent).where(AuditEvent.kind == "ENTRY_REJECTED")) is not None


def test_migration_matches_models_and_can_roundtrip(db_engine):
    from pathlib import Path

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with db_engine.begin() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert "accounts" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        assert "paper_positions" in inspect(connection).get_table_names()


def test_exported_contracts_are_current():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "shared/schemas"
    for name, expected in artifacts().items():
        assert (root / name).read_text(encoding="utf-8") == expected
