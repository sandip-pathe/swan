"""Manual planning cannot mutate trading state or forge strategy approval."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_instrument_search import client_for, instruments, save
from test_market_details import seed

from services.api import order_preview as api
from services.core.contracts import IST
from services.core.execution import PaperExecutionConfig
from services.core.models import (
    Account,
    AuditEvent,
    DecisionRecord,
    LedgerEntry,
    PaperFill,
    PaperOrder,
    SnapshotRecord,
    StrategyRecord,
)


@pytest.fixture
def preview_case(paper, db_engine, scenario, monkeypatch):
    _, owner = paper
    item = instruments(scenario)[0]
    save(db_engine, [item])
    seed(db_engine, scenario, [item])
    source = dict(
        url="https://example.test/isolated-preview",
        checked_at=datetime.now(UTC).isoformat(),
        finding="Fixture arithmetic only",
        status="documented",
    )
    config = PaperExecutionConfig.model_validate(
        dict(
            version="preview-fixture",
            execution=dict(
                version="fixture",
                reviewed=True,
                assumed_latency_ms=250,
                displayed_participation="0.5",
                extra_adverse_slippage_bps="0",
                market_protection_bps="100",
                quote_max_age_ms=2000,
                pending_entry_lifetime_ms=5000,
                quantity_unit="units",
                quantity_unit_sources=[source],
                partial_fill_granularity="lots",
                notes="Isolated assumptions",
            ),
            fee_schedules=[
                dict(
                    version="fixture-fees",
                    exchange="NFO",
                    effective_from="2026-01-01",
                    reviewed=True,
                    account_pricing_verified=True,
                    notes="Fixture only",
                    rules=[
                        dict(
                            code=code,
                            sides=["BUY", "SELL"],
                            calculation="flat_per_order",
                            amount="1" if code == "BROKERAGE" else "0",
                            rounding_increment="0.01",
                            rounding_mode="HALF_UP",
                            rounding_scope="cumulative_order",
                            sources=[source],
                        )
                        for code in (
                            "BROKERAGE",
                            "EXCHANGE",
                            "STT",
                            "SEBI",
                            "STAMP",
                            "GST",
                            "IPFT",
                            "CLEARING",
                        )
                    ],
                )
            ],
        )
    )
    monkeypatch.setattr(api, "load_execution", lambda: config)
    monkeypatch.setattr(api, "load_session", lambda exchange, now: None)
    with Session(db_engine) as db, db.begin():
        account = db.get(Account, owner)
        account.enabled = False
        account.session_key = datetime.now(UTC).astimezone(IST).date()
    return owner, item, config


def counts(engine):
    with Session(engine) as db:
        return [
            db.scalar(select(func.count()).select_from(model))
            for model in (
                PaperOrder,
                PaperFill,
                LedgerEntry,
                DecisionRecord,
                StrategyRecord,
                SnapshotRecord,
                AuditEvent,
            )
        ]


@pytest.mark.integration
def test_preview_costs_whole_lots_and_no_mutations(preview_case, db_engine):
    owner, item, _ = preview_case
    before = counts(db_engine)
    with client_for(db_engine, owner) as client:
        response = client.post(
            "/api/paper/orders/preview",
            json=dict(instrument_id=item.id, lots=2, entry="100", stop_loss="96", target="106"),
        )
        assert response.status_code == 200, response.text
        result = response.json()
        quantity = 2 * item.lot_size
        assert result["quantity"] == quantity and Decimal(result["premium"]) == 100 * quantity
        assert (
            Decimal(result["entry_fee_allowance"]) == 1
            and Decimal(result["stop_exit_fee_allowance"]) == 1
        )
        assert Decimal(result["planned_stop_loss"]) == 4 * quantity + 2
        assert Decimal(result["gross_target_gain"]) == 6 * quantity
        assert result["submission_ready"] is False and result["provider_called"] is False
        checks = {c["code"]: c["status"] for c in result["checks"]}
        assert checks["QUOTE"] == checks["SESSION"] == checks["MANUAL_SUBMISSION"] == "blocked"
        assert checks["FEES"] == checks["CONTRACT"] == "passed"
        assert datetime.fromisoformat(result["expires_at"]) > datetime.fromisoformat(
            result["as_of"]
        )
    assert counts(db_engine) == before


@pytest.mark.integration
@pytest.mark.parametrize(
    "changes",
    [
        dict(lots=0),
        dict(lots=1.5),
        dict(lots=True),
        dict(lots=1001),
        dict(entry="NaN"),
        dict(entry="100.001"),
        dict(stop_loss="101"),
        dict(target="99"),
        dict(entry="100.01"),
        dict(account_id=str(uuid4())),
    ],
)
def test_preview_rejects_invalid_inputs(preview_case, db_engine, changes):
    owner, item, _ = preview_case
    before = counts(db_engine)
    with client_for(db_engine, owner) as client:
        body = dict(instrument_id=item.id, lots=1, entry="100", stop_loss="96", target="106")
        body.update(changes)
        assert client.post("/api/paper/orders/preview", json=body).status_code == 422
    assert counts(db_engine) == before


@pytest.mark.integration
def test_preview_missing_configuration_and_unknown_account(preview_case, db_engine, monkeypatch):
    owner, item, _ = preview_case

    def missing():
        raise OSError("Isolated unavailable config")

    monkeypatch.setattr(api, "load_execution", missing)
    body = dict(instrument_id=item.id, lots=1, entry="100", stop_loss="96", target="106")
    with client_for(db_engine, owner) as client:
        result = client.post("/api/paper/orders/preview", json=body).json()
        assert (
            result["entry_fee_allowance"] is None
            and result["planned_stop_loss"] is None
            and result["cash_required"] is None
        )
        assert Decimal(result["gross_stop_loss"]) == 4 * item.lot_size
        assert (
            client.post(
                "/api/paper/orders/preview", json={**body, "instrument_id": "unknown"}
            ).status_code
            == 404
        )
    with client_for(db_engine, uuid4()) as client:
        assert client.post("/api/paper/orders/preview", json=body).status_code == 409
