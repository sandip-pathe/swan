"""Authenticated manual paper admission; never calls a broker or refreshes prices."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import Instrument, RiskConfig
from services.core.models import Account, InstrumentRecord, PaperOrder, PaperValidation
from services.paper.manual import ManualPaperService, load_session
from services.paper.orders import DurableOrderLedger
from services.paper.qualification import entry_permission
from services.paper.validation import view
from services.worker.models import RuntimeControl

router = APIRouter()


class SubmitManualOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    expected_account_revision: int = Field(ge=0, strict=True)


@router.post("/api/paper/plans/{plan_id}/submit")
def submit(
    plan_id: UUID,
    body: SubmitManualOrder,
    request: Request,
    identifier: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        if db.get(Account, identifier) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
    try:
        result = ManualPaperService(request.app.state.engine, identifier).submit(
            plan_id, body.request_id, body.expected_account_revision
        )
    except (ValueError, OSError) as error:
        # Never send configuration contents, paths or exception internals to the UI.
        code = str(error)
        allowed = {
            "PAPER_PLAN_NOT_FOUND",
            "PREVIEW_ACCOUNT_CHANGED",
            "MANUAL_REQUEST_CONFLICT",
            "MANUAL_CONTRACT_CHANGED",
            "MANUAL_MARKET_CLOSED",
            "MANUAL_QUOTE_UNAVAILABLE",
            "ENTRY_SOURCE_MISMATCH",
            "CONTROLLED_VALIDATION_REQUIRED",
            "MANUAL_VALIDATION_REQUIRED",
        }
        if code not in allowed and not code.startswith("VALIDATION_"):
            code = "MANUAL_ADMISSION_CHANGED"
        raise HTTPException(404 if code == "PAPER_PLAN_NOT_FOUND" else 409, code) from None
    if result.get("status") == "REJECTED":
        raise HTTPException(409, result["reason"])
    return {
        **result,
        "manual_intent_id": str(body.request_id),
        "plan_id": str(plan_id),
        "source": "HUMAN",
    }


@router.get("/api/paper/manual/status")
def status(
    request: Request,
    instrument_id: str = Query(..., min_length=1, max_length=100),
    identifier: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db, db.begin():
        account = db.scalar(select(Account).where(Account.id == identifier).with_for_update())
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        now = datetime.now(UTC)
        control = db.get(RuntimeControl, identifier)
        lease = db.scalar(
            select(PaperValidation)
            .where(
                PaperValidation.account_id == identifier,
                PaperValidation.status.in_(("ACTIVE", "STOPPING")),
            )
            .order_by(PaperValidation.started_at.desc())
            .limit(1)
        )
        order = (
            db.scalar(
                select(PaperOrder).where(
                    PaperOrder.account_id == identifier,
                    PaperOrder.validation_id == lease.id,
                    PaperOrder.side == "BUY",
                )
            )
            if lease
            else None
        )
        result = {
            "account_id": str(account.id),
            "revision": account.revision,
            "ready": False,
            "reason": None,
            "session": view(lease) if lease else None,
            "order": (
                {
                    **DurableOrderLedger.view(order),
                    "manual_intent_id": str(order.manual_intent_id),
                    "instrument_id": order.instrument_id,
                }
                if order and order.manual_intent_id
                else None
            ),
            "worker_mode": control.mode if control else None,
        }
        record = db.get(InstrumentRecord, instrument_id)
        if record is None:
            result["reason"] = "INSTRUMENT_NOT_SAVED"
            return result
        instrument = Instrument.model_validate(record.payload)
        try:
            session = load_session(instrument.exchange, now)
        except (OSError, ValueError):
            session = None
        if (
            session is None
            or not session.verified
            or not session.opens_at <= now < session.closes_at
        ):
            result["reason"] = "MANUAL_MARKET_CLOSED"
        elif now >= session.closes_at - timedelta(
            minutes=RiskConfig.model_validate(account.config).entry_cutoff_minutes
        ):
            result["reason"] = "MANUAL_ENTRY_CUTOFF"
        elif control is None or control.mode != "VALIDATION":
            result["reason"] = "VALIDATION_WORKER_REQUIRED"
        elif lease is None:
            result["reason"] = "MANUAL_SESSION_REQUIRED"
        elif lease.request.get("entry_source", "AI") != "HUMAN":
            result["reason"] = "ENTRY_SOURCE_MISMATCH"
        elif lease.instrument_id != instrument_id:
            result["reason"] = "VALIDATION_SCOPE_EXCEEDED"
        elif lease.status == "STOPPING":
            result["reason"] = "VALIDATION_STOPPING"
        elif order:
            result["reason"] = "MANUAL_ENTRY_USED"
        else:
            try:
                entry_permission(db, account, now, instrument_id, entry_source="HUMAN")
                result["ready"] = account.enabled and not account.daily_blocked
                result["reason"] = None if result["ready"] else "MANUAL_WAITING"
            except ValueError as error:
                result["reason"] = str(error)
        return result
