"""Underlying references are display data, not executable option snapshots."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from test_instrument_search import client_for, instruments, save
from test_market_details import seed

from services.core.models import UnderlyingReference
from services.market.references import normalize_reference, reference_context, save_reference
from services.market.settings import ProviderError


@pytest.mark.integration
def test_stream_reference_publication_keeps_same_session_previous_close(db_engine):
    from services.market.reference_contracts import IndexReference

    now = datetime.now(UTC)
    reference = IndexReference(underlying="NIFTY", exchange="NSE", provider_token="fixture",
                               timestamp=now, received_at=now, last_price="100", previous_close="99")
    with Session(db_engine) as db, db.begin():
        save_reference(db, reference)
    streamed = reference.model_copy(update={"timestamp": now + timedelta(seconds=1),
                                            "received_at": now + timedelta(seconds=1),
                                            "last_price": Decimal("101"), "previous_close": None,
                                            "source": "angelone-websocket-v2:ltp"})
    with Session(db_engine) as db, db.begin():
        save_reference(db, streamed)
    with Session(db_engine) as db:
        saved = db.get(UnderlyingReference, "NIFTY").payload
        assert saved["last_price"] == "101" and saved["previous_close"] == "99"


@pytest.mark.parametrize("invalid", [None, "exchange", "token", "future", "zero"])
def test_reference_normalization_preserves_exchange_time_and_checks_identity(invalid):
    now = datetime.now(UTC)
    stamp = now - timedelta(minutes=5)
    row = dict(
        exchange="NSE",
        symbolToken="fixture",
        exchFeedTime=stamp.isoformat(),
        ltp="125",
        close="100",
    )
    if invalid == "exchange":
        row["exchange"] = "BSE"
    if invalid == "token":
        row["symbolToken"] = "other"
    if invalid == "future":
        row["exchFeedTime"] = (now + timedelta(minutes=1)).isoformat()
    if invalid == "zero":
        row["ltp"] = "0"
    if invalid:
        with pytest.raises(ProviderError):
            normalize_reference(row, "NIFTY", "fixture", now)
    else:
        result = normalize_reference(row, "NIFTY", "fixture", now)
        assert result.timestamp == stamp and result.received_at == now and result.last_price == 125
        row.update(exchange="BSE", close="0")
        assert normalize_reference(row, "SENSEX", "fixture", now).previous_close is None


@pytest.mark.integration
def test_reference_retention_global_atm_tie_and_selected_context(paper, db_engine, scenario):
    _, owner = paper
    now = datetime.now(UTC)
    items = instruments(scenario, 3)
    save(db_engine, items)
    seed(db_engine, scenario, items)
    reference = normalize_reference(
        dict(
            exchange="NSE",
            symbolToken="fixture",
            exchFeedTime=now.isoformat(),
            ltp="125",
            close="100",
        ),
        "NIFTY",
        "fixture",
        now,
    )
    with Session(db_engine) as db, db.begin():
        save_reference(db, reference)
        save_reference(
            db,
            reference.model_copy(
                update={"timestamp": now - timedelta(days=1), "last_price": Decimal(190)}
            ),
        )
    with client_for(db_engine, owner) as client:
        chain = client.get("/api/chain").json()["reference"]
        assert Decimal(chain["atm_strike"]) == 100
        assert chain["change"] == "25" and Decimal(chain["change_pct"]) == 25
        assert datetime.fromisoformat(chain["quote"]["timestamp"]) == now
        selected = client.get(
            "/api/market/instruments/selected", params={"instrument_id": items[2].id}
        ).json()
        assert selected["reference"] == chain
        assert (
            client.get("/api/chain", params={"underlying": "SENSEX"}).json()["reference"]["quote"]
            is None
        )
    with Session(db_engine) as db, db.begin():
        record = db.get(UnderlyingReference, "NIFTY")
        record.timestamp = now - timedelta(days=1)
        record.payload = reference.model_copy(update={"timestamp": record.timestamp}).model_dump(
            mode="json"
        )
    with Session(db_engine) as db:
        context = reference_context(db, "NIFTY", items[0].expiry)
        assert (
            context["atm_strike"] is None
            and context["atm_status"] == "reference_from_another_session"
        )


@pytest.mark.integration
def test_atm_missing_or_stale_catalog_is_unavailable(db_engine, scenario):
    now = datetime.now(UTC)
    reference = normalize_reference(
        dict(exchange="NSE", symbolToken="fixture", exchFeedTime=now.isoformat(), ltp="125"),
        "NIFTY",
        "fixture",
        now,
    )
    with Session(db_engine) as db, db.begin():
        save_reference(db, reference)
    with Session(db_engine) as db:
        context = reference_context(db, "NIFTY", None)
        assert context["atm_strike"] is None and context["atm_status"] == "catalog_refresh_required"
        assert context["change"] is None
    items = instruments(scenario, 2)
    save(db_engine, items, now - timedelta(days=1))
    with Session(db_engine) as db:
        assert reference_context(db, "NIFTY", items[0].expiry)["atm_strike"] is None
