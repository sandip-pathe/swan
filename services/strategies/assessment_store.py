"""Immutable storage and bounded reads for deterministic assessments."""

import hashlib
import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.contracts import IST
from services.core.models import IndexHistoryBatch, StrategyAssessmentRecord
from services.strategies.contracts import ORBAssessment

MAX_ASSESSMENT_READ = 100


def persist_assessment(session: Session, assessment: ORBAssessment) -> StrategyAssessmentRecord:
    """Persist an assessment only when its exact source snapshot and evidence exist."""
    batch = session.get(IndexHistoryBatch, assessment.snapshot_id)
    if batch is None:
        raise ValueError("ASSESSMENT_SNAPSHOT_NOT_FOUND")
    received_at = batch.received_at
    if received_at.tzinfo is None:
        # SQLite drops tzinfo in unit tests; production PostgreSQL returns it.
        received_at = received_at.replace(tzinfo=IST)
    if received_at > assessment.as_of:
        raise ValueError("ASSESSMENT_SNAPSHOT_AFTER_AS_OF")
    source_bars = batch.payload.get("bars", [])
    source_ids = {item.get("evidence_id") for item in source_bars if isinstance(item, dict)}
    referenced = set(assessment.evidence_ids) | set(assessment.excluded_bar_ids)
    if not referenced <= source_ids:
        raise ValueError("ASSESSMENT_UNKNOWN_EVIDENCE_ID")

    payload = assessment.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    record_id = hashlib.sha256(canonical.encode()).hexdigest()
    existing = session.get(StrategyAssessmentRecord, record_id)
    if existing is not None:
        return existing
    existing_version = session.scalar(
        select(StrategyAssessmentRecord).where(
            StrategyAssessmentRecord.snapshot_id == assessment.snapshot_id,
            StrategyAssessmentRecord.strategy_id == assessment.strategy_id,
            StrategyAssessmentRecord.version == assessment.version,
        )
    )
    if existing_version is not None:
        if existing_version.payload != payload:
            raise ValueError("ASSESSMENT_DETERMINISM_CONFLICT")
        return existing_version
    record = StrategyAssessmentRecord(
        id=record_id,
        snapshot_id=assessment.snapshot_id,
        strategy_id=assessment.strategy_id,
        version=assessment.version,
        definition_fingerprint=assessment.definition_fingerprint,
        session_key=date.fromisoformat(assessment.session_key),
        as_of=assessment.as_of,
        status=assessment.status,
        payload=payload,
    )
    session.add(record)
    session.flush()
    return record


def read_assessments(
    session: Session,
    *,
    session_key: date,
    as_of: datetime,
    strategy_id: str = "S01-NIFTY-ORB",
    limit: int = MAX_ASSESSMENT_READ,
) -> tuple[ORBAssessment, ...]:
    """Return newest eligible records, capped to a small audit page."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("ASSESSMENT_AWARE_AS_OF_REQUIRED")
    if not 1 <= limit <= MAX_ASSESSMENT_READ:
        raise ValueError("ASSESSMENT_READ_LIMIT_INVALID")
    rows = session.scalars(
        select(StrategyAssessmentRecord)
        .where(
            StrategyAssessmentRecord.session_key == session_key,
            StrategyAssessmentRecord.strategy_id == strategy_id,
            StrategyAssessmentRecord.as_of <= as_of,
        )
        .order_by(StrategyAssessmentRecord.as_of.desc(), StrategyAssessmentRecord.id.desc())
        .limit(limit)
    )
    return tuple(ORBAssessment.model_validate(row.payload) for row in rows)
