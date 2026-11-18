from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from services.core.models import Base


class RuntimeControl(Base):
    __tablename__ = "runtime_controls"
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    resume_requested: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(default="STOPPED")
    mode: Mapped[str] = mapped_column(default="OBSERVATION", server_default="OBSERVATION")
    problem: Mapped[str | None]
    heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    active_envelope: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    attempted_envelope_id: Mapped[UUID | None]
    stream_generation: Mapped[int] = mapped_column(default=0)


class EvaluationSlot(Base):
    __tablename__ = "evaluation_slots"
    __table_args__ = (
        UniqueConstraint("account_id", "session_key", "slot_at", name="one_evaluation_per_slot"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    session_key: Mapped[date]
    slot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str]
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    validation_id: Mapped[UUID | None] = mapped_column(ForeignKey("paper_validations.id"))
    arm_id: Mapped[UUID | None] = mapped_column(ForeignKey("paper_arms.id"))


class LatestMarketQuote(Base):
    """Replaceable live projection; immutable trade/evaluation evidence lives separately."""

    __tablename__ = "latest_market_quotes"
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
