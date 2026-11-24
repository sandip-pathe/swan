"""Durable owner-requested entry stop, independent of loss limits and exits."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from services.core.contracts import IST, ExchangeSession
from services.core.models import AuditEvent
from services.paper.engine import PaperEngine
from services.worker.models import RuntimeControl


def session_entry_stopped(db: Session, account_id: UUID, now: datetime) -> bool:
    return db.scalar(select(AuditEvent.id).where(
        AuditEvent.account_id == account_id,
        AuditEvent.kind == "USER_SESSION_ENTRY_STOP",
        AuditEvent.details["session_key"].as_string() == now.astimezone(IST).date().isoformat(),
    ).limit(1)) is not None


def stop_session_entries(
    engine: Engine, account_id: UUID, request_id: UUID, session: ExchangeSession, now: datetime,
) -> dict:
    if not session.verified or not session.opens_at <= now < session.closes_at:
        raise ValueError("VERIFIED_OPEN_SESSION_REQUIRED")
    with Session(engine) as db, db.begin():
        account = PaperEngine._account(db, account_id)
        if account.session_key != session.key:
            raise ValueError("CURRENT_ACCOUNT_SESSION_REQUIRED")
        previous = db.scalar(select(AuditEvent).where(
            AuditEvent.account_id == account_id,
            AuditEvent.kind == "USER_SESSION_ENTRY_STOP",
            AuditEvent.details["request_id"].as_string() == str(request_id),
        ).limit(1))
        if previous is not None and previous.details["session_key"] != session.key.isoformat():
            raise ValueError("SESSION_STOP_REQUEST_CONFLICT")
        duplicate = session_entry_stopped(db, account_id, now)
        account.enabled = False
        control = db.get(RuntimeControl, account_id)
        if control is not None:
            control.resume_requested = False
            # Keep the active protection policy and worker running. A daily-loss
            # flag or clearing the strategy would incorrectly force liquidation.
        if not duplicate:
            account.revision += 1
            PaperEngine._event(db, account, "USER_SESSION_ENTRY_STOP", now,
                               session_key=session.key.isoformat(), request_id=str(request_id),
                               source="CHAT", effect="STOP_NEW_ENTRIES_KEEP_PROTECTION")
        return {"status": "ENTRIES_STOPPED_FOR_SESSION", "session_key": session.key.isoformat(),
                "as_of": now.isoformat(), "duplicate": duplicate,
                "effect": "New entries are stopped today. Existing position protection continues."}
