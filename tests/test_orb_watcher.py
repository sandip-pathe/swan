from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from services.core.contracts import IST, ExchangeSession
from services.core.models import IndexHistoryBatch, StrategyAssessmentRecord, StrategyWatcherEvent
from services.strategies.contracts import IndexBar, ORBSnapshot
from services.strategies.orb_watcher import process_orb_event


def test_watcher_deduplicates_replay_and_suppresses_unchanged_state():
    engine = create_engine("sqlite://")
    IndexHistoryBatch.__table__.create(engine)
    StrategyAssessmentRecord.__table__.create(engine)
    StrategyWatcherEvent.__table__.create(engine)
    day = date(2026, 11, 20)
    opens = datetime(2026, 11, 20, 9, 15, tzinfo=IST)
    exchange_session = ExchangeSession(
        key=day, opens_at=opens, closes_at=opens.replace(hour=15, minute=30),
        calendar_source="fixture", verified=True,
    )
    bars = tuple(_bar(opens + timedelta(minutes=i), i) for i in range(16))
    with Session(engine) as db:
        _save_snapshot(db, "snapshot-1", bars, opens + timedelta(minutes=16, seconds=30))
        first_snapshot = ORBSnapshot(
            snapshot_id="snapshot-1", source="fixture", underlying="NIFTY", exchange="NSE",
            as_of=opens + timedelta(minutes=16, seconds=30), bars=bars,
        )
        first = process_orb_event(
            db, snapshot=first_snapshot, exchange_session=exchange_session, event_kind="bar_close"
        )
        db.commit()
        assert first.emitted and first.reason == "SETUP_STATE_CHANGED"
        replay = process_orb_event(
            db, snapshot=first_snapshot, exchange_session=exchange_session, event_kind="bar_close"
        )
        assert replay.event_key == first.event_key
        _save_snapshot(db, "snapshot-2", bars, opens + timedelta(minutes=16, seconds=40))
        second_snapshot = first_snapshot.model_copy(
            update={"snapshot_id": "snapshot-2", "as_of": opens + timedelta(minutes=16, seconds=40)}
        )
        second = process_orb_event(
            db, snapshot=second_snapshot, exchange_session=exchange_session, event_kind="bar_close"
        )
        db.commit()
        assert not second.emitted and second.reason == "STATE_UNCHANGED"
        assert db.scalar(select(func.count()).select_from(StrategyWatcherEvent)) == 2
    engine.dispose()


def _bar(opened: datetime, minute: int) -> IndexBar:
    if minute < 15:
        low, high, close = Decimal("99"), Decimal("102"), Decimal("101")
    else:
        low, high, close = Decimal("101"), Decimal("103"), Decimal("102.5")
    return IndexBar(
        evidence_id=f"bar-{minute}", underlying="NIFTY", exchange="NSE", source="fixture",
        opens_at=opened, closes_at=opened + timedelta(minutes=1),
        available_at=opened + timedelta(minutes=1), final=True,
        open=Decimal("102") if minute >= 15 else Decimal("100"),
        high=high, low=low, close=close,
    )


def _save_snapshot(db: Session, snapshot_id: str, bars: tuple[IndexBar, ...], received: datetime):
    db.add(
        IndexHistoryBatch(
            snapshot_id=snapshot_id, underlying="NIFTY", exchange="NSE",
            session_key=received.date(), received_at=received, source="fixture",
            response_sha256="b" * 64, provider_request={},
            payload={"bars": [bar.model_dump(mode="json") for bar in bars]},
        )
    )
    db.flush()
