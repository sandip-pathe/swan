"""Read-only daily reservation allowance and recorded provider usage."""

from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.agents.settings import AgentSettings
from services.api.auth import account_identity
from services.core.contracts import IST
from services.core.models import Account, AuditEvent

router = APIRouter()


def utc_now() -> datetime:
    return datetime.now(UTC)


def token_usage(value: object) -> int | None:
    if not isinstance(value, dict):
        return None
    total = value.get("total_tokens")
    return total if type(total) is int and total >= 0 else None


@router.get("/api/paper/agent-usage")
def agent_usage(request: Request, owner: UUID = Depends(account_identity)):
    now = utc_now()
    start = datetime.combine(now.astimezone(IST).date(), time.min, IST)
    try:
        settings = AgentSettings()
        policy = {
            "model": settings.openai_model or None,
            "daily_allowance": settings.swan_ai_daily_token_budget,
        }
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
        ids = {str(row.id): row for row in reservations}
        outputs = db.scalars(
            select(AuditEvent).where(
                AuditEvent.account_id == owner,
                AuditEvent.kind == "AI_OUTPUT",
                AuditEvent.timestamp >= start,
            )
        )
        linked: dict[str, list[AuditEvent]] = {}
        for row in outputs:
            key = str(row.details.get("reservation_id", ""))
            if key in ids:
                linked.setdefault(key, []).append(row)
        reserved = 0
        valid = True
        known = 0
        reported = 0
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
            matches = linked.get(str(row.id), [])
            usage = token_usage(matches[0].details.get("usage")) if len(matches) == 1 else None
            if usage is not None:
                known += 1
                reported += usage
        allowance = policy["daily_allowance"] if policy else None
        return {
            "day": start.date().isoformat(),
            "as_of": now.isoformat(),
            "resets_at": (start + timedelta(days=1)).isoformat(),
            "policy": policy,
            "reservation_count": len(reservations),
            "reserved_allowance": reserved if valid else None,
            "remaining_allowance": max(0, allowance - reserved)
            if valid and isinstance(allowance, int)
            else None,
            "reported_tokens": reported,
            "reported_calls": known,
            "unknown_calls": len(reservations) - known,
            "models": [
                {"model": model, "reservations": count} for model, count in sorted(models.items())
            ],
            "billing_cost": None,
        }
