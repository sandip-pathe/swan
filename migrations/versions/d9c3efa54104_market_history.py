"""Immutable owner-scoped market history batches, separate from trade snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "d9c3efa54104"
down_revision = "c8b2def43003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "market_history_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("instrument_id", sa.String(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index(
        "history_account_time", "market_history_batches", ["account_id", "requested_at"]
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM market_history_batches)")):
        raise RuntimeError("Preserve market history evidence before downgrade")
    op.drop_index("history_account_time", table_name="market_history_batches")
    op.drop_table("market_history_batches")
