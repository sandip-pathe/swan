"""Durable orders, multiple fills, reservations and lifecycle events.

Legacy monetary records remain unchanged; only lifecycle metadata is backfilled.
"""

import sqlalchemy as sa
from alembic import op

revision = "84c6d21b09fa"
down_revision = "31fa5ac4735a"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind, default in (
        ("status", sa.String(), "SUBMITTED"),
        ("filled_quantity", sa.Integer(), "0"),
        ("execution_version", sa.String(), "legacy-immediate-v1"),
        ("order_type", sa.String(), "MARKET"),
        ("time_in_force", sa.String(), "DAY"),
        ("cash_budget", sa.Numeric(18, 2), "0"),
        ("risk_budget", sa.Numeric(18, 2), "0"),
        ("reserved_cash", sa.Numeric(18, 2), "0"),
        ("reserved_risk", sa.Numeric(18, 2), "0"),
    ):
        op.add_column("paper_orders", sa.Column(name, kind, nullable=False, server_default=default))
    for name in ("limit_price", "trigger_price"):
        op.add_column("paper_orders", sa.Column(name, sa.Numeric(18, 4), nullable=True))
    for name in ("accepted_at", "eligible_at", "expires_at", "cancel_requested_at", "completed_at"):
        op.add_column("paper_orders", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    for name in ("request_payload", "execution_config"):
        op.add_column("paper_orders", sa.Column(name, sa.JSON(), nullable=True))
    op.add_column("paper_orders", sa.Column("position_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "order_exit_position", "paper_orders", "paper_positions", ["position_id"], ["id"]
    )
    op.add_column(
        "paper_positions",
        sa.Column("closed_quantity", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("paper_fills", sa.Column("event_key", sa.String(), nullable=True))
    op.add_column("paper_fills", sa.Column("market_event_id", sa.String(), nullable=True))
    op.add_column("paper_fills", sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "paper_fills",
        sa.Column(
            "execution_version", sa.String(), nullable=False, server_default="legacy-immediate-v1"
        ),
    )
    op.drop_constraint("paper_fills_order_id_key", "paper_fills", type_="unique")
    op.create_index("ix_paper_fills_order_id", "paper_fills", ["order_id"])
    op.create_unique_constraint("fill_event_idempotency", "paper_fills", ["order_id", "event_key"])
    op.execute("""
        UPDATE paper_orders o SET status = 'FILLED', filled_quantity = o.quantity,
            accepted_at = o.timestamp, eligible_at = o.timestamp, completed_at = o.timestamp
        WHERE EXISTS (SELECT 1 FROM paper_fills f WHERE f.order_id = o.id)
    """)
    op.execute("""
        UPDATE paper_fills f SET timestamp = o.timestamp,
            event_key = 'legacy:' || CAST(f.id AS text)
        FROM paper_orders o WHERE o.id = f.order_id
    """)
    op.execute("UPDATE paper_positions SET closed_quantity = quantity WHERE closed_at IS NOT NULL")
    op.execute("""
        UPDATE paper_orders o SET position_id = p.id
        FROM paper_positions p WHERE p.exit_order_id = o.id
    """)
    op.create_check_constraint(
        "order_filled_bounds",
        "paper_orders",
        "filled_quantity >= 0 AND filled_quantity <= quantity",
    )
    op.create_check_constraint(
        "order_reservations_nonnegative",
        "paper_orders",
        "reserved_cash >= 0 AND reserved_risk >= 0 AND cash_budget >= 0 AND risk_budget >= 0",
    )
    op.create_check_constraint(
        "order_status",
        "paper_orders",
        "status IN ('SUBMITTED', 'OPEN', 'PARTIALLY_FILLED', 'CANCEL_REQUESTED', 'FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')",
    )
    op.create_check_constraint(
        "position_closed_bounds",
        "paper_positions",
        "closed_quantity >= 0 AND closed_quantity <= quantity",
    )
    op.create_table(
        "paper_order_events",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("paper_orders.id"), nullable=False),
        sa.Column("event_key", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("account_id", "event_key", name="order_event_idempotency"),
    )
    op.create_index("ix_paper_order_events_account_id", "paper_order_events", ["account_id"])
    op.create_index("ix_paper_order_events_order_id", "paper_order_events", ["order_id"])
    op.create_table(
        "paper_funds_holds",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("fill_id", sa.Uuid(), sa.ForeignKey("paper_fills.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_evidence", sa.JSON(), nullable=True),
        sa.CheckConstraint("amount > 0", name="funds_hold_positive"),
        sa.UniqueConstraint("fill_id", name="one_funds_hold_per_fill"),
    )
    op.create_index("ix_paper_funds_holds_account_id", "paper_funds_holds", ["account_id"])


def downgrade():
    # A lossy downgrade must never silently discard durable financial history.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM paper_orders WHERE execution_version <> 'legacy-immediate-v1')
               OR EXISTS (SELECT order_id FROM paper_fills GROUP BY order_id HAVING COUNT(*) > 1)
            THEN RAISE EXCEPTION 'Durable paper history exists; restore a reviewed backup instead';
            END IF;
        END $$;
    """)
    op.drop_table("paper_funds_holds")
    op.drop_table("paper_order_events")
    op.drop_constraint("position_closed_bounds", "paper_positions", type_="check")
    for name in ("order_filled_bounds", "order_reservations_nonnegative", "order_status"):
        op.drop_constraint(name, "paper_orders", type_="check")
    op.drop_constraint("fill_event_idempotency", "paper_fills", type_="unique")
    op.drop_index("ix_paper_fills_order_id", table_name="paper_fills")
    op.create_unique_constraint("paper_fills_order_id_key", "paper_fills", ["order_id"])
    for name in ("event_key", "market_event_id", "timestamp", "execution_version"):
        op.drop_column("paper_fills", name)
    op.drop_column("paper_positions", "closed_quantity")
    op.drop_constraint("order_exit_position", "paper_orders", type_="foreignkey")
    for name in (
        "position_id",
        "request_payload",
        "execution_config",
        "accepted_at",
        "eligible_at",
        "expires_at",
        "cancel_requested_at",
        "completed_at",
        "limit_price",
        "trigger_price",
        "cash_budget",
        "risk_budget",
        "reserved_cash",
        "reserved_risk",
        "status",
        "filled_quantity",
        "execution_version",
        "order_type",
        "time_in_force",
    ):
        op.drop_column("paper_orders", name)
