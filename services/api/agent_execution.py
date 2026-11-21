"""Owned evaluation -> accepted envelope -> risk decision -> actual paper order."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.agent_activity import REASONS
from services.core.contracts import Instrument, StrategyEnvelope, TradeDecision
from services.core.models import AuditEvent, DecisionRecord, InstrumentRecord, PaperFill, PaperOrder
from services.paper.contracts import OrderRiskApproval


def execution(db: Session, owner: UUID, evaluation_id: UUID, after: UUID | None = None) -> dict:
    unavailable = {"state": "unavailable", "decisions": [], "next_after": None}
    outcomes = list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.account_id == owner,
                AuditEvent.kind == "AGENT_EVALUATION",
                AuditEvent.details["evaluation_id"].as_string() == str(evaluation_id),
            )
            .limit(2)
        )
    )
    if len(outcomes) != 1:
        return unavailable
    outcome = outcomes[0].details
    if not isinstance(outcome.get("status"), str):
        return unavailable
    if outcome.get("envelope") is None:
        return (
            {**unavailable, "state": "none"}
            if outcome.get("status") != "STRATEGY_APPROVED"
            else unavailable
        )
    if outcome.get("status") != "STRATEGY_APPROVED":
        return unavailable
    try:
        envelope = StrategyEnvelope.model_validate(outcome["envelope"])
        if envelope.invalidated:
            return unavailable
    except (ValueError, TypeError):
        return unavailable
    statement = select(DecisionRecord).where(
        DecisionRecord.account_id == owner,
        DecisionRecord.payload["strategy_id"].as_string() == str(envelope.id),
    )
    if after:
        cursor = db.get(DecisionRecord, after)
        if (
            cursor is None
            or cursor.account_id != owner
            or cursor.payload.get("strategy_id") != str(envelope.id)
        ):
            raise HTTPException(400, "RUN_CURSOR_INVALID")
        statement = statement.where(DecisionRecord.id > cursor.id)
    records = list(db.scalars(statement.order_by(DecisionRecord.id).limit(21)))
    more = len(records) > 20
    records = records[:20]
    decision_ids = [row.id for row in records]
    orders = list(
        db.scalars(
            select(PaperOrder)
            .where(PaperOrder.account_id == owner, PaperOrder.decision_id.in_(decision_ids))
            .order_by(PaperOrder.timestamp, PaperOrder.id)
        )
    )
    quantities = dict(
        db.execute(
            select(PaperFill.order_id, func.sum(PaperFill.quantity))
            .where(PaperFill.order_id.in_([row.id for row in orders]))
            .group_by(PaperFill.order_id)
        ).all()
    )
    rows = []
    for record in records:
        try:
            decision = TradeDecision.model_validate(record.payload)
            if decision.strategy_id != envelope.id or decision.id != record.id:
                raise ValueError("Decision identity mismatch")
            status = record.result.get("status")
            if status not in ("APPROVED", "REJECTED"):
                status = "UNAVAILABLE"
            if status == "APPROVED":
                OrderRiskApproval.model_validate(record.result.get("approval"))
                if record.result.get("reason") != "APPROVED":
                    raise ValueError("Approval reason mismatch")
            elif status == "REJECTED" and record.result.get("reason") == "APPROVED":
                raise ValueError("Rejection reason mismatch")
            summary = REASONS.get(
                str(record.result.get("reason", "")), "The recorded risk reason is unavailable."
            )
            if status == "UNAVAILABLE":
                summary = "The recorded risk result is unavailable."
            row_orders = [
                {
                    "id": str(order.id),
                    "status": order.status,
                    "side": order.side,
                    "quantity": order.quantity,
                    "filled_quantity": quantities.get(order.id, 0),
                }
                for order in orders
                if order.decision_id == record.id
            ]
            rows.append(
                {
                    "id": str(record.id),
                    "status": status,
                    "summary": summary,
                    "timestamp": decision.timestamp.isoformat(),
                    "orders": row_orders,
                }
            )
        except (ValueError, TypeError, KeyError):
            rows.append(
                {
                    "id": str(record.id),
                    "status": "UNAVAILABLE",
                    "summary": "The linked risk record could not be verified.",
                    "timestamp": None,
                    "orders": [],
                }
            )
    label = None
    if len(envelope.instrument_ids) == 1:
        instrument = db.get(InstrumentRecord, envelope.instrument_ids[0])
        try:
            parsed = Instrument.model_validate(instrument.payload) if instrument else None
            if parsed:
                label = (
                    f"{parsed.underlying} {parsed.strike} {parsed.option_type} / {parsed.expiry}"
                )
        except (ValueError, TypeError):
            pass
    return {
        "state": "accepted",
        "strategy": {
            "version": envelope.version[:150],
            "action": envelope.action,
            "instrument": label,
            "issued_at": envelope.issued_at.isoformat(),
            "expires_at": envelope.expires_at.isoformat(),
            "min_entry": str(envelope.min_entry),
            "max_entry": str(envelope.max_entry),
            "stop_loss": str(envelope.stop_loss),
            "target": str(envelope.target),
        },
        "decisions": rows,
        "next_after": str(records[-1].id) if more else None,
    }
