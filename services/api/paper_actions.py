"""Authenticated owner controls; no broker calls, price refreshes or fake fills."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.models import Account
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
