"""Authenticated configuration and diagnostics for the single-owner local app."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.core.contracts import RiskConfig
from services.core.models import Account, AuditEvent, PaperOrder, PaperPosition
from services.core.setup import CONFIG_FILES, atomic_text, digest, document, save_document
from services.market.diagnostics import NAMES, run_diagnostic
from services.paper.accounting import ACTIVE
from services.worker.models import RuntimeControl

router = APIRouter()


def editable(db: Session, account_id: UUID) -> tuple[Account, RuntimeControl]:
    account = db.scalar(select(Account).where(Account.id == account_id).with_for_update())
    control = db.scalar(
        select(RuntimeControl).where(RuntimeControl.account_id == account_id).with_for_update()
    )
    if account is None or control is None:
        raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
    pending = db.scalar(
        select(PaperOrder.id)
        .where(PaperOrder.account_id == account_id, PaperOrder.status.in_(ACTIVE))
        .limit(1)
    )
    held = db.scalar(
        select(PaperPosition.id)
        .where(PaperPosition.account_id == account_id, PaperPosition.closed_at.is_(None))
        .limit(1)
    )
    if account.enabled or control.resume_requested or pending or held:
        raise HTTPException(409, "PAUSE_AND_RESOLVE_ORDERS_POSITIONS_BEFORE_SETTINGS")
    return account, control


@router.get("/api/settings/setup")
def setup_documents(request: Request, identifier: UUID = Depends(account_identity)):
    with Session(request.app.state.engine) as db:
        if db.get(Account, identifier) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
    return {"documents": [document(name) for name in CONFIG_FILES]}


class SetupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    document: dict


@router.post("/api/settings/setup/{name}")
def update_setup(
    name: Literal["execution", "calendar", "news", "agents"],
    body: SetupUpdate,
    request: Request,
    identifier: UUID = Depends(account_identity),
):
    if len(body.model_dump_json()) > 1000000:
        raise HTTPException(413, "CONFIGURATION_TOO_LARGE")
    with request.app.state.engine.connect() as lease:
        # Keep the shared-file lock through commit and any compensating file restore.
        if not lease.scalar(text("SELECT pg_try_advisory_lock(726230519841)")):
            lease.rollback()
            raise HTTPException(409, "SETUP_EDIT_ALREADY_RUNNING")
        lease.commit()
        try:
            with Session(bind=lease) as db, db.begin():
                accounts = list(db.scalars(select(Account.id).limit(2)))
                if accounts != [identifier]:
                    raise HTTPException(409, "SHARED_CONFIGURATION_REQUIRES_SINGLE_OWNER")
                account, control = editable(db, identifier)
                path = CONFIG_FILES[name]
                old_raw = path.read_text(encoding="utf-8") if path.exists() else None
                try:
                    previous = save_document(name, body.document, body.expected_revision)
                except ValueError as error:
                    code = (
                        "SETTINGS_CHANGED_REFRESH_REQUIRED"
                        if str(error) == "SETTINGS_CHANGED_REFRESH_REQUIRED"
                        else "INVALID_SETUP_CONFIGURATION"
                    )
                    raise HTTPException(
                        409 if code.startswith("SETTINGS_CHANGED") else 422, code
                    ) from None
                except OSError:
                    raise HTTPException(503, "CONFIGURATION_WRITE_UNAVAILABLE") from None
                control.active_envelope = None
                account.revision += 1
                db.add(
                    AuditEvent(
                        account_id=identifier,
                        kind="SETUP_CONFIGURATION_UPDATED",
                        timestamp=datetime.now(UTC),
                        details={
                            "name": name,
                            "previous": previous,
                            "current_revision": document(name)["revision"],
                        },
                    )
                )
                # Flush/commit while the account and configuration locks are still held.
                # Compensate a database failure so a failed save cannot silently alter policy.
                try:
                    db.commit()
                except Exception:
                    if old_raw is None:
                        path.unlink(missing_ok=True)
                    else:
                        atomic_text(path, old_raw)
                    raise
        finally:
            lease.execute(text("SELECT pg_advisory_unlock(726230519841)"))
            lease.commit()
    return {"status": "CONFIGURATION_SAVED", **document(name)}


class RiskPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    policy: RiskConfig
    reviewed: Literal[True]


@router.post("/api/settings/risk-policy")
def review_risk(
    body: RiskPolicyUpdate, request: Request, identifier: UUID = Depends(account_identity)
):
    required = set(RiskConfig.model_fields) - {"costs"}
    if not required <= body.policy.model_fields_set:
        raise HTTPException(422, "COMPLETE_RISK_POLICY_REQUIRED")
    with Session(request.app.state.engine) as db, db.begin():
        account, control = editable(db, identifier)
        if account.revision != body.expected_revision:
            raise HTTPException(409, "SETTINGS_CHANGED_REFRESH_REQUIRED")
        if body.policy.capital != RiskConfig.model_validate(account.config).capital:
            raise HTTPException(409, "CAPITAL_CHANGE_REQUIRES_LEDGER_OPERATION")
        if body.policy.costs != RiskConfig.model_validate(account.config).costs:
            raise HTTPException(409, "LEGACY_COST_CHANGE_NOT_SUPPORTED")
        previous = account.config
        policy = body.policy.model_copy(update={"version": str(uuid4())}).model_dump(mode="json")
        account.config = policy
        account.revision += 1
        control.active_envelope = None
        db.add(
            AuditEvent(
                account_id=identifier,
                kind="RISK_POLICY_REVIEWED",
                timestamp=datetime.now(UTC),
                details={"previous": previous, "policy_digest": digest(policy), "policy": policy},
            )
        )
    return {"status": "RISK_POLICY_REVIEWED"}


@router.post("/api/diagnostics/{name}")
def connection_check(name: str, request: Request, identifier: UUID = Depends(account_identity)):
    if name not in NAMES:
        raise HTTPException(404, "UNKNOWN_CONNECTION_CHECK")
    try:
        return run_diagnostic(request.app.state.engine, identifier, name)
    except ValueError:
        raise HTTPException(409, "CONNECTION_CHECK_UNAVAILABLE") from None
