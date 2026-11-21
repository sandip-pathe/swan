"""Read-only portfolio display, sharing execution's conservative valuation model."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import IST, Quote, RiskConfig, money
from services.core.models import Account, LedgerEntry, PaperFill, PaperOrder, PaperPosition
from services.paper.accounting import reconcile_account
from services.paper.portfolio import portfolio_snapshot
from services.worker.models import LatestMarketQuote

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(UTC)


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
        session_current = (
            account.session_key == now.astimezone(IST).date()
            and account.session_opening_equity is not None
        )
        risk_headroom = None
        if valued and snapshot and session_current and account.session_opening_equity:
            try:
                risk_config = RiskConfig.model_validate(account.config)
                loss_limit = money(account.session_opening_equity * risk_config.max_daily_loss_pct)
                loss_used = max(Decimal(0), money(account.session_opening_equity - equity))
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
            "session_pnl": str(money(equity - account.session_opening_equity))
            if equity is not None and session_current and account.session_opening_equity is not None
            else None,
            "session_date": account.session_key.isoformat()
            if session_current and account.session_key is not None
            else None,
            "fees": str(money(fees)) if reconciled else None,
            "trade_statistics": trade_statistics,
            "risk_headroom": risk_headroom,
        }
