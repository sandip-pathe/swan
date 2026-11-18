"""Conservative matching of real post-eligible depth against persistent paper orders."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from services.core.contracts import IST, Instrument, Quote, money
from services.core.execution import PaperExecutionConfig
from services.paper.accounting import ACTIVE
from services.paper.contracts import FillBooking
from services.paper.fees import fee_contexts, incremental_fees
from services.paper.liquidity import available_units, displayed_units, execution_price, level_budget
from services.paper.orders import DurableOrderLedger


def mapped_quote(quote: Quote, config: PaperExecutionConfig) -> Quote:
    """Apply verified feed-unit metadata; prices/quantities/times are never generated."""
    policy = config.execution
    if policy.blockers():
        raise ValueError("Reviewed execution policy required")
    if quote.quantity_unit != "unknown":
        if quote.quantity_unit != policy.quantity_unit:
            raise ValueError("Quote quantity metadata conflicts with policy")
        return quote
    payload = quote.model_dump(mode="json")
    payload.update(
        {
            "id": str(uuid5(quote.id, "quantity-mapping:" + config.version)),
            "quantity_unit": policy.quantity_unit,
            "quantity_unit_source": ";".join(str(s.url) for s in policy.quantity_unit_sources),
        }
    )
    return Quote.model_validate(payload)


class DepthMatcher:
    def __init__(self, engine: Engine, clock: Callable[[], datetime] | None = None):
        self.engine = engine
        self.clock = clock or (lambda: datetime.now(UTC))
        self.ledger = DurableOrderLedger(engine, self.clock)

    def match_order(
        self, account_id: UUID, order_id: UUID, instrument: Instrument, observed: Quote
    ) -> dict:
        with Session(self.engine) as db:
            order = DurableOrderLedger._order(db, account_id, order_id)
            config = PaperExecutionConfig.model_validate(order.execution_config)
        quote = mapped_quote(observed, config)
        prepared = self.ledger.prepare_match(account_id, order_id, instrument, quote, self.clock())
        if prepared["reason"] != "READY":
            return prepared
        try:
            fills, blocked = self._match_levels(
                account_id, order_id, instrument, quote, config, order.side
            )
        finally:
            self._finalize_ioc(account_id, order_id)
        with Session(self.engine) as db:
            result = DurableOrderLedger.view(DurableOrderLedger._order(db, account_id, order_id))
        return {**result, "reason": blocked, "matched_levels": fills}

    def _match_levels(
        self,
        account_id: UUID,
        order_id: UUID,
        instrument: Instrument,
        quote: Quote,
        config: PaperExecutionConfig,
        side: str,
    ) -> tuple[int, str]:
        assert quote.market_event_id is not None
        fills = 0
        blocked = "NO_EXECUTABLE_DEPTH"
        levels = quote.ask_depth if side == "BUY" else quote.bid_depth
        for level in levels:
            with Session(self.engine) as db:
                order = DurableOrderLedger._order(db, account_id, order_id)
                if order.status not in ACTIVE:
                    break
                assert order.accepted_at is not None
                previous = level_budget(
                    db,
                    account_id,
                    order.accepted_at.astimezone(IST).date(),
                    instrument,
                    order.side,
                    level.price,
                )
                if previous and previous.config_version != config.version:
                    raise ValueError("Execution model changed within a durable liquidity budget")
                units = displayed_units(level, quote, instrument)
                quantity = min(
                    order.quantity - order.filled_quantity,
                    available_units(previous, quote, units, config.execution),
                )
                if config.execution.partial_fill_granularity == "lots":
                    quantity = quantity // instrument.lot_size * instrument.lot_size
                if quantity <= 0:
                    continue
                adverse = config.execution.extra_adverse_slippage_bps
                assert adverse is not None
                price = execution_price(level.price, instrument.tick_size, order.side, adverse)
                if order.limit_price is not None and (
                    order.side == "BUY"
                    and price > order.limit_price
                    or order.side == "SELL"
                    and price < order.limit_price
                ):
                    blocked = "PRICE_BOUND_NOT_REACHED"
                    break  # Worse levels cannot satisfy this bound either.
                now = self.clock()
                schedule = next(
                    (
                        s
                        for s in config.fee_schedules
                        if s.exchange == instrument.exchange
                        and s.applies(now.astimezone(IST).date())
                    ),
                    None,
                )
                if schedule is None:
                    raise ValueError("Effective fee schedule missing")
                current, others = fee_contexts(db, order, schedule)
                if order.side == "BUY":
                    granularity = (
                        instrument.lot_size
                        if config.execution.partial_fill_granularity == "lots"
                        else 1
                    )
                    low, high = 0, quantity // granularity
                    while low < high:
                        middle = (low + high + 1) // 2
                        delta = money(price * middle * granularity)
                        additional = sum(
                            incremental_fees(schedule, current, delta, others).values(), Decimal(0)
                        )
                        if (
                            current.premium
                            + sum(current.booked.values(), Decimal(0))
                            + delta
                            + additional
                            <= order.cash_budget
                        ):
                            low = middle
                        else:
                            high = middle - 1
                    quantity = low * granularity
                    if not quantity:
                        blocked = "REMAINING_CASH_BUDGET_TOO_SMALL"
                        break
                parts = incremental_fees(schedule, current, money(price * quantity), others)
                event_key = str(uuid5(order.id, f"{quote.market_event_id}:{level.price}"))
                booking = FillBooking(
                    event_key=event_key,
                    snapshot_id=quote.id,
                    market_event_id=quote.market_event_id,
                    quantity=quantity,
                    price=price,
                    raw_price=level.price,
                    fees=sum(parts.values(), Decimal(0)),
                    fee_breakdown=parts,
                    cost_version=schedule.version,
                )
            # The ledger recomputes fees/capacity under the account lock; stale proposals fail.
            booked = self.ledger.book_fill(account_id, order_id, booking, self.clock())
            if not booked.get("duplicate"):
                fills += 1
                blocked = "MATCHED"
                if side == "BUY":
                    break  # Yield immediately so the coordinator protects the first held units.
        return fills, blocked

    def _finalize_ioc(self, account_id: UUID, order_id: UUID) -> None:
        with Session(self.engine) as db:
            order = DurableOrderLedger._order(db, account_id, order_id)
            ioc = order.time_in_force == "IOC" and order.status in ACTIVE
        if ioc:
            self.ledger.cancel(account_id, order_id, "ioc-request:" + str(order_id), self.clock())
            self.ledger.cancel(
                account_id, order_id, "ioc-ack:" + str(order_id), self.clock(), confirm=True
            )
