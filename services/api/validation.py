"""Owner-scoped controls for explicit, bounded paper validation."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.models import Account, PaperValidation
from services.market.settings import ProviderError
from services.paper.validation import ValidationRequest, ValidationService, view
from services.worker.models import RuntimeControl

router = APIRouter()


@router.get("/api/validation")
def validation_status(request: Request, identifier: UUID = Depends(account_identity)):
    with Session(request.app.state.engine) as db:
        account = db.get(Account, identifier)
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        control = db.get(RuntimeControl, identifier)
        rows = list(
            db.scalars(
                select(PaperValidation)
                .where(PaperValidation.account_id == identifier)
                .order_by(PaperValidation.started_at.desc())
                .limit(20)
            )
        )
        return {
            "revision": account.revision,
            "worker_mode": control.mode if control else None,
            "sessions": [view(row) for row in rows],
            "autonomous_qualified": False,
        }


@router.post("/api/validation/start")
def start_validation(
    body: ValidationRequest, request: Request, identifier: UUID = Depends(account_identity)
):
    try:
        return ValidationService(
            request.app.state.engine, identifier, clock=lambda: datetime.now(UTC)
        ).start(
            body, datetime.now(UTC)
        )
    except (ValueError, OSError, ProviderError) as error:
        code = str(error)
        if not (code.startswith("VALIDATION_") or code == "SETTINGS_CHANGED_REFRESH_REQUIRED"):
            code = "VALIDATION_PREFLIGHT_UNAVAILABLE"
        raise HTTPException(409, code) from None


@router.post("/api/validation/{session_id}/stop")
def stop_validation(
    session_id: UUID, request: Request, identifier: UUID = Depends(account_identity)
):
    try:
        return ValidationService(request.app.state.engine, identifier).stop(
            session_id, datetime.now(UTC)
        )
    except ValueError:
        raise HTTPException(404, "VALIDATION_NOT_FOUND") from None
