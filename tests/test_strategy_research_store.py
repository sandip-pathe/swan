from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.core.models import StrategyResearchCandidateRecord
from services.strategies.contracts import StrategyPlanDraft, StrategyResearchCandidate
from services.strategies.paper_admission import preflight_strategy_plan
from services.strategies.research_store import make_candidate, persist_candidate, read_candidates


def test_strategy_plan_fails_closed_before_paper_order_path():
    plan = StrategyPlanDraft(
        plan_id="a" * 64, assessment_id="b" * 64, snapshot_id="snapshot",
        strategy_id="S01-NIFTY-ORB", version="0.1-setup", definition_fingerprint="c" * 64,
        session_key="2026-11-20", as_of=datetime(2026, 11, 20, 9, 30, tzinfo=UTC),
        outcome="FIT", reason_codes=("BULLISH_TRIGGER",), evidence_ids=("bar-1",),
    )
    result = preflight_strategy_plan(plan)
    assert result.admitted is False
    assert result.blockers == ("PLAN_RESEARCH_ONLY", "MANDATE_NOT_REVIEWED")


def test_candidate_is_immutable_inactive_and_as_of_bounded():
    engine = create_engine("sqlite://")
    StrategyResearchCandidateRecord.__table__.create(engine)
    candidate = make_candidate(
        strategy_id="S01-NIFTY-ORB", version="0.2-research", parent_version="0.1-setup",
        hypothesis="A tighter opening range filter may reduce false breakouts.",
        scope="NIFTY intraday, research only", evidence_ids=("assessment-1",),
        assumptions=("Chronological comparison",),
        evaluation_method="Compare setup frequency and later outcomes on held-out sessions.",
    )
    assert isinstance(candidate, StrategyResearchCandidate)
    created_at = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    with Session(engine) as db:
        persist_candidate(db, candidate, created_at=created_at)
        db.commit()
        assert read_candidates(db, as_of=created_at.replace(hour=9, minute=59)) == ()
        assert read_candidates(db, as_of=created_at) == (candidate,)
    engine.dispose()
