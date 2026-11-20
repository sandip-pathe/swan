"""Display-only metrics and paired-chain fixtures never enter the real account."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_instrument_search import client_for, instruments

from services.api.app import app
from services.api.auth import account_identity
from services.core.contracts import IST
from services.core.models import Account, InstrumentRecord, PaperOrder
from services.market.display import quote_statistics
from services.worker.models import LatestMarketQuote


@pytest.mark.parametrize(
    "last,previous,bid,ask,change,spread",
    [
        ("110", "100", "99", "101", "10", "2"),
        ("0", "100", "100", "100", "-100", "0"),
        ("100", "0", "101", "99", None, None),
        (None, "100", None, "101", None, None),
        ("100", None, "0", "1", None, None),
    ],
)
def test_display_statistics_handle_missing_zero_locked_and_crossed(
    scenario, last, previous, bid, ask, change, spread
):
    quote = scenario.quote.model_copy(
        update={
            key: Decimal(value) if value is not None else None
            for key, value in (
                ("last_price", last),
                ("previous_close", previous),
                ("bid", bid),
                ("ask", ask),
            )
        }
    )
    result = quote_statistics(quote)
    assert result["change"] == change and result["spread"] == spread
    if spread == "2":
        assert Decimal(result["spread_bps"]) == 200
        assert Decimal(result["change_pct"]) == 10
    if spread == "0":
        assert Decimal(result["spread_bps"]) == 0
    if spread is None:
        assert result["spread_bps"] is None
    assert all(value is None for value in quote_statistics(None).values())


def seed(db_engine, scenario, items):
    stamp = datetime.now(UTC) - timedelta(days=1)
    with Session(db_engine) as db, db.begin():
        for item in items:
            db.add(InstrumentRecord(id=item.id, payload=item.model_dump(mode="json")))
            quote = scenario.quote.model_copy(
                update={
                    "instrument_id": item.id,
                    "timestamp": stamp,
                    "last_price": Decimal("110"),
                    "previous_close": Decimal("100"),
                    "bid": Decimal("99"),
                    "ask": Decimal("101"),
                    "volume": 0,
                    "oi": 0,
                }
            )
            db.add(
                LatestMarketQuote(
                    instrument_id=item.id, timestamp=stamp, payload=quote.model_dump(mode="json")
                )
            )


@pytest.mark.integration
def test_chain_filters_expiry_sorts_numeric_strikes_and_pages_whole_pairs(
    paper, db_engine, scenario
):
    _, owner = paper
    base = instruments(scenario)[0]
    items = [
        base.model_copy(
            update={"id": f"pair-{i}-{side}", "strike": Decimal(100 + i * 50), "option_type": side}
        )
        for i in range(51)
        for side in ("CALL", "PUT")
    ]
    later = base.model_copy(update={"id": "later", "expiry": base.expiry + timedelta(days=7)})
    expired = base.model_copy(
        update={"id": "expired", "expiry": datetime.now(IST).date() - timedelta(days=1)}
    )
    seed(db_engine, scenario, [*items, later, expired])
    with client_for(db_engine, owner) as client:
        response = client.get("/api/chain")
        assert response.status_code == 200, response.text
        first = response.json()
        assert len(first["rows"]) == 100 and first["next_offset"] == 50
        assert first["expiry"] == base.expiry.isoformat() and not first["provider_called"]
        assert first["expiries"] == [base.expiry.isoformat(), later.expiry.isoformat()]
        assert first["rows"][0]["instrument"]["strike"] == "100"
        assert {row["instrument"]["option_type"] for row in first["rows"][-2:]} == {"CALL", "PUT"}
        second = client.get("/api/chain", params={"offset": 50}).json()
        assert len(second["rows"]) == 2 and second["next_offset"] is None
        assert {row["instrument"]["strike"] for row in second["rows"]} == {"2600"}
        chosen = client.get("/api/chain", params={"expiry": later.expiry.isoformat()}).json()
        assert len(chosen["rows"]) == 1 and chosen["rows"][0]["instrument"]["id"] == "later"
        assert (
            client.get("/api/chain", params={"expiry": expired.expiry.isoformat()}).json()["rows"]
            == []
        )
        assert client.get("/api/chain", params={"underlying": "SENSEX"}).json()["rows"] == []
        app.dependency_overrides[account_identity] = lambda: uuid4()
        assert client.get("/api/chain").status_code == 409


@pytest.mark.integration
def test_selected_details_preserve_quote_age_zero_values_and_account_state(
    paper, db_engine, scenario
):
    _, owner = paper
    item = instruments(scenario)[0]
    seed(db_engine, scenario, [item])
    with client_for(db_engine, owner) as client:
        result = client.get(
            "/api/market/instruments/selected", params={"instrument_id": item.id}
        ).json()
        assert (
            result["statistics"]["change"] == "10"
            and Decimal(result["statistics"]["spread_bps"]) == 200
        )
        assert result["quote"]["oi"] == 0 and result["quote"]["volume"] == 0
        assert datetime.fromisoformat(result["quote"]["timestamp"]) < datetime.now(UTC) - timedelta(
            hours=23
        )
        assert result["provider_called"] is False
        with Session(db_engine) as db:
            assert db.scalar(select(func.count()).select_from(PaperOrder)) == 0
            assert db.get(Account, owner).cash == scenario.config.capital


@pytest.mark.integration
def test_chain_newest_pairs_precede_old_quotes_across_pages(paper, db_engine, scenario):
    _, owner = paper
    base = instruments(scenario)[0]
    items = [
        base.model_copy(
            update={"id": f"fresh-{i}-{side}", "strike": Decimal(100 + i * 50), "option_type": side}
        )
        for i in range(51)
        for side in ("CALL", "PUT")
    ]
    seed(db_engine, scenario, items)
    with Session(db_engine) as db, db.begin():
        # The highest strike has the newest exchange time on only one side.
        row = db.get(LatestMarketQuote, "fresh-50-PUT")
        row.timestamp = datetime.now(UTC)
        row.payload = {**row.payload, "timestamp": row.timestamp.isoformat()}
    with client_for(db_engine, owner) as client:
        latest = client.get("/api/chain").json()
        assert latest["rows"][0]["instrument"]["strike"] == "2600"
        assert {row["instrument"]["option_type"] for row in latest["rows"][:2]} == {"CALL", "PUT"}
        tail = client.get("/api/chain", params={"offset": 50}).json()
        assert {row["instrument"]["strike"] for row in tail["rows"]} == {"2550"}
        ascending = client.get("/api/chain", params={"sort": "strike"}).json()
        assert ascending["rows"][0]["instrument"]["strike"] == "100"
        assert client.get("/api/chain", params={"sort": "bad"}).status_code == 422
