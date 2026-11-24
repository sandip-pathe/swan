"""Store immutable index-history source responses separately from options."""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f7a9bcd87412"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "index_history_batches",
        sa.Column("snapshot_id", sa.String(length=64), primary_key=True),
        sa.Column("underlying", sa.String(length=20), nullable=False),
        sa.Column("exchange", sa.String(length=10), nullable=False),
        sa.Column("session_key", sa.Date(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("response_sha256", sa.String(length=64), nullable=False),
        sa.Column("provider_request", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint("underlying = 'NIFTY' AND exchange = 'NSE'", name="index_history_identity"),
    )
    op.create_index(
        "index_history_session_received",
        "index_history_batches",
        ["underlying", "exchange", "session_key", "received_at"],
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM index_history_batches)")):
        raise RuntimeError("Preserve index history evidence before downgrade")
    op.drop_index("index_history_session_received", table_name="index_history_batches")
    op.drop_table("index_history_batches")
