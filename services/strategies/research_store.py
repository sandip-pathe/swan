"""Immutable persistence for inactive strategy research candidates."""

import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.models import StrategyResearchCandidateRecord
from services.strategies.contracts import StrategyResearchCandidate

MAX_CANDIDATE_READ = 100


def make_candidate(**values) -> StrategyResearchCandidate:
    """Assign deterministic identity to a candidate's complete research content."""
    normalized = StrategyResearchCandidate(
        candidate_id="0" * 64, **values
    ).model_dump(exclude={"candidate_id"})
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    return StrategyResearchCandidate(
        candidate_id=hashlib.sha256(canonical.encode()).hexdigest(), **normalized
    )


def persist_candidate(
    session: Session, candidate: StrategyResearchCandidate, *, created_at: datetime
) -> StrategyResearchCandidateRecord:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("CANDIDATE_AWARE_CREATED_AT_REQUIRED")
    expected = make_candidate(**candidate.model_dump(exclude={"candidate_id"}))
    if candidate != expected:
        raise ValueError("CANDIDATE_ID_MISMATCH")
    existing = session.get(StrategyResearchCandidateRecord, candidate.candidate_id)
    if existing is not None:
        if existing.payload != candidate.model_dump(mode="json"):
            raise ValueError("CANDIDATE_IMMUTABILITY_CONFLICT")
        return existing
    row = StrategyResearchCandidateRecord(
        candidate_id=candidate.candidate_id,
        strategy_id=candidate.strategy_id,
        version=candidate.version,
        created_at=created_at,
        payload=candidate.model_dump(mode="json"),
    )
    session.add(row)
    session.flush()
    return row


def read_candidates(
    session: Session, *, as_of: datetime, limit: int = MAX_CANDIDATE_READ
) -> tuple[StrategyResearchCandidate, ...]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("CANDIDATE_AWARE_AS_OF_REQUIRED")
    if not 1 <= limit <= MAX_CANDIDATE_READ:
        raise ValueError("CANDIDATE_READ_LIMIT_INVALID")
    rows = session.scalars(
        select(StrategyResearchCandidateRecord)
        .where(StrategyResearchCandidateRecord.created_at <= as_of)
        .order_by(
            StrategyResearchCandidateRecord.created_at.desc(),
            StrategyResearchCandidateRecord.candidate_id.desc(),
        )
        .limit(limit)
    )
    return tuple(StrategyResearchCandidate.model_validate(row.payload) for row in rows)
