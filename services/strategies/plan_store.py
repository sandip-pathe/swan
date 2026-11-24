"""Research-only ORB plan drafts with deterministic identity and bounded reads."""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.models import StrategyAssessmentRecord, StrategyPlanDraftRecord
from services.strategies.contracts import ORBAssessment, StrategyPlanDraft

MAX_PLAN_READ = 100


def draft_strategy_plan(assessment_id: str, assessment: ORBAssessment) -> StrategyPlanDraft:
    """Translate deterministic assessment status into a non-executable plan draft."""
    values: dict = {
        "assessment_id": assessment_id,
        "snapshot_id": assessment.snapshot_id,
        "strategy_id": assessment.strategy_id,
        "version": assessment.version,
        "definition_fingerprint": assessment.definition_fingerprint,
        "session_key": assessment.session_key,
        "as_of": assessment.as_of,
        "reason_codes": assessment.reason_codes,
        "evidence_ids": assessment.evidence_ids,
    }
    if assessment.status in {"BULLISH_SETUP", "BEARISH_SETUP"}:
        required = (
            assessment.range_high, assessment.range_low, assessment.range_width,
            assessment.buffer, assessment.trigger_close, assessment.invalidation,
            assessment.target, assessment.expires_at,
        )
        if any(value is None for value in required):
            raise ValueError("PLAN_SETUP_ASSESSMENT_INCOMPLETE")
        high, low, width, buffer, _, invalidation, target, expires_at = (
            cast(Decimal, assessment.range_high),
            cast(Decimal, assessment.range_low),
            cast(Decimal, assessment.range_width),
            cast(Decimal, assessment.buffer),
            cast(Decimal, assessment.trigger_close),
            cast(Decimal, assessment.invalidation),
            cast(Decimal, assessment.target),
            assessment.expires_at,
        )
        bullish = assessment.status == "BULLISH_SETUP"
        values.update(
            outcome="FIT",
            direction="BULLISH" if bullish else "BEARISH",
            option_type="CALL" if bullish else "PUT",
            trigger_operator="GT" if bullish else "LT",
            trigger_threshold=(high + buffer) if bullish else (
                low - buffer
            ),
            trigger_ceiling_or_floor=(high + width * Decimal("0.25")) if bullish else (
                low - width * Decimal("0.25")
            ),
            invalidation=invalidation,
            target=target,
            valid_until=expires_at,
        )
    elif assessment.status in {"UNAVAILABLE", "NOT_READY"}:
        values["outcome"] = "INSUFFICIENT_DATA"
    elif assessment.status == "NOT_APPLICABLE":
        values["outcome"] = "OUT_OF_SCOPE"
    else:
        values["outcome"] = "DOES_NOT_FIT"
    plan_id = hashlib.sha256(
        json.dumps(
            {key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
             for key, value in values.items()},
            sort_keys=True, separators=(",", ":"), default=str,
        ).encode()
    ).hexdigest()
    return StrategyPlanDraft(plan_id=plan_id, **values)


def persist_plan_draft(
    session: Session, plan: StrategyPlanDraft
) -> StrategyPlanDraftRecord:
    """Save a plan only when it matches its stored immutable assessment."""
    assessment_row = session.get(StrategyAssessmentRecord, plan.assessment_id)
    if assessment_row is None:
        raise ValueError("PLAN_ASSESSMENT_NOT_FOUND")
    assessment = ORBAssessment.model_validate(assessment_row.payload)
    expected = draft_strategy_plan(plan.assessment_id, assessment)
    if plan != expected:
        raise ValueError("PLAN_ASSESSMENT_LINK_MISMATCH")
    existing = session.get(StrategyPlanDraftRecord, plan.assessment_id)
    if existing is not None:
        if existing.payload != plan.model_dump(mode="json"):
            raise ValueError("PLAN_IMMUTABILITY_CONFLICT")
        return existing
    record = StrategyPlanDraftRecord(
        assessment_id=plan.assessment_id,
        plan_id=plan.plan_id,
        strategy_id=plan.strategy_id,
        version=plan.version,
        session_key=date.fromisoformat(plan.session_key),
        as_of=plan.as_of,
        outcome=plan.outcome,
        payload=plan.model_dump(mode="json"),
    )
    session.add(record)
    session.flush()
    return record


def read_plan_drafts(
    session: Session,
    *,
    session_key: date,
    as_of: datetime,
    limit: int = MAX_PLAN_READ,
) -> tuple[StrategyPlanDraft, ...]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("PLAN_AWARE_AS_OF_REQUIRED")
    if not 1 <= limit <= MAX_PLAN_READ:
        raise ValueError("PLAN_READ_LIMIT_INVALID")
    rows = session.scalars(
        select(StrategyPlanDraftRecord)
        .where(
            StrategyPlanDraftRecord.session_key == session_key,
            StrategyPlanDraftRecord.as_of <= as_of,
        )
        .order_by(StrategyPlanDraftRecord.as_of.desc(), StrategyPlanDraftRecord.plan_id.desc())
        .limit(limit)
    )
    return tuple(StrategyPlanDraft.model_validate(row.payload) for row in rows)
