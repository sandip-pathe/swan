"""TLS-verified SnapQuote stream; bounded cache and reconnect invalidation."""

import asyncio
import json
import random
import ssl
import struct
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Awaitable, Callable
from uuid import UUID, uuid4

from pydantic import ValidationError
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from services.core.contracts import DepthLevel, Instrument, Quote
from services.market.angelone import AngelOneClient
from services.market.catalog import EXCHANGE_TYPES
from services.market.evidence import identify_quote
from services.market.settings import AuthenticationRequired, ProviderError

STREAM_URL = "wss://smartapisocket.angelone.in/smart-stream"


class QuoteCache:
    def __init__(self):
        self.quotes: dict[str, Quote] = {}
        self.connected = False
        self.generation = 0
        self.last_tick_monotonic: float | None = None
        self.changed = asyncio.Event()
        self.problem: str | None = "NOT_CONNECTED"
        self.history: dict[str, deque] = {}
        self.rejected: dict[str, str] = {}
        self.source_quotes: dict[tuple[str, str], Quote] = {}

    def invalidate(self, problem: str) -> None:
        self.quotes.clear()
        self.history.clear()
        self.rejected.clear()
        self.source_quotes.clear()
        self.connected = False
        self.generation += 1
        self.problem = problem
        self.changed.set()

    def update(self, quote: Quote) -> None:
        previous = self.quotes.get(quote.instrument_id)
        if (
            quote.timestamp > quote.received_at
            or quote.bid is not None
            and quote.ask is not None
            and quote.bid > quote.ask
        ):
            self.quotes.pop(quote.instrument_id, None)
            self.history.pop(quote.instrument_id, None)
            self.rejected[quote.instrument_id] = "INVALID_QUOTE_TIME_OR_CROSSED_BOOK"
            self.changed.set()
            return
        if previous and previous.timestamp > quote.timestamp:
            self.rejected[quote.instrument_id] = "OUT_OF_ORDER_OBSERVATION"
            return
        source_previous = self.source_quotes.get((quote.instrument_id, quote.source))
        if source_previous:
            if quote.market_event_id and quote.market_event_id == source_previous.market_event_id:
                self.rejected[quote.instrument_id] = "DUPLICATE_OBSERVATION"
                return
            if (
                quote.stream_id is not None
                and quote.stream_id == source_previous.stream_id
                and quote.sequence is not None
                and source_previous.sequence is not None
                and quote.sequence <= source_previous.sequence
            ):
                self.rejected[quote.instrument_id] = "NONADVANCING_SEQUENCE"
                return
        self.rejected.pop(quote.instrument_id, None)
        self.source_quotes[(quote.instrument_id, quote.source)] = quote
        self.quotes[quote.instrument_id] = quote
        if (
            quote.bid is not None
            and quote.ask is not None
            and quote.bid <= quote.ask
            and quote.timestamp <= quote.received_at
        ):
            history = self.history.setdefault(quote.instrument_id, deque(maxlen=400))
            if not history or history[-1][0] < quote.timestamp:
                history.append((quote.timestamp, (quote.bid + quote.ask) / 2))
            while history and quote.timestamp - history[0][0] > timedelta(seconds=180):
                history.popleft()
        self.last_tick_monotonic = time.monotonic()
        self.changed.set()


def decode_quote(
    packet: bytes,
    instruments: dict[tuple[int, str], Instrument],
    received_at: datetime,
    stream_id: UUID | None = None,
) -> Quote | None:
    if len(packet) < 379 or packet[0] != 3:
        raise ProviderError("INVALID_SNAPQUOTE_PACKET")
    token = packet[2:27].split(b"\0", 1)[0].decode("ascii")
    instrument = instruments.get((packet[1], token))
    if instrument is None:
        return None
    milliseconds = struct.unpack_from("<q", packet, 35)[0]
    timestamp = datetime.fromtimestamp(milliseconds // 1000, UTC) + timedelta(
        milliseconds=milliseconds % 1000
    )
    sequence = struct.unpack_from("<q", packet, 27)[0]
    if sequence < 0:
        raise ProviderError("INVALID_QUOTE_SEQUENCE")
    bids: list[DepthLevel] = []
    asks: list[DepthLevel] = []
    for offset in range(147, 347, 20):
        side, quantity, paise, orders = struct.unpack_from("<HqqH", packet, offset)
        if side not in (0, 1) or quantity < 0 or paise < 0 or paise == 0 and quantity > 0:
            raise ProviderError("INVALID_DEPTH_LEVEL")
        if paise > 0 and quantity > 0:
            (bids if side == 1 else asks).append(
                DepthLevel(price=Decimal(paise) / 100, quantity=quantity, orders=orders)
            )
    bids.sort(key=lambda level: level.price, reverse=True)
    asks.sort(key=lambda level: level.price)
    bid = bids[0] if bids else None
    ask = asks[0] if asks else None
    volume = struct.unpack_from("<q", packet, 67)[0]
    oi = struct.unpack_from("<q", packet, 131)[0]

    def price(offset: int) -> Decimal | None:
        value = struct.unpack_from("<q", packet, offset)[0]
        return Decimal(value) / 100 if value > 0 else None

    last_quantity = struct.unpack_from("<q", packet, 51)[0]
    return identify_quote(
        Quote(
            instrument_id=instrument.id,
            timestamp=timestamp,
            received_at=received_at,
            source="angelone-websocket-v2:snapquote",
            sequence=sequence,
            stream_id=stream_id,
            timestamp_basis="exchange_feed",
            bid_depth=tuple(bids),
            ask_depth=tuple(asks),
            depth_kind="best_five",
            bid=bid.price if bid else None,
            bid_quantity=bid.quantity if bid else None,
            ask=ask.price if ask else None,
            ask_quantity=ask.quantity if ask else None,
            last_price=price(43),
            last_trade_quantity=last_quantity if last_quantity >= 0 else None,
            average_price=price(59),
            session_open=price(91),
            session_high=price(99),
            session_low=price(107),
            previous_close=price(115),
            volume=volume if volume >= 0 else None,
            oi=oi if oi >= 0 else None,
        )
    )


class AngelOneStream:
    def __init__(
        self,
        client: AngelOneClient,
        cache: QuoteCache,
        on_observation: Callable[[Quote], None] | None = None,
    ):
        self.client = client
        self.cache = cache
        self.on_observation = on_observation

    async def run(
        self, instruments: list[Instrument], on_problem: Callable[[str], Awaitable[None]]
    ) -> None:
        lookup = {
            (EXCHANGE_TYPES[item.exchange], item.provider_token): item for item in instruments
        }
        groups = defaultdict(list)
        for exchange, token in lookup:
            groups[exchange].append(token)
        tokens = [
            {"exchangeType": exchange, "tokens": values} for exchange, values in groups.items()
        ]
        failures = 0
        while True:
            self.cache.invalidate("CONNECTING")
            try:
                session = await self.client.session()
                headers = {
                    "Authorization": session.jwt.get_secret_value(),
                    "x-api-key": self.client.settings.api_key.get_secret_value(),
                    "x-client-code": self.client.settings.client_code.get_secret_value(),
                    "x-feed-token": session.feed.get_secret_value(),
                }
                async with connect(
                    STREAM_URL,
                    additional_headers=headers,
                    ssl=ssl.create_default_context(),
                    open_timeout=15,
                    close_timeout=5,
                    max_queue=16,
                    max_size=65536,
                    ping_interval=None,
                ) as websocket:
                    stream_id = uuid4()
                    await websocket.send(
                        json.dumps(
                            {
                                "correlationID": "swanquote1",
                                "action": 1,
                                "params": {"mode": 3, "tokenList": tokens},
                            }
                        )
                    )
                    self.cache.connected = True
                    self.cache.problem = None

                    async def heartbeat():
                        while True:
                            await websocket.send("ping")
                            await asyncio.sleep(10)

                    task = asyncio.create_task(heartbeat())
                    try:
                        while True:
                            if session.expires_at <= datetime.now(UTC) + timedelta(seconds=30):
                                raise AuthenticationRequired("STREAM_TOKEN_RENEWAL")
                            packet = await asyncio.wait_for(websocket.recv(), timeout=25)
                            if packet in ("pong", b"pong"):
                                continue
                            if not isinstance(packet, bytes):
                                raise ProviderError("STREAM_SUBSCRIPTION_REJECTED")
                            quote = decode_quote(packet, lookup, datetime.now(UTC), stream_id)
                            if quote:
                                if self.on_observation:
                                    self.on_observation(quote)
                                self.cache.update(quote)
                                failures = 0
                    finally:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
            except asyncio.CancelledError:
                self.cache.invalidate("STOPPED")
                raise
            except (
                OSError,
                TimeoutError,
                WebSocketException,
                ProviderError,
                ValidationError,
                ValueError,
                struct.error,
            ):
                self.cache.invalidate("STREAM_UNAVAILABLE")
                await on_problem("STREAM_UNAVAILABLE")
                failures = min(failures + 1, 6)
                await asyncio.sleep(min(60, 2**failures) + random.random())
