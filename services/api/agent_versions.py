"""Recorded request/response model names and local-rule fingerprints."""

from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from services.agents.provenance import checksum, name
from services.api.agent_activity import identifier
from services.core.models import AuditEvent


def versions(db: Session, owner: UUID, evaluation_id: UUID, before: UUID | None = None) -> dict:
    statement = select(AuditEvent).where(
        AuditEvent.account_id == owner,
        AuditEvent.kind == "AI_RESERVATION",
        AuditEvent.details["request"]["evaluation_id"].as_string() == str(evaluation_id),
    )
    if before:
        cursor = db.get(AuditEvent, before)
        request = cursor.details.get("request") if cursor else None
        if (
            cursor is None
            or cursor.account_id != owner
            or cursor.kind != "AI_RESERVATION"
            or not isinstance(request, dict)
            or request.get("evaluation_id") != str(evaluation_id)
        ):
            raise HTTPException(400, "RUN_CURSOR_INVALID")
        statement = statement.where(
            tuple_(AuditEvent.timestamp, AuditEvent.id) < (cursor.timestamp, cursor.id)
        )
    reservations = list(
        db.scalars(statement.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc()).limit(21))
    )
    more = len(reservations) > 20
    reservations = reservations[:20]
    ids = [str(row.id) for row in reservations]
    outputs = list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.account_id == owner,
                AuditEvent.kind == "AI_OUTPUT",
                AuditEvent.details["evaluation_id"].as_string() == str(evaluation_id),
                AuditEvent.details["reservation_id"].as_string().in_(ids),
            )
            .limit(201)
        )
    )
    complete = len(outputs) <= 200
    linked: dict[str, list[AuditEvent]] = defaultdict(list)
    if complete:
        for output in outputs:
            linked[str(output.details.get("reservation_id"))].append(output)
    context_ids = [
        value
        for row in reservations
        if (value := identifier((row.details.get("request") or {}).get("context_id")))
    ]
    contexts = {
        row.id: row
        for row in db.scalars(
            select(AuditEvent).where(
                AuditEvent.account_id == owner,
                AuditEvent.kind == "AI_CONTEXT",
                AuditEvent.id.in_(context_ids),
                AuditEvent.details["evaluation_id"].as_string() == str(evaluation_id),
            )
        )
    }
    rows = []
    for row in reservations:
        request = row.details.get("request") or {}
        context_id = identifier(request.get("context_id"))
        context = contexts.get(context_id) if context_id else None
        implementation = context.details.get("implementation") if context else None
        implementation = implementation if isinstance(implementation, dict) else {}
        prompt = checksum(request.get("prompt_sha256"))
        schema = checksum(request.get("schema_sha256"))
        pipeline = checksum(implementation.get("pipeline_sha256"))
        matching = linked.get(str(row.id), [])
        reported = (
            name(matching[0].details.get("reported_model"))
            if len(matching) == 1
            and matching[0].details.get("context_id") == request.get("context_id")
            and matching[0].details.get("role") == row.details.get("role")
            else None
        )
        role = row.details.get("role")
        rows.append(
            {
                "id": str(row.id),
                "stage": role if role in ("analysis", "proposal", "review") else "unknown",
                "timestamp": row.timestamp.isoformat(),
                "requested_model": name(request.get("model")),
                "reported_model": reported,
                "strategy_version": name(implementation.get("strategy_version")),
                "rules_recorded": bool(prompt and schema and pipeline),
                "fingerprints": {"prompt": prompt, "schema": schema, "pipeline": pipeline},
            }
        )
    return {
        "rows": rows,
        "truncated": more,
        "next_before": str(reservations[-1].id) if more else None,
        "outputs_incomplete": not complete,
    }
