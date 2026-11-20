"""Database projections and immutable evidence; mutations belong to PaperEngine."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("cash >= 0", name="account_cash_nonnegative"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(default=False)
    revision: Mapped[int] = mapped_column(default=0)
    daily_blocked: Mapped[bool] = mapped_column(default=False)
    session_key: Mapped[date | None]
    session_opening_equity: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))


class InstrumentRecord(Base):
    __tablename__ = "instruments"
    id: Mapped[str] = mapped_column(primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class ListedInstrument(Base):
    """Discovery metadata; separate from identities retained by the execution ledger."""

    __tablename__ = "listed_instruments"
    id: Mapped[str] = mapped_column(primary_key=True)
    catalog_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"), primary_key=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SnapshotRecord(Base):
    __tablename__ = "market_snapshots"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class MarketHistoryBatch(Base):
    """Immutable history attempts, including provider failures; never fill evidence."""

    __tablename__ = "market_history_batches"
    __table_args__ = (Index("history_account_time", "account_id", "requested_at"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"))
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class LiveCandleSegment(Base):
    __tablename__ = "live_candle_segments"
    __table_args__ = (
        Index("live_candles_account_range", "account_id", "instrument_id", "opens_at"),
    )
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"), primary_key=True)
    stream_id: Mapped[UUID] = mapped_column(primary_key=True)
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class StrategyRecord(Base):
    __tablename__ = "strategy_envelopes"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class DecisionRecord(Base):
    __tablename__ = "trade_decisions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)


class PaperOrder(Base):
    __tablename__ = "paper_orders"
    __table_args__ = (
        UniqueConstraint("account_id", "idempotency_key", name="order_idempotency"),
        UniqueConstraint("decision_id", name="one_entry_per_decision"),
        Index(
            "one_entry_per_validation",
            "validation_id",
            unique=True,
            postgresql_where=text("validation_id IS NOT NULL AND side = 'BUY'"),
        ),
        CheckConstraint("quantity > 0", name="order_quantity_positive"),
        CheckConstraint("side IN ('BUY', 'SELL')", name="order_side"),
        CheckConstraint(
            "filled_quantity >= 0 AND filled_quantity <= quantity", name="order_filled_bounds"
        ),
        CheckConstraint(
            "reserved_cash >= 0 AND reserved_risk >= 0 AND cash_budget >= 0 AND risk_budget >= 0",
            name="order_reservations_nonnegative",
        ),
        CheckConstraint(
            "status IN ('SUBMITTED', 'OPEN', 'PARTIALLY_FILLED', 'CANCEL_REQUESTED', "
            "'FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')",
            name="order_status",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    decision_id: Mapped[UUID | None] = mapped_column(ForeignKey("trade_decisions.id"))
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    idempotency_key: Mapped[str]
    side: Mapped[str]
    quantity: Mapped[int]
    reason: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(default="SUBMITTED", server_default="SUBMITTED")
    filled_quantity: Mapped[int] = mapped_column(default=0, server_default="0")
    execution_version: Mapped[str] = mapped_column(
        default="legacy-immediate-v1", server_default="legacy-immediate-v1"
    )
    order_type: Mapped[str] = mapped_column(default="MARKET", server_default="MARKET")
    time_in_force: Mapped[str] = mapped_column(default="DAY", server_default="DAY")
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    trigger_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cash_budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    risk_budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    reserved_cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    reserved_risk: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    position_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paper_positions.id", name="order_exit_position", use_alter=True)
    )
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    execution_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    arm_id: Mapped[UUID | None] = mapped_column(ForeignKey("paper_arms.id"), index=True)
    validation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("paper_validations.id"), index=True
    )


class PaperOrderEvent(Base):
    __tablename__ = "paper_order_events"
    __table_args__ = (UniqueConstraint("account_id", "event_key", name="order_event_idempotency"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("paper_orders.id"), index=True)
    event_key: Mapped[str]
    kind: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class PaperFill(Base):
    __tablename__ = "paper_fills"
    __table_args__ = (
        CheckConstraint("price > 0 AND fees >= 0 AND quantity > 0", name="fill_positive"),
        UniqueConstraint("order_id", "event_key", name="fill_event_idempotency"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("paper_orders.id"), index=True)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("market_snapshots.id"))
    quantity: Mapped[int]
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    fee_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON)
    config_version: Mapped[str]
    cost_version: Mapped[str]
    event_key: Mapped[str | None]
    market_event_id: Mapped[str | None]
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_version: Mapped[str] = mapped_column(
        default="legacy-immediate-v1", server_default="legacy-immediate-v1"
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("fill_id", "category", name="one_ledger_category_per_fill"),
        CheckConstraint("category IN ('CAPITAL', 'PREMIUM', 'FEE')", name="ledger_category"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    fill_id: Mapped[UUID | None] = mapped_column(ForeignKey("paper_fills.id"))
    category: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaperFundsHold(Base):
    __tablename__ = "paper_funds_holds"
    __table_args__ = (
        CheckConstraint("amount > 0", name="funds_hold_positive"),
        UniqueConstraint("fill_id", name="one_funds_hold_per_fill"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    fill_id: Mapped[UUID] = mapped_column(ForeignKey("paper_fills.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str]
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class PaperLiquidityLevel(Base):
    __tablename__ = "paper_liquidity_levels"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "session_key",
            "instrument_id",
            "side",
            "price",
            name="liquidity_level_scope",
        ),
        CheckConstraint(
            "capacity >= 0 AND consumed >= 0 AND consumed <= capacity AND displayed >= 0",
            name="liquidity_capacity_bounds",
        ),
        CheckConstraint("side IN ('BUY', 'SELL')", name="liquidity_side"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    session_key: Mapped[date]
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    side: Mapped[str]  # BUY consumes asks; SELL consumes bids.
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    displayed: Mapped[int] = mapped_column(BigInteger)
    capacity: Mapped[int] = mapped_column(BigInteger)
    consumed: Mapped[int] = mapped_column(BigInteger, default=0)
    observation_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str]
    config_version: Mapped[str]


class PaperLiquidityUse(Base):
    __tablename__ = "paper_liquidity_uses"
    __table_args__ = (
        UniqueConstraint("fill_id", name="one_liquidity_use_per_fill"),
        CheckConstraint("quantity > 0", name="liquidity_use_positive"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    level_id: Mapped[UUID] = mapped_column(ForeignKey("paper_liquidity_levels.id"), index=True)
    fill_id: Mapped[UUID] = mapped_column(ForeignKey("paper_fills.id"))
    quantity: Mapped[int] = mapped_column(BigInteger)
    raw_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        CheckConstraint("quantity > 0 AND average_price > 0", name="position_positive"),
        CheckConstraint(
            "closed_quantity >= 0 AND closed_quantity <= quantity", name="position_closed_bounds"
        ),
        Index(
            "one_open_instrument",
            "account_id",
            "instrument_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    entry_order_id: Mapped[UUID] = mapped_column(ForeignKey("paper_orders.id"), unique=True)
    exit_order_id: Mapped[UUID | None] = mapped_column(ForeignKey("paper_orders.id"), unique=True)
    quantity: Mapped[int]
    closed_quantity: Mapped[int] = mapped_column(default=0, server_default="0")
    average_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    entry_fees: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    target: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    planned_risk: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    max_holding_seconds: Mapped[int]
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    pending_exit: Mapped[str | None]
    config: Mapped[dict[str, Any]] = mapped_column(JSON)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    kind: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSON)


class PaperValidation(Base):
    __tablename__ = "paper_validations"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'STOPPING', 'STOPPED')", name="validation_status"),
        CheckConstraint("max_quantity > 0", name="validation_quantity"),
        Index(
            "one_live_validation_per_account",
            "account_id",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE', 'STOPPING')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    exchange: Mapped[str]
    session_key: Mapped[date]
    status: Mapped[str]
    max_quantity: Mapped[int]
    stream_generation: Mapped[int]
    binding: Mapped[str]
    qualification_binding: Mapped[str | None]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_reason: Mapped[str | None]
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    preflight: Mapped[dict[str, Any]] = mapped_column(JSON)
    outcome: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class PaperQualification(Base):
    __tablename__ = "paper_qualifications"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    binding: Mapped[str]
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    matrix_version: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON)
    request: Mapped[dict[str, Any]] = mapped_column(JSON)


class PaperArm(Base):
    __tablename__ = "paper_arms"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'STOPPED')", name="paper_arm_status"),
        Index(
            "one_active_paper_arm",
            "account_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    qualification_id: Mapped[UUID] = mapped_column(ForeignKey("paper_qualifications.id"))
    status: Mapped[str]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_reason: Mapped[str | None]
    stream_generation: Mapped[int]
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
