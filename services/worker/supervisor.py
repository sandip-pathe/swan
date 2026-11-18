"""Single-owner local supervisor. Only fixed worker modes reach a shell script."""

import os
import subprocess
import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from services.core.models import Account, AuditEvent
from services.market.settings import ROOT
from services.paper.engine import PaperEngine
from services.paper.qualification import active_arm, flat
from services.paper.validation import current
from services.worker.models import RuntimeControl

MODES = {"OBSERVATION", "VALIDATION", "AUTONOMOUS"}


def launch(mode: str) -> None:
    if mode not in MODES or os.name != "nt":
        raise ValueError("LOCAL_WORKER_SUPERVISOR_UNAVAILABLE")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "local.ps1"),
            "worker-prepare",
            "-WorkerMode",
            mode,
        ],
        cwd=ROOT,
        shell=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise ValueError("WORKER_PREPARATION_FAILED")


def prepare(engine: Engine, identifier: UUID, mode: str, revision: int) -> dict:
    if mode not in MODES:
        raise ValueError("INVALID_WORKER_MODE")
    with engine.connect() as connection:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(726230519842)")):
            raise ValueError("WORKER_PREPARATION_ALREADY_RUNNING")
        connection.commit()
        try:
            with Session(bind=connection) as db, db.begin():
                accounts = list(db.scalars(select(Account.id).limit(2)))
                owners = list(
                    db.scalars(
                        select(AuditEvent.account_id)
                        .where(AuditEvent.kind == "LOCAL_OWNER_ENROLLED")
                        .distinct()
                    )
                )
                if accounts != [identifier] or owners != [identifier]:
                    raise ValueError("LOCAL_SINGLE_OWNER_REQUIRED")
                account = PaperEngine._account(db, identifier)
                control = db.get(RuntimeControl, identifier)
                if control is None or account.revision != revision:
                    raise ValueError("SETTINGS_CHANGED_REFRESH_REQUIRED")
                if (
                    account.enabled
                    or control.resume_requested
                    or current(db, identifier)
                    or active_arm(db, account)
                    or not flat(db, account)
                ):
                    raise ValueError("WORKER_PREPARATION_REQUIRES_FLAT_PAUSED_ACCOUNT")
                control.status, control.problem = "MODE_SWITCHING", None
                control.active_envelope = None
                account.revision += 1
                requested_at = datetime.now(UTC)
                PaperEngine._event(db, account, "WORKER_MODE_REQUESTED", requested_at, mode=mode)
            try:
                deadline = time.monotonic() + 45
                launch(mode)
                initialized = False
                while time.monotonic() < deadline:
                    with Session(bind=connection) as db:
                        control = db.get(RuntimeControl, identifier)
                        initialized = bool(
                            control
                            and control.mode == mode
                            and control.status != "MODE_SWITCHING"
                            and control.heartbeat
                            and control.heartbeat >= requested_at
                        )
                    if initialized:
                        break
                    time.sleep(0.25)
                if not initialized:
                    raise ValueError("WORKER_PREPARATION_FAILED")
            except (ValueError, OSError, subprocess.SubprocessError):
                with Session(bind=connection) as db, db.begin():
                    account = PaperEngine._account(db, identifier)
                    control = db.get(RuntimeControl, identifier)
                    if control:
                        control.status, control.problem = (
                            "WORKER_PREPARATION_FAILED",
                            "WORKER_PREPARATION_FAILED",
                        )
                        control.resume_requested, control.active_envelope = False, None
                    account.enabled = False
                    PaperEngine._event(
                        db, account, "WORKER_MODE_FAILED", datetime.now(UTC), mode=mode
                    )
                raise ValueError("WORKER_PREPARATION_FAILED") from None
            return {"status": "PREPARATION_REQUESTED", "mode": mode}
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(726230519842)"))
            connection.commit()
