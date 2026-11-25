"""Advisory one-lot scenarios from actual depth; never an execution simulator."""

import json
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from functools import lru_cache
from pathlib import Path

from services.core.contracts import IST, Instrument, Quote
from services.core.execution import FeeSchedule
from services.paper.fees import estimate_fees


@lru_cache(maxsize=1)
def depth_mapping() -> dict:
    config = Path(__file__).resolve().parents[2] / "config/paper-execution.json"
    from services.core.execution import PaperExecutionConfig

    policy = PaperExecutionConfig.model_validate_json(config.read_text()).execution
    if policy.blockers() or policy.quantity_unit != "units":
        raise ValueError("REVIEWED_DEPTH_MAPPING_REQUIRED")
    return {
        "unit": policy.quantity_unit,
        "source": ";".join(str(row.url) for row in policy.quantity_unit_sources),
    }


@lru_cache(maxsize=1)
def fee_schedule() -> FeeSchedule:
    config = Path(__file__).resolve().parents[2] / "config/paper-execution.json"
    schedules = json.loads(config.read_text())["fee_schedules"]
    return FeeSchedule.model_validate(next(row for row in schedules if row["exchange"] == "BFO"))


def assess(
    instrument: Instrument,
    quote: Quote | None,
    now: datetime,
    history: list | dict | None = None,
    frozen: dict | None = None,
) -> tuple[dict | None, list[str]]:
    problems = []
    if (
        instrument.underlying != "SENSEX"
        or instrument.exchange != "BFO"
        or instrument.verified_at.astimezone(IST).date() != now.astimezone(IST).date()
    ):
        return None, ["CONTRACT_IDENTITY_OR_MASTER_STALE"]
    if instrument.expiry < now.astimezone(IST).date():
        return None, ["CONTRACT_EXPIRED"]
    if quote is None or not timedelta(0) <= now - quote.timestamp <= timedelta(seconds=5):
        return None, ["OPTION_QUOTE_STALE_OR_MISSING"]
    if (
        quote.instrument_id != instrument.id
        or quote.bid is None
        or quote.ask is None
        or quote.bid >= quote.ask
        or quote.timestamp_basis != "exchange_feed"
    ):
        return None, ["EXECUTABLE_SPREAD_UNAVAILABLE"]
    if quote.quantity_unit == "unknown" and quote.source == "angelone-websocket-v2:snapquote":
        try:
            mapping = depth_mapping()
            # Reuse the reviewed exchange/SDK mapping; raw quantities are unchanged.
            quote = quote.model_copy(
                update={"quantity_unit": mapping["unit"], "quantity_unit_source": mapping["source"]}
            )
        except (ValueError, OSError):
            problems.append("DEPTH_MAPPING_CONFIGURATION_UNAVAILABLE")
    if quote.quantity_unit != "units":
        problems.append("DEPTH_QUANTITY_UNITS_UNVERIFIED")
    if (
        not quote.bid_depth
        or not quote.ask_depth
        or quote.depth_kind != "best_five"
        or (quote.bid_quantity or 0) < instrument.lot_size
        or (quote.ask_quantity or 0) < instrument.lot_size
    ):
        problems.append("ONE_LOT_DEPTH_UNCONFIRMED")
    assert quote.ask is not None and quote.bid is not None
    premium = quote.ask * instrument.lot_size
    spread = quote.ask - quote.bid
    tick = instrument.tick_size
    summary = history if isinstance(history, dict) else None
    samples = (
        [
            (stamp, Decimal(str(price)))
            for stamp, price in (history or [])
            if timedelta(0) <= now - stamp <= timedelta(minutes=3)
        ]
        if not summary
        else []
    )
    minimum_noise = spread * 2
    if (
        summary
        and summary.get("count", 0) >= 20
        and timedelta(0) <= now - datetime.fromisoformat(summary["to"]) <= timedelta(seconds=5)
        and datetime.fromisoformat(summary["to"]) - datetime.fromisoformat(summary["from"])
        >= timedelta(seconds=60)
    ):
        minimum_noise = max(minimum_noise, Decimal(summary["high"]) - Decimal(summary["low"]))
    elif len(samples) >= 20 and samples[-1][0] - samples[0][0] >= timedelta(seconds=60):
        minimum_noise = max(minimum_noise, max(p for _, p in samples) - min(p for _, p in samples))
    else:
        problems.append("PREMIUM_NOISE_WINDOW_WARMING_UP")
    distance = max(minimum_noise, tick * 2)
    stop = ((quote.ask - distance) / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
    target = ((quote.ask + distance * 2) / tick).to_integral_value(rounding=ROUND_CEILING) * tick
    if frozen:
        stop = Decimal(frozen["premium_invalidation"])
        target = Decimal(frozen["premium_target_scenario"])
    if stop <= 0 or stop >= quote.ask or target <= quote.ask:
        return None, ["PREMIUM_INVALIDATION_NOT_FEASIBLE"]
    try:
        schedule = fee_schedule()
        if (
            not schedule.reviewed
            or not schedule.effective_from <= now.astimezone(IST).date()
            or schedule.effective_until
            and now.astimezone(IST).date() > schedule.effective_until
        ):
            raise ValueError
        entry_fee = estimate_fees(schedule, "BUY", premium)
        stop_fee = estimate_fees(schedule, "SELL", stop * instrument.lot_size)
        target_fee = estimate_fees(schedule, "SELL", target * instrument.lot_size)
    except (OSError, ValueError, KeyError, StopIteration):
        return None, ["FEE_ESTIMATE_UNAVAILABLE"]
    slippage = max(tick, spread / 2) * instrument.lot_size * 2
    loss = (quote.ask - stop) * instrument.lot_size + entry_fee + stop_fee + slippage
    gain = (target - quote.ask) * instrument.lot_size - entry_fee - target_fee - slippage
    reference = premium * Decimal("0.05")
    if loss > reference:
        problems.append("DOWNSIDE_EXCEEDS_FIVE_PERCENT_REFERENCE")
    if gain <= 0 or gain < loss:
        problems.append("NET_SCENARIO_NOT_WORTH_DOWNSIDE")
    return {
        "quantity": instrument.lot_size,
        "entry_ask": str(quote.ask),
        "exit_bid": str(quote.bid),
        "premium_required": str(premium),
        "spread": str(spread),
        "premium_invalidation": str(stop),
        "premium_target_scenario": str(target),
        "estimated_net_loss": str(loss.quantize(Decimal(".01"))),
        "estimated_net_gain": str(gain.quantize(Decimal(".01"))),
        "loss_reference": str(reference),
        "estimated_round_trip_cost": str(entry_fee + stop_fee + slippage),
        "quote_at": quote.timestamp.isoformat(),
        "quote_source": quote.source,
        "depth_quantity_unit": quote.quantity_unit,
        "depth_quantity_source": quote.quantity_unit_source,
        "fee_basis": schedule.version,
        "costs_are_estimates": True,
        "assumptions": "One entry/exit, displayed best quotes, two-sided slippage allowance; "
        "fee schedule includes estimated rounding/IPFT. Noise uses observed premium range, "
        "not a fitted option-price forecast. Gaps can exceed the reference.",
    }, problems


def personalize(value: dict, budget: Decimal, now: datetime, market_open: bool) -> dict:
    result = dict(value)
    if result.get("kind") != "idea" or result["state"] in {"expired", "invalidated"}:
        return result
    reasons = list(result.get("reasons", []))
    if now >= datetime.fromisoformat(result["expires_at"]):
        result["state"] = "expired"
    elif result["state"] == "eligible":
        economics = result.get("economics") or {}
        stamp = economics.get("quote_at")
        if (
            not market_open
            or not stamp
            or not timedelta(0) <= now - datetime.fromisoformat(stamp) <= timedelta(seconds=5)
        ):
            result["state"] = "suspended"
            reasons.append("FRESH_PRICING_REQUIRED")
        elif budget <= 0:
            result["state"] = "watch"
            reasons.append("SET_POSITION_BUDGET")
        elif Decimal(economics["premium_required"]) > budget:
            result["state"] = "watch"
            reasons.append("ONE_LOT_EXCEEDS_POSITION_BUDGET")
    result["reasons"] = list(dict.fromkeys(reasons))
    return result
