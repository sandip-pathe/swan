from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from services.api.auth import account_identity
from services.api.strategy_records import router
from services.core.models import (
    IndexHistoryBatch,
    StrategyAssessmentRecord,
    StrategyPlanDraftRecord,
    StrategyResearchCandidateRecord,
)
from services.strategies.research_store import make_candidate, persist_candidate


def test_research_candidate_api_is_authenticated_read_only_and_as_of_bounded():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    IndexHistoryBatch.__table__.create(engine)
    StrategyAssessmentRecord.__table__.create(engine)
    StrategyPlanDraftRecord.__table__.create(engine)
    StrategyResearchCandidateRecord.__table__.create(engine)
    created_at = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    candidate = make_candidate(
        strategy_id="S01-NIFTY-ORB", version="0.2-research", parent_version="0.1-setup",
        hypothesis="Test a bounded filter.", scope="NIFTY research only", evidence_ids=(),
        assumptions=(), evaluation_method="Chronological held-out comparison.",
    )
    with Session(engine) as db:
        persist_candidate(db, candidate, created_at=created_at)
        db.commit()

    app = FastAPI()
    app.state.engine = engine
    app.include_router(router)
    app.dependency_overrides[account_identity] = lambda: uuid4()
    client = TestClient(app)
    try:
        before = client.get(
            "/api/strategies/research-candidates",
            params={"as_of": "2026-11-20T09:59:00Z"},
        )
        after = client.get(
            "/api/strategies/research-candidates",
            params={"as_of": "2026-11-20T10:00:00Z"},
        )
        assert before.status_code == 200 and before.json() == []
        assert after.status_code == 200 and after.json()[0]["candidate_id"] == candidate.candidate_id
        assert client.get(
            "/api/strategies/assessments",
            params={"session_key": "2026-11-20", "as_of": "2026-11-20T10:00:00Z"},
        ).json() == []
        assert client.get(
            "/api/strategies/plans",
            params={"session_key": "2026-11-20", "as_of": "2026-11-20T10:00:00Z"},
        ).json() == []
        assert client.post("/api/strategies/research-candidates").status_code == 405
        app.dependency_overrides.pop(account_identity)
        assert client.get(
            "/api/strategies/research-candidates",
            params={"as_of": "2026-11-20T10:00:00Z"},
        ).status_code == 401
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()
