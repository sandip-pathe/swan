"""Estimated fee accounting must disclose assumptions without weakening depth gates."""

from datetime import date
from decimal import Decimal

import pytest

from services.core.execution import REQUIRED_FEE_CODES, ExecutionPolicy, FeeSchedule
from services.paper.fees import FeeContext, incremental_fees


def estimated_schedule():
    source = {
        "url": "https://example.test/simulation-policy",
        "checked_at": "2026-11-23T00:00:00Z",
        "finding": "Explicit test-only rounding and fee assumptions, not broker facts",
        "status": "assumed",
    }
    return {
        "version": "test-estimated", "exchange": "NFO",
        "effective_from": "2026-11-23", "reviewed": True,
        "calculation_basis": "estimated", "account_pricing_verified": False,
        "notes": "Test-only estimated fee arithmetic",
        "rules": [
            {"code": code, "sides": ["BUY", "SELL"],
             "calculation": "flat_per_order", "amount": "20" if code == "BROKERAGE" else "0",
             "rounding_increment": "0.01", "rounding_mode": "HALF_UP",
             "rounding_scope": "cumulative_order", "sources": [source]}
            for code in sorted(REQUIRED_FEE_CODES)
        ],
    }


def test_estimated_schedule_books_flat_fee_once_across_partial_fills():
    schedule = FeeSchedule.model_validate(estimated_schedule())
    assert not schedule.blockers() and schedule.applies(date(2026, 11, 23))
    first = incremental_fees(schedule, FeeContext(side="BUY", premium=Decimal(0), booked={}), Decimal(100))
    second = incremental_fees(schedule, FeeContext(side="BUY", premium=Decimal(100), booked=first), Decimal(100))
    assert sum(first.values()) == 20 and sum(second.values()) == 0


def test_estimates_cannot_be_promoted_to_documented_or_omit_components():
    payload = estimated_schedule()
    with pytest.raises(ValueError):
        FeeSchedule.model_validate({**payload, "calculation_basis": "documented", "account_pricing_verified": True})
    with pytest.raises(ValueError):
        FeeSchedule.model_validate({**payload, "rules": payload["rules"][:-1]})
    payload["rules"][0]["sources"][0]["status"] = "unverified"
    with pytest.raises(ValueError):
        FeeSchedule.model_validate(payload)


def test_fee_assumptions_cannot_verify_depth_or_reusable_sale_proceeds():
    source = estimated_schedule()["rules"][0]["sources"][0]
    policy = ExecutionPolicy.model_validate({
        "version": "test", "reviewed": True, "notes": "Test only",
        "quantity_unit": "units", "quantity_unit_sources": [source],
        "sale_proceeds_reuse": "same_session_verified", "sale_proceeds_sources": [source],
    })
    assert "QUANTITY_UNIT_UNVERIFIED" in policy.blockers()
    assert "SALE_PROCEEDS_REUSE_UNVERIFIED" in policy.blockers()
