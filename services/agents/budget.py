"""Settle conservative reservations only against unambiguous provider receipts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.agents.provenance import token_usage
from services.core.models import AuditEvent


def consumed_allowance(db: Session, reservations: list[AuditEvent]) -> int:
    total = 0
    for reservation in reservations:
        reserved = reservation.details.get("tokens")
        if type(reserved) is not int or reserved < 0:
            raise ValueError("AI_INVALID_RESERVATION")
        receipts = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.account_id == reservation.account_id,
                    AuditEvent.kind == "AI_RESPONSE_USAGE",
                    AuditEvent.details["reservation_id"].as_string() == str(reservation.id),
                )
            )
        )
        used = None
        if len(receipts) == 1:
            usage = receipts[0].details.get("usage")
            used = token_usage(usage)
            if used is not None and isinstance(usage, dict):
                parts = [usage.get(key) for key in ("input_tokens", "output_tokens")]
                if any(value is not None for value in parts) and (
                    not all(type(value) is int and value >= 0 for value in parts)
                    or sum(value for value in parts if isinstance(value, int)) != used
                ):
                    used = None
        total += reserved if used is None else used
    return total
