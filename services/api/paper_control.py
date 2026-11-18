"""Owner-authenticated qualification, arming and local worker preparation."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from services.api.auth import account_identity
from services.market.settings import ProviderError
from services.paper.qualification import ArmRequest, QualificationService, ReviewRequest
from services.worker.supervisor import prepare

router = APIRouter()


@router.get("/api/paper/qualification")
def status(request: Request, identifier: UUID = Depends(account_identity)):
    try:
        return QualificationService(request.app.state.engine, identifier).status(datetime.now(UTC))
    except (ValueError, OSError, ProviderError):
        raise HTTPException(409, "QUALIFICATION_STATUS_UNAVAILABLE") from None


@router.post("/api/paper/qualification/review")
def review(body: ReviewRequest, request: Request, identifier: UUID = Depends(account_identity)):
    try:
        return QualificationService(request.app.state.engine, identifier).review(
            body, datetime.now(UTC)
        )
    except (ValueError, OSError, ProviderError) as error:
        code = str(error)
        raise HTTPException(
            409,
            code
            if code.startswith(("QUALIFICATION_", "SETTINGS_CHANGED"))
            else "QUALIFICATION_REVIEW_UNAVAILABLE",
        ) from None


@router.post("/api/paper/arm")
def arm(body: ArmRequest, request: Request, identifier: UUID = Depends(account_identity)):
    try:
        return QualificationService(request.app.state.engine, identifier).arm(
            body, datetime.now(UTC)
        )
    except (ValueError, OSError, ProviderError) as error:
        code = str(error)
        raise HTTPException(
            409,
            code
            if code.startswith(("PAPER_", "AUTONOMOUS_", "SETTINGS_CHANGED"))
            else "PAPER_ARM_UNAVAILABLE",
        ) from None


@router.post("/api/paper/disarm")
def disarm(request: Request, identifier: UUID = Depends(account_identity)):
    QualificationService(request.app.state.engine, identifier).tick(
        datetime.now(UTC), "USER_DISARM"
    )
    return {
        "status": "DISARMED",
        "detail": "New entries disabled; existing exposure still requires exit management.",
    }


@router.post("/api/paper/qualification/{qualification_id}/revoke")
def revoke(qualification_id: UUID, request: Request, identifier: UUID = Depends(account_identity)):
    try:
        QualificationService(request.app.state.engine, identifier).revoke(
            qualification_id, datetime.now(UTC)
        )
    except ValueError:
        raise HTTPException(404, "QUALIFICATION_NOT_FOUND") from None
    return {
        "status": "REVOKED",
        "detail": "All account qualifications revoked and new entries disarmed; existing exposure still needs exit management.",
    }


class WorkerPreparation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["OBSERVATION", "VALIDATION", "AUTONOMOUS"]
    expected_revision: int = Field(ge=0, strict=True)


@router.post("/api/worker/prepare")
def worker(body: WorkerPreparation, request: Request, identifier: UUID = Depends(account_identity)):
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "LOCAL_WORKER_CONTROL_ONLY")
    try:
        return prepare(request.app.state.engine, identifier, body.mode, body.expected_revision)
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
