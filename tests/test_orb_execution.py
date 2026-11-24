"""Isolated ORB mapping and exit contracts; no account activation or providers."""

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.core.contracts import IST, StrategyEnvelope, UnderlyingExitPolicy
from services.market.reference_contracts import IndexReference
from services.strategies.contracts import ORBAssessment, ORBPaperMandate, StrategyPaperPlanCandidate
from services.strategies.orb_execution import prepare_orb_execution
from services.strategies.plan_store import draft_strategy_plan


def candidate(now):
    assessment = ORBAssessment(
        strategy_id="S01-NIFTY-ORB", version="0.1-setup", definition_fingerprint="f" * 64,
        snapshot_id="b" * 64, as_of=now, session_key=now.date().isoformat(),
        status="BULLISH_SETUP", reason_codes=("BULLISH_TRIGGER",), evidence_ids=("bar",),
        range_high=Decimal("25000"), range_low=Decimal("24900"),
        range_width=Decimal("100"), buffer=Decimal("5"), trigger_close=Decimal("25010"),
        invalidation=Decimal("24995"), target=Decimal("25110"),
        expires_at=now + timedelta(seconds=30),
    )
    plan = draft_strategy_plan("a" * 64, assessment)
    mandate = ORBPaperMandate()
    fingerprint = hashlib.sha256(json.dumps(
        mandate.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    assignment, artifact = uuid4(), uuid4()
    identity = {"candidate_version": "0.1-candidate", "source_plan_id": plan.plan_id,
                "review_assignment_id": str(assignment), "review_artifact_id": str(artifact),
                "mandate_fingerprint": fingerprint}
    from services.strategies.paper_plan_candidates import PAPER_CANDIDATE_BLOCKERS

    return StrategyPaperPlanCandidate(
        candidate_id=hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(), source_plan=plan, mandate=mandate,
        mandate_fingerprint=fingerprint, review_assignment_id=assignment,
        review_artifact_id=artifact, reviewed_at=now, blocker_codes=PAPER_CANDIDATE_BLOCKERS,
    )


def prepare(scenario, **updates):
    now = datetime(2026, 11, 13, 9, 31, 30, tzinfo=IST)
    instrument = scenario.instrument.model_copy(update={
        "exchange": "NFO", "strike": Decimal("25000"),
        "verified_at": now - timedelta(minutes=20),
    })
    from services.core.contracts import DepthLevel

    quote = scenario.quote.model_copy(update={
        "timestamp": now, "received_at": now, "market_event_id": "unit-event",
        "timestamp_basis": "exchange_feed", "depth_kind": "best_five",
        "quantity_unit": "units", "quantity_unit_source": "isolated-test",
        "bid_depth": (DepthLevel(price=scenario.quote.bid, quantity=200),),
        "ask_depth": (DepthLevel(price=scenario.quote.ask, quantity=200),),
    })
    args = dict(
        candidate=candidate(now), account_id=uuid4(), instruments=[instrument],
        quotes={instrument.id: quote}, session=scenario.session, risk=scenario.config, now=now,
        reference=IndexReference(underlying="NIFTY", exchange="NSE", provider_token="test",
                                 timestamp=now, received_at=now, last_price="25010"),
    )
    args.update(updates)
    return prepare_orb_execution(**args), args


def test_underlying_target_has_no_invented_premium_target(scenario):
    result, inputs = prepare(scenario)
    assert result.envelope.target is None and result.decision.target is None
    assert result.envelope.underlying_exit_policy.target == Decimal("25110")
    assert result.envelope.max_holding_seconds <= 300
    assert result.envelope.stop_loss == Decimal("80.00")
    assert result.envelope.expires_at == inputs["candidate"].source_plan.valid_until
    assert inputs["candidate"].execution_eligible is False
    # Same account/session has one deterministic entry identity across candidates.
    again, _ = prepare(scenario, account_id=inputs["account_id"])
    assert again.decision.id == result.decision.id


@pytest.mark.parametrize("price", ["25005", "25026", "24994", "25110"])
def test_rejects_lost_or_chased_setup(scenario, price):
    now = datetime(2026, 11, 13, 9, 31, 30, tzinfo=IST)
    reference = IndexReference(underlying="NIFTY", exchange="NSE", provider_token="test",
                               timestamp=now, received_at=now, last_price=price)
    with pytest.raises(ValueError, match="PREDICATE"):
        prepare(scenario, reference=reference)


def test_no_fallback_when_selected_contract_has_no_quote(scenario):
    with pytest.raises(ValueError, match="QUOTE_UNAVAILABLE"):
        prepare(scenario, quotes={})


def test_premium_stop_uses_actual_fill_and_rounds_toward_protection():
    policy = UnderlyingExitPolicy(underlying="NIFTY", direction="BULLISH",
                                  invalidation="24995", target="25110",
                                  premium_stop_fraction="0.20")
    assert policy.premium_stop(Decimal("98.03"), Decimal("0.05")) == Decimal("78.45")


def test_no_premium_target_requires_underlying_exit_policy(scenario):
    payload = scenario.envelope.model_dump()
    payload["target"] = None
    with pytest.raises(ValidationError, match="underlying exit policy"):
        StrategyEnvelope.model_validate(payload)
