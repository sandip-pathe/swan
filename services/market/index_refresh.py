"""Shared bounded index acquisition and durable strategy event production."""

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from services.core.contracts import IST
from services.core.models import Account, IndexHistoryBatch
from services.market.angelone import AngelOneClient
from services.market.calendar import SessionCalendar
from services.market.history_refresh import HistoryError
from services.market.index_history import IndexHistoryQuery
from services.market.settings import MarketSettings, ProviderError
from services.strategies.contracts import ORBSnapshot
from services.strategies.index_assessment import persist_index_assessment
from services.strategies.orb_watcher import enqueue_orb_assignment, process_orb_event

INDEX_HISTORY_LOCK = 726230519846
REFRESH_COOLDOWN = timedelta(seconds=55)
ORB_CUTOFF = time(11, 0)


async def fetch_index_history(query: IndexHistoryQuery):
    async with asyncio.timeout(80):
        client = AngelOneClient(MarketSettings())
        try:
            return await client.index_candles(query)
        finally:
            await client.close()


def refresh_index_history(session_key: date, engine, identifier: UUID, fetcher=None):
    now = datetime.now(UTC)
    day = now.astimezone(IST).date()
    if session_key != day:
        raise HistoryError(422, "INDEX_HISTORY_CURRENT_SESSION_ONLY")

    settings = MarketSettings()
    exchange_session = SessionCalendar(settings.calendar_file, strict=False).get("NFO", day)
    if exchange_session is None:
        raise HistoryError(409, "VERIFIED_NIFTY_SESSION_REQUIRED")
    start = exchange_session.opens_at.astimezone(IST)
    end = min(
        now.astimezone(IST).replace(second=0, microsecond=0),
        datetime.combine(day, ORB_CUTOFF, IST),
        exchange_session.closes_at.astimezone(IST),
    )
    if end <= start:
        raise HistoryError(409, "INDEX_HISTORY_NO_COMPLETED_MINUTE_YET")
    try:
        query = IndexHistoryQuery(
            session=exchange_session,
            start=start,
            end=end,
        )
    except ValueError:
        raise HistoryError(422, "INDEX_HISTORY_SESSION_OR_WINDOW_UNSUPPORTED") from None

    with Session(engine) as db, db.begin():
        if db.get(Account, identifier) is None:
            raise HistoryError(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        if not db.scalar(
            text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": INDEX_HISTORY_LOCK}
        ):
            raise HistoryError(429, "INDEX_HISTORY_REFRESH_BUSY")
        latest = db.scalar(
            select(IndexHistoryBatch)
            .where(IndexHistoryBatch.session_key == day)
            .order_by(IndexHistoryBatch.received_at.desc())
            .limit(1)
        )
        if latest is not None:
            latest_received = latest.received_at
            if latest_received.tzinfo is None:
                latest_received = latest_received.replace(tzinfo=IST)
            if now - latest_received.astimezone(UTC) < REFRESH_COOLDOWN:
                raise HistoryError(429, "INDEX_HISTORY_REFRESH_RATE_LIMIT")
        try:
            result = asyncio.run((fetcher or fetch_index_history)(query))
        except ProviderError as error:
            raise HistoryError(409, str(error)) from None
        except TimeoutError:
            raise HistoryError(504, "INDEX_HISTORY_REFRESH_TIMEOUT") from None

        capture = persist_index_assessment(
            db,
            result=result,
            exchange_session=exchange_session,
        )
        snapshot = ORBSnapshot(
            snapshot_id=result.snapshot_id,
            source=result.source,
            underlying=result.underlying,
            exchange=result.exchange,
            as_of=result.received_at.astimezone(IST),
            bars=result.bars,
        )
        watcher = process_orb_event(
            db,
            snapshot=snapshot,
            exchange_session=exchange_session,
            event_kind="bar_close",
        )
        assignment = enqueue_orb_assignment(
            db,
            account_id=identifier,
            event=watcher,
            now=now,
        )
        return {
            **capture.model_dump(mode="json"),
            "watcher": watcher.model_dump(mode="json"),
            "agent_assignment": ({
                "id": str(assignment.id),
                "state": assignment.state,
                "deadline": assignment.deadline.isoformat(),
            } if assignment else None),
            "provider_called": True,
            "availability_semantics": "available_at_is_response_receipt_time",
            "finality_semantics": "elapsed_interval_only_not_provider_confirmation",
            "missing_intervals_semantics": "gaps_are_preserved_not_filled",
        }

