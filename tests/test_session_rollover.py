"""Regression: prior-session daily loss must not permanently block a new session.

Found during functional QA on 2026-11-18. Uses an isolated database and calendar.
Value: protects=verified flat-account rollover; fails_when=old daily block wins;
why_new=existing tests retry only same-session start; seam=none;
no_claim=calendar authenticity or live provider readiness (test session only).
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session

from services.core.models import Account
from services.market.settings import MarketSettings
from services.worker import runtime as module
from services.worker.runtime import TradingRuntime

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "new_day,coverage", [(False, "open"), (True, "open"), (True, "preopen"), (True, "unknown")]
)
async def test_worker_rolls_verified_session_without_rearming_or_resetting_same_day(
    paper, scenario, db_engine, tmp_path, monkeypatch, new_day, coverage
):
    engine, identifier = paper
    now = scenario.now + timedelta(days=int(new_day))
    session = scenario.session.model_copy(
        update={
            "key": now.date(),
            "opens_at": now.replace(hour=9, minute=15),
            "closes_at": now.replace(hour=15, minute=30),
        }
    )
    if coverage == "preopen":
        session = session.model_copy(update={"opens_at": now + timedelta(hours=1)})
    path = tmp_path / "calendar.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sessions": []
                if coverage == "unknown"
                else [
                    {
                        "exchange": "NFO",
                        "session": session.model_dump(mode="json"),
                        "official_source_url": "https://www.nseindia.com/fixture",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with Session(db_engine) as db, db.begin():
        account = db.get(Account, identifier)
        account.daily_blocked = True
        account.enabled = False
        before_revision = account.revision
        before_cash = account.cash

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    monkeypatch.setattr(module, "datetime", FixedDatetime)
    worker = TradingRuntime(
        db_engine, identifier, MarketSettings(_env_file=None, calendar_file=path), observe_only=True
    )
    worker.store.initialize(now)
    worker.last_publication = asyncio.get_running_loop().time()
    worker.publish_latest = AsyncMock()
    try:
        await worker.cycle()
        rolled = new_day and coverage == "open"
        with Session(db_engine) as db:
            account = db.get(Account, identifier)
            assert account.session_key == (now.date() if rolled else scenario.now.date())
            assert account.daily_blocked is (not rolled)
            assert account.enabled is False
            assert account.cash == before_cash
            assert account.revision == before_revision + int(rolled)
        # A repeated cycle cannot move the baseline or erase a same-day loss block.
        await worker.cycle()
        with Session(db_engine) as db:
            assert db.get(Account, identifier).revision == before_revision + int(rolled)
    finally:
        await worker.client.close()
