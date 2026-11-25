"""Incremental, source-aware bars and two explicit experimental strategies."""

import hashlib
from datetime import datetime, time, timedelta
from decimal import Decimal

from services.bot.contracts import Idea
from services.core.contracts import IST
from services.market.reference_contracts import IndexReference
from services.strategies.contracts import IndexBar


class RollingMarket:
    def __init__(self, name: str):
        self.name = name
        self.bars: dict[datetime, IndexBar] = {}
        self.forming: dict | None = None
        self.generation: int | None = None
        self.corrections = 0

    def merge(self, bars: list[IndexBar]) -> bool:
        corrected = False
        for bar in bars:
            if bar.underlying != self.name or not bar.final:
                continue
            previous = self.bars.get(bar.opens_at)
            if previous and (previous.open, previous.high, previous.low, previous.close) != (
                bar.open,
                bar.high,
                bar.low,
                bar.close,
            ):
                corrected = True
                self.corrections += 1
            self.bars[bar.opens_at] = bar
        for opened in sorted(self.bars)[:-400]:
            del self.bars[opened]
        return corrected

    def tick(self, quote: IndexReference, generation: int) -> bool:
        minute = quote.timestamp.replace(second=0, microsecond=0)
        if self.generation != generation:
            self.forming = None
            self.generation = generation
        current = self.forming
        changed = False
        continuous = bool(
            current and timedelta(0) <= quote.timestamp - current["last"] <= timedelta(seconds=10)
        )
        if current and minute > current["minute"]:
            # Only a minute observed from its first second, without disconnect, is complete.
            if current["complete"]:
                identity = (
                    f"{self.name}:{current['minute'].isoformat()}:{current['values']}:{generation}"
                )
                values = current["values"]
                bar = IndexBar(
                    underlying=self.name,
                    exchange=quote.exchange,
                    opens_at=current["minute"],
                    closes_at=current["minute"] + timedelta(minutes=1),
                    open=values[0],
                    high=values[1],
                    low=values[2],
                    close=values[3],
                    final=True,
                    available_at=quote.received_at,
                    source="angelone-websocket-v2:observed-minute",
                    evidence_id=hashlib.sha256(identity.encode()).hexdigest(),
                )
                self.merge([bar])
                changed = True
            self.forming = None
        if self.forming is None:
            self.forming = {
                "minute": minute,
                "complete": continuous,
                "last": quote.timestamp,
                "values": [quote.last_price] * 4,
            }
        elif minute == self.forming["minute"] and quote.timestamp >= self.forming["last"]:
            # A long silence means tick coverage was lost even without a socket close.
            if quote.timestamp - self.forming["last"] > timedelta(seconds=10):
                self.forming["complete"] = False
            values = self.forming["values"]
            values[1] = max(values[1], quote.last_price)
            values[2] = min(values[2], quote.last_price)
            values[3] = quote.last_price
            self.forming["last"] = quote.timestamp
        return changed

    def window(self, start: datetime, count: int) -> list[IndexBar] | None:
        stamps = [start + timedelta(minutes=i) for i in range(count)]
        return (
            [self.bars[stamp] for stamp in stamps]
            if all(stamp in self.bars for stamp in stamps)
            else None
        )

    def context(self, now: datetime) -> dict:
        opening = datetime.combine(now.astimezone(IST).date(), time(9, 15), IST)
        end = now.replace(second=0, microsecond=0)
        morning = self.window(opening, 15) if end >= opening + timedelta(minutes=15) else None
        recent = self.window(end - timedelta(minutes=20), 20)
        day = [
            bar
            for bar in self.bars.values()
            if bar.opens_at.astimezone(IST).date() == opening.date()
        ]
        last = max(day, key=lambda bar: bar.opens_at) if day else None
        value: dict = {
            "underlying": self.name,
            "status": "current"
            if recent and morning
            else "partial"
            if recent or morning
            else "insufficient",
            "opening_range_status": "complete" if morning else "incomplete",
            "rolling_status": "complete" if recent else "incomplete",
            "reason": None
            if recent and morning
            else "Some required windows are incomplete; independent facts remain available.",
            "as_of": last.closes_at.isoformat() if last else None,
            "last_close": str(last.close) if last else None,
            "bars": len(day),
            "corrections": self.corrections,
            "source": last.source if last else "unavailable",
            "evidence": [],
            "rule": "dependency-windows-v2",
        }
        if morning:
            value.update(
                range_high=str(max(b.high for b in morning)),
                range_low=str(min(b.low for b in morning)),
            )
            value["evidence"].extend(b.evidence_id for b in morning)
        if recent:
            average = sum((b.close for b in recent), Decimal(0)) / 20
            atr = sum((b.high - b.low for b in recent[-14:]), Decimal(0)) / 14
            travel = sum((abs(b.close - a.close) for a, b in zip(recent, recent[1:])), Decimal(0))
            efficiency = abs(recent[-1].close - recent[0].close) / travel if travel else Decimal(0)
            value.update(
                efficiency20=str(efficiency),
                sma20=str(average),
                range_atr14=str(atr),
                trend="above_average" if recent[-1].close > average else "below_average",
            )
            value["evidence"].extend(b.evidence_id for b in recent)
        if morning and last:
            value["range_state"] = (
                "above_opening_range"
                if last.close > Decimal(value["range_high"])
                else "below_opening_range"
                if last.close < Decimal(value["range_low"])
                else "inside_range"
            )
        return value

    def candidates(self, now: datetime) -> list[dict]:
        if now.astimezone(IST).time() >= time(15, 25):
            return []
        context = self.context(now)
        if self.name != "SENSEX" or context["status"] != "current":
            return []
        end = now.replace(second=0, microsecond=0)
        pair = self.window(end - timedelta(minutes=2), 2)
        if not pair:
            return []
        previous, last = pair
        high, low, average = (Decimal(context[key]) for key in ("range_high", "range_low", "sma20"))
        atr = max(Decimal(context["range_atr14"]), Decimal("0.01"))
        buffer = atr * Decimal("0.1")
        candidates = []
        for direction, sign, level in (("CALL", Decimal(1), high), ("PUT", Decimal(-1), low)):
            outside = sign * (last.close - level) > buffer
            aligned = sign * (last.close - average) > 0
            retest = (
                last.low <= level + buffer if direction == "CALL" else last.high >= level - buffer
            )
            if outside and aligned:
                confirmed = sign * (previous.close - level) > buffer and retest
                candidates.append(
                    make_idea(
                        "range-retest-v1",
                        direction,
                        level + sign * buffer,
                        level - sign * atr * Decimal("0.5"),
                        now,
                        context,
                        "trigger_pending" if confirmed else "watch",
                    )
                )
            # Failed break is an actual confirmed close back inside, not a guessed reversal.
            failed = (
                sign * (previous.close - level) > buffer and sign * (last.close - level) < -buffer
            )
            if failed:
                opposite = "PUT" if direction == "CALL" else "CALL"
                candidates.append(
                    make_idea(
                        "failed-break-v1",
                        opposite,
                        level - sign * buffer,
                        level + sign * atr * Decimal("0.5"),
                        now,
                        context,
                        "trigger_pending",
                    )
                )
        # Trend pullback: directional displacement, average slope, and a reclaimed mean.
        recent = self.window(end - timedelta(minutes=20), 20)
        if recent and Decimal(context.get("efficiency20", "0")) >= Decimal("0.35"):
            first_mean = sum((bar.close for bar in recent[:10]), Decimal(0)) / 10
            last_mean = sum((bar.close for bar in recent[10:]), Decimal(0)) / 10
            for direction, sign in (("CALL", Decimal(1)), ("PUT", Decimal(-1))):
                touched = previous.low <= average if sign > 0 else previous.high >= average
                reclaimed = sign * (last.close - average) > buffer
                slope = sign * (last_mean - first_mean) > atr * Decimal("0.2")
                inside = low < last.close < high
                if touched and reclaimed and slope and not inside:
                    trigger = last.high + buffer if sign > 0 else last.low - buffer
                    stop = (
                        min(previous.low, last.low) - buffer
                        if sign > 0
                        else max(previous.high, last.high) + buffer
                    )
                    if sign * (trigger - stop) > 0:
                        candidates.append(
                            make_idea(
                                "trend-pullback-v1",
                                direction,
                                trigger,
                                stop,
                                now,
                                context,
                                "trigger_pending",
                            )
                        )
        return candidates


def make_idea(
    strategy: str,
    direction: str,
    trigger: Decimal,
    invalidation: Decimal,
    now: datetime,
    facts: dict,
    state: str,
    horizon: str = "intraday",
) -> dict:
    risk = abs(trigger - invalidation)
    target = trigger + (risk * 2 if direction == "CALL" else -risk * 2)
    day = now.astimezone(IST).date()
    identity = f"{day}:{strategy}:{direction}:{horizon}:{facts.get('as_of')}"
    expires = (
        datetime.combine(day, time(15, 25), IST)
        if horizon == "intraday"
        else now + timedelta(days=7)
    )
    return Idea.model_validate(
        dict(
            id=hashlib.sha256(identity.encode()).hexdigest(),
            horizon=horizon,
            strategy=strategy,
            direction=direction,
            state=state,
            as_of=now,
            published_at=now,
            expires_at=expires,
            title=f"SENSEX {direction.lower()} {'retest' if strategy == 'range-retest-v1' else 'reversal' if strategy == 'failed-break-v1' else 'trend pullback' if strategy == 'trend-pullback-v1' else 'weekly structure'}",
            summary="Experimental conditional idea; contract and risk checks must pass before eligibility.",
            trigger=f"Completed {'close above' if direction == 'CALL' else 'close below'} {trigger}; {'successful retest required' if strategy == 'range-retest-v1' else 'trend continuation required' if strategy == 'trend-pullback-v1' else 'confirmed reversal required'}.",
            invalidation=f"Underlying {'at or below' if direction == 'CALL' else 'at or above'} {invalidation}, source loss, or expiry.",
            trigger_level=trigger,
            invalidation_level=invalidation,
            target_level=target,
            reasons=["RESEARCH_PENDING", "CONTRACT_CHECK_PENDING"],
            evidence_ids=list(dict.fromkeys(facts.get("evidence", []))),
            facts=facts,
        )
    ).model_dump(mode="json")
