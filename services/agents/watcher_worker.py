"""Background consumer for durable, bounded ORB watcher assignments."""

import asyncio
import logging
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.agents.assessment_workflow import AssessmentWorkflow
from services.core.models import AgentArtifact, AgentAssignment
from services.market.calendar import SessionCalendar
from services.market.settings import MarketSettings

logger = logging.getLogger(__name__)
POLL_SECONDS = 2


def _next_queued(engine) -> tuple[UUID, UUID, date] | None:
    with Session(engine) as db:
        assignment = db.scalar(
            select(AgentAssignment)
            .where(
                AgentAssignment.kind == "WATCHER_STRATEGY_ASSESSMENT",
                AgentAssignment.state == "QUEUED",
            )
            .order_by(AgentAssignment.created_at, AgentAssignment.id)
            .limit(1)
        )
        if assignment is None:
            return None
        try:
            session_key = date.fromisoformat(assignment.input_refs["session_key"])
        except (KeyError, TypeError, ValueError):
            return assignment.account_id, assignment.id, date.min
        return assignment.account_id, assignment.id, session_key


def _close_unrunnable(engine, assignment_id: UUID, reason: str) -> None:
    now = datetime.now(UTC)
    with Session(engine) as db, db.begin():
        assignment = db.scalar(
            select(AgentAssignment)
            .where(AgentAssignment.id == assignment_id)
            .with_for_update()
        )
        if assignment is None or assignment.state != "QUEUED":
            return
        expired = now >= assignment.deadline.replace(tzinfo=UTC) if assignment.deadline.tzinfo is None else now >= assignment.deadline.astimezone(UTC)
        state = "EXPIRED" if expired else "UNAVAILABLE"
        payload = {"reason": "OPPORTUNITY_EXPIRED_BEFORE_CLAIM" if expired else reason}
        assignment.state = state
        assignment.outcome = payload
        db.add(AgentArtifact(
            assignment_id=assignment.id,
            kind="OUTCOME",
            created_at=now,
            payload=payload,
        ))


def _expire_stale_running(engine) -> None:
    now = datetime.now(UTC)
    with Session(engine) as db, db.begin():
        stale = db.scalars(
            select(AgentAssignment)
            .where(
                AgentAssignment.kind == "WATCHER_STRATEGY_ASSESSMENT",
                AgentAssignment.state == "RUNNING",
            )
            .order_by(AgentAssignment.deadline, AgentAssignment.id)
            .limit(25)
            .with_for_update(skip_locked=True)
        )
        for assignment in stale:
            deadline = assignment.deadline
            deadline = deadline.replace(tzinfo=UTC) if deadline.tzinfo is None else deadline.astimezone(UTC)
            if now < deadline:
                continue
            payload = {"reason": "RUNNING_ASSIGNMENT_EXPIRED_AFTER_RESTART"}
            assignment.state = "EXPIRED"
            assignment.outcome = payload
            db.add(AgentArtifact(
                assignment_id=assignment.id,
                kind="OUTCOME",
                created_at=now,
                payload=payload,
            ))


async def watcher_assignment_worker(engine, stop: asyncio.Event) -> None:
    """Consume persisted work; a crash leaves queued items available on restart."""
    calendar = SessionCalendar(MarketSettings().calendar_file, strict=False)
    while not stop.is_set():
        try:
            await asyncio.to_thread(_expire_stale_running, engine)
            item = await asyncio.to_thread(_next_queued, engine)
            if item is None:
                await asyncio.sleep(POLL_SECONDS)
                continue
            account_id, assignment_id, session_key = item
            if session_key == date.min:
                await asyncio.to_thread(
                    _close_unrunnable, engine, assignment_id, "WATCHER_INPUT_REFS_INVALID"
                )
                continue
            exchange_session = calendar.get("NFO", session_key) if session_key != date.min else None
            if exchange_session is None:
                await asyncio.to_thread(
                    _close_unrunnable, engine, assignment_id, "WATCHER_SESSION_UNAVAILABLE"
                )
                continue
            workflow = AssessmentWorkflow(engine, account_id)
            await workflow.run_queued_watcher_assignment(assignment_id, exchange_session)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Watcher assignment consumer iteration failed")
            await asyncio.sleep(POLL_SECONDS)
