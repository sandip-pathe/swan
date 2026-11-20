"""Manual planning cannot mutate trading state or forge strategy approval."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_instrument_search import client_for, instruments, save
from test_market_details import seed

from services.api import order_preview as api
from services.core.contracts import IST, DepthLevel, Quote
from services.core.execution import PaperExecutionConfig
from services.core.models import (
    Account,
    AuditEvent,
    DecisionRecord,
    LedgerEntry,
    PaperFill,
    PaperLiquidityLevel,
    PaperOrder,
    SnapshotRecord,
    StrategyRecord,
)
from services.worker.models import LatestMarketQuote


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
                PaperLiquidityLevel,
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


def fresh_depth(engine, item, *, changes=None):
    stamp = datetime.now(UTC)
    quote = Quote(
        instrument_id=item.id,
        timestamp=stamp,
        received_at=stamp,
        source="isolated-preview",
        market_event_id="fixture:" + str(uuid4()),
        timestamp_basis="exchange_feed",
        quantity_unit="units",
        quantity_unit_source="isolated-fixture",
        depth_kind="best_five",
        bid="99.95",
        ask="100",
        bid_quantity=item.lot_size * 4,
        ask_quantity=item.lot_size * 4,
        bid_depth=(DepthLevel(price="99.95", quantity=item.lot_size * 4),),
        ask_depth=(
            DepthLevel(price="100", quantity=item.lot_size * 4),
            DepthLevel(price="101", quantity=item.lot_size * 4),
        ),
        volume=10000,
        oi=10000,
    )
    if changes:
        quote = quote.model_copy(update=changes)
    with Session(engine) as db, db.begin():
        row = db.get(LatestMarketQuote, item.id)
        row.payload, row.timestamp = quote.model_dump(mode="json"), quote.timestamp
    return quote


@pytest.mark.integration
def test_preview_usable_depth_respects_limit_consumption_and_read_only(preview_case, db_engine):
    owner, item, execution = preview_case
    quote = fresh_depth(db_engine, item)
    with Session(db_engine) as db, db.begin():
        db.add(
            PaperLiquidityLevel(
                account_id=owner,
                session_key=quote.timestamp.astimezone(IST).date(),
                instrument_id=item.id,
                side="BUY",
                price=Decimal("100"),
                displayed=item.lot_size * 4,
                capacity=item.lot_size * 2,
                consumed=item.lot_size,
                observation_at=quote.timestamp,
                source=quote.source,
                config_version=execution.version,
            )
        )
    before = counts(db_engine)
    body = dict(instrument_id=item.id, lots=2, entry="100", stop_loss="96", target="106")
    with client_for(db_engine, owner) as client:
        result = client.post("/api/paper/orders/preview", json=body).json()
        checks = {c["code"]: c["status"] for c in result["checks"]}
        assert checks["DEPTH"] == "passed" and checks["DEPTH_CAPACITY"] == "blocked"
        assert result["available_depth_quantity"] == item.lot_size
        assert result["available_depth_lots"] == 1
        one = client.post("/api/paper/orders/preview", json={**body, "lots": 1}).json()
        assert next(c for c in one["checks"] if c["code"] == "DEPTH_CAPACITY")["status"] == "passed"
        # A higher limit can access the second level; the consumed first level stays consumed.
        higher = client.post("/api/paper/orders/preview", json={**body, "entry": "101"}).json()
        assert higher["available_depth_quantity"] == 3 * item.lot_size
        assert higher["submission_ready"] is False
    assert counts(db_engine) == before
    with Session(db_engine) as db:
        row = db.scalar(select(PaperLiquidityLevel).where(PaperLiquidityLevel.account_id == owner))
        assert row.consumed == item.lot_size and row.capacity == 2 * item.lot_size


@pytest.mark.integration
@pytest.mark.parametrize(
    "problem", ["future", "stale", "unknown_source", "budget_ahead", "wrong_config"]
)
def test_preview_unusable_depth_is_unknown_not_zero(preview_case, db_engine, problem):
    owner, item, execution = preview_case
    changes = {}
    stamp = datetime.now(UTC)
    if problem == "future":
        changes = dict(
            timestamp=stamp + timedelta(seconds=30), received_at=stamp + timedelta(seconds=30)
        )
    elif problem == "stale":
        changes = dict(timestamp=stamp - timedelta(seconds=30))
    elif problem == "unknown_source":
        changes = dict(timestamp_basis="unknown")
    quote = fresh_depth(db_engine, item, changes=changes)
    if problem in {"budget_ahead", "wrong_config"}:
        with Session(db_engine) as db, db.begin():
            db.add(
                PaperLiquidityLevel(
                    account_id=owner,
                    session_key=quote.timestamp.astimezone(IST).date(),
                    instrument_id=item.id,
                    side="BUY",
                    price=Decimal("100"),
                    displayed=4 * item.lot_size,
                    capacity=2 * item.lot_size,
                    consumed=0,
                    observation_at=quote.timestamp + timedelta(seconds=1)
                    if problem == "budget_ahead"
                    else quote.timestamp,
                    source=quote.source,
                    config_version="different" if problem == "wrong_config" else execution.version,
                )
            )
    with client_for(db_engine, owner) as client:
        result = client.post(
            "/api/paper/orders/preview",
            json=dict(
                instrument_id=item.id,
                lots=1,
                entry="100",
                stop_loss="96",
                target="106",
            ),
        ).json()
        assert result["available_depth_quantity"] is None and result["available_depth_lots"] is None
        assert (
            next(c for c in result["checks"] if c["code"] == "DEPTH_CAPACITY")["status"]
            == "blocked"
        )


@pytest.mark.integration
def test_preview_slippage_lots_and_order_quantity_limit(preview_case, db_engine, monkeypatch):
    owner, item, execution = preview_case
    # Unit conversion applies before participation and whole-lot rounding.
    changes = dict(
        quantity_unit="lots", ask_quantity=3, ask_depth=(DepthLevel(price="100", quantity=3),)
    )
    fresh_depth(db_engine, item, changes=changes)
    lot_policy = execution.model_copy(
        update={"execution": execution.execution.model_copy(update={"quantity_unit": "lots"})}
    )
    monkeypatch.setattr(api, "load_execution", lambda: lot_policy)
    body = dict(instrument_id=item.id, lots=1, entry="100", stop_loss="96", target="106")
    with client_for(db_engine, owner) as client:
        result = client.post("/api/paper/orders/preview", json=body).json()
        assert result["available_depth_lots"] == 1
        # Slippage is applied before comparing executable prices with the limit.
        slipped = lot_policy.model_copy(
            update={
                "execution": lot_policy.execution.model_copy(
                    update={"extra_adverse_slippage_bps": Decimal("10")}
                )
            }
        )
        monkeypatch.setattr(api, "load_execution", lambda: slipped)
        result = client.post("/api/paper/orders/preview", json=body).json()
        assert result["available_depth_quantity"] == 0
        assert (
            next(c for c in result["checks"] if c["code"] == "DEPTH_CAPACITY")["status"]
            == "blocked"
        )
        result = client.post("/api/paper/orders/preview", json={**body, "lots": 1000}).json()
        assert next(c for c in result["checks"] if c["code"] == "QUANTITY")["status"] == "blocked"
