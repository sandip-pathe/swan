from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.core.contracts import Quote, RiskConfig, TradeDecision
from services.risk.engine import PortfolioState, evaluate_risk


def state(**changes):
    return replace(
        PortfolioState(Decimal("100000"), Decimal("100000"), Decimal("100000"), enabled=True),
        **changes,
    )


def evaluate(s, **changes):
    arguments = dict(
        decision=s.decision,
        instrument=s.instrument,
        quote=s.quote,
        envelope=s.envelope,
        config=s.config,
        state=state(),
        session=s.session,
        now=s.now,
    )
    arguments.update(changes)
    return evaluate_risk(**arguments)


def test_whole_lots_include_round_trip_costs(scenario):
    result = evaluate(scenario)
    assert result.approved and result.quantity == 100
    assert result.fill_price == Decimal("100.05")
    assert result.planned_risk == Decimal("413.96")
    assert result.planned_risk <= Decimal("500")


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"bid": None}, "MISSING_BID_ASK"),
        ({"oi": None}, "MISSING_METRICS"),
        ({"volume": None}, "MISSING_METRICS"),
        ({"bid": Decimal("101")}, "CROSSED_QUOTE"),
        ({"bid": Decimal("98")}, "EXCESSIVE_SPREAD"),
        ({"volume": 0}, "INSUFFICIENT_LIQUIDITY"),
        ({"ask_quantity": 1}, "ONE_LOT_DOES_NOT_FIT"),
    ],
)
def test_bad_market_data_rejected(scenario, changes, reason):
    assert evaluate(scenario, quote=scenario.quote.model_copy(update=changes)).reason == reason


def test_zero_is_not_missing_when_threshold_allows_it(scenario):
    quote = scenario.quote.model_copy(update={"oi": 0, "volume": 0})
    config = scenario.config.model_copy(update={"min_oi": 0, "min_volume": 0})
    assert evaluate(scenario, quote=quote, config=config).approved


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"enabled": False}, "PAUSED"),
        ({"open_positions": 1}, "POSITION_LIMIT"),
        ({"cash": Decimal("1")}, "ONE_LOT_DOES_NOT_FIT"),
        ({"equity": Decimal("98000")}, "DAILY_LOSS_LIMIT"),
        ({"reconciled": False}, "UNRECONCILED_OR_STALE_PORTFOLIO"),
        ({"valuation_fresh": False}, "UNRECONCILED_OR_STALE_PORTFOLIO"),
        ({"session_matches": False}, "SESSION_UNVERIFIED"),
    ],
)
def test_account_guards(scenario, changes, reason):
    assert evaluate(scenario, state=state(**changes)).reason == reason


def test_one_lot_never_rounds_up(scenario):
    config = scenario.config.model_copy(update={"max_trade_risk_pct": Decimal("0.0001")})
    assert evaluate(scenario, config=config).reason == "ONE_LOT_DOES_NOT_FIT"


def test_remaining_daily_budget_and_reservations(scenario):
    result = evaluate(scenario, state=state(equity=Decimal("98150"), reserved_risk=Decimal("40")))
    assert result.approved and result.quantity == 25
    assert result.budget == Decimal("110")


def test_quote_freshness_boundary_and_future_timestamp(scenario):
    assert evaluate(scenario, now=scenario.now + timedelta(seconds=2)).approved
    assert (
        evaluate(scenario, now=scenario.now + timedelta(seconds=2, microseconds=1)).reason
        == "STALE_QUOTE"
    )
    assert (
        evaluate(
            scenario,
            quote=scenario.quote.model_copy(
                update={"received_at": scenario.now + timedelta(seconds=1)}
            ),
        ).reason
        == "INVALID_QUOTE_TIME"
    )


@pytest.mark.parametrize("days", [-1, 8])
def test_expiry_outside_zero_to_seven_days_rejected(scenario, days):
    instrument = scenario.instrument.model_copy(
        update={"expiry": scenario.session.key + timedelta(days=days)}
    )
    assert evaluate(scenario, instrument=instrument).reason == "INELIGIBLE_EXPIRY"


@pytest.mark.parametrize("days", [0, 7])
def test_expiry_day_and_seven_day_boundary_allowed(scenario, days):
    instrument = scenario.instrument.model_copy(
        update={"expiry": scenario.session.key + timedelta(days=days)}
    )
    assert evaluate(scenario, instrument=instrument).approved


def test_closed_market_and_cutoff(scenario):
    assert (
        evaluate(scenario, now=scenario.session.opens_at - timedelta(seconds=1)).reason
        == "MARKET_CLOSED"
    )
    assert evaluate(scenario, now=scenario.session.closes_at).reason == "MARKET_CLOSED"
    assert (
        evaluate(scenario, now=scenario.session.closes_at - timedelta(minutes=20)).reason
        == "ENTRY_CUTOFF"
    )
    assert (
        evaluate(scenario, session=scenario.session.model_copy(update={"verified": False})).reason
        == "SESSION_UNVERIFIED"
    )


def test_invalidated_expired_and_mismatching_envelopes(scenario):
    assert (
        evaluate(
            scenario, envelope=scenario.envelope.model_copy(update={"invalidated": True})
        ).reason
        == "INVALID_STRATEGY_ENVELOPE"
    )
    assert (
        evaluate(
            scenario, envelope=scenario.envelope.model_copy(update={"expires_at": scenario.now})
        ).reason
        == "INVALID_STRATEGY_ENVELOPE"
    )
    assert (
        evaluate(
            scenario, decision=scenario.decision.model_copy(update={"strategy_id": uuid4()})
        ).reason
        == "STRATEGY_MISMATCH"
    )
    assert (
        evaluate(
            scenario, decision=scenario.decision.model_copy(update={"stop_loss": Decimal("95")})
        ).reason
        == "STRATEGY_PRICE_MISMATCH"
    )
    assert (
        evaluate(
            scenario, instrument=scenario.instrument.model_copy(update={"option_type": "PUT"})
        ).reason
        == "OPTION_TYPE_MISMATCH"
    )


def test_entry_rule_and_partial_greeks(scenario):
    assert (
        evaluate(
            scenario, envelope=scenario.envelope.model_copy(update={"min_entry": Decimal("100.50")})
        ).reason
        == "ENTRY_PREDICATE_FAILED"
    )
    envelope = scenario.envelope.model_copy(update={"required_metrics": ("greeks",)})
    assert evaluate(scenario, envelope=envelope).reason == "MISSING_METRICS"
    assert (
        evaluate(
            scenario, envelope=envelope, quote=scenario.quote.model_copy(update={"greeks": {}})
        ).reason
        == "MISSING_METRICS"
    )


def test_contracts_reject_unsafe_input(scenario):
    with pytest.raises(ValidationError):
        Quote.model_validate({**scenario.quote.model_dump(), "bid": "NaN"})
    with pytest.raises(ValidationError):
        Quote.model_validate({**scenario.quote.model_dump(), "timestamp": "2026-11-13T09:30:00"})
    with pytest.raises(ValidationError):
        RiskConfig.model_validate({"version": "incomplete"})
    with pytest.raises(ValidationError):
        TradeDecision.model_validate({**scenario.decision.model_dump(), "action": "WAIT"})
    with pytest.raises(ValidationError):
        TradeDecision.model_validate({**scenario.decision.model_dump(), "quantity": 500})


def test_wait_never_creates_risk_approval(scenario):
    decision = TradeDecision(
        action="WAIT",
        timestamp=scenario.now,
        expires_at=scenario.now + timedelta(seconds=60),
        rationale="No setup",
    )
    assert evaluate(scenario, decision=decision).reason == "WAIT"
