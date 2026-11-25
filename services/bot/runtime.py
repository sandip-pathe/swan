"""One bounded event engine; no account database and no order capability."""

import asyncio
import hashlib
import json
import logging
import os
import time as clock
from collections import deque
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from services.bot.contracts import active
from services.bot.engine import RollingMarket
from services.bot.feasibility import assess
from services.bot.notifications import deliver
from services.bot.research import packet_for, synthesize
from services.bot.session import market_context
from services.bot.sources import headlines, weekly
from services.bot.store import Store
from services.core.contracts import IST, Instrument, Quote
from services.market.angelone import AngelOneClient
from services.market.calendar import SessionCalendar
from services.market.catalog import InstrumentCatalog
from services.market.index_history import IndexHistoryQuery
from services.market.reference_contracts import IndexReference
from services.market.references import normalize_reference
from services.market.settings import MarketSettings, ProviderError
from services.market.stream import AngelOneStream, QuoteCache

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self, store: Store):
        self.store = store
        self.settings = MarketSettings()
        self.client = AngelOneClient(self.settings)
        self.cache = QuoteCache()
        self.markets = {name: RollingMarket(name) for name in ("SENSEX", "NIFTY")}
        self.instruments: list[Instrument] = []
        self.stream: asyncio.Task | None = None
        self.stream_started = 0.0
        self.last_generation = -1
        self.last_processed: dict = {}
        self.bootstrap_day = ""
        self.last_snapshot = 0.0
        self.last_repair = 0.0
        self.status: dict = {}
        self.noise: dict[str, deque] = {}
        self.noise_generation = -1
        self.repair_after: dict[tuple, float] = {}
        self.calendar = SessionCalendar(self.settings.calendar_file)

    async def problem(self, reason: str):
        self.status = {"status": "degraded", "detail": reason}
        logger.warning(
            "market_stream_unavailable reason=%s generation=%s", reason, self.cache.generation
        )

    async def bootstrap(self, now: datetime, calendar: SessionCalendar):
        for name, venue, exchange in (("SENSEX", "BFO", "BSE"), ("NIFTY", "NFO", "NSE")):
            session = calendar.get(venue, now.astimezone(IST).date())
            end = now.replace(second=0, microsecond=0)
            if not session or end <= session.opens_at:
                continue
            try:
                result = await asyncio.wait_for(
                    self.client.index_candles(
                        IndexHistoryQuery.model_validate(
                            dict(
                                underlying=name,
                                exchange=exchange,
                                session=session,
                                start=session.opens_at,
                                end=min(end, datetime.combine(session.key, time(15, 30), IST)),
                            )
                        )
                    ),
                    15,
                )
                self.markets[name].merge(list(result.bars))
                self.store.write(f"evidence:{name}", result.model_dump(mode="json"))
            except (ProviderError, TimeoutError, ValueError, OSError):
                logger.warning("bootstrap_history_unavailable underlying=%s", name)

    async def start_stream(self, now: datetime):
        rows = await asyncio.wait_for(
            self.client.quotes(
                {
                    "NSE": [self.settings.nifty_index_token],
                    "BSE": [self.settings.sensex_index_token],
                }
            ),
            15,
        )
        spot = None
        for row in rows:
            for name, venue, token in (
                ("SENSEX", "BSE", self.settings.sensex_index_token),
                ("NIFTY", "NSE", self.settings.nifty_index_token),
            ):
                if (
                    row.get("exchange") == venue
                    and str(row.get("symbolToken", row.get("symboltoken"))) == token
                ):
                    reference = normalize_reference(row, name, token, now)
                    self.store.write(f"quote:{name}", reference.model_dump(mode="json"))
                    if name == "SENSEX":
                        spot = reference.last_price
        if spot is None:
            raise ProviderError("SENSEX_REFERENCE_REQUIRED")
        catalog = await asyncio.wait_for(asyncio.to_thread(self.load_catalog, now), 2)
        if catalog is None:
            fetched = await asyncio.wait_for(InstrumentCatalog.fetch(("SENSEX",)), 70)
            catalog = fetched
            self.store.write(
                "master",
                {
                    "fetched_at": catalog.fetched_at.isoformat(),
                    "instruments": [
                        item.model_dump(mode="json")
                        for item in catalog.instruments.values()
                        if item.underlying == "SENSEX" and item.expiry >= now.astimezone(IST).date()
                    ],
                },
            )
        assert catalog is not None
        available = [
            item
            for item in catalog.instruments.values()
            if item.underlying == "SENSEX"
            and now.astimezone(IST).date()
            <= item.expiry
            <= now.astimezone(IST).date() + timedelta(days=35)
        ]
        expiries = sorted({item.expiry for item in available})
        chosen = (
            expiries[:1]
            + [
                expiry
                for expiry in expiries[1:]
                if expiry >= now.astimezone(IST).date() + timedelta(days=7)
            ][:1]
        )
        selected: list[Instrument] = []
        for expiry in chosen:
            group = [item for item in available if item.expiry == expiry]
            strikes = sorted(
                {item.strike for item in group}, key=lambda strike: abs(strike - spot)
            )[:2]
            selected.extend(item for item in group if item.strike in strikes)
        pinned_ids = {
            (self.store.read("scenario:" + idea["id"]) or {}).get("contract_id")
            for idea in self.store.ideas()
            if active(idea, now)
        }
        pinned = [item for item in available if item.id in pinned_ids]
        ordered = pinned + sorted(
            selected, key=lambda item: (item.expiry, item.strike, item.option_type)
        )
        unique = {item.id: item for item in ordered}
        self.instruments = list(unique.values())[:8]
        self.stream_started = clock.monotonic()
        self.store.write(
            "selected_contracts", [item.model_dump(mode="json") for item in self.instruments]
        )
        self.stream = asyncio.create_task(
            AngelOneStream(
                self.client,
                self.cache,
                on_observation=self.on_option,
                on_reference=self.on_reference,
            ).run(self.instruments, self.problem)
        )

    def on_reference(self, reference: IndexReference):
        self.markets[reference.underlying].tick(reference, self.cache.generation)

    def on_option(self, quote: Quote):
        if self.noise_generation != self.cache.generation:
            self.noise.clear()
            self.noise_generation = self.cache.generation
        if (
            quote.bid is None
            or quote.ask is None
            or quote.bid >= quote.ask
            or quote.timestamp > quote.received_at
        ):
            return
        values = self.noise.setdefault(quote.instrument_id, deque(maxlen=181))
        if not values or quote.timestamp - values[-1][0] >= timedelta(seconds=1):
            values.append((quote.timestamp, (quote.bid + quote.ask) / 2))

    def noise_summary(self, identifier: str, now: datetime) -> dict:
        values = [
            (stamp, price)
            for stamp, price in self.noise.get(identifier, [])
            if timedelta(0) <= now - stamp <= timedelta(minutes=3)
        ]
        return (
            {
                "count": len(values),
                "from": values[0][0].isoformat(),
                "to": values[-1][0].isoformat(),
                "high": str(max(p for _, p in values)),
                "low": str(min(p for _, p in values)),
            }
            if values
            else {}
        )

    def load_catalog(self, now: datetime) -> InstrumentCatalog | None:
        saved = self.store.read("master")
        if (
            not saved
            or datetime.fromisoformat(saved["fetched_at"]).astimezone(IST).date()
            != now.astimezone(IST).date()
        ):
            return None
        return InstrumentCatalog(
            [Instrument.model_validate(row) for row in saved["instruments"]],
            datetime.fromisoformat(saved["fetched_at"]),
            0,
        )

    async def repair(self, now: datetime, calendar: SessionCalendar):
        if clock.monotonic() - self.last_repair < 60:
            return
        self.last_repair = clock.monotonic()
        for name, venue, exchange in (("SENSEX", "BFO", "BSE"), ("NIFTY", "NFO", "NSE")):
            session = calendar.get(venue, now.astimezone(IST).date())
            if not session:
                continue
            end = min(
                now.replace(second=0, microsecond=0),
                datetime.combine(session.key, time(15, 30), IST),
            )
            stamps = [session.opens_at + timedelta(minutes=i) for i in range(15)]
            stamps += [end - timedelta(minutes=i) for i in range(20, 0, -1)]
            missing = [
                stamp
                for stamp in stamps
                if session.opens_at <= stamp < end and stamp not in self.markets[name].bars
            ]
            if not missing:
                continue
            missing = [
                stamp
                for stamp in missing
                if clock.monotonic() >= self.repair_after.get((name, stamp), 0)
            ]
            if not missing:
                continue
            start = min(missing)
            for stamp in missing:
                if start <= stamp < start + timedelta(minutes=10):
                    self.repair_after[(name, stamp)] = clock.monotonic() + 600
            result = await asyncio.wait_for(
                self.client.index_candles(
                    IndexHistoryQuery.model_validate(
                        dict(
                            underlying=name,
                            exchange=exchange,
                            session=session,
                            start=start,
                            end=min(end, start + timedelta(minutes=10)),
                        )
                    )
                ),
                12,
            )
            corrected = self.markets[name].merge(list(result.bars))
            if corrected and name == "SENSEX":
                for idea in self.store.ideas():
                    if active(idea, now) and idea["horizon"] == "intraday":
                        self.save(
                            idea,
                            {
                                **idea,
                                "state": "invalidated",
                                "reasons": ["DEPENDENCY_SOURCE_CORRECTED"],
                            },
                            now,
                        )
            break  # One repair window globally per minute, no request fan-out.

    def suspend_all(self, reason: str, now: datetime):
        for idea in self.store.ideas():
            if active(idea, now) and idea["state"] not in {"watch", "suspended"}:
                self.save(idea, {**idea, "state": "suspended", "reasons": [reason]}, now)

    def save(self, prior: dict | None, value: dict, now: datetime, snapshot: dict | None = None):
        keys = ("state", "reasons", "contract", "research")
        if prior and all(prior.get(key) == value.get(key) for key in keys):
            return False
        expected = prior["revision"] if prior else 0
        value = {**value, "revision": expected + 1, "published_at": now.isoformat()}
        return self.store.revise(value, expected, snapshot)

    def evaluate(self, now: datetime):
        existing = self.store.ideas()
        market = self.markets["SENSEX"]
        candidates = market.candidates(now)
        # Keep weekly watch ideas from the verified daily pipeline in the same lifecycle.
        candidates += self.store.read("weekly_candidates", [])
        for candidate in candidates:
            if datetime.fromisoformat(candidate["expires_at"]) <= now:
                continue
            prior = next(
                (
                    idea
                    for idea in existing
                    if idea["strategy"] == candidate["strategy"]
                    and idea["direction"] == candidate["direction"]
                    and active(idea, now)
                ),
                None,
            )
            if prior:
                continue  # Existing thesis levels remain frozen, not moved with every candle.
            recent_terminal = any(
                idea["strategy"] == candidate["strategy"]
                and idea["direction"] == candidate["direction"]
                and now - datetime.fromisoformat(idea["published_at"]) < timedelta(minutes=10)
                for idea in existing
            )
            if recent_terminal or any(idea["id"] == candidate["id"] for idea in existing):
                continue
            if self.save(
                None,
                candidate,
                now,
                {
                    "bars": [
                        bar.model_dump(mode="json")
                        for bar in sorted(market.bars.values(), key=lambda bar: bar.opens_at)
                        if bar.opens_at.isoformat() in candidate.get("evidence_ids", [])
                        or bar in sorted(market.bars.values(), key=lambda bar: bar.opens_at)[:15]
                        or bar in sorted(market.bars.values(), key=lambda bar: bar.opens_at)[-20:]
                    ],
                    "source": "retained source-specific candles",
                    "received_at": now.isoformat(),
                    "response_sha256": hashlib.sha256(
                        json.dumps(candidate["evidence_ids"]).encode()
                    ).hexdigest(),
                },
            ):
                self.store.enqueue(candidate)
        reference = self.cache.references.get("SENSEX")
        fresh = bool(
            self.cache.connected
            and reference
            and timedelta(0) <= now - reference.timestamp <= timedelta(seconds=5)
        )
        latest = market.context(now)
        for prior in self.store.ideas():
            if prior["state"] in {"expired", "invalidated"}:
                continue
            value = dict(prior)
            if now >= datetime.fromisoformat(prior["expires_at"]):
                value.update(state="expired", reasons=["IDEA_TIME_EXPIRED"])
            elif not fresh:
                value.update(state="suspended", reasons=["STREAM_OR_REFERENCE_UNAVAILABLE"])
            elif reference:
                sign = Decimal(1) if prior["direction"] == "CALL" else Decimal(-1)
                if sign * (reference.last_price - Decimal(prior["invalidation_level"])) <= 0:
                    value.update(state="invalidated", reasons=["UNDERLYING_INVALIDATION_REACHED"])
                elif prior["horizon"] == "intraday" and latest["status"] != "current":
                    value.update(state="suspended", reasons=["REQUIRED_BAR_WINDOW_INCOMPLETE"])
                else:
                    pair = market.window(
                        now.replace(second=0, microsecond=0) - timedelta(minutes=2), 2
                    )
                    confirmed = False
                    if pair:
                        a, b = pair
                        level = Decimal(prior["trigger_level"])
                        if prior["strategy"] == "range-retest-v1":
                            confirmed = (
                                sign * (a.close - level) > 0
                                and sign * (b.close - level) > 0
                                and (b.low <= level if sign > 0 else b.high >= level)
                            )
                        elif prior["strategy"] == "failed-break-v1":
                            confirmed = sign * (b.close - level) > 0
                        else:
                            confirmed = sign * (b.close - level) > 0
                    eligible = [
                        item
                        for item in self.instruments
                        if item.option_type == prior["direction"]
                        and (
                            prior["horizon"] != "weekly"
                            or item.expiry
                            >= datetime.fromisoformat(prior["expires_at"]).astimezone(IST).date()
                        )
                    ]
                    frozen = self.store.read("scenario:" + prior["id"])
                    if frozen:
                        eligible = [item for item in eligible if item.id == frozen["contract_id"]]
                    instrument = (
                        min(eligible, key=lambda item: abs(item.strike - reference.last_price))
                        if eligible
                        else None
                    )
                    economics, reasons = (
                        assess(
                            instrument,
                            self.cache.quotes.get(instrument.id),
                            now,
                            self.noise_summary(instrument.id, now),
                            frozen["economics"] if frozen else None,
                        )
                        if instrument
                        else (None, ["SUITABLE_CONTRACT_UNAVAILABLE"])
                    )
                    value.update(
                        contract=instrument.model_dump(mode="json") if instrument else None,
                        economics=economics,
                    )
                    research = prior.get("research") or {}
                    if not research.get("result") or research["result"].get("abstain"):
                        reasons.append(research.get("status", "RESEARCH_PENDING"))
                    if research.get("at") and now - datetime.fromisoformat(
                        research["at"]
                    ) > timedelta(minutes=15):
                        reasons.append("RESEARCH_REASSESSMENT_REQUIRED")
                        if now - datetime.fromisoformat(research["at"]) < timedelta(minutes=16):
                            self.store.enqueue(prior)
                    if not confirmed:
                        reasons.append("ENTRY_CONDITION_NOT_CONFIRMED")
                    value.update(
                        state="eligible"
                        if not reasons
                        else "trigger_pending"
                        if confirmed
                        else "watch",
                        reasons=reasons,
                    )
                    conflicting = any(
                        active(other, now)
                        and other["id"] != prior["id"]
                        and other["direction"] != prior["direction"]
                        and other["horizon"] == prior["horizon"]
                        and other["state"] in {"eligible", "trigger_pending"}
                        for other in self.store.ideas()
                    )
                    if conflicting and value["state"] == "eligible":
                        value.update(
                            state="watch", reasons=["OPPOSING_IDEA_REQUIRES_RESOLUTION"], rank=0
                        )
                    if value["state"] == "eligible":
                        value["rank"] = 1
                        value["summary"] = (
                            "Entry conditions and one-lot checks passed. Confirm your budget and fresh pricing; this remains an experimental idea."
                        )
            frozen = self.store.read("scenario:" + prior["id"])
            contract = value.get("contract") or {}
            quote = self.cache.quotes.get(contract.get("id", ""))
            if (
                frozen
                and quote
                and quote.bid
                and fresh
                and timedelta(0) <= now - quote.timestamp <= timedelta(seconds=5)
            ):
                if quote.bid <= Decimal(frozen["economics"]["premium_invalidation"]):
                    value.update(state="invalidated", reasons=["PREMIUM_INVALIDATION_REACHED"])
                elif quote.bid >= Decimal(frozen["economics"]["premium_target_scenario"]):
                    value.update(state="expired", reasons=["PREMIUM_TARGET_SCENARIO_REACHED"])
            if value["state"] == "eligible" and not frozen and value.get("economics"):
                self.store.write(
                    "scenario:" + prior["id"],
                    {"contract_id": contract["id"], "economics": value["economics"]},
                )
            self.save(prior, value, now)
            self.track(value, now)

    def track(self, idea: dict, now: datetime):
        # Prospective hypothetical outcomes are distinct from user-reported fills.
        with self.store.connect() as db:
            row = db.execute(
                "SELECT payload FROM evaluations WHERE idea_id=?", (idea["id"],)
            ).fetchone()
            value = json.loads(row[0]) if row else None
            economics = idea.get("economics")
            if value is None and idea["state"] == "eligible" and economics:
                value = {
                    "idea_id": idea["id"],
                    "strategy": idea["strategy"],
                    "horizon": idea["horizon"],
                    "entry_at": now.isoformat(),
                    "entry_ask": economics["entry_ask"],
                    "contract_id": idea["contract"]["id"],
                    "quantity": economics["quantity"],
                    "cost_assumption": economics["estimated_round_trip_cost"],
                    "hypothetical": True,
                    "max_gross_adverse": "0",
                    "max_gross_favourable": "0",
                    "premium_stop": economics["premium_invalidation"],
                    "premium_target": economics["premium_target_scenario"],
                }
            if value is None or value.get("outcome"):
                return
            contract = idea.get("contract") or {}
            quote = self.cache.quotes.get(value.get("contract_id", contract.get("id", "")))
            if (
                quote
                and quote.bid
                and timedelta(0) <= now - quote.timestamp <= timedelta(seconds=5)
            ):
                gross = (quote.bid - Decimal(value["entry_ask"])) * value["quantity"]
                value["max_gross_adverse"] = str(min(Decimal(value["max_gross_adverse"]), gross))
                value["max_gross_favourable"] = str(
                    max(Decimal(value["max_gross_favourable"]), gross)
                )
                outcome = (
                    "premium_invalidation"
                    if quote.bid <= Decimal(value["premium_stop"])
                    else "premium_target"
                    if quote.bid >= Decimal(value["premium_target"])
                    else idea["state"]
                    if idea["state"] in {"invalidated", "expired"}
                    else None
                )
                if outcome:
                    value.update(
                        outcome=outcome,
                        exit_at=now.isoformat(),
                        exit_bid=str(quote.bid),
                        net_estimate=str(gross - Decimal(value["cost_assumption"])),
                    )
            elif idea["state"] in {"invalidated", "expired"}:
                value.update(outcome="unpriced_" + idea["state"], exit_at=now.isoformat())
            db.execute(
                "INSERT INTO evaluations VALUES (?,?) ON CONFLICT(idea_id) DO UPDATE SET payload=excluded.payload",
                (idea["id"], json.dumps(value)),
            )
            db.execute(
                "DELETE FROM evaluations WHERE idea_id NOT IN (SELECT idea_id FROM evaluations ORDER BY "
                "json_extract(payload,'$.entry_at') DESC LIMIT 2000)"
            )

    async def research_loop(self, stop: asyncio.Event):
        with self.store.connect() as db:
            db.execute(
                "UPDATE research_jobs SET state='unknown_usage_after_restart' WHERE state='running'"
            )
        while not stop.is_set():
            job = await asyncio.to_thread(self.store.claim_job)
            if job:
                idea = job["idea"]
                now = datetime.now(UTC)
                current = self.store.idea(idea["id"])
                if not current or not active(current, now):
                    self.store.finish_job(job["job_id"], "superseded")
                    continue
                if os.environ.get("BOT_COLLECTION_ENABLED", "false").lower() != "true":
                    self.store.finish_job(job["job_id"], "paused")
                    continue
                try:
                    result, status = await synthesize(
                        self.store, packet_for(current, self.store.read("news", {}))
                    )
                    if status == "AI_BUSY":
                        self.store.finish_job(job["job_id"], "queued")
                        await asyncio.sleep(2)
                        continue
                    latest = self.store.idea(idea["id"])
                    if (
                        latest
                        and active(latest, datetime.now(UTC))
                        and latest["trigger_level"] == current["trigger_level"]
                    ):
                        # Research describes a frozen thesis; eligibility is rechecked in evaluate().
                        latest["research"] = {
                            "result": result,
                            "status": status,
                            "at": datetime.now(UTC).isoformat(),
                        }
                        self.store.revise(
                            {**latest, "revision": latest["revision"] + 1}, latest["revision"]
                        )
                    self.store.finish_job(job["job_id"], status)
                    self.store.write(
                        "research_status", {"status": status, "at": datetime.now(UTC).isoformat()}
                    )
                except (ValueError, OSError) as error:
                    logger.warning("research_job_unavailable type=%s", type(error).__name__)
                    self.store.finish_job(job["job_id"], "unavailable")
            try:
                await asyncio.wait_for(stop.wait(), 2)
            except TimeoutError:
                pass

    async def auxiliary(self, stop: asyncio.Event):
        news_next = weekly_next = backup_next = 0.0
        while not stop.is_set():
            now = datetime.now(UTC)
            tick = clock.monotonic()
            if tick >= news_next:
                try:
                    result = await headlines()
                    self.store.write("news", result)
                    catalyst_ids = sorted(
                        row["id"] for row in result.get("items", []) if row.get("fresh_catalyst")
                    )
                    previous = self.store.read("catalysts", [])
                    self.store.write("catalysts", catalyst_ids)
                    if set(catalyst_ids) - set(previous):
                        for idea in self.store.ideas():
                            if active(idea, now):
                                updated = {
                                    **idea,
                                    "state": "watch",
                                    "research": None,
                                    "reasons": ["NEW_RELEVANT_CATALYST_REQUIRES_RESEARCH"],
                                }
                                if self.save(idea, updated, now):
                                    latest = self.store.idea(idea["id"])
                                    if latest:
                                        self.store.enqueue(latest)
                except (ValueError, OSError, ProviderError):
                    self.store.write("news", {"sources": [{"status": "unavailable"}], "items": []})
                news_next = tick + 300
            if (
                tick >= weekly_next
                and os.environ.get("BOT_COLLECTION_ENABLED", "false").lower() == "true"
            ):
                try:
                    result, ideas = await weekly(self.client, self.calendar, now)
                    self.store.write("weekly", result)
                    self.store.write("weekly_candidates", ideas)
                except (ProviderError, ValueError, TimeoutError):
                    self.store.write(
                        "weekly",
                        {"status": "unavailable", "reason": "Daily history could not be verified."},
                    )
                weekly_next = tick + 3600
            if tick >= backup_next:
                await asyncio.to_thread(self.store.backup)
                self.store.write(
                    "backup",
                    {"at": now.isoformat(), "kind": "consistent_local_sqlite", "off_host": False},
                )
                backup_next = tick + 86400
            with self.store.connect() as db:
                notices = db.execute(
                    "SELECT key,payload FROM documents WHERE key LIKE 'notification:%' LIMIT 4"
                ).fetchall()
            for key, payload in notices:
                idea = json.loads(payload)
                if datetime.now(UTC) - datetime.fromisoformat(idea["published_at"]) < timedelta(
                    seconds=60
                ):
                    await asyncio.to_thread(deliver, self.store, idea)
                with self.store.connect() as db:
                    db.execute("DELETE FROM documents WHERE key=? AND payload=?", (key, payload))
            self.store.prune()
            try:
                await asyncio.wait_for(stop.wait(), 15)
            except TimeoutError:
                pass

    async def run(self, stop: asyncio.Event):
        tasks = [
            asyncio.create_task(self.research_loop(stop), name="research"),
            asyncio.create_task(self.auxiliary(stop), name="auxiliary"),
        ]
        next_start = heartbeat_next = calendar_next = 0.0
        try:
            while not stop.is_set():
                now = datetime.now(UTC)
                tick = clock.monotonic()
                for task in tasks:
                    if task.get_name() in {"research", "auxiliary"} and task.done():
                        await task
                        raise RuntimeError("Background service stopped: " + task.get_name())
                if tick >= calendar_next:
                    self.calendar = SessionCalendar(self.settings.calendar_file)
                    calendar_next = tick + 60
                calendar = self.calendar
                contexts = {
                    name: market_context(calendar, now, venue)
                    for name, venue in (("SENSEX", "BFO"), ("NIFTY", "NFO"))
                }
                enabled = os.environ.get("BOT_COLLECTION_ENABLED", "false").lower() == "true"
                opened = contexts["SENSEX"]["state"] == "open"
                if not enabled or not opened:
                    if self.stream:
                        self.stream.cancel()
                        await asyncio.gather(self.stream, return_exceptions=True)
                        self.stream = None
                    self.suspend_all("MARKET_CLOSED" if enabled else "COLLECTION_PAUSED", now)
                    # Expiry transitions still happen outside market hours.
                    for idea in self.store.ideas():
                        if idea["state"] not in {
                            "expired",
                            "invalidated",
                        } and now >= datetime.fromisoformat(idea["expires_at"]):
                            self.track({**idea, "state": "expired"}, now)
                            self.save(
                                idea,
                                {**idea, "state": "expired", "reasons": ["IDEA_TIME_EXPIRED"]},
                                now,
                            )
                    self.status = {"status": contexts["SENSEX"]["state"] if enabled else "paused"}
                elif self.stream is None and tick >= next_start:
                    try:
                        day = str(now.astimezone(IST).date())
                        if self.bootstrap_day != day:
                            self.markets = {
                                name: RollingMarket(name) for name in ("SENSEX", "NIFTY")
                            }
                            await self.bootstrap(now, calendar)
                            self.bootstrap_day = day
                        await self.start_stream(now)
                        self.status = {"status": "connecting"}
                    except (ProviderError, TimeoutError, ValueError, OSError) as error:
                        self.status = {"status": "unavailable", "detail": type(error).__name__}
                        next_start = tick + 60
                elif self.stream:
                    if self.stream.done():
                        await asyncio.gather(self.stream, return_exceptions=True)
                        self.stream = None
                        next_start = tick + 10
                    reference = self.cache.references.get("SENSEX")
                    if (
                        self.stream
                        and reference
                        and self.instruments
                        and tick - self.stream_started > 300
                    ):
                        distance = min(
                            abs(item.strike - reference.last_price) for item in self.instruments
                        )
                        if distance > Decimal("200"):
                            self.stream.cancel()
                            await asyncio.gather(self.stream, return_exceptions=True)
                            self.stream = None
                            self.suspend_all("CONTRACT_WATCHLIST_RECENTERING", now)
                            continue
                    if self.cache.generation != self.last_generation:
                        self.last_generation = self.cache.generation
                        self.suspend_all("STREAM_GENERATION_CHANGED", now)
                    if tick - self.last_snapshot >= 2:
                        self.last_snapshot = tick
                        for name, market in self.markets.items():
                            self.store.write(f"analysis:{name}", market.context(now))
                            reference = self.cache.references.get(name)
                            if reference:
                                self.store.write(f"quote:{name}", reference.model_dump(mode="json"))
                        self.store.write(
                            "option_market",
                            {
                                "connected": self.cache.connected,
                                "generation": self.cache.generation,
                                "at": now.isoformat(),
                                "quotes": {
                                    key: value.model_dump(mode="json")
                                    for key, value in self.cache.quotes.items()
                                },
                                "noise": {key: self.noise_summary(key, now) for key in self.noise},
                            },
                        )
                        self.evaluate(now)
                        self.status = {
                            "status": "streaming" if self.cache.connected else "degraded",
                            "contracts": len(self.instruments),
                            "generation": self.cache.generation,
                        }
                    # Repair is asynchronous and bounded; it must not stall tick processing.
                    repair = next(
                        (task for task in tasks if task.get_name() == "repair" and not task.done()),
                        None,
                    )
                    if repair is None and tick - self.last_repair >= 60:

                        async def safe_repair():
                            try:
                                await self.repair(datetime.now(UTC), calendar)
                            except (ProviderError, ValueError, TimeoutError):
                                logger.warning("targeted_history_repair_unavailable")

                        tasks = [task for task in tasks if not task.done()]
                        tasks.append(asyncio.create_task(safe_repair(), name="repair"))
                if tick >= heartbeat_next:
                    heartbeat_next = tick + 5
                    self.store.write(
                        "worker",
                        {
                            **self.status,
                            "heartbeat": now.isoformat(),
                            "mode": "event-driven",
                            "background_model_polling": False,
                        },
                    )
                try:
                    await asyncio.wait_for(stop.wait(), 0.2 if opened and enabled else 5)
                except TimeoutError:
                    pass
        finally:
            if self.stream:
                self.stream.cancel()
                tasks.append(self.stream)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.client.close()
