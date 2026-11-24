"""Persist one immutable index snapshot and its deterministic strategy assessment."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from services.core.contracts import IST, ExchangeSession
from services.market.index_history import IndexHistoryResult
from services.market.index_history_store import persist_index_history
from services.strategies.assessment_store import persist_assessment
from services.strategies.contracts import ORBAssessment, ORBSnapshot
from services.strategies.orb import evaluate_orb


class IndexAssessmentCapture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    assessment_id: str
    source: str
    received_at: str
    response_sha256: str
    bar_count: int
    assessment: ORBAssessment


def persist_index_assessment(
    session: Session,
    *,
    result: IndexHistoryResult,
    exchange_session: ExchangeSession,
) -> IndexAssessmentCapture:
    """Save source data first, then evaluate only that exact received snapshot."""
    if result.received_at.astimezone(IST).date() != exchange_session.key:
        raise ValueError("INDEX_ASSESSMENT_RECEIPT_SESSION_MISMATCH")
    if result.underlying != "NIFTY" or result.exchange != "NSE":
        raise ValueError("INDEX_ASSESSMENT_UNSUPPORTED_SOURCE")

    snapshot = ORBSnapshot(
        snapshot_id=result.snapshot_id,
        source=result.source,
        underlying=result.underlying,
        exchange=result.exchange,
        as_of=result.received_at.astimezone(IST),
        bars=result.bars,
    )
    persist_index_history(session, result)
    assessment = evaluate_orb(snapshot, exchange_session)
    saved = persist_assessment(session, assessment)
    return IndexAssessmentCapture(
        snapshot_id=result.snapshot_id,
        assessment_id=saved.id,
        source=result.source,
        received_at=result.received_at.isoformat(),
        response_sha256=result.response_sha256,
        bar_count=len(result.bars),
        assessment=assessment,
    )
