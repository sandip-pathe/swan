from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.core.contracts import IST
from services.core.models import IndexHistoryBatch, StrategyAssessmentRecord
from services.strategies.assessment_store import persist_assessment, read_assessments
from services.strategies.contracts import ORBAssessment


def test_assessments_are_immutable_evidence_linked_and_as_of_bounded():
    engine = create_engine("sqlite://")
    IndexHistoryBatch.__table__.create(engine)
    StrategyAssessmentRecord.__table__.create(engine)
    now = datetime(2026, 11, 20, 9, 30, tzinfo=IST)
    with Session(engine) as session:
        session.add(
            IndexHistoryBatch(
                snapshot_id="snapshot-1", underlying="NIFTY", exchange="NSE",
                session_key=date(2026, 11, 20), received_at=now, source="fixture",
                response_sha256="a" * 64, provider_request={},
                payload={"bars": [{"evidence_id": "bar-1"}]},
            )
        )
        session.commit()
        assessment = _assessment(now)
        first = persist_assessment(session, assessment)
        session.commit()
        assert persist_assessment(session, assessment).id == first.id
        assert read_assessments(
            session, session_key=date(2026, 11, 20), as_of=now.replace(minute=29)
        ) == ()
        assert read_assessments(
            session, session_key=date(2026, 11, 20), as_of=now
        )[0].evidence_ids == ("bar-1",)
        with pytest.raises(ValueError, match="UNKNOWN_EVIDENCE"):
            persist_assessment(session, _assessment(now, evidence_id="invented"))
    engine.dispose()


def _assessment(as_of: datetime, *, evidence_id: str = "bar-1") -> ORBAssessment:
    return ORBAssessment(
        strategy_id="S01-NIFTY-ORB", version="0.1-setup", definition_fingerprint="f" * 64,
        snapshot_id="snapshot-1", as_of=as_of, session_key="2026-11-20",
        status="NO_SETUP", reason_codes=("NO_TRIGGER_YET",), evidence_ids=(evidence_id,),
    )
