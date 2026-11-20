"""Authenticated owner controls; no broker calls, price refreshes or fake fills."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import Price
from services.core.models import Account
from services.paper.amend import ManualAmendService
from services.paper.user_actions import PaperUserActions

router = APIRouter()


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


def perform(request: Request, owner: UUID, target: UUID, body: ActionRequest, kind: str):
    with Session(request.app.state.engine) as db:
        if db.get(Account, owner) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
    service = PaperUserActions(request.app.state.engine, owner)
    try:
        return (
            service.cancel_entry(target, body.request_id)
            if kind == "CANCEL"
            else service.exit_position(target, body.request_id)
        )
    except ValueError as error:
        code = str(error)
        allowed = {
            "PAPER_ORDER_NOT_FOUND",
            "PAPER_POSITION_NOT_FOUND",
            "PAPER_ENTRY_CANCEL_ONLY",
            "PAPER_DURABLE_POSITION_REQUIRED",
            "PAPER_ACTION_REQUEST_CONFLICT",
        }
        if code not in allowed:
            code = "PAPER_ACTION_RECONCILIATION_REQUIRED"
        raise HTTPException(404 if code.endswith("_NOT_FOUND") else 409, code) from None


@router.post("/api/paper/orders/{order_id}/cancel")
def cancel(
    order_id: UUID,
    body: ActionRequest,
    request: Request,
    identifier: UUID = Depends(account_identity),
):
    return perform(request, identifier, order_id, body, "CANCEL")


@router.post("/api/paper/positions/{position_id}/exit")
def exit_position(
    position_id: UUID,
    body: ActionRequest,
    request: Request,
    identifier: UUID = Depends(account_identity),
):
    return perform(request, identifier, position_id, body, "EXIT")


class AmendPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_account_revision: int = Field(ge=0, strict=True)
    entry: Price
    stop_loss: Price
    target: Price

    @model_validator(mode="after")
    def prices(self):
        if not self.stop_loss < self.entry < self.target:
            raise ValueError("Stop must be below entry and target above it")
        return self


class AmendCommand(AmendPreview):
    request_id: UUID


def amend_action(request: Request, owner: UUID, target: UUID, body: AmendPreview):
    with Session(request.app.state.engine) as db:
        if db.get(Account, owner) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
    try:
        return ManualAmendService(request.app.state.engine, owner).amend(
            target,
            body.expected_account_revision,
            body.entry,
            body.stop_loss,
            body.target,
            body.request_id if isinstance(body, AmendCommand) else None,
        )
    except (ValueError, OSError) as error:
        code = str(error)
        if code not in {
            "PAPER_ORDER_NOT_FOUND",
            "PREVIEW_ACCOUNT_CHANGED",
            "MANUAL_REQUEST_CONFLICT",
        } and not code.startswith(
            ("MANUAL_AMEND_", "MANUAL_EXECUTION_", "MANUAL_MARKET_", "MANUAL_QUOTE_", "VALIDATION_")
        ):
            code = "MANUAL_AMEND_CHECKS_CHANGED"
        raise HTTPException(404 if code == "PAPER_ORDER_NOT_FOUND" else 409, code) from None


@router.post("/api/paper/orders/{order_id}/amend/preview")
def preview_amend(
    order_id: UUID,
    body: AmendPreview,
    request: Request,
    identifier: UUID = Depends(account_identity),
):
    return amend_action(request, identifier, order_id, body)


@router.post("/api/paper/orders/{order_id}/amend")
def amend(
    order_id: UUID,
    body: AmendCommand,
    request: Request,
    identifier: UUID = Depends(account_identity),
):
    return amend_action(request, identifier, order_id, body)
