import csv
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from services.api.auth import account_identity, settings
from services.api.candles import router as candle_router
from services.api.history import router as history_router
from services.api.market import router as market_router
from services.api.paper_control import router as paper_control_router
from services.api.setup import router as setup_router
from services.api.validation import router as validation_router
from services.core.contracts import RiskConfig
from services.core.database import make_engine
from services.core.models import (
    Account,
    AuditEvent,
    DecisionRecord,
    InstrumentRecord,
    LedgerEntry,
    PaperFill,
    PaperFundsHold,
    PaperOrder,
    PaperOrderEvent,
    PaperPosition,
)
from services.market.diagnostics import evidence_context
from services.market.readiness import readiness
from services.paper.accounting import ACTIVE, reservations, restricted_proceeds
from services.paper.qualification import qualification_context
from services.worker.models import EvaluationSlot, LatestMarketQuote, RuntimeControl


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = make_engine(
        connect_args={"options": "-clock_timeout=5000 -cstatement_timeout=15000"}
    )
    yield
    app.state.engine.dispose()


app = FastAPI(
    title="SWAN Trade", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
)
app.include_router(setup_router)
app.include_router(paper_control_router)
app.include_router(validation_router)
app.include_router(history_router)
app.include_router(candle_router)
app.include_router(market_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().swan_web_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, error: SQLAlchemyError):
    return JSONResponse(status_code=503, content={"detail": "DATABASE_UNAVAILABLE"})


def row(value) -> dict:
    result = {column.key: getattr(value, column.key) for column in inspect(type(value)).columns}
    if isinstance(value, PaperPosition):
        result["remaining_quantity"] = value.quantity - value.closed_quantity
    # Preserve decimal money/price precision across the wire.
    return jsonable_encoder(result, custom_encoder={Decimal: str})


def require_account(db: Session, identifier: UUID) -> Account:
    account = db.get(Account, identifier)
    if account is None:
        raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
    return account


@app.get("/health")
def health(request: Request):
    """Local service/database liveness; does not claim trading/provider readiness."""
    with request.app.state.engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"service": "swan-api", "database": "connected"}


@app.get("/api/workspace")
def workspace(request: Request, identifier: UUID = Depends(account_identity)):
    with Session(
        request.app.state.engine.execution_options(isolation_level="REPEATABLE READ")
    ) as db:
        account = require_account(db, identifier)
        control = db.get(RuntimeControl, identifier)
        positions = list(
            db.scalars(
                select(PaperPosition).where(
                    PaperPosition.account_id == identifier, PaperPosition.closed_at.is_(None)
                )
            )
        )
        journal = list(
            db.scalars(
                select(PaperPosition)
                .where(PaperPosition.account_id == identifier, PaperPosition.closed_at.is_not(None))
                .order_by(PaperPosition.closed_at.desc(), PaperPosition.id)
                .limit(50)
            )
        )
        orders = list(
            db.scalars(
                select(PaperOrder)
                .where(PaperOrder.account_id == identifier)
                .order_by(PaperOrder.timestamp.desc(), PaperOrder.id)
                .limit(50)
            )
        )
        active_orders = list(
            db.scalars(
                select(PaperOrder)
                .where(PaperOrder.account_id == identifier, PaperOrder.status.in_(ACTIVE))
                .order_by(PaperOrder.timestamp, PaperOrder.id)
                .limit(200)
            )
        )
        active_order_count = db.scalar(
            select(func.count())
            .select_from(PaperOrder)
            .where(PaperOrder.account_id == identifier, PaperOrder.status.in_(ACTIVE))
        )
        fills = list(
            db.execute(
                select(PaperFill, PaperOrder)
                .join(PaperOrder)
                .where(PaperOrder.account_id == identifier)
                .order_by(PaperFill.timestamp.desc(), PaperFill.id)
                .limit(50)
            )
        )
        ledger = list(
            db.scalars(
                select(LedgerEntry)
                .where(LedgerEntry.account_id == identifier)
                .order_by(LedgerEntry.timestamp.desc(), LedgerEntry.id)
                .limit(50)
            )
        )
        decisions = list(
            db.scalars(
                select(DecisionRecord)
                .where(DecisionRecord.account_id == identifier)
                .order_by(DecisionRecord.id.desc())
                .limit(50)
            )
        )
        evaluations = list(
            db.scalars(
                select(EvaluationSlot)
                .where(EvaluationSlot.account_id == identifier)
                .order_by(EvaluationSlot.slot_at.desc())
                .limit(30)
            )
        )
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.account_id == identifier)
                .where(AuditEvent.kind != "AI_CONTEXT")
                .order_by(AuditEvent.timestamp.desc(), AuditEvent.id)
                .limit(50)
            )
        )
        reserved_cash, pending_risk, _ = reservations(db, identifier)
        restricted_cash = restricted_proceeds(db, identifier)
        instrument_ids = {value.instrument_id for value in [*positions, *journal]}
        instrument_ids.update(value.instrument_id for value in [*orders, *active_orders])
        instrument_ids.update(order.instrument_id for _, order in fills)
        instruments = list(
            db.scalars(select(InstrumentRecord).where(InstrumentRecord.id.in_(instrument_ids)))
        )
        return {
            "as_of": datetime.now(UTC).isoformat(),
            "mode": "PAPER",
            "readiness": readiness(
                datetime.now(UTC),
                account=row(account),
                runtime=row(control) if control else None,
                **evidence_context(db, identifier),
                qualification=qualification_context(db, account, datetime.now(UTC)),
            ),
            "account": row(account),
            "funds": {
                "cash": str(account.cash),
                "reserved_cash": str(reserved_cash),
                "reserved_pending_risk": str(pending_risk),
                "restricted_proceeds": str(restricted_cash),
                "available_cash": str(account.cash - reserved_cash - restricted_cash),
            },
            "runtime": row(control) if control else None,
            "positions": [row(value) for value in positions],
            "journal": [row(value) for value in journal],
            "orders": [row(value) for value in orders],
            "active_orders": [row(value) for value in active_orders],
            "order_summary": {
                "active_count": active_order_count or 0,
                "active_truncated": (active_order_count or 0) > len(active_orders),
            },
            "instruments": {value.id: value.payload for value in instruments},
            "fills": [
                {**row(fill), "instrument_id": order.instrument_id, "side": order.side}
                for fill, order in fills
            ],
            "order_events": [
                row(value)
                for value in db.scalars(
                    select(PaperOrderEvent)
                    .where(PaperOrderEvent.account_id == identifier)
                    .order_by(PaperOrderEvent.timestamp.desc(), PaperOrderEvent.id)
                    .limit(100)
                )
            ],
            "funds_holds": [
                row(value)
                for value in db.scalars(
                    select(PaperFundsHold)
                    .where(PaperFundsHold.account_id == identifier)
                    .order_by(
                        PaperFundsHold.released_at.is_not(None),
                        PaperFundsHold.created_at.desc(),
                        PaperFundsHold.id,
                    )
                    .limit(100)
                )
            ],
            "ledger": [row(value) for value in ledger],
            "decisions": [row(value) for value in decisions],
            "evaluations": [row(value) for value in evaluations],
            "events": [row(value) for value in events],
        }


@app.get("/api/chain")
def chain(
    request: Request,
    underlying: str = Query("NIFTY", pattern="^(NIFTY|SENSEX)$"),
    offset: int = Query(0, ge=0, le=10000),
    identifier: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        require_account(db, identifier)
        records = db.execute(
            select(InstrumentRecord, LatestMarketQuote)
            .join(LatestMarketQuote, LatestMarketQuote.instrument_id == InstrumentRecord.id)
            .where(InstrumentRecord.payload["underlying"].as_string() == underlying)
            .order_by(InstrumentRecord.id)
            .offset(offset)
            .limit(101)
        ).all()
        return {
            "as_of": datetime.now(UTC).isoformat(),
            "underlying": underlying,
            "next_offset": offset + 100 if len(records) > 100 else None,
            "rows": [
                {"instrument": item.payload, "quote": quote.payload}
                for item, quote in records[:100]
            ],
        }


def control_action(request: Request, identifier: UUID, resume: bool):
    now = datetime.now(UTC)
    with Session(request.app.state.engine) as db, db.begin():
        account = db.scalar(select(Account).where(Account.id == identifier).with_for_update())
        control = db.scalar(
            select(RuntimeControl).where(RuntimeControl.account_id == identifier).with_for_update()
        )
        if account is None or control is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        if resume and control.status == "OBSERVATION_ONLY":
            raise HTTPException(409, "WORKER_OBSERVATION_ONLY")
        now = datetime.now(UTC)
        if resume:
            raise HTTPException(409, "USE_EXPLICIT_PAPER_ARMING")
        if resume and (
            account.daily_blocked
            or control.heartbeat is None
            or not 0 <= (now - control.heartbeat).total_seconds() <= 10
        ):
            raise HTTPException(409, "WORKER_NOT_READY_OR_DAILY_BLOCKED")
        control.resume_requested = resume
        if not resume:
            from services.paper.qualification import disarm

            disarm(db, account, now, "USER_PAUSE")
            from services.paper.validation import current, halt, settle

            validation = current(db, identifier)
            if validation:
                halt(db, account, validation, now, "USER_PAUSE")
                settle(db, account, validation, now)
            account.enabled = False
            account.revision += 1
            control.active_envelope = None
            control.status = "PAUSED"
        db.add(
            AuditEvent(
                account_id=identifier,
                timestamp=now,
                kind="USER_CONTROL",
                details={"action": "REQUEST_RESUME" if resume else "PAUSE"},
            )
        )
    return {"status": "RESUME_REQUESTED" if resume else "PAUSED"}


@app.post("/api/control/pause")
def pause(request: Request, identifier: UUID = Depends(account_identity)):
    return control_action(request, identifier, False)


@app.post("/api/control/resume")
def resume(request: Request, identifier: UUID = Depends(account_identity)):
    return control_action(request, identifier, True)


class RiskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    expected_revision: int = Field(ge=0, strict=True)
    max_trade_risk_pct: Decimal = Field(gt=0, le=1)
    max_daily_loss_pct: Decimal = Field(gt=0, le=1)
    max_holding_seconds: int = Field(gt=0, le=300, strict=True)


@app.post("/api/settings/risk")
def update_risk(body: RiskUpdate, request: Request, identifier: UUID = Depends(account_identity)):
    with Session(request.app.state.engine) as db, db.begin():
        account = db.scalar(select(Account).where(Account.id == identifier).with_for_update())
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        control = db.scalar(
            select(RuntimeControl).where(RuntimeControl.account_id == identifier).with_for_update()
        )
        if (
            account.enabled
            or control is None
            or control.resume_requested
            or db.scalar(
                select(PaperOrder.id)
                .where(PaperOrder.account_id == identifier, PaperOrder.status.in_(ACTIVE))
                .limit(1)
            )
            or db.scalar(
                select(PaperPosition.id)
                .where(PaperPosition.account_id == identifier, PaperPosition.closed_at.is_(None))
                .limit(1)
            )
        ):
            raise HTTPException(409, "PAUSE_AND_RESOLVE_ORDERS_POSITIONS_BEFORE_SETTINGS")
        if account.revision != body.expected_revision:
            raise HTTPException(409, "SETTINGS_CHANGED_REFRESH_REQUIRED")
        payload = {
            **account.config,
            **body.model_dump(exclude={"expected_revision"}),
            "version": str(uuid4()),
        }
        try:
            config = RiskConfig.model_validate(payload)
        except ValueError:
            raise HTTPException(422, "INVALID_RISK_LIMITS") from None
        previous = account.config
        account.config = config.model_dump(mode="json")
        account.revision += 1
        control.active_envelope = None
        db.add(
            AuditEvent(
                account_id=identifier,
                timestamp=datetime.now(UTC),
                kind="RISK_POLICY_UPDATED",
                details={"previous": previous, "current": account.config},
            )
        )
    return {"status": "RISK_POLICY_UPDATED"}


@app.get("/api/reports/journal.csv")
def journal_report(request: Request, identifier: UUID = Depends(account_identity)):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Position ID",
            "Instrument",
            "Quantity",
            "Entry INR",
            "Opened UTC",
            "Closed UTC",
            "Realized P&L INR",
        ]
    )
    with Session(request.app.state.engine) as db:
        require_account(db, identifier)
        positions = db.scalars(
            select(PaperPosition)
            .where(PaperPosition.account_id == identifier, PaperPosition.closed_at.is_not(None))
            .order_by(PaperPosition.closed_at.desc())
            .limit(10000)
        )
        for position in positions:
            symbol = position.instrument_id
            if symbol.lstrip().startswith(("=", "+", "-", "@")):
                symbol = "'" + symbol
            writer.writerow(
                [
                    str(position.id),
                    symbol,
                    position.quantity,
                    str(position.average_price),
                    position.opened_at.isoformat(),
                    position.closed_at.isoformat() if position.closed_at else "",
                    str(position.realized_pnl),
                ]
            )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="swan-paper-journal.csv"'},
    )
