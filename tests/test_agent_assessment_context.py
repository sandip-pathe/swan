from datetime import datetime

import pytest
from pydantic import ValidationError

from services.agents.assessment_workflow import (
    AnalystDraft,
    AssessmentContext,
    AssessmentWorkflow,
    validate_analyst_output,
)
from services.core.contracts import IST
from services.market.settings import ProviderError


def test_analyst_selection_is_bound_to_assessment_strategy_and_evidence():
    context = _context()
    valid = AnalystDraft(
        disposition="SELECT", assessment_id="assessment-1", strategy_id="S01-NIFTY-ORB",
        strategy_version="0.1-setup", rationale="Setup fits", evidence_ids=["bar-1"],
        draft="Research-only plan draft",
    )
    validate_analyst_output(valid, context)
    with pytest.raises(ProviderError, match="UNKNOWN_ASSESSMENT"):
        validate_analyst_output(valid.model_copy(update={"assessment_id": "invented"}), context)
    with pytest.raises(ProviderError, match="VERSION_MISMATCH"):
        validate_analyst_output(valid.model_copy(update={"strategy_version": "9"}), context)
    with pytest.raises(ProviderError, match="UNKNOWN_OR_MISSING_EVIDENCE"):
        validate_analyst_output(valid.model_copy(update={"evidence_ids": ["unknown"]}), context)


def test_unavailable_assessment_cannot_become_a_strategy_selection():
    context = _context(status="UNAVAILABLE")
    model_output = AnalystDraft(
        disposition="SELECT", assessment_id="assessment-1", strategy_id="S01-NIFTY-ORB",
        strategy_version="0.1-setup", rationale="Claimed setup", evidence_ids=["bar-1"],
        draft="Attempted selection",
    )
    with pytest.raises(ProviderError, match="INELIGIBLE_STRATEGY"):
        validate_analyst_output(model_output, context)
    with pytest.raises(ValidationError):
        AnalystDraft(
            disposition="DRAFT", assessment_id="assessment-1", rationale="Legacy",
            evidence_ids=["bar-1"],
        )


def test_expired_assessment_context_is_rejected():
    with pytest.raises(ProviderError, match="ASSESSMENT_CONTEXT_EXPIRED"):
        AssessmentWorkflow._guard_context_expiry(_context())


def _context(*, status: str = "BULLISH_SETUP") -> AssessmentContext:
    return AssessmentContext(
        assessment_id="assessment-1", strategy_id="S01-NIFTY-ORB", version="0.1-setup",
        definition_fingerprint="f" * 64, snapshot_id="snapshot-1", status=status,
        evidence_ids=("bar-1",), as_of=datetime(2026, 11, 20, 9, 30, tzinfo=IST),
        expires_at=datetime(2026, 11, 20, 9, 31, tzinfo=IST),
    )
