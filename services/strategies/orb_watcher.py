"""Offline, idempotent ORB watcher; it records transitions but schedules no model work."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.contracts import IST, ExchangeSession
from services.core.models import AgentArtifact, AgentAssignment, StrategyWatcherEvent
from services.strategies.assessment_store import persist_assessment
from services.strategies.contracts import ORBAssessment, ORBSnapshot
from services.strategies.orb import evaluate_orb


class WatcherResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_key: str
    event_kind: Literal["session_prepare", "bar_close"]
    emitted: bool
    reason: str
    assessment: ORBAssessment


def process_orb_event(
    session: Session,
    *,
    snapshot: ORBSnapshot,
    exchange_session: ExchangeSession,
    event_kind: Literal["session_prepare", "bar_close"],
) -> WatcherResult:
    """Evaluate once per source event and record whether setup state changed."""
    if snapshot.as_of.astimezone(IST).date() != exchange_session.key:
        raise ValueError("WATCHER_CROSS_SESSION_SNAPSHOT")
    assessment = evaluate_orb(snapshot, exchange_session)
    saved_assessment = persist_assessment(session, assessment)
    identity = {
        "session": exchange_session.key.isoformat(),
        "strategy": assessment.strategy_id,
        "version": assessment.version,
        "snapshot_id": snapshot.snapshot_id,
        "event_kind": event_kind,
    }
    event_key = _hash(identity)
    prior_delivery = session.get(StrategyWatcherEvent, event_key)
    if prior_delivery is not None:
        return WatcherResult.model_validate(prior_delivery.payload)

    state = {
        "status": assessment.status,
        "reason_codes": assessment.reason_codes,
        "missing_intervals": assessment.missing_intervals,
        "range_high": assessment.range_high,
        "range_low": assessment.range_low,
        "trigger_evidence_id": assessment.trigger_evidence_id,
        "invalidation": assessment.invalidation,
        "target": assessment.target,
    }
    state_fingerprint = _hash(state)
    latest = session.scalar(
        select(StrategyWatcherEvent)
        .where(StrategyWatcherEvent.session_key == exchange_session.key)
        .order_by(StrategyWatcherEvent.created_at.desc(), StrategyWatcherEvent.event_key.desc())
        .limit(1)
    )
    changed = latest is None or latest.state_fingerprint != state_fingerprint
    setup = assessment.status in {"BULLISH_SETUP", "BEARISH_SETUP"}
    emitted = changed and setup
    reason = "SETUP_STATE_CHANGED" if emitted else (
        "STATE_UNCHANGED" if not changed else "NO_ELIGIBLE_SETUP"
    )
    result = WatcherResult(
        event_key=event_key,
        event_kind=event_kind,
        emitted=emitted,
        reason=reason,
        assessment=assessment,
    )
    session.add(
        StrategyWatcherEvent(
            event_key=event_key,
            snapshot_id=snapshot.snapshot_id,
            assessment_id=saved_assessment.id,
            session_key=exchange_session.key,
            event_kind=event_kind,
            state_fingerprint=state_fingerprint,
            emitted=emitted,
            reason=reason,
            created_at=assessment.as_of,
            payload=result.model_dump(mode="json"),
        )
    )
    session.flush()
    return result


def enqueue_orb_assignment(
    session: Session,
    *,
    account_id: UUID,
    event: WatcherResult,
    now: datetime | None = None,
) -> AgentAssignment | None:
    """Durably queue one bounded analyst assignment for a changed eligible setup."""
    if not event.emitted:
        return None
    now = now or datetime.now(UTC)
    assessment = event.assessment
    expiry = assessment.expires_at
    if expiry is None or expiry.tzinfo is None or expiry.utcoffset() is None:
        return None
    deadline = min(now + timedelta(seconds=100), expiry.astimezone(UTC))
    request_key = f"orb-watcher:{event.event_key}"
    refs = {
        "snapshot_id": assessment.snapshot_id,
        "as_of": assessment.as_of.astimezone(UTC).isoformat(),
        "watcher_event_key": event.event_key,
        "session_key": assessment.as_of.astimezone(IST).date().isoformat(),
    }
    existing = session.scalar(
        select(AgentAssignment).where(
            AgentAssignment.account_id == account_id,
            AgentAssignment.request_key == request_key,
        )
    )
    if existing is not None:
        return existing

    # Coalesce queued work for the same account/session. Running work is retained;
    # its fixed deadline and the workflow's expiry guard decide whether it can finish.
    queued = session.scalars(
        select(AgentAssignment).where(
            AgentAssignment.account_id == account_id,
            AgentAssignment.kind == "WATCHER_STRATEGY_ASSESSMENT",
            AgentAssignment.state == "QUEUED",
        ).with_for_update()
    )
    for prior in queued:
        if prior.input_refs.get("session_key") != refs["session_key"]:
            continue
        prior.state = "EXPIRED"
        prior.outcome = {"reason": "SUPERSEDED_BY_NEWER_WATCHER_EVENT", "event_key": event.event_key}
        session.add(AgentArtifact(
            assignment_id=prior.id,
            kind="OUTCOME",
            created_at=now,
            payload=prior.outcome,
        ))

    assignment = AgentAssignment(
        account_id=account_id,
        request_key=request_key,
        kind="WATCHER_STRATEGY_ASSESSMENT",
        state="QUEUED" if deadline > now else "EXPIRED",
        created_at=now,
        deadline=deadline,
        input_refs=refs,
        outcome=None if deadline > now else {"reason": "OPPORTUNITY_EXPIRED_BEFORE_QUEUE"},
    )
    session.add(assignment)
    session.flush()
    if deadline <= now:
        session.add(AgentArtifact(
            assignment_id=assignment.id,
            kind="OUTCOME",
            created_at=now,
            payload=assignment.outcome,
        ))
    return assignment


def _hash(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
