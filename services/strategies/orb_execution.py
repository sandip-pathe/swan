"""Translate reviewed ORB evidence into paper contracts, without granting permission."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR
from uuid import NAMESPACE_URL, UUID, uuid5

from services.core.contracts import (
    IST,
    ExchangeSession,
    Instrument,
    Quote,
    RiskConfig,
    StrategyEnvelope,
    TradeDecision,
    UnderlyingExitPolicy,
)
from services.market.reference_contracts import IndexReference
from services.risk.engine import quote_problem
from services.strategies.contracts import StrategyPaperPlanCandidate


@dataclass(frozen=True)
class PreparedORB:
    instrument: Instrument
    envelope: StrategyEnvelope
    decision: TradeDecision


def prepare_orb_execution(
    candidate: StrategyPaperPlanCandidate,
    *,
    account_id: UUID,
    instruments: list[Instrument],
    quotes: dict[str, Quote],
    reference: IndexReference,
    session: ExchangeSession,
    risk: RiskConfig,
    now: datetime,
) -> PreparedORB:
    """Pure mapping only. Caller must separately verify provenance and account authority.

    The immutable research candidate remains blocked. This result is an input to
    existing paper admission, never evidence that qualification or arming passed.
    """
    plan = candidate.source_plan
    if (
        now.tzinfo is None or not session.verified
        or not session.opens_at <= now < session.closes_at
        or plan.session_key != session.key.isoformat()
        or plan.as_of > now or candidate.reviewed_at > now
        or plan.valid_until is None or not now < plan.valid_until
    ):
        raise ValueError("ORB_OPPORTUNITY_NOT_CURRENT")
    if (
        reference.underlying != "NIFTY" or reference.exchange != "NSE"
        or not 0 <= (now - reference.timestamp).total_seconds() <= risk.quote_max_age_seconds
        or not 0 <= (now - reference.received_at).total_seconds() <= risk.quote_max_age_seconds
    ):
        raise ValueError("ORB_UNDERLYING_NOT_FRESH")
    if any(value is None for value in (
        plan.trigger_threshold, plan.trigger_ceiling_or_floor, plan.invalidation, plan.target,
    )):
        raise ValueError("ORB_PLAN_LEVELS_MISSING")
    assert plan.trigger_threshold is not None and plan.trigger_ceiling_or_floor is not None
    assert plan.invalidation is not None and plan.target is not None
    price = reference.last_price
    if plan.direction == "BULLISH":
        matches = plan.trigger_threshold < price <= plan.trigger_ceiling_or_floor
        matches = matches and plan.invalidation < price < plan.target
    elif plan.direction == "BEARISH":
        matches = plan.trigger_ceiling_or_floor <= price < plan.trigger_threshold
        matches = matches and plan.target < price < plan.invalidation
    else:
        raise ValueError("ORB_DIRECTION_INVALID")
    if not matches:
        raise ValueError("ORB_UNDERLYING_PREDICATE_FAILED")
    pool = [item for item in instruments if (
        item.underlying == "NIFTY" and item.exchange == "NFO"
        and item.option_type == plan.option_type
        and 0 < (item.expiry - session.key).days <= plan.maximum_expiry_days
    )]
    if not pool:
        raise ValueError("ORB_OPTION_CONTRACT_UNAVAILABLE")
    expiry = min(item.expiry for item in pool)
    instrument = min(
        (item for item in pool if item.expiry == expiry),
        key=lambda item: (abs(item.strike - price), item.strike, item.id),
    )
    if (
        instrument.verified_at > now
        or instrument.verified_at.astimezone(IST).date() != session.key
    ):
        raise ValueError("ORB_METADATA_NOT_CURRENT")
    quote = quotes.get(instrument.id)
    if quote is None or quote_problem(quote, now, risk.quote_max_age_seconds):
        raise ValueError("ORB_EXECUTABLE_QUOTE_UNAVAILABLE")
    if (
        quote.instrument_id != instrument.id or not quote.ask_depth or not quote.bid_depth
        or quote.depth_kind != "best_five" or quote.timestamp_basis != "exchange_feed"
        or quote.quantity_unit == "unknown" or not quote.market_event_id
    ):
        raise ValueError("ORB_EXECUTABLE_DEPTH_UNAVAILABLE")
    assert quote.ask is not None
    if quote.ask % instrument.tick_size:
        raise ValueError("ORB_ASK_OFF_TICK")
    policy = UnderlyingExitPolicy(
        underlying="NIFTY", direction=plan.direction,
        invalidation=plan.invalidation, target=plan.target,
        premium_stop_fraction=candidate.mandate.premium_stop_fraction,
        entry_lower=min(plan.trigger_threshold, plan.trigger_ceiling_or_floor),
        entry_upper=max(plan.trigger_threshold, plan.trigger_ceiling_or_floor),
        entry_deadline_only=True,
    )
    stop = policy.premium_stop(quote.ask, instrument.tick_size)
    # Admission estimates loss conservatively at the maximum entry price. Actual
    # position protection is recalculated from average fills by the paper ledger.
    minimum = max(stop + instrument.tick_size, instrument.tick_size)
    minimum = (minimum / instrument.tick_size).to_integral_value(
        rounding=ROUND_FLOOR
    ) * instrument.tick_size
    if minimum > quote.ask:
        raise ValueError("ORB_PREMIUM_STOP_NOT_REPRESENTABLE")
    identifier = uuid5(NAMESPACE_URL, f"swan:orb-paper:{account_id}:{session.key}")
    envelope = StrategyEnvelope(
        id=identifier, version="S01-NIFTY-ORB-PAPER:0.2-underlying-target",
        instrument_ids=(instrument.id,),
        action="BUY_CALL" if instrument.option_type == "CALL" else "BUY_PUT",
        issued_at=now, expires_at=plan.valid_until, evidence_ids=(quote.id,),
        min_entry=minimum, max_entry=quote.ask, stop_loss=stop, target=None,
        max_holding_seconds=min(risk.max_holding_seconds, 300),
        underlying_exit_policy=policy,
    )
    decision = TradeDecision(
        id=uuid5(identifier, str(account_id)), action=envelope.action,
        timestamp=now, expires_at=min(plan.valid_until, now + timedelta(seconds=5)),
        rationale=f"Reviewed ORB candidate {candidate.candidate_id}",
        snapshot_ids=(quote.id,), instrument_id=instrument.id,
        entry=quote.ask, stop_loss=stop, target=None, strategy_id=identifier,
    )
    return PreparedORB(instrument, envelope, decision)
