"""Read-only portfolio display, sharing execution's conservative valuation model."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import IST, Quote, RiskConfig, money
from services.core.models import (
    Account,
    InstrumentRecord,
    LedgerEntry,
    PaperFill,
    PaperOrder,
    PaperPosition,
)
from services.paper.accounting import ACTIVE, reconcile_account
from services.paper.portfolio import portfolio_snapshot
from services.worker.models import LatestMarketQuote

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ExposureBucket:
    instrument_id: str
    open_quantity: int = 0
    entry_cost_basis: Decimal = Decimal(0)
    planned_stop_risk: Decimal = Decimal(0)
    pending_quantity: int = 0
    pending_limit_notional: Decimal = Decimal(0)
    pending_limit_orders: int = 0
    pending_order_count: int = 0
    pending_reserved_risk: Decimal = Decimal(0)


@router.get("/api/paper/portfolio")
def portfolio(request: Request, owner: UUID = Depends(account_identity)):
    with Session(request.app.state.engine) as db:
        # This display grants no permission; snapshot isolation avoids mixing ledger states.
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        account = db.get(Account, owner)
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        now = utc_now()
        held = select(PaperPosition.instrument_id).where(
            PaperPosition.account_id == owner, PaperPosition.closed_at.is_(None)
        )
        positions = db.scalar(
            select(func.count())
            .select_from(PaperPosition)
            .where(PaperPosition.account_id == owner, PaperPosition.closed_at.is_(None))
        )
        status, reason, snapshot = "UNAVAILABLE", "VALUATION_UNAVAILABLE", None
        try:
            quotes = {
                row.instrument_id: Quote.model_validate(row.payload)
                for row in db.scalars(
                    select(LatestMarketQuote).where(LatestMarketQuote.instrument_id.in_(held))
                )
            }
            snapshot = portfolio_snapshot(db, account, quotes, now)
            if not snapshot.state.reconciled:
                status, reason = "UNRECONCILED", "ACCOUNT_RECONCILIATION_REQUIRED"
            elif snapshot.state.valuation_fresh:
                status, reason = (
                    ("FRESH", "BID_DEPTH_ESTIMATE") if positions else ("FLAT", "NO_OPEN_POSITIONS")
                )
            elif snapshot.valid_until is not None and now >= snapshot.valid_until:
                status, reason = "STALE", "VALUATION_QUOTES_STALE"
            else:
                status, reason = "UNAVAILABLE", "VALUATION_DEPTH_OR_POLICY_UNAVAILABLE"
        except (ValueError, KeyError, TypeError, AssertionError):
            # Never return raw configuration/quote parsing errors or placeholder equity.
            if reconcile_account(db, account):
                status, reason = "UNRECONCILED", "ACCOUNT_RECONCILIATION_REQUIRED"
        reconciled = status != "UNRECONCILED"
        valued = status in {"FRESH", "FLAT"} and snapshot is not None
        capital, capital_records = db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0), func.count()).where(
                LedgerEntry.account_id == owner, LedgerEntry.category == "CAPITAL"
            )
        ).one()
        realized = db.scalar(
            select(func.coalesce(func.sum(PaperPosition.realized_pnl), 0)).where(
                PaperPosition.account_id == owner
            )
        ) or Decimal(0)
        # Keep cost-basis exposure explicitly separate from the liquidation
        # estimate above. It remains useful when quotes are stale, but it must
        # never be presented as current market value.
        open_positions = list(
            db.scalars(
                select(PaperPosition)
                .where(PaperPosition.account_id == owner, PaperPosition.closed_at.is_(None))
                .order_by(PaperPosition.instrument_id, PaperPosition.opened_at, PaperPosition.id)
            )
        )
        pending_entries = list(
            db.scalars(
                select(PaperOrder)
                .where(
                    PaperOrder.account_id == owner,
                    PaperOrder.side == "BUY",
                    PaperOrder.status.in_(ACTIVE),
                )
                .order_by(PaperOrder.instrument_id, PaperOrder.timestamp, PaperOrder.id)
            )
        )
        exposure_by_instrument: dict[str, ExposureBucket] = {}
        for position in open_positions:
            remaining = position.quantity - position.closed_quantity
            if remaining <= 0:
                continue
            item = exposure_by_instrument.setdefault(
                position.instrument_id, ExposureBucket(position.instrument_id)
            )
            item.open_quantity += remaining
            item.entry_cost_basis += money(position.average_price * remaining)
            item.planned_stop_risk += money(position.planned_risk)
        for order in pending_entries:
            remaining = order.quantity - order.filled_quantity
            if remaining <= 0:
                continue
            item = exposure_by_instrument.setdefault(
                order.instrument_id, ExposureBucket(order.instrument_id)
            )
            item.pending_quantity += remaining
            item.pending_order_count += 1
            item.pending_reserved_risk += money(order.reserved_risk)
            if order.limit_price is not None:
                item.pending_limit_notional += money(order.limit_price * remaining)
                item.pending_limit_orders += 1
        exposure = None
        if reconciled:
            exposure = [
                {
                    "instrument_id": item.instrument_id,
                    "open_quantity": item.open_quantity,
                    "entry_cost_basis": str(money(item.entry_cost_basis)),
                    "planned_stop_risk": str(money(item.planned_stop_risk)),
                    "pending_quantity": item.pending_quantity,
                    "pending_limit_notional": (
                        str(money(item.pending_limit_notional))
                        if item.pending_limit_orders == item.pending_order_count
                        else None
                    ),
                    "pending_order_count": item.pending_order_count,
                    "pending_limit_orders": item.pending_limit_orders,
                    "pending_reserved_risk": str(money(item.pending_reserved_risk)),
                }
                for item in sorted(exposure_by_instrument.values(), key=lambda row: row.instrument_id)
            ]
        fees = db.scalar(
            select(func.coalesce(func.sum(PaperFill.fees), 0))
            .join(PaperOrder, PaperOrder.id == PaperFill.order_id)
            .where(PaperOrder.account_id == owner)
        ) or Decimal(0)
        trades = db.execute(
            select(PaperPosition.opened_at, PaperPosition.closed_at, PaperPosition.realized_pnl)
            .where(
                PaperPosition.account_id == owner,
                PaperPosition.closed_at.is_not(None),
            )
            .order_by(PaperPosition.closed_at, PaperPosition.id)
        ).yield_per(500)
        trade_count = wins = losses = 0
        win_total = loss_total = net_total = cumulative = peak = max_drawdown = Decimal(0)
        holding_seconds = 0.0
        for opened_at, closed_at, pnl in trades:
            if closed_at is None:
                continue
            value = pnl or Decimal(0)
            trade_count += 1
            net_total += value
            cumulative += value
            peak = max(peak, cumulative)
            max_drawdown = max(max_drawdown, peak - cumulative)
            if value > 0:
                wins += 1
                win_total += value
            elif value < 0:
                losses += 1
                loss_total += value
            holding_seconds += max(0.0, (closed_at - opened_at).total_seconds())
        trade_statistics = {
            "closed_positions": trade_count,
            "win_rate": str((Decimal(wins) / trade_count).quantize(Decimal("0.0001")))
            if trade_count
            else None,
            "average_win": str(money(win_total / wins)) if wins else None,
            "average_loss": str(money(loss_total / losses)) if losses else None,
            "expectancy": str(money(net_total / trade_count)) if trade_count else None,
            "profit_factor": str((win_total / abs(loss_total)).quantize(Decimal("0.0001")))
            if losses
            else None,
            "realized_drawdown": str(money(max_drawdown)) if trade_count else None,
            "average_holding_seconds": round(holding_seconds / trade_count)
            if trade_count
            else None,
        }
        equity = snapshot.state.equity if valued and snapshot else None
        total = money(equity - capital) if equity is not None and capital_records else None
        session_opening_equity = account.session_opening_equity
        session_current = (
            account.session_key == now.astimezone(IST).date()
            and session_opening_equity is not None
        )
        risk_headroom = None
        if (
            valued
            and snapshot
            and session_current
            and session_opening_equity is not None
        ):
            try:
                risk_config = RiskConfig.model_validate(account.config)
                assert equity is not None
                loss_limit = money(session_opening_equity * risk_config.max_daily_loss_pct)
                loss_used = max(Decimal(0), money(session_opening_equity - equity))
                allocated = money(snapshot.state.reserved_risk)
                risk_headroom = {
                    "loss_limit": str(loss_limit),
                    "loss_used": str(loss_used),
                    "allocated_risk": str(allocated),
                    "remaining": str(max(Decimal(0), money(loss_limit - loss_used - allocated))),
                    "blocked": account.daily_blocked,
                }
            except ValueError:
                risk_headroom = None
        fee_bases = set()
        for execution, instrument in db.execute(
            select(PaperOrder.execution_config, InstrumentRecord.payload)
            .join(InstrumentRecord, InstrumentRecord.id == PaperOrder.instrument_id)
            .where(PaperOrder.account_id == owner, PaperOrder.filled_quantity > 0)
        ):
            if not isinstance(execution, dict) or not execution:
                fee_bases.add("legacy")
                continue
            if not isinstance(instrument, dict):
                fee_bases.add("unknown")
                continue
            for schedule in execution.get("fee_schedules", []):
                if schedule.get("exchange") == instrument.get("exchange"):
                    fee_bases.add(schedule.get("calculation_basis", "documented"))
        return {
            "as_of": now.isoformat(),
            "status": status,
            "reason": reason,
            "reconciled": reconciled,
            "open_positions": positions,
            "valid_until": snapshot.valid_until.isoformat()
            if valued and snapshot and snapshot.valid_until
            else None,
            "oldest_quote_at": min(q.timestamp for q in snapshot.evidence).isoformat()
            if snapshot and snapshot.evidence
            else None,
            "cash_balance": str(account.cash) if reconciled else None,
            "available_cash": str(snapshot.state.cash) if reconciled and snapshot else None,
            "equity": str(equity) if equity is not None else None,
            "open_position_value": str(money(equity - account.cash))
            if equity is not None
            else None,
            "realized_pnl": str(money(realized)) if reconciled else None,
            "unrealized_pnl": str(money(total - realized)) if total is not None else None,
            "total_pnl": str(total) if total is not None else None,
            "session_pnl": str(money(equity - session_opening_equity))
            if equity is not None and session_current and session_opening_equity is not None
            else None,
            "session_date": account.session_key.isoformat()
            if session_current and account.session_key is not None
            else None,
            "fees": str(money(fees)) if reconciled else None,
            "fee_basis": next(iter(fee_bases)) if len(fee_bases) == 1 else (
                "mixed" if fee_bases else "no_fills"
            ),
            "trade_statistics": trade_statistics,
            "risk_headroom": risk_headroom,
            "exposure": exposure,
        }
