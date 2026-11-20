"""Recorded agent stages and risk outcomes; no new inference or provider calls."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from services.agents.contracts import Analysis, Proposal, Review
from services.api.auth import account_identity
from services.core.contracts import TradeDecision
from services.core.models import Account, AuditEvent, DecisionRecord, InstrumentRecord, PaperOrder
from services.paper.contracts import OrderRiskApproval
from services.worker.models import RuntimeControl

router = APIRouter()
KINDS = {
    "agents": ("AI_OUTPUT", "AGENT_EVALUATION"),
    "risk": ("DURABLE_RISK_DECISION", "ENTRY_REJECTED"),
}
REASONS = {
    "APPROVED": "The entry passed deterministic risk checks at this observation.",
    "PAUSED": "New entries were paused.",
    "DAILY_LOSS_LIMIT": "The daily loss limit blocked this entry.",
    "POSITION_LIMIT": "The open-position limit was reached.",
    "ONE_LOT_DOES_NOT_FIT": "One lot did not fit the available cash or risk budget.",
    "INSUFFICIENT_EXECUTABLE_DEPTH": "Recorded executable depth was insufficient.",
    "STALE_QUOTE": "The market quote was too old.",
    "ENTRY_CUTOFF": "The session entry cutoff had passed.",
    "MARKET_CLOSED": "The market session was closed.",
    "UNAVAILABLE_EVIDENCE": "Required evidence was unavailable.",
    "UNRECONCILED_OR_STALE_PORTFOLIO": "Account reconciliation or fresh portfolio valuation was unavailable.",
    "EXCESSIVE_SPREAD": "The bid/ask spread exceeded the configured limit.",
}


def identifier(value) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def evaluation(status: str) -> tuple[str, str, str]:
    if status == "STRATEGY_APPROVED":
        return (
            "ready",
            "Strategy accepted",
            "A reviewed strategy was accepted. Entry still requires current permission, risk checks and execution.",
        )
    if status == "AGENT_WAIT_OR_REJECT":
        return (
            "unspecified",
            "No strategy accepted",
            "This recorded outcome does not distinguish WAIT from review rejection. No strategy approval was recorded.",
        )
    if status == "AWAITING_AGENT":
        return (
            "pending",
            "Analysis pending",
            "An evaluation was awaiting agent output at this recorded stage.",
        )
    if status == "INVALIDATED_DURING_ANALYSIS":
        return (
            "blocked",
            "Analysis invalidated",
            "Market stream or trading permission changed before the result could be accepted.",
        )
    if status.startswith("AI_HTTP_"):
        return (
            "failed",
            "AI provider unavailable",
            "The provider request failed. This is not an agent WAIT decision.",
        )
    known = {
        "AI_NOT_CONFIGURED": "Agent access was not configured.",
        "AI_DAILY_TOKEN_BUDGET": "The daily agent token allowance was exhausted.",
        "AI_NO_FRESH_STREAM": "Fresh streaming market evidence was unavailable.",
        "AI_NO_MARKET_EVIDENCE": "No usable market evidence was available.",
        "AI_INVALID_OR_TIMED_OUT": "The agent response was invalid or timed out.",
        "AI_RESPONSE_UNAVAILABLE_OR_INVALID": "The provider response was unavailable or invalid.",
        "BLOCKED_NO_FRESH_DATA": "Fresh market data was unavailable for analysis.",
    }
    if status in known:
        return "failed", "Evaluation unavailable", known[status]
    return (
        "unavailable",
        "Evaluation outcome unavailable",
        "The recorded outcome could not be classified. No current approval is implied.",
    )


@router.get("/api/paper/agent-activity")
def activity(
    request: Request,
    category: str = Query("all", pattern="^(all|agents|risk)$"),
    before: UUID | None = None,
    limit: int = Query(20, ge=1, le=50),
    owner: UUID = Depends(account_identity),
):
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        if db.get(Account, owner) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        kinds = KINDS[category] if category != "all" else (*KINDS["agents"], *KINDS["risk"])
        statement = select(AuditEvent).where(
            AuditEvent.account_id == owner, AuditEvent.kind.in_(kinds)
        )
        if before:
            cursor = db.get(AuditEvent, before)
            if cursor is None or cursor.account_id != owner or cursor.kind not in kinds:
                raise HTTPException(400, "ACTIVITY_CURSOR_INVALID")
            statement = statement.where(
                tuple_(AuditEvent.timestamp, AuditEvent.id) < (cursor.timestamp, cursor.id)
            )
        events = list(
            db.scalars(
                statement.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc()).limit(
                    limit + 1
                )
            )
        )
        more, events = len(events) > limit, events[:limit]
        decision_ids = [
            value
            for event in events
            if event.kind in KINDS["risk"]
            if (value := identifier(event.details.get("decision_id")))
        ]
        decisions = {
            d.id: d
            for d in db.scalars(
                select(DecisionRecord).where(
                    DecisionRecord.account_id == owner, DecisionRecord.id.in_(decision_ids)
                )
            )
        }
        orders = {
            o.decision_id: o
            for o in db.scalars(
                select(PaperOrder).where(
                    PaperOrder.account_id == owner, PaperOrder.decision_id.in_(decision_ids)
                )
            )
        }
        rows: list[dict] = []
        for event in events:
            row: dict = {
                "id": str(event.id),
                "timestamp": event.timestamp.isoformat(),
                "stage": "evaluation",
                "state": "unavailable",
                "title": "Recorded outcome unavailable",
                "summary": "Details could not be verified from this record.",
                "rationale": None,
                "evidence_count": None,
                "concerns": [],
                "instrument_id": None,
                "risk": None,
                "order": None,
            }
            try:
                if event.kind == "AI_OUTPUT":
                    role = str(event.details.get("role", ""))
                    models: dict[str, type[Analysis] | type[Proposal] | type[Review]] = {
                        "analysis": Analysis,
                        "proposal": Proposal,
                        "review": Review,
                    }
                    row["stage"] = role if role in models else "output"
                    model = models.get(role)
                    if model:
                        output = model.model_validate(event.details.get("output"))
                        row.update(
                            stage=role,
                            rationale=output.rationale[:2000],
                            evidence_count=len(set(output.evidence_ids)),
                            summary="Recorded model output. Evidence acceptance, permission and execution are separate checks.",
                        )
                        if isinstance(output, Analysis):
                            row.update(
                                state="analysis",
                                title={
                                    "BULLISH": "Bullish analysis",
                                    "BEARISH": "Bearish analysis",
                                    "UNCERTAIN": "Uncertain analysis",
                                }[output.outlook],
                                concerns=[text[:300] for text in output.concerns[:5]],
                            )
                        elif isinstance(output, Proposal):
                            row.update(
                                state="wait" if output.action == "WAIT" else "proposed",
                                title={
                                    "WAIT": "Agent chose to wait",
                                    "BUY_CALL": "Buy call proposed",
                                    "BUY_PUT": "Buy put proposed",
                                }[output.action],
                                instrument_id=output.instrument_id,
                            )
                        elif isinstance(output, Review):
                            row.update(
                                state="reviewed" if output.approved else "blocked",
                                title="Review supported proposal"
                                if output.approved
                                else "Review rejected proposal",
                            )
                elif event.kind == "AGENT_EVALUATION":
                    state, title, summary = evaluation(str(event.details.get("status", "")))
                    row.update(state=state, title=title, summary=summary)
                else:
                    row["stage"] = "risk"
                    decision_id = identifier(event.details.get("decision_id"))
                    record = decisions.get(decision_id) if decision_id else None
                    if record:
                        decision = TradeDecision.model_validate(record.payload)
                        allowed = record.result.get("status") == "APPROVED"
                        row.update(
                            state="ready"
                            if allowed
                            else "wait"
                            if decision.action == "WAIT"
                            else "blocked",
                            title="Risk checks passed"
                            if allowed
                            else "No entry proposed"
                            if decision.action == "WAIT"
                            else "Risk checks blocked entry",
                            summary=REASONS.get(
                                str(record.result.get("reason", "")),
                                "The detailed reason is unavailable in this record.",
                            ),
                            rationale=decision.rationale[:2000],
                            evidence_count=len(set(decision.snapshot_ids)),
                            instrument_id=decision.instrument_id,
                        )
                        if allowed:
                            approval = OrderRiskApproval.model_validate(
                                record.result.get("approval")
                            )
                            row["risk"] = {
                                "quantity": approval.quantity,
                                "cash_budget": str(approval.cash_budget),
                                "risk_budget": str(approval.risk_budget),
                                "expires_at": approval.expires_at.isoformat(),
                            }
                        order = orders.get(decision_id)
                        if order:
                            row["order"] = {
                                "id": str(order.id),
                                "status": order.status,
                                "quantity": order.quantity,
                                "filled_quantity": order.filled_quantity,
                            }
            except (ValueError, TypeError, KeyError):
                row.update(
                    state="unavailable",
                    title="Recorded outcome unavailable",
                    summary="Details could not be verified from this record.",
                    rationale=None,
                    concerns=[],
                    risk=None,
                )
            rows.append(row)
        instruments = {
            r.id: {
                key: r.payload.get(key) for key in ("underlying", "strike", "option_type", "expiry")
            }
            for r in db.scalars(
                select(InstrumentRecord).where(
                    InstrumentRecord.id.in_(
                        [row["instrument_id"] for row in rows if row["instrument_id"]]
                    )
                )
            )
        }
        for row in rows:
            row["instrument"] = instruments.get(row.pop("instrument_id"))
        control = db.get(RuntimeControl, owner)
        return {
            "as_of": datetime.now(UTC).isoformat(),
            "mode": control.mode
            if control and control.mode in {"OBSERVATION", "VALIDATION", "AUTONOMOUS"}
            else "UNKNOWN",
            "rows": rows,
            "next_before": str(events[-1].id) if more else None,
        }
