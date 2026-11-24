from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.core.contracts import IST
from services.core.models import (
    IndexHistoryBatch,
    StrategyAssessmentRecord,
    StrategyPlanDraftRecord,
)
from services.strategies.contracts import ORBAssessment
from services.strategies.plan_store import (
    draft_strategy_plan,
    persist_plan_draft,
    read_plan_drafts,
)


def test_plan_draft_preserves_trigger_and_stays_non_executable():
    engine = create_engine("sqlite://")
    IndexHistoryBatch.__table__.create(engine)
    StrategyAssessmentRecord.__table__.create(engine)
    StrategyPlanDraftRecord.__table__.create(engine)
    assessment_id = "a" * 64
    as_of = datetime(2026, 11, 20, 9, 31, 59, tzinfo=IST)
    assessment = ORBAssessment(
        strategy_id="S01-NIFTY-ORB", version="0.1-setup", definition_fingerprint="f" * 64,
        snapshot_id="b" * 64, as_of=as_of, session_key="2026-11-20",
        status="BULLISH_SETUP", reason_codes=("BULLISH_TRIGGER",),
        evidence_ids=("bar-open", "bar-trigger"), range_high=Decimal("102"),
        range_low=Decimal("99"), range_width=Decimal("3"), buffer=Decimal("0.15"),
        trigger_evidence_id="bar-trigger", trigger_closes_at=datetime(2026, 11, 20, 9, 31, tzinfo=IST),
        trigger_close=Decimal("102.2"), invalidation=Decimal("101.85"),
        target=Decimal("105.2"), expires_at=datetime(2026, 11, 20, 9, 32, tzinfo=IST),
    )
    with Session(engine) as db:
        db.add(IndexHistoryBatch(
            snapshot_id=assessment.snapshot_id, underlying="NIFTY", exchange="NSE",
            session_key=date(2026, 11, 20), received_at=as_of, source="fixture",
            response_sha256="c" * 64, provider_request={}, payload={"bars": []},
        ))
        db.flush()
        db.add(StrategyAssessmentRecord(
            id=assessment_id, snapshot_id=assessment.snapshot_id,
            strategy_id=assessment.strategy_id, version=assessment.version,
            definition_fingerprint=assessment.definition_fingerprint,
            session_key=date(2026, 11, 20), as_of=as_of, status=assessment.status,
            payload=assessment.model_dump(mode="json"),
        ))
        db.commit()
        plan = draft_strategy_plan(assessment_id, assessment)
        assert plan.outcome == "FIT" and plan.execution_eligible is False
        assert plan.trigger_operator == "GT" and plan.trigger_threshold == Decimal("102.15")
        assert plan.option_type == "CALL" and plan.maximum_holding_seconds == 300
        assert plan.maximum_expiry_days == 7 and plan.maximum_entry_attempts_per_session == 1
        assert plan.valid_until == assessment.expires_at
        saved = persist_plan_draft(db, plan)
        db.commit()
        assert persist_plan_draft(db, plan).plan_id == saved.plan_id
        assert read_plan_drafts(
            db, session_key=date(2026, 11, 20), as_of=as_of.replace(minute=30)
        ) == ()
        assert read_plan_drafts(
            db, session_key=date(2026, 11, 20), as_of=as_of
        )[0] == plan
    engine.dispose()


def test_missing_evidence_maps_to_insufficient_data_not_failure():
    assessment = ORBAssessment(
        strategy_id="S01-NIFTY-ORB", version="0.1-setup", definition_fingerprint="f" * 64,
        snapshot_id="b" * 64, as_of=datetime(2026, 11, 20, 9, 20, tzinfo=IST),
        session_key="2026-11-20", status="UNAVAILABLE", reason_codes=("OPENING_RANGE_GAP",),
    )
    plan = draft_strategy_plan("a" * 64, assessment)
    assert plan.outcome == "INSUFFICIENT_DATA"
    assert plan.execution_eligible is False
