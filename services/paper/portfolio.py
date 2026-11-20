"""Locked account snapshots for durable entry risk and protective monitoring."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.contracts import IST, Instrument, Quote, money
from services.core.execution import PaperExecutionConfig
from services.core.models import (
    Account,
    InstrumentRecord,
    PaperLiquidityLevel,
    PaperOrder,
    PaperPosition,
)
from services.paper.accounting import (
    ACTIVE,
    LEGACY,
    reconcile_account,
    reservations,
    restricted_proceeds,
)
from services.paper.fees import fee_contexts
from services.paper.matching import mapped_quote
from services.paper.valuation import liquidation_estimate
from services.risk.engine import PortfolioState


@dataclass(frozen=True)
class AccountSnapshot:
    state: PortfolioState
    evidence: tuple[Quote, ...]
    problems: tuple[str, ...]
    valid_until: datetime | None


def portfolio_snapshot(
    db: Session, account: Account, quotes: dict[str, Quote], now: datetime
) -> AccountSnapshot:
    """Admission holds the account lock; displays use a consistent read snapshot.

    No incomplete subtotal becomes equity.
    """
    positions = list(
        db.scalars(
            select(PaperPosition).where(
                PaperPosition.account_id == account.id, PaperPosition.closed_at.is_(None)
            )
        )
    )
    pending = list(
        db.scalars(
            select(PaperOrder).where(
                PaperOrder.account_id == account.id,
                PaperOrder.side == "BUY",
                PaperOrder.status.in_(ACTIVE),
            )
        )
    )
    cash, risk, _ = reservations(db, account.id)
    problems = list(reconcile_account(db, account))
    reconciled = not problems
    valid_until = None
    equity, evidence = account.cash, []
    complete = True
    for position in positions:
        entry = db.get(PaperOrder, position.entry_order_id)
        record = db.get(InstrumentRecord, position.instrument_id)
        observed = quotes.get(position.instrument_id)
        if entry is None or entry.execution_version == LEGACY or record is None or observed is None:
            complete = False
            problems.append("POSITION_VALUATION_UNAVAILABLE")
            continue
        instrument = Instrument.model_validate(record.payload)
        execution = PaperExecutionConfig.model_validate(entry.execution_config)
        try:
            quote = mapped_quote(observed, execution)
            age = execution.execution.quote_max_age_ms
            assert age is not None
            expiry = quote.timestamp + timedelta(milliseconds=age)
            valid_until = min(valid_until, expiry) if valid_until is not None else expiry
            schedule = next(
                (
                    s
                    for s in execution.fee_schedules
                    if s.exchange == instrument.exchange and s.applies(now.astimezone(IST).date())
                ),
                None,
            )
            if schedule is None:
                raise ValueError("Effective fee schedule unavailable")
            levels = list(
                db.scalars(
                    select(PaperLiquidityLevel).where(
                        PaperLiquidityLevel.account_id == account.id,
                        PaperLiquidityLevel.session_key == now.astimezone(IST).date(),
                        PaperLiquidityLevel.instrument_id == instrument.id,
                        PaperLiquidityLevel.side == "SELL",
                    )
                )
            )
            current, others = fee_contexts(db, entry, schedule)
            estimate = liquidation_estimate(
                instrument,
                quote,
                position.quantity - position.closed_quantity,
                execution.execution,
                schedule,
                now,
                configuration_version=execution.version,
                budgets={level.price: level for level in levels},
                fee_context=(current, *others),
            )
            evidence.append(quote)
            if estimate.net_value is None:
                complete = False
                problems.append(estimate.reason)
            else:
                equity += estimate.net_value
        except ValueError:
            complete = False
            problems.append("POSITION_VALUATION_POLICY_UNAVAILABLE")
    occupied = len(positions) + sum(
        order.id not in {p.entry_order_id for p in positions} for order in pending
    )
    return AccountSnapshot(
        PortfolioState(
            cash=money(account.cash - cash - restricted_proceeds(db, account.id)),
            # This placeholder is never actionable when valuation_fresh is false.
            equity=money(equity) if complete else Decimal(0),
            session_opening_equity=account.session_opening_equity or Decimal(0),
            open_positions=occupied,
            reserved_risk=risk + sum((p.planned_risk for p in positions), Decimal(0)),
            enabled=account.enabled,
            daily_blocked=account.daily_blocked,
            reconciled=reconciled,
            valuation_fresh=complete,
            session_matches=account.session_key == now.astimezone(IST).date(),
        ),
        tuple(evidence),
        tuple(problems),
        valid_until,
    )
