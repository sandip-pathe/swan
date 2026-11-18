"""Owner-scoped bounded paper sessions, never autonomous qualification."""

import sqlalchemy as sa
from alembic import op

revision = "a6f0bce21801"
down_revision = "95d7e32c10ab"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "runtime_controls",
        sa.Column("mode", sa.String(), server_default="OBSERVATION", nullable=False),
    )
    op.create_table(
        "paper_validations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("instrument_id", sa.String(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("session_key", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("max_quantity", sa.Integer(), nullable=False),
        sa.Column("stream_generation", sa.Integer(), nullable=False),
        sa.Column("binding", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        sa.Column("stop_reason", sa.String()),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("preflight", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.JSON()),
        sa.CheckConstraint("status IN ('ACTIVE', 'STOPPING', 'STOPPED')", name="validation_status"),
        sa.CheckConstraint("max_quantity > 0", name="validation_quantity"),
    )
    op.create_index("ix_paper_validations_account_id", "paper_validations", ["account_id"])
    op.create_index(
        "one_live_validation_per_account",
        "paper_validations",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE', 'STOPPING')"),
    )
    op.add_column(
        "paper_orders", sa.Column("validation_id", sa.Uuid(), sa.ForeignKey("paper_validations.id"))
    )
    op.create_index("ix_paper_orders_validation_id", "paper_orders", ["validation_id"])
    op.create_index(
        "one_entry_per_validation",
        "paper_orders",
        ["validation_id"],
        unique=True,
        postgresql_where=sa.text("validation_id IS NOT NULL AND side = 'BUY'"),
    )


def downgrade():
    # Historical validation evidence must not be silently discarded.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM paper_validations) THEN RAISE EXCEPTION 'Preserve validation evidence before downgrade'; END IF; END $$;"
    )
    op.drop_index("one_entry_per_validation", table_name="paper_orders")
    op.drop_index("ix_paper_orders_validation_id", table_name="paper_orders")
    op.drop_column("paper_orders", "validation_id")
    op.drop_table("paper_validations")
    op.drop_column("runtime_controls", "mode")
