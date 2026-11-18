"""Single-owner local wallet enrollment after genuine Firebase verification."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from services.core.contracts import RiskConfig
from services.core.models import Account, AuditEvent, LedgerEntry
from services.worker.models import RuntimeControl


def local_owner_account(engine: Engine, project: str, uid: str) -> UUID:
    if engine.url.host not in {"127.0.0.1", "localhost", "::1"}:
        raise HTTPException(403, "LOCAL_ONBOARDING_ONLY")
    with Session(engine) as db, db.begin():
        # Serialize first-owner enrollment across processes; never enroll a second owner.
        db.execute(text("SELECT pg_advisory_xact_lock(873928617451)"))
        owner = db.scalar(select(AuditEvent).where(AuditEvent.kind == "LOCAL_OWNER_ENROLLED"))
        if owner is not None:
            if owner.details.get("project") != project or owner.details.get("uid") != uid:
                raise HTTPException(403, "ACCOUNT_NOT_AUTHORIZED")
            if db.get(Account, owner.account_id) is None:
                raise HTTPException(409, "PAPER_ACCOUNT_NOT_CONFIGURED")
            return owner.account_id
        if db.scalar(select(Account.id).limit(1)) is not None:
            raise HTTPException(409, "EXISTING_ACCOUNT_REQUIRES_LINK")
        now = datetime.now(UTC)
        policy = RiskConfig(
            version="local-paper-unreviewed-v1",
            # Startup limits require review. Quantity=1 blocks option-lot entry.
            max_spread_bps=Decimal("100"),
            min_volume=1,
            min_oi=1,
            max_fill_quantity=1,
        )
        identifier = uuid5(NAMESPACE_URL, f"swan-paper:{project}:{uid}")
        db.add(
            Account(
                id=identifier,
                cash=policy.capital,
                config=policy.model_dump(mode="json"),
                enabled=False,
            )
        )
        db.flush()
        db.add_all(
            [
                LedgerEntry(
                    account_id=identifier, category="CAPITAL", amount=policy.capital, timestamp=now
                ),
                RuntimeControl(
                    account_id=identifier, status="PAUSED", problem="PAPER_ENGINE_NOT_READY"
                ),
                AuditEvent(
                    account_id=identifier,
                    kind="LOCAL_OWNER_ENROLLED",
                    timestamp=now,
                    details={"project": project, "uid": uid, "risk_policy_reviewed": False},
                ),
            ]
        )
        return identifier
