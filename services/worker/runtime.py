"""Singleton market worker: no fake agent output, persistent slots, independent exits."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Engine, text

from services.agents.pipeline import AgentPipeline
from services.core.contracts import IST, ExchangeSession, Instrument, TradeDecision
from services.market.analysis import (
    ChainAnalysis,
    normalize_rest_quote,
    provider_decimal,
    provider_time,
)
from services.market.angelone import AngelOneClient
from services.market.calendar import SessionCalendar
from services.market.candle_store import CandleStore
from services.market.catalog import InstrumentCatalog
from services.market.history import HistoryQuery
from services.market.history_refresh import HistoryError, refresh_history
from services.market.live_candles import LiveCandles
from services.market.references import normalize_reference
from services.market.settings import MarketSettings, ProviderError
from services.market.stream import AngelOneStream, QuoteCache
from services.market.subscriptions import add_display_contracts
from services.paper.coordinator import PaperCoordinator
from services.paper.engine import PaperEngine
from services.paper.qualification import QualificationService
from services.paper.validation import ValidationService
from services.risk.engine import quote_problem
from services.worker.store import RuntimeStore

logger = logging.getLogger(__name__)


class TradingRuntime:
    def __init__(
        self,
        engine: Engine,
        account_id: UUID,
        settings: MarketSettings,
        *,
        observe_only: bool = False,
        validation_only: bool = False,
    ):
        self.engine, self.account_id, self.settings = engine, account_id, settings
        self.observe_only = observe_only
        if observe_only and validation_only:
            raise ValueError("Worker modes are mutually exclusive")
        self.validation_only = validation_only
        self.validation = ValidationService(engine, account_id)
        self.qualification = QualificationService(engine, account_id)
        self.paper = PaperEngine(engine, clock=lambda: datetime.now(UTC))
        self.execution = PaperCoordinator(engine, account_id)
        self.store = RuntimeStore(engine, account_id)
        self.agents = None if observe_only else AgentPipeline(engine, account_id)
        self.client = AngelOneClient(settings)
        self.calendar = SessionCalendar(settings.calendar_file, strict=False)
        self.cache = QuoteCache()
        self.candles = LiveCandles()
        self.candle_store = CandleStore(engine, account_id)
        self.backfill_task: asyncio.Task | None = None
        self.candle_task: asyncio.Task | None = None
        self.last_candle_publication = 0.0
        self.last_backfill = 0.0
        self.analysis = ChainAnalysis(self.cache, settings.greek_max_age_seconds)
        self.instruments: dict[str, Instrument] = {}
        self.base_instruments: list[Instrument] = []
        self.catalog: InstrumentCatalog | None = None
        self.stream_task: asyncio.Task | None = None
        self.fallback_task: asyncio.Task | None = None
        self.publication_task: asyncio.Task | None = None
        self.execution_task: asyncio.Task | None = None
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.refresh_lock = asyncio.Lock()
        self.last_problem: str | None = None
        self.last_fallback = 0.0
        self.last_publication = 0.0
        self.published_ids: dict[str, UUID] = {}
        self.stopping = asyncio.Event()

    async def problem(self, code: str) -> None:
        # Stream invalidation belongs to the transport. A policy/session blocker
        # must not poison otherwise healthy exit data until the next reconnect.
        if code == self.last_problem:
            return
        self.last_problem = code
        now = datetime.now(UTC)
        await asyncio.to_thread(self.validation.tick, now, force_reason=code)
        await asyncio.to_thread(self.qualification.tick, now, code)
        await asyncio.to_thread(self.paper.set_enabled, self.account_id, False, now)
        await asyncio.to_thread(
            self.store.update,
            status="BLOCKED",
            problem=code,
            resume_requested=False,
            active_envelope=None,
            stream_generation=self.cache.generation,
        )
        logger.warning("Market runtime blocked: %s", code)

    def current_session(self, now: datetime, exchange: str | None = None) -> ExchangeSession | None:
        day = now.astimezone(IST).date()
        for venue in [exchange] if exchange else ["NFO", "BFO"]:
            session = self.calendar.get(venue, day)
            if session and session.opens_at <= now < session.closes_at:
                return session
        return None

    async def refresh_universe(self) -> None:
        if self.refresh_lock.locked():
            return
        async with self.refresh_lock:
            try:
                self.calendar.reload()
                now = datetime.now(UTC)
                pinned = await asyncio.to_thread(self.store.open_instruments)
                if not pinned and self.current_session(now) is None:
                    return  # Closed/unknown sessions do not require fresh reference quotes.
                if (
                    self.catalog is None
                    or self.catalog.fetched_at.astimezone(IST).date() != now.astimezone(IST).date()
                ):
                    self.catalog = await InstrumentCatalog.fetch()
                references = {
                    "NSE": self.settings.nifty_index_token,
                    "BSE": self.settings.sensex_index_token,
                }
                requested = {exchange: [token] for exchange, token in references.items() if token}
                spots: dict[str, Decimal] = {}
                if requested:
                    rows = await self.client.quotes(requested)
                    observations = []
                    for row in rows:
                        exchange = str(row.get("exchange", ""))
                        token = str(row.get("symbolToken", row.get("symboltoken", "")))
                        if token != references.get(exchange) or not row.get("exchFeedTime"):
                            continue
                        observations.append(
                            normalize_reference(
                                row,
                                "NIFTY" if exchange == "NSE" else "SENSEX",
                                token,
                                datetime.now(UTC),
                            )
                        )
                        stamp = provider_time(row["exchFeedTime"])
                        age = (datetime.now(UTC) - stamp).total_seconds()
                        price = provider_decimal(row.get("ltp"))
                        if price and price > 0 and 0 <= age <= 10:
                            spots["NIFTY" if exchange == "NSE" else "SENSEX"] = price
                    await asyncio.to_thread(self.store.publish_references, observations)
                if not spots and not pinned:
                    raise ProviderError("FRESH_INDEX_REFERENCE_REQUIRED")
                selected = self.catalog.select(
                    spots,
                    now,
                    self.settings.strikes_each_side,
                    self.settings.max_subscriptions,
                    pinned,
                )
                self.base_instruments = selected
                await self.apply_display_subscriptions(now)
            except (ProviderError, ValueError, OSError):
                await self.problem("UNIVERSE_OR_CALENDAR_UNAVAILABLE")

    async def refresh_display_subscriptions(self) -> None:
        if self.refresh_lock.locked() or self.current_session(datetime.now(UTC)) is None:
            return
        async with self.refresh_lock:
            await self.apply_display_subscriptions(datetime.now(UTC))

    async def apply_display_subscriptions(self, now: datetime) -> None:
        if self.catalog is None or not self.base_instruments:
            return
        requested = await asyncio.to_thread(self.store.display_instruments, now)
        pinned = await asyncio.to_thread(self.store.open_instruments)
        protected = {item.id: item for item in [*self.base_instruments, *pinned]}
        selected = add_display_contracts(
            list(protected.values()), requested, self.catalog, now, self.settings.max_subscriptions
        )
        await self.replace_subscriptions(selected)

    async def replace_subscriptions(self, selected: list[Instrument]) -> None:
        changed = set(self.instruments) != {item.id for item in selected}
        self.instruments = {item.id: item for item in selected}
        self.candles.retain(set(self.instruments))
        if changed or self.stream_task is None or self.stream_task.done():
            if self.stream_task:
                self.stream_task.cancel()
                await asyncio.gather(self.stream_task, return_exceptions=True)
            self.cache.invalidate("SUBSCRIPTIONS_CHANGED")
            await self.problem("SUBSCRIPTIONS_CHANGED")
            self.stream_task = asyncio.create_task(
                AngelOneStream(self.client, self.cache, self.observe_candle).run(
                    selected, self.problem
                )
            )

    async def refresh_metrics(self) -> None:
        if self.current_session(datetime.now(UTC)):
            await self.analysis.refresh_greeks(self.client, list(self.instruments.values()))

    async def evaluation_slot(self) -> None:
        if self.observe_only:
            return
        now = datetime.now(UTC)
        autonomy = (
            await asyncio.to_thread(self.qualification.scope, now)
            if not self.validation_only
            else None
        )
        if not self.validation_only and autonomy is None:
            return
        scope = (
            await asyncio.to_thread(self.validation.active_scope, now)
            if self.validation_only
            else None
        )
        if self.validation_only and (scope is None or scope["entry_used"]):
            return
        allowed = (
            {scope["instrument_id"]}
            if scope
            else {s["instrument_id"] for s in autonomy["instruments"]}
            if autonomy
            else set()
        )
        session = self.current_session(now, scope["exchange"] if scope else None)
        if session is None:
            return
        config = (await asyncio.to_thread(self.store.state))["config"]
        quotes = [
            quote
            for item in self.instruments.values()
            if item.id in allowed
            if (quote := self.analysis.observed_quote(item, now)) is not None
            and quote_problem(quote, now, config.quote_max_age_seconds) is None
        ]
        index = int((now - session.opens_at).total_seconds()) // 180
        slot = session.opens_at + timedelta(seconds=index * 180)
        instruments = {key: item for key, item in self.instruments.items() if key in allowed}
        generation = self.cache.generation
        identifier = await asyncio.to_thread(
            self.store.save_evaluation, session, slot, instruments, quotes, now
        )
        if identifier is None:
            return
        envelope = None
        try:
            if not self.cache.connected or not quotes:
                raise ProviderError("AI_NO_FRESH_STREAM")
            if self.agents is None:
                return
            envelope = await self.agents.evaluate(instruments, quotes, session, config)
            status = "STRATEGY_APPROVED" if envelope else "AGENT_WAIT_OR_REJECT"
            if generation != self.cache.generation or not self.cache.connected:
                envelope, status = None, "INVALIDATED_DURING_ANALYSIS"
        except ProviderError as error:
            status = str(error)
        except (ValueError, TimeoutError):
            status = "AI_INVALID_OR_TIMED_OUT"
        await asyncio.to_thread(
            self.store.finish_evaluation,
            identifier,
            status,
            generation,
            envelope,
            datetime.now(UTC),
        )

    async def fallback_exits(self, positions: list[Instrument]) -> None:
        if not positions or asyncio.get_running_loop().time() - self.last_fallback < 5:
            return
        self.last_fallback = asyncio.get_running_loop().time()
        requested: dict[str, list[str]] = {}
        lookup = {}
        for instrument in positions:
            requested.setdefault(instrument.exchange, []).append(instrument.provider_token)
            lookup[(instrument.exchange, instrument.provider_token)] = instrument
        try:
            rows = await self.client.quotes(requested)
            for row in rows:
                key = (row.get("exchange"), str(row.get("symbolToken", row.get("symboltoken"))))
                if key in lookup:
                    self.cache.update(normalize_rest_quote(row, lookup[key], datetime.now(UTC)))
        except (ProviderError, ValueError, TypeError):
            await self.problem("EXIT_DATA_UNAVAILABLE")

    async def publish_latest(self) -> None:
        now = datetime.now(UTC)
        instruments = dict(self.instruments)
        latest = [
            quote
            for item in instruments.values()
            if (quote := self.analysis.observed_quote(item, now)) is not None
            and self.published_ids.get(item.id) != quote.id
        ]
        await asyncio.to_thread(self.store.publish_quotes, instruments, latest)
        self.published_ids.update({quote.instrument_id: quote.id for quote in latest})

    async def publish_candles(self) -> None:
        rows = self.candles.drain()
        try:
            await asyncio.to_thread(self.candle_store.save, rows)
        except Exception:
            self.candles.restore(rows)
            logger.warning("Observed candle persistence unavailable; retrying separately.")

    def observe_candle(self, quote) -> None:
        try:
            instrument = self.instruments.get(quote.instrument_id)
            if instrument is None:
                return
            session = self.calendar.get(instrument.exchange, quote.timestamp.astimezone(IST).date())
            if session is not None:
                self.candles.observe(quote, instrument, session)
        except Exception:
            logger.warning("Candle observation unavailable; execution quote delivery continues.")

    async def recover_candles(self) -> None:
        """One bounded background backfill; never blocks the independent exit watchdog."""
        now = datetime.now(UTC)
        for identifier, job in list(self.candles.recoveries.items()):
            stream_id, session, target = job
            if target + timedelta(minutes=1) > now:
                continue
            # Detach this job before awaiting: new gaps during the fetch queue
            # independently, even when they belong to the same connection.
            self.candles.recoveries.pop(identifier)
            try:
                start = await asyncio.to_thread(
                    self.candle_store.recovery_start, identifier, stream_id, session, target
                )
                end = min(now.replace(second=0, microsecond=0), session.closes_at)
                if start >= end:
                    continue
                query = HistoryQuery(
                    instrument_id=identifier, interval="ONE_MINUTE", start=start, end=end
                )
                await asyncio.to_thread(refresh_history, query, self.engine, self.account_id)
            except HistoryError as error:
                if error.status_code == 429:
                    self.candles.recoveries.setdefault(identifier, job)
                    return  # Shared budget is busy. Keep the request queued.
                logger.warning("Candle history recovery unavailable; retained as a gap.")
            except Exception:
                self.candles.recoveries.setdefault(identifier, job)
                logger.warning("Candle recovery persistence unavailable; retrying separately.")
                return
            return

    async def execution_watchdog(self) -> None:
        """A single coalesced consumer; agents, news and entry admission cannot await it."""
        while not self.stopping.is_set():
            now = datetime.now(UTC)
            sessions = {
                venue: session
                for venue in ("NFO", "BFO")
                if (session := self.calendar.get(venue, now.astimezone(IST).date())) is not None
            }
            try:
                await asyncio.to_thread(self.validation.tick, now)
                await asyncio.to_thread(self.qualification.tick, now)
                await asyncio.to_thread(
                    self.execution.cycle,
                    dict(self.cache.quotes),
                    sessions,
                    self.cache.connected and self.cache.problem is None,
                )
            except ValueError:
                await self.problem("DURABLE_EXECUTION_RECONCILIATION_REQUIRED")
            await asyncio.sleep(0.25)

    async def cycle(self) -> None:
        now = datetime.now(UTC)
        clock = asyncio.get_running_loop().time()
        if clock - self.last_candle_publication >= 1 and (
            self.candle_task is None or self.candle_task.done()
        ):
            self.last_candle_publication = clock
            self.candle_task = asyncio.create_task(self.publish_candles())
        if self.backfill_task and self.backfill_task.done():
            self.backfill_task.result()
        if (
            self.candles.recoveries
            and clock - self.last_backfill >= 5
            and (self.backfill_task is None or self.backfill_task.done())
        ):
            self.last_backfill = clock
            self.backfill_task = asyncio.create_task(self.recover_candles())
        if self.execution_task and self.execution_task.done():
            self.execution_task.result()
            raise RuntimeError("EXECUTION_WATCHDOG_STOPPED")
        if self.publication_task and self.publication_task.done():
            try:
                self.publication_task.result()
            except Exception:
                raise RuntimeError("MARKET_PERSISTENCE_FAILED") from None
        if clock - self.last_publication >= 1 and (
            self.publication_task is None or self.publication_task.done()
        ):
            self.last_publication = clock
            self.publication_task = asyncio.create_task(self.publish_latest())
        state = await asyncio.to_thread(self.store.state)
        positions = await asyncio.to_thread(self.store.open_instruments)
        config = state["config"]
        if positions:
            if any(
                quote_problem(self.cache.quotes.get(item.id), now, config.quote_max_age_seconds)
                for item in positions
            ):
                # A separate task performs REST recovery; it must not delay the exit watchdog.
                if self.fallback_task is None or self.fallback_task.done():
                    self.fallback_task = asyncio.create_task(self.fallback_exits(positions))
            session = state["session"]
            await asyncio.to_thread(
                self.paper.monitor, self.account_id, dict(self.cache.quotes), session, now
            )
        session = self.current_session(now)
        if session is not None and state.get("session_key") != session.key:
            # Session rollover is independent of entry activation, strategy and
            # yesterday's loss block. The engine still requires reconciled, flat
            # holdings and no unresolved orders; a failed rollover never resets risk.
            try:
                await asyncio.to_thread(self.paper.start_session, self.account_id, session, now)
            except ValueError:
                await self.problem("SESSION_ROLLOVER_BLOCKED")
                return
            await asyncio.to_thread(
                self.store.update,
                session_payload=session.model_dump(mode="json"),
                resume_requested=False,
                active_envelope=None,
                attempted_envelope_id=None,
                status="OBSERVATION_ONLY" if self.observe_only else "PAUSED",
                problem=None,
            )
            state = await asyncio.to_thread(self.store.state)
        if self.observe_only:
            if state["enabled"]:
                await asyncio.to_thread(self.paper.set_enabled, self.account_id, False, now)
            # Protection and existing-position monitoring above remain independent.
            if state["runtime_status"] != "OBSERVATION_ONLY" or state["resume_requested"]:
                await asyncio.to_thread(
                    self.store.update,
                    status="OBSERVATION_ONLY",
                    problem=None,
                    resume_requested=False,
                    active_envelope=None,
                )
            return
        scope = (
            await asyncio.to_thread(self.validation.active_scope, now)
            if self.validation_only
            else None
        )
        if self.validation_only and (scope is None or scope["entry_used"]):
            if scope is None and state["enabled"]:
                await asyncio.to_thread(self.paper.set_enabled, self.account_id, False, now)
            if scope is None and state["runtime_status"] == "STARTING":
                await asyncio.to_thread(self.store.update, status="VALIDATION_IDLE")
            return
        autonomy = (
            await asyncio.to_thread(self.qualification.scope, now)
            if not self.validation_only
            else None
        )
        if not self.validation_only and autonomy is None:
            if state["enabled"]:
                await asyncio.to_thread(self.paper.set_enabled, self.account_id, False, now)
            if state["runtime_status"] == "STARTING":
                await asyncio.to_thread(self.store.update, status="AWAITING_PAPER_ARM")
            return
        allowed = (
            {scope["instrument_id"]}
            if scope
            else {s["instrument_id"] for s in autonomy["instruments"]}
            if autonomy
            else set()
        )
        session = self.current_session(now, scope["exchange"] if scope else None)
        if session is None:
            await self.problem("NO_VERIFIED_OPEN_SESSION")
            return
        if not self.cache.connected:
            await self.problem("STREAM_NOT_READY")
            return
        if state["daily_blocked"]:
            await self.problem("DAILY_LOSS_LIMIT")
            return
        # Any gap invalidates an old envelope before a new entry can be proposed.
        envelope = state["envelope"]
        if envelope and (
            envelope.invalidated or not envelope.issued_at <= now < envelope.expires_at
        ):
            await asyncio.to_thread(
                self.store.update,
                active_envelope=None,
                status="AWAITING_AGENT",
                problem="NO_CURRENT_STRATEGY",
            )
            if state["enabled"]:
                await asyncio.to_thread(self.paper.set_enabled, self.account_id, False, now)
            return
        if not envelope:
            await asyncio.to_thread(
                self.store.update, status="AWAITING_AGENT", problem="NO_APPROVED_STRATEGY"
            )
            return
        eligible = [
            self.instruments[identifier]
            for identifier in envelope.instrument_ids
            if identifier in self.instruments and identifier in allowed
        ]
        if not eligible or any(
            quote_problem(self.cache.quotes.get(item.id), now, config.quote_max_age_seconds)
            for item in eligible
        ):
            await self.problem("STRATEGY_QUOTES_UNAVAILABLE")
            return
        if state["resume_requested"] and not state["enabled"]:
            await asyncio.to_thread(self.paper.start_session, self.account_id, session, now)
            state["enabled"] = await asyncio.to_thread(
                self.store.enable_requested, envelope.id, self.cache.generation, datetime.now(UTC)
            )
            if state["enabled"]:
                self.last_problem = None
        if not state["enabled"] or positions or state["attempted_envelope_id"] == envelope.id:
            return
        for instrument in eligible:
            quote = self.analysis.observed_quote(instrument, now)
            venue_session = self.current_session(now, instrument.exchange)
            if quote is None or quote.ask is None or venue_session is None:
                continue
            if not envelope.min_entry <= quote.ask <= envelope.max_entry:
                continue
            # This is an actual deterministic rule trigger, not an invented AI response.
            decision = TradeDecision(
                id=uuid5(envelope.id, str(self.account_id)),
                action=envelope.action,
                timestamp=now,
                expires_at=min(envelope.expires_at, now + timedelta(seconds=5)),
                rationale=f"Entry predicate matched approved strategy {envelope.version}",
                snapshot_ids=tuple(set(envelope.evidence_ids) | {quote.id}),
                instrument_id=instrument.id,
                entry=quote.ask,
                stop_loss=envelope.stop_loss,
                target=envelope.target,
                strategy_id=envelope.id,
            )
            await asyncio.to_thread(
                self.store.update,
                attempted_envelope_id=envelope.id,
                session_payload=venue_session.model_dump(mode="json"),
            )
            await asyncio.to_thread(
                self.execution.admit,
                decision,
                instrument,
                quote,
                envelope,
                venue_session,
                dict(self.cache.quotes),
            )
            break

    async def run(self) -> None:
        lease = self.engine.connect()
        key = int.from_bytes(self.account_id.bytes[:8], "big") & ((1 << 63) - 1)
        acquired = False
        try:
            acquired = bool(lease.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}))
            lease.commit()
            if not acquired:
                raise ProviderError("ACCOUNT_WORKER_ALREADY_RUNNING")
            now = datetime.now(UTC)
            mode = (
                "OBSERVATION"
                if self.observe_only
                else "VALIDATION"
                if self.validation_only
                else "AUTONOMOUS"
            )
            await asyncio.to_thread(self.store.initialize, now, mode)
            recovery = await asyncio.to_thread(self.execution.ledger.recover, self.account_id, now)
            if not recovery["reconciled"]:
                raise ProviderError("RECONCILIATION_REQUIRED")
            self.execution_task = asyncio.create_task(self.execution_watchdog())
            await self.refresh_universe()
            for name, function, interval in (
                ("universe", self.refresh_universe, 180),
                ("display", self.refresh_display_subscriptions, 15),
                ("metrics", self.refresh_metrics, 60),
                ("evaluation", self.evaluation_slot, 180),
            ):
                self.scheduler.add_job(
                    function,
                    "interval",
                    seconds=interval,
                    id=name,
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=15,
                )
            self.scheduler.start()
            while not self.stopping.is_set():
                try:
                    await asyncio.wait_for(self.cache.changed.wait(), timeout=1)
                except TimeoutError:
                    pass
                self.cache.changed.clear()
                # Loss of this dedicated connection loses the singleton lock: stop immediately.
                lease.execute(text("SELECT 1"))
                lease.commit()
                await asyncio.to_thread(
                    self.store.update,
                    heartbeat=datetime.now(UTC),
                    stream_generation=self.cache.generation,
                )
                try:
                    await self.cycle()
                except (ValueError, ProviderError):
                    await self.problem("RUNTIME_PREFLIGHT_FAILED")
        finally:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            tasks = [
                task
                for task in (
                    self.stream_task,
                    self.fallback_task,
                    self.publication_task,
                    self.execution_task,
                    self.backfill_task,
                    self.candle_task,
                )
                if task
            ]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.client.close()
            if acquired:
                try:
                    await asyncio.to_thread(
                        self.validation.tick, datetime.now(UTC), force_reason="WORKER_STOP"
                    )
                    await asyncio.to_thread(
                        self.qualification.tick, datetime.now(UTC), "WORKER_STOP"
                    )
                    await asyncio.to_thread(
                        self.paper.set_enabled, self.account_id, False, datetime.now(UTC)
                    )
                    await asyncio.to_thread(
                        self.store.update,
                        status="STOPPED",
                        resume_requested=False,
                        active_envelope=None,
                    )
                    lease.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                    lease.commit()
                except Exception:
                    logger.error(
                        "Worker stopped with unavailable persistence; reconciliation required."
                    )
            lease.close()
