"""Read-only daily reservation allowance and recorded provider usage."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.agents.budget import consumed_allowance
from services.agents.provenance import token_usage
from services.agents.settings import AgentSettings
from services.api.auth import account_identity
from services.core.contracts import IST
from services.core.models import Account, AuditEvent

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(UTC)


@router.get("/api/paper/agent-usage")
def agent_usage(request: Request, owner: UUID = Depends(account_identity), day: date | None = None):
    now = utc_now()
    today = now.astimezone(IST).date()
    selected = day or today
    if selected > today:
        raise HTTPException(422, "USAGE_DAY_NOT_STARTED")
    historical = selected < today
    start = datetime.combine(selected, time.min, IST)
    policy_source = "current"
    try:
        settings = AgentSettings() if not historical else None
        policy = (
            {
                "model": settings.openai_model or None,
                "daily_allowance": settings.swan_ai_daily_token_budget,
            }
            if settings
            else None
        )
    except (ValueError, OSError):
        policy = None
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        if db.get(Account, owner) is None:
            raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
        reservations = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.account_id == owner,
                    AuditEvent.kind == "AI_RESERVATION",
                    AuditEvent.timestamp >= start,
                    AuditEvent.timestamp < start + timedelta(days=1),
                )
            )
        )
        if historical:
            limits = [row.details.get("daily_allowance") for row in reservations]
            valid_limits = bool(limits) and all(
                type(value) is int and value > 0 for value in limits
            )
            if valid_limits and len(set(limits)) == 1:
                policy = {"model": None, "daily_allowance": limits[0]}
                policy_source = "recorded"
            else:
                policy = None
                policy_source = "changed" if valid_limits else "unrecorded"
        ids = {str(row.id): row for row in reservations}
        outputs = db.scalars(
            select(AuditEvent).where(
                AuditEvent.account_id == owner,
                AuditEvent.kind.in_(("AI_OUTPUT", "AI_RESPONSE_USAGE")),
                AuditEvent.details["reservation_id"].as_string().in_(list(ids)),
            )
        )
        linked: dict[str, list[AuditEvent]] = {}
        receipts: dict[str, list[AuditEvent]] = {}
        for row in outputs:
            key = str(row.details.get("reservation_id", ""))
            if key in ids:
                target = receipts if row.kind == "AI_RESPONSE_USAGE" else linked
                target.setdefault(key, []).append(row)
        reserved = 0
        valid = True
        known = 0
        reported = 0
        without_output = 0
        models: dict[str, int] = {}
        for row in reservations:
            tokens = row.details.get("tokens")
            if type(tokens) is not int or tokens < 0:
                valid = False
            else:
                reserved += tokens
            model = row.details.get("model")
            model = model if isinstance(model, str) and len(model) <= 150 else "Unknown model"
            models[model] = models.get(model, 0) + 1
            matches = receipts.get(str(row.id), []) or linked.get(str(row.id), [])
            usage = token_usage(matches[0].details.get("usage")) if len(matches) == 1 else None
            if (
                receipts.get(str(row.id))
                and usage is not None
                and any(
                    token_usage(output.details.get("usage")) != usage
                    for output in linked.get(str(row.id), [])
                )
            ):
                usage = None
            if usage is not None:
                known += 1
                reported += usage
                without_output += not linked.get(str(row.id))
        allowance = policy["daily_allowance"] if policy else None
        consumed = consumed_allowance(db, reservations) if valid else None
        return {
            "day": start.date().isoformat(),
            "as_of": now.isoformat(),
            "resets_at": (start + timedelta(days=1)).isoformat(),
            "policy": policy,
            "policy_source": policy_source,
            "day_ended": historical,
            "reservation_count": len(reservations),
            "reserved_allowance": reserved if valid else None,
            "consumed_allowance": consumed,
            "remaining_allowance": max(0, allowance - consumed)
            if consumed is not None and isinstance(allowance, int)
            else None,
            "reported_tokens": reported,
            "reported_calls": known,
            "reported_without_output_calls": without_output,
            "unknown_calls": len(reservations) - known,
            "models": [
                {"model": model, "reservations": count} for model, count in sorted(models.items())
            ],
            "billing_cost": None,
        }
