"""One bounded collector: independent failures, no trading or model loops."""

import asyncio
import logging
import os
import signal
from datetime import UTC, datetime, time, timedelta
from typing import Literal

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
    markets = {name: market_context(calendar, now, venue)
               for name, venue in (("NIFTY", "NFO"), ("SENSEX", "BFO"))}
    market = markets["SENSEX"]
    store.write("calendar", market)
    if not any(value["state"] == "open" for value in markets.values()):
        store.write("worker", {"heartbeat": now.isoformat(), "status": market["state"],
                               "detail": "Collection sleeps outside verified sessions."})
        return
    problems = []
    tokens = {venue: token for venue, name, token in
              (("NSE", "NIFTY", settings.nifty_index_token),
               ("BSE", "SENSEX", settings.sensex_index_token)) if markets[name]["state"] == "open"}
    try:
        rows = await asyncio.wait_for(
            client.quotes({venue: [token] for venue, token in tokens.items() if token}), 12)
        for venue, underlying in (("NSE", "NIFTY"), ("BSE", "SENSEX")):
            if venue not in tokens:
                continue
            matched = [row for row in rows if row.get("exchange") == venue and
                       str(row.get("symbolToken", row.get("symboltoken"))) == tokens.get(venue)]
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
    except (ProviderError, ValueError, TypeError, KeyError, TimeoutError):
        problems.append("QUOTES_UNAVAILABLE")
    repair_available = True
    indices: tuple[tuple[Literal["SENSEX", "NIFTY"], str, Literal["BSE", "NSE"]], ...] = (
        ("SENSEX", "BFO", "BSE"), ("NIFTY", "NFO", "NSE"))
    for underlying, venue, exchange in indices:
        if markets[underlying]["state"] != "open":
            continue
        try:
            session = calendar.get(venue, now.astimezone(IST).date())
            if session is None:
                raise ProviderError("VERIFIED_SESSION_REQUIRED")
            end = min(now.replace(second=0, microsecond=0), session.closes_at,
                      datetime.combine(session.key, time(15, 30), IST))
            if end <= session.opens_at:
                continue
            query = IndexHistoryQuery(underlying=underlying, exchange=exchange,
                                      session=session, start=session.opens_at, end=end)
            result = await asyncio.wait_for(client.index_candles(query), 10)
            analysis = analyze(list(result.bars), datetime.now(UTC), session.opens_at, underlying)
            # One bounded retry of the first gap, no interpolation or invented candles.
            missing = analysis.get("missing_minutes", [])
            if missing and repair_available:
                repair_available = False
                store.write(f"analysis:{underlying}", analysis)
                store.write(f"evidence:{underlying}", result.model_dump(mode="json"))
                gap_start = datetime.fromisoformat(missing[0])
                gap_end = min(end, gap_start + timedelta(minutes=10))
                repair = await asyncio.wait_for(client.index_candles(IndexHistoryQuery(
                    underlying=underlying, exchange=exchange, session=session,
                    start=gap_start, end=gap_end)), 10)
                merged = {bar.opens_at: bar for bar in result.bars}
                for bar in repair.bars:
                    prior = merged.get(bar.opens_at)
                    if prior and (prior.open, prior.high, prior.low, prior.close) != (
                            bar.open, bar.high, bar.low, bar.close):
                        raise ProviderError("INDEX_REPAIR_CONFLICT")
                    if prior is None:
                        merged[bar.opens_at] = bar
                # Retain both original source snapshots; never rewrite their provenance.
                combined = sorted(merged.values(), key=lambda bar: bar.opens_at)
                analysis = analyze(combined, datetime.now(UTC), session.opens_at, underlying)
                snapshot = {"primary": result.model_dump(mode="json"),
                            "repair": repair.model_dump(mode="json"),
                            "source": result.source, "received_at": repair.received_at.isoformat(),
                            "response_sha256": result.response_sha256,
                            "bars": [bar.model_dump(mode="json") for bar in combined]}
            else:
                snapshot = result.model_dump(mode="json")
            store.write(f"evidence:{underlying}", snapshot)
            store.write(f"analysis:{underlying}", analysis)
            if analysis.get("status") != "current":
                problems.append(f"{underlying}_COVERAGE_OR_FRESHNESS")
            previous = store.read(f"last_published:{underlying}")
            insight = insight_for(analysis, previous, str(session.key))
            if insight:
                insight["published_at"] = datetime.now(UTC).isoformat()
                insight["source_snapshot"] = snapshot
                store.publish(insight)
                store.write(f"last_published:{underlying}", {**analysis, "session": str(session.key)})
        except (ProviderError, ValueError, TypeError, KeyError, TimeoutError):
            problems.append(f"{underlying}_CANDLES_UNAVAILABLE")
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
            store.prune()
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
            # Fetch just after a completed minute, rather than drifting by request duration.
            finished = datetime.now(UTC)
            next_minute = finished.replace(second=3, microsecond=0)
            if next_minute <= finished:
                next_minute += timedelta(minutes=1)
            delay = min(300, 60 * 2 ** min(failures, 3)) if failures else (
                next_minute - finished).total_seconds()
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
