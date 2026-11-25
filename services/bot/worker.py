"""One bounded collector: independent failures, no trading or model loops."""

import asyncio
import logging
import os
import signal
from datetime import UTC, datetime, time

from services.bot.analysis import analyze, insight_for
from services.bot.session import market_context
from services.bot.store import Store
from services.core.contracts import IST
from services.market.angelone import AngelOneClient
from services.market.calendar import SessionCalendar
from services.market.index_history import IndexHistoryQuery
from services.market.references import normalize_reference
from services.market.settings import MarketSettings, ProviderError

logger = logging.getLogger(__name__)


async def collect(store: Store, client: AngelOneClient, settings: MarketSettings,
                  now: datetime) -> None:
    calendar = SessionCalendar(settings.calendar_file)
    market = market_context(calendar, now)
    store.write("calendar", market)
    if market["state"] != "open":
        store.write("worker", {"heartbeat": now.isoformat(), "status": market["state"],
                               "detail": "Collection sleeps outside verified sessions."})
        return
    problems = []
    tokens = {"NSE": settings.nifty_index_token, "BSE": settings.sensex_index_token}
    try:
        rows = await client.quotes({venue: [token] for venue, token in tokens.items() if token})
        for venue, underlying in (("NSE", "NIFTY"), ("BSE", "SENSEX")):
            matched = [row for row in rows if row.get("exchange") == venue and
                       str(row.get("symbolToken", row.get("symboltoken"))) == tokens[venue]]
            if len(matched) != 1:
                problems.append(f"{underlying}_QUOTE_UNAVAILABLE")
                continue
            reference = normalize_reference(matched[0], underlying, tokens[venue],
                                            datetime.now(UTC))
            prior = store.read(f"quote:{underlying}")
            if prior and datetime.fromisoformat(prior["timestamp"]) > reference.timestamp:
                problems.append(f"{underlying}_OUT_OF_ORDER")
                continue
            store.write(f"quote:{underlying}", reference.model_dump(mode="json"))
    except (ProviderError, ValueError, TypeError, KeyError):
        problems.append("QUOTES_UNAVAILABLE")
    try:
        session = calendar.get("NFO", now.astimezone(IST).date())
        if session is None:
            raise ProviderError("VERIFIED_SESSION_REQUIRED")
        # The reused derivatives calendar can extend past the underlying cash session.
        end = min(now.replace(second=0, microsecond=0), session.closes_at,
                  datetime.combine(session.key, time(15, 30), IST))
        if end > session.opens_at:
            query = IndexHistoryQuery(session=session, start=session.opens_at, end=end)
            result = await client.index_candles(query)
            store.write("evidence", result.model_dump(mode="json"))
            analysis = analyze(list(result.bars), datetime.now(UTC), session.opens_at)
            store.write("analysis", analysis)
            previous = store.read("last_published")
            insight = insight_for(analysis, previous, str(session.key))
            if insight:
                insight["source_snapshot"] = result.model_dump(mode="json")
                store.publish(insight)
                store.write("last_published", {**analysis, "session": str(session.key)})
    except (ProviderError, ValueError, TypeError, KeyError):
        problems.append("CANDLES_UNAVAILABLE")
    store.write("worker", {"heartbeat": datetime.now(UTC).isoformat(),
                           "status": "degraded" if problems else "collecting",
                           "problems": problems})


async def run() -> None:
    store = Store(os.environ.get("BOT_DB_PATH", ".local/bot/bot.sqlite3"))
    # Deployment uses Linux. The shared-volume lock prevents two collectors from
    # consuming provider quotas during a mistaken duplicate start.
    import fcntl

    lease = open(store.path + ".worker.lock", "a")
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    settings = MarketSettings()
    client = AngelOneClient(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    failures = 0
    try:
        while not stop.is_set():
            now = datetime.now(UTC)
            if os.environ.get("BOT_COLLECTION_ENABLED", "false").lower() != "true":
                store.write("worker", {"heartbeat": now.isoformat(), "status": "paused",
                                       "detail": "Provider collection has not been enabled."})
            else:
                try:
                    async with asyncio.timeout(55):
                        await collect(store, client, settings, now)
                    failures = 0
                except Exception:
                    failures += 1
                    logger.warning("Bot collection unavailable; retrying with bounded backoff")
                    store.write("worker", {"heartbeat": now.isoformat(), "status": "unavailable",
                                           "detail": "Collection failed; saved data retained."})
            delay = min(300, 60 * 2 ** min(failures, 3))
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass
    finally:
        await client.close()
        lease.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
