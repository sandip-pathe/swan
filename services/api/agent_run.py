"""Explicit evaluation correlation, never reconstructed by timestamp proximity."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.agents.checks import FAILURES
from services.agents.contracts import Analysis, Proposal, Review
from services.api.agent_activity import evaluation, identifier
from services.api.auth import account_identity
from services.core.models import AuditEvent
from services.worker.models import EvaluationSlot

router = APIRouter()


@router.get("/api/paper/agent-activity/{event_id}/run")
def run(event_id: UUID, request: Request, owner: UUID = Depends(account_identity)):
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        event = db.get(AuditEvent, event_id)
        if (
            event is None
            or event.account_id != owner
            or event.kind not in ("AI_OUTPUT", "AGENT_EVALUATION")
        ):
            raise HTTPException(404, "ACTIVITY_NOT_FOUND")
        key = identifier(event.details.get("evaluation_id"))
        slot = db.get(EvaluationSlot, key) if key else None
        if slot is None or slot.account_id != owner:
            return {"available": False}
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.account_id == owner,
                    AuditEvent.kind == "AI_OUTPUT",
                    AuditEvent.details["evaluation_id"].as_string() == str(slot.id),
                )
                .order_by(AuditEvent.timestamp, AuditEvent.id)
                .limit(21)
            )
        )
        rows = []
        models: dict[str, type[Analysis] | type[Proposal] | type[Review]] = {
            "analysis": Analysis,
            "proposal": Proposal,
            "review": Review,
        }
        for item in events[:20]:
            role = str(item.details.get("role", ""))
            model = models.get(role)
            row = {
                "id": str(item.id),
                "timestamp": item.timestamp.isoformat(),
                "stage": role if role in models else "unknown",
                "summary": "Recorded output unavailable",
                "rationale": None,
            }
            if model:
                try:
                    output = model.model_validate(item.details.get("output"))
                    summary = (
                        {
                            "BULLISH": "Bullish analysis",
                            "BEARISH": "Bearish analysis",
                            "UNCERTAIN": "Uncertain analysis",
                        }[output.outlook]
                        if isinstance(output, Analysis)
                        else "Wait proposed"
                        if isinstance(output, Proposal) and output.action == "WAIT"
                        else "Buy call proposed"
                        if isinstance(output, Proposal) and output.action == "BUY_CALL"
                        else "Buy put proposed"
                        if isinstance(output, Proposal)
                        else "Review supported proposal"
                        if output.approved
                        else "Review rejected proposal"
                    )
                    row.update(summary=summary, rationale=output.rationale[:2000])
                except (ValueError, TypeError, KeyError):
                    pass
            rows.append(row)
        records = list(
            db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.account_id == owner,
                    AuditEvent.kind == "AI_STAGE_CHECK",
                    AuditEvent.details["evaluation_id"].as_string() == str(slot.id),
                )
                .order_by(AuditEvent.timestamp, AuditEvent.id)
                .limit(21)
            )
        )
        checks = []
        for record in records[:20]:
            detail = record.details
            stage = detail.get("stage")
            state = detail.get("state")
            reason = detail.get("reason")
            if stage not in ("analysis", "proposal", "review", "strategy"):
                stage, state = "unknown", "UNKNOWN"
            if state == "PASSED" and reason is None:
                message = "Recorded checks passed."
            elif state in ("FAILED", "INTERRUPTED"):
                message = FAILURES.get(str(reason), "Check details are unavailable.")
            else:
                state, message = "UNKNOWN", "Check details are unavailable."
            checks.append(
                {
                    "id": str(record.id),
                    "timestamp": record.timestamp.isoformat(),
                    "stage": stage,
                    "state": state,
                    "summary": message,
                }
            )
        state, title, summary = evaluation(slot.status)
        return {
            "available": True,
            "slot_at": slot.slot_at.isoformat(),
            "state": state,
            "title": title,
            "summary": summary,
            "rows": rows,
            "checks": checks,
            "checks_truncated": len(records) > 20,
            "truncated": len(events) > 20,
        }
