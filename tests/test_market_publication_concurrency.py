"""Quote and candle publishers share ordered, monotonic instrument metadata."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from services.core.contracts import Instrument
from services.core.models import InstrumentRecord
from services.market.candle_store import CandleStore
from services.market.live_candles import LiveCandles
from services.paper.engine import PaperEngine
from services.worker.store import RuntimeStore

pytestmark = pytest.mark.integration


def test_instrument_verification_cannot_regress(db_engine, scenario):
    newer = scenario.instrument.model_copy(update={"verified_at": scenario.now + timedelta(seconds=1)})
    with Session(db_engine) as db, db.begin():
        PaperEngine._persist_instrument(db, newer)
    with Session(db_engine) as db, db.begin():
        PaperEngine._persist_instrument(db, scenario.instrument)
    with Session(db_engine) as db:
        saved = Instrument.model_validate(db.get(InstrumentRecord, newer.id).payload)
        assert saved.verified_at == newer.verified_at


def test_opposite_stream_arrival_orders_do_not_deadlock(paper, db_engine, scenario):
    _, owner = paper
    instruments = [scenario.instrument.model_copy(update={"id": key, "exchange": "NFO"}) for key in ("AA", "ZZ")]
    quotes = [scenario.quote.model_copy(update={
        "instrument_id": item.id, "source": "angelone-websocket-v2:snapquote",
        "timestamp_basis": "exchange_feed", "stream_id": uuid4(), "sequence": 1,
        "last_price": scenario.quote.ask,
    }) for item in instruments]
    aggregator = LiveCandles()
    for item, quote in zip(instruments, quotes, strict=True):
        assert aggregator.observe(quote, item, scenario.session)
    rows = aggregator.drain()
    start = Barrier(2)

    def publish_quotes():
        start.wait(timeout=5)
        for index in range(8):
            current = {item.id: item.model_copy(update={"verified_at": scenario.now + timedelta(seconds=index * 2)}) for item in instruments}
            RuntimeStore(db_engine, owner).publish_quotes(current, list(reversed(quotes)))

    def publish_candles():
        start.wait(timeout=5)
        for index in range(8):
            current = deepcopy(rows)
            for row in current:
                row["instrument"]["verified_at"] = (scenario.now + timedelta(seconds=index * 2 + 1)).isoformat()
            CandleStore(db_engine, owner).save(current)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(publish_quotes), pool.submit(publish_candles)]
        for future in futures:
            future.result(timeout=20)
    with Session(db_engine) as db:
        for item in instruments:
            saved = Instrument.model_validate(db.get(InstrumentRecord, item.id).payload)
            assert saved.verified_at == scenario.now + timedelta(seconds=15)
