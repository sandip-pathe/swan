from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.core.contracts import IST
from services.core.models import IndexHistoryBatch
from services.market.index_history import normalize_index_bars
from services.market.index_history_store import persist_index_history, read_index_history


def test_persist_is_idempotent_and_reads_are_bounded_by_as_of():
    engine = create_engine("sqlite://")
    IndexHistoryBatch.__table__.create(engine)
    request = {"fromdate": "2026-11-20 09:15", "todate": "2026-11-20 09:18"}
    result = normalize_index_bars(
        [["2026-11-20T09:15:00+05:30", 100, 101, 99, 100.5, 0]],
        # The normalizer uses only the validated query range.
        _query(),
        _stamp(9, 20),
        request,
    )
    with Session(engine) as session:
        saved = persist_index_history(session, result)
        session.commit()
        assert persist_index_history(session, result).snapshot_id == saved.snapshot_id
        assert read_index_history(
            session,
            session_key=date(2026, 11, 20),
            start=_stamp(9, 15),
            end=_stamp(9, 18),
            as_of=_stamp(9, 19),
        ) == ()
        bars = read_index_history(
            session,
            session_key=date(2026, 11, 20),
            start=_stamp(9, 15),
            end=_stamp(9, 18),
            as_of=_stamp(9, 20),
        )
        assert len(bars) == 1 and bars[0].evidence_id == result.bars[0].evidence_id
    engine.dispose()


def _stamp(hour: int, minute: int):
    from datetime import datetime

    return datetime(2026, 11, 20, hour, minute, tzinfo=IST)


def _query():
    from services.core.contracts import ExchangeSession
    from services.market.index_history import IndexHistoryQuery

    return IndexHistoryQuery(
        session=ExchangeSession(
            key=date(2026, 11, 20), opens_at=_stamp(9, 15), closes_at=_stamp(15, 30),
            calendar_source="fixture", verified=True,
        ),
        start=_stamp(9, 15),
        end=_stamp(9, 18),
    )
