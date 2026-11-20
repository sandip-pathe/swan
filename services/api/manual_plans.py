"""Owned, idempotent human plans. No order admission, reservation or AI approval."""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.auth import account_identity
from services.api.order_preview import ManualPreview, calculate_preview
from services.core.models import (
    Account,
    AuditEvent,
    InstrumentRecord,
    ManualIntentRecord,
    ManualPaperPlan,
    PaperOrder,
)

router = APIRouter()
PLAN_LIMIT = 50


class SavePlan(ManualPreview):
    idempotency_key: UUID
    expected_account_revision: int = Field(ge=0, strict=True)


def plan_orders(db: Session, plans: list[ManualPaperPlan]) -> dict[UUID, PaperOrder]:
    if not plans:
        return {}
    ranked = (
        select(
            PaperOrder.id,
            ManualIntentRecord.plan_id,
            func.row_number()
            .over(
                partition_by=ManualIntentRecord.plan_id,
                order_by=(PaperOrder.accepted_at.desc(), PaperOrder.id.desc()),
            )
            .label("rank"),
        )
        .join(ManualIntentRecord, PaperOrder.manual_intent_id == ManualIntentRecord.id)
        .where(
            ManualIntentRecord.plan_id.in_([p.id for p in plans]),
            PaperOrder.account_id == plans[0].account_id,
        )
        .subquery()
    )
    return {
        cast(UUID, plan_id): cast(PaperOrder, order)
        for order, plan_id in db.execute(
            select(PaperOrder, ranked.c.plan_id)
            .join(ranked, PaperOrder.id == ranked.c.id)
            .where(ranked.c.rank == 1)
        )
    }


def view(plan: ManualPaperPlan, order: PaperOrder | None = None):
    return {
        "id": str(plan.id),
        "instrument": plan.instrument_payload,
        "inputs": plan.request_payload,
        "created_at": plan.created_at.isoformat(),
        "archived_at": plan.archived_at.isoformat() if plan.archived_at else None,
        "preview": plan.preview_payload,
        "status": "archived" if plan.archived_at else "saved",
        "source": "human",
        "order_id": str(order.id) if order else None,
        "last_order_status": order.status if order else None,
        "submission_ready": False,
    }


@router.post("/api/paper/plans")
def save_plan(body: SavePlan, request: Request, identifier: UUID = Depends(account_identity)):
    inputs = ManualPreview.model_validate(
        body.model_dump(exclude={"idempotency_key", "expected_account_revision"})
    )
    canonical = inputs.model_dump(mode="json")
    for key in ("entry", "stop_loss", "target"):
        canonical[key] = format(getattr(inputs, key), ".2f")
    with Session(request.app.state.engine) as db, db.begin():
        account = db.scalar(select(Account).where(Account.id == identifier).with_for_update())
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        existing = db.scalar(
            select(ManualPaperPlan).where(
                ManualPaperPlan.account_id == identifier,
                ManualPaperPlan.idempotency_key == body.idempotency_key,
            )
        )
        if existing:
            if existing.request_payload != canonical:
                raise HTTPException(409, "PAPER_PLAN_REQUEST_CONFLICT")
            return view(existing, plan_orders(db, [existing]).get(existing.id))
        if account.revision != body.expected_account_revision:
            raise HTTPException(409, "PREVIEW_ACCOUNT_CHANGED")
        count = db.scalar(
            select(func.count())
            .select_from(ManualPaperPlan)
            .where(ManualPaperPlan.account_id == identifier, ManualPaperPlan.archived_at.is_(None))
        )
        if count is not None and count >= PLAN_LIMIT:
            raise HTTPException(409, "PAPER_PLAN_LIMIT")
        now = datetime.now(UTC)
        estimate = calculate_preview(inputs, db, account, now)
        instrument = db.get(InstrumentRecord, body.instrument_id)
        assert instrument is not None
        plan = ManualPaperPlan(
            account_id=identifier,
            instrument_id=body.instrument_id,
            idempotency_key=body.idempotency_key,
            created_at=now,
            request_payload=canonical,
            instrument_payload=instrument.payload,
            preview_payload=estimate,
        )
        db.add(plan)
        db.flush()
        db.add(
            AuditEvent(
                account_id=identifier,
                kind="MANUAL_PAPER_PLAN_SAVED",
                timestamp=now,
                details={
                    "plan_id": str(plan.id),
                    "instrument_id": plan.instrument_id,
                    "source": "human",
                    "order_created": False,
                },
            )
        )
        return view(plan, plan_orders(db, [plan]).get(plan.id))


@router.get("/api/paper/plans")
def plans(
    request: Request,
    instrument_id: str | None = Query(None, max_length=100),
    offset: int = Query(0, ge=0, le=10000),
    identifier: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        if db.get(Account, identifier) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        filters = [ManualPaperPlan.account_id == identifier, ManualPaperPlan.archived_at.is_(None)]
        if instrument_id:
            filters.append(ManualPaperPlan.instrument_id == instrument_id)
        rows = list(
            db.scalars(
                select(ManualPaperPlan)
                .where(*filters)
                .order_by(ManualPaperPlan.created_at.desc(), ManualPaperPlan.id)
                .offset(offset)
                .limit(26)
            )
        )
        orders = plan_orders(db, rows[:25])
        return {
            "rows": [view(row, orders.get(row.id)) for row in rows[:25]],
            "next_offset": offset + 25 if len(rows) > 25 else None,
            "limit": PLAN_LIMIT,
        }


@router.post("/api/paper/plans/{plan_id}/archive")
def archive(plan_id: UUID, request: Request, identifier: UUID = Depends(account_identity)):
    with Session(request.app.state.engine) as db, db.begin():
        account = db.scalar(select(Account).where(Account.id == identifier).with_for_update())
        if account is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        plan = db.get(ManualPaperPlan, plan_id)
        if plan is None or plan.account_id != identifier:
            raise HTTPException(404, "PAPER_PLAN_NOT_FOUND")
        if plan.archived_at is None:
            plan.archived_at = datetime.now(UTC)
            db.add(
                AuditEvent(
                    account_id=identifier,
                    kind="MANUAL_PAPER_PLAN_ARCHIVED",
                    timestamp=plan.archived_at,
                    details={"plan_id": str(plan.id)},
                )
            )
        return view(plan, plan_orders(db, [plan]).get(plan.id))
