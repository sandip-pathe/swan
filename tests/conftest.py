"""Integration tests use and remove only their own UUID-named PostgreSQL schema."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from services.core.contracts import (
    ExchangeSession,
    Instrument,
    Quote,
    RiskConfig,
    StrategyEnvelope,
    TradeDecision,
)
from services.core.database import make_engine
from services.paper.engine import PaperEngine

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scenario():
    # Ordinary numeric test cases only. No replay dataset or production seed data.
    now = datetime.fromisoformat("2026-11-13T09:30:00+05:30")
    config = RiskConfig.model_validate(
        {
            "version": "test",
            "max_spread_bps": "25",
            "min_volume": 100,
            "min_oi": 100,
            "max_fill_quantity": 200,
            "costs": {
                "version": "test",
                "label": "Unit-test arithmetic inputs",
                "flat_per_fill": "1.00",
                "turnover_rate": "0.0001",
                "slippage_bps": "5",
            },
        }
    )
    instrument = Instrument(
        id="test-contract",
        provider_token="test",
        exchange="test",
        underlying="NIFTY",
        expiry=now.date() + timedelta(days=4),
        strike=Decimal("25000"),
        option_type="CALL",
        lot_size=25,
        tick_size=Decimal("0.05"),
        metadata_source="unit-test",
        verified_at=now - timedelta(minutes=30),
    )
    session = ExchangeSession(
        key=now.date(),
        opens_at=now.replace(hour=9, minute=15),
        closes_at=now.replace(hour=15, minute=30),
        calendar_source="unit-test",
        verified=True,
    )
    quote = Quote(
        instrument_id=instrument.id,
        timestamp=now,
        received_at=now,
        source="unit-test",
        bid=Decimal("99.95"),
        ask=Decimal("100.00"),
        bid_quantity=200,
        ask_quantity=200,
        volume=1000,
        oi=2000,
    )
    envelope = StrategyEnvelope(
        version="test",
        instrument_ids=(instrument.id,),
        action="BUY_CALL",
        issued_at=now,
        expires_at=now + timedelta(seconds=180),
        evidence_ids=(quote.id,),
        min_entry=Decimal("99"),
        max_entry=Decimal("101"),
        stop_loss=Decimal("96"),
        target=Decimal("106"),
    )
    decision = TradeDecision(
        action="BUY_CALL",
        timestamp=now,
        expires_at=now + timedelta(seconds=60),
        rationale="Unit-test input",
        snapshot_ids=(quote.id,),
        instrument_id=instrument.id,
        entry=Decimal("100"),
        stop_loss=envelope.stop_loss,
        target=envelope.target,
        strategy_id=envelope.id,
    )
    exit_quote = quote.model_copy(
        update={
            "id": uuid4(),
            "timestamp": now + timedelta(minutes=1),
            "received_at": now + timedelta(minutes=1),
            "bid": Decimal("106.00"),
            "ask": Decimal("106.05"),
        }
    )
    return SimpleNamespace(
        config=config,
        instrument=instrument,
        session=session,
        quote=quote,
        envelope=envelope,
        decision=decision,
        exit_quote=exit_quote,
        now=now,
        expected={
            "quantity": 100,
            "entry_price": "100.05",
            "fees": "4.06",
            "net_pnl": "580.94",
            "final_cash": "100580.94",
        },
    )


@pytest.fixture
def db_engine():
    schema = "swan_test_" + uuid4().hex
    admin = make_engine()
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = make_engine(connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.begin() as connection:
            config = Config(str(ROOT / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def paper(db_engine, scenario):
    engine = PaperEngine(db_engine)
    account = engine.create_account(scenario.config, scenario.now)
    engine.start_session(account, scenario.session, scenario.now)
    engine.set_enabled(account, True, scenario.now)
    return engine, account
