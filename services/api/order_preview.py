"""Read-only manual BUY LIMIT calculations. Never an order or risk approval."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import IST, Instrument, Quote, RiskConfig, money
from services.core.execution import PaperExecutionConfig
from services.core.models import (
    Account,
    InstrumentRecord,
    ListedInstrument,
    PaperLiquidityLevel,
    PaperPosition,
)
from services.market.calendar import SessionCalendar
from services.market.settings import MarketSettings
from services.paper.liquidity import buy_capacity, execution_price
from services.paper.matching import mapped_quote
from services.paper.portfolio import portfolio_snapshot
from services.paper.risk import fee_ceiling
from services.paper.settings import DEFAULT_CONFIG
from services.risk.engine import quote_problem
from services.worker.models import LatestMarketQuote

router = APIRouter()
PriceInput = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class ManualPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument_id: str = Field(min_length=1, max_length=100)
    lots: int = Field(ge=1, le=1000, strict=True)
    entry: PriceInput
    stop_loss: PriceInput
    target: PriceInput

    @model_validator(mode="after")
    def valid_prices(self) -> Self:
        if not self.stop_loss < self.entry < self.target:
            raise ValueError("Stop must be below limit price and target above it")
        return self


def load_execution() -> PaperExecutionConfig:
    return PaperExecutionConfig.model_validate_json(DEFAULT_CONFIG.read_text(encoding="utf-8"))


def load_session(exchange: str, now: datetime):
    return SessionCalendar(MarketSettings().calendar_file, strict=False).get(
        exchange, now.astimezone(IST).date()
    )


@router.post("/api/paper/orders/preview")
def preview(body: ManualPreview, request: Request, identifier: UUID = Depends(account_identity)):
    now = datetime.now(UTC)
    with Session(request.app.state.engine) as db, db.begin():
        # A coherent preview cannot reserve funds or write approval/evidence by accident.
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        account = db.get(Account, identifier)
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        return calculate_preview(body, db, account, now)


def calculate_preview(body: ManualPreview, db: Session, account: Account, now: datetime):
    identifier = account.id
    record = db.get(InstrumentRecord, body.instrument_id)
    if record is None:
        raise HTTPException(404, "INSTRUMENT_NOT_SAVED")
    instrument = Instrument.model_validate(record.payload)
    if any(price % instrument.tick_size for price in (body.entry, body.stop_loss, body.target)):
        raise HTTPException(422, "ORDER_PRICES_OFF_TICK")
    config = RiskConfig.model_validate(account.config)
    quantity = body.lots * instrument.lot_size
    premium = money(body.entry * quantity)
    gross_loss = money((body.entry - body.stop_loss) * quantity)
    gross_gain = money((body.target - body.entry) * quantity)
    checks = []

    def check(code: str, label: str, passed: bool):
        checks.append({"code": code, "label": label, "status": "passed" if passed else "blocked"})

    today = now.astimezone(IST).date()
    listing = db.get(ListedInstrument, instrument.id)
    latest = db.scalar(select(func.max(ListedInstrument.catalog_at)))
    metadata_ok = (
        listing is not None
        and listing.catalog_at == latest
        and listing.catalog_at.astimezone(IST).date() == today
        and {k: v for k, v in listing.payload.items() if k != "verified_at"}
        == {k: v for k, v in record.payload.items() if k != "verified_at"}
    )
    check("CONTRACT", "Current listed contract", metadata_ok and instrument.expiry >= today)
    observed = db.get(LatestMarketQuote, instrument.id)
    quote = Quote.model_validate(observed.payload) if observed else None
    check(
        "QUOTE",
        "Fresh bid and ask",
        quote_problem(quote, now, config.quote_max_age_seconds) is None,
    )
    check(
        "LIQUIDITY",
        "Volume, open interest and spread meet policy",
        quote is not None
        and quote.volume is not None
        and quote.oi is not None
        and quote.volume >= config.min_volume
        and quote.oi >= config.min_oi
        and quote.bid is not None
        and quote.ask is not None
        and 0 < quote.bid <= quote.ask
        and (quote.ask - quote.bid) / ((quote.ask + quote.bid) / 2) * 10000
        <= config.max_spread_bps,
    )
    try:
        session = load_session(instrument.exchange, now)
    except (OSError, ValueError):
        session = None
    check(
        "SESSION",
        "Verified session before entry cutoff",
        session is not None
        and session.verified
        and session.opens_at
        <= now
        < session.closes_at - timedelta(minutes=config.entry_cutoff_minutes),
    )
    held = select(PaperPosition.instrument_id).where(
        PaperPosition.account_id == identifier, PaperPosition.closed_at.is_(None)
    )
    quotes = {
        row.instrument_id: Quote.model_validate(row.payload)
        for row in db.scalars(
            select(LatestMarketQuote).where(LatestMarketQuote.instrument_id.in_(held))
        )
    }
    snapshot = portfolio_snapshot(db, account, quotes, now)
    state = snapshot.state
    check(
        "ACCOUNT",
        "Account reconciles with current valuations",
        state.reconciled and state.valuation_fresh,
    )
    check("POSITIONS", "Position capacity available", state.open_positions < config.max_positions)
    check("ENTRY_MODE", "Automated entries are paused", not account.enabled)
    execution = None
    try:
        execution = load_execution()
    except (OSError, ValueError):
        pass
    check(
        "EXECUTION",
        "Simulation settings reviewed",
        execution is not None and not execution.execution.blockers(),
    )
    depth_ok = False
    capacity = None
    if execution is not None and quote is not None:
        try:
            mapped = mapped_quote(quote, execution)
            depth_ok = (
                not execution.execution.blockers()
                and mapped.instrument_id == instrument.id
                and quote_problem(mapped, now, config.quote_max_age_seconds) is None
                and mapped.depth_kind == "best_five"
                and bool(mapped.ask_depth)
                and mapped.timestamp_basis == "exchange_feed"
                and bool(mapped.market_event_id)
                and (now - mapped.timestamp).total_seconds() * 1000
                <= (execution.execution.quote_max_age_ms or 0)
            )
            if depth_ok:
                budgets = {
                    row.price: row
                    for row in db.scalars(
                        select(PaperLiquidityLevel).where(
                            PaperLiquidityLevel.account_id == identifier,
                            PaperLiquidityLevel.session_key == today,
                            PaperLiquidityLevel.instrument_id == instrument.id,
                            PaperLiquidityLevel.side == "BUY",
                        )
                    )
                }
                capacity = buy_capacity(
                    mapped,
                    instrument,
                    execution,
                    identifier,
                    today,
                    budgets,
                    minimum=instrument.tick_size,
                    limit=body.entry,
                )
        except ValueError:
            pass
    check("DEPTH", "Depth quantities and quote source verified", depth_ok)
    check(
        "DEPTH_CAPACITY",
        "Usable depth at your limit covers requested lots",
        capacity is not None and quantity <= capacity,
    )
    check("QUANTITY", "Requested quantity meets order limit", quantity <= config.max_fill_quantity)
    schedule = (
        next(
            (
                s
                for s in execution.fee_schedules
                if s.exchange == instrument.exchange and s.applies(today) and s.reviewed
            ),
            None,
        )
        if execution
        else None
    )
    check("FEES", "Effective fee schedule reviewed", schedule is not None)
    entry_fees = fee_ceiling(schedule, "BUY", premium) if schedule else None
    planned_stop = planned_loss = stop_fees = cash_required = None
    if entry_fees is not None:
        cash_required = money(premium + entry_fees)
    if schedule and execution and not execution.execution.blockers():
        assert execution.execution.extra_adverse_slippage_bps is not None
        assert entry_fees is not None
        try:
            planned_stop = execution_price(
                body.stop_loss,
                instrument.tick_size,
                "SELL",
                execution.execution.extra_adverse_slippage_bps,
            )
            stop_fees = fee_ceiling(schedule, "SELL", planned_stop * quantity)
            planned_loss = money((body.entry - planned_stop) * quantity + entry_fees + stop_fees)
        except ValueError:
            planned_stop = None
    budget = None
    if (
        state.reconciled
        and state.valuation_fresh
        and state.session_matches
        and state.session_opening_equity > 0
    ):
        headroom = (
            state.session_opening_equity * config.max_daily_loss_pct
            - max(Decimal(0), state.session_opening_equity - state.equity)
            - state.reserved_risk
        )
        budget = max(
            Decimal(0),
            min(min(config.capital, state.equity) * config.max_trade_risk_pct, headroom),
        )
    check(
        "CASH",
        "Cash covers premium and fee allowance",
        cash_required is not None and state.reconciled and cash_required <= state.cash,
    )
    check(
        "RISK",
        "Planned stop loss fits remaining risk budget",
        planned_loss is not None
        and budget is not None
        and not state.daily_blocked
        and planned_loss <= budget,
    )
    check("MANUAL_SUBMISSION", "Order placement is unavailable in this preview", False)

    def amount(value):
        return str(money(value)) if value is not None else None

    return {
        "kind": "manual_buy_limit_preview",
        "submission_ready": False,
        "provider_called": False,
        "as_of": now.isoformat(),
        "expires_at": (now + timedelta(seconds=10)).isoformat(),
        "account_revision": account.revision,
        "instrument_id": instrument.id,
        "side": "BUY",
        "order_type": "LIMIT",
        "lots": body.lots,
        "quantity": quantity,
        "lot_size": instrument.lot_size,
        "available_depth_quantity": capacity,
        "available_depth_lots": capacity // instrument.lot_size if capacity is not None else None,
        "entry": str(body.entry),
        "stop_loss": str(body.stop_loss),
        "target": str(body.target),
        "premium": amount(premium),
        "gross_stop_loss": amount(gross_loss),
        "gross_target_gain": amount(gross_gain),
        "entry_fee_allowance": amount(entry_fees),
        "stop_exit_fee_allowance": amount(stop_fees),
        "cash_required": amount(cash_required),
        "available_cash": amount(state.cash) if state.reconciled else None,
        "planned_stop_price": amount(planned_stop),
        "planned_stop_loss": amount(planned_loss),
        "remaining_risk_budget": amount(budget),
        "fee_schedule_version": schedule.version if schedule else None,
        "execution_version": execution.version if execution else None,
        "quote_at": quote.timestamp.isoformat() if quote else None,
        "checks": checks,
    }
