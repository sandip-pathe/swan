"""Persist idempotent deterministic strategy watcher decisions."""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strategy_watcher_events",
        sa.Column("event_key", sa.String(length=64), primary_key=True),
        sa.Column(
            "snapshot_id", sa.String(length=64),
            sa.ForeignKey("index_history_batches.snapshot_id"), nullable=False,
        ),
        sa.Column(
            "assessment_id", sa.String(length=64),
            sa.ForeignKey("strategy_assessments.id"), nullable=False,
        ),
        sa.Column("session_key", sa.Date(), nullable=False),
        sa.Column("event_kind", sa.String(length=30), nullable=False),
        sa.Column("state_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("emitted", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint("event_kind IN ('session_prepare', 'bar_close')", name="strategy_watcher_event_kind"),
    )
    op.create_index(
        "strategy_watcher_session_time", "strategy_watcher_events", ["session_key", "created_at"]
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM strategy_watcher_events)")):
        raise RuntimeError("Preserve strategy watcher evidence before downgrade")
    op.drop_index("strategy_watcher_session_time", table_name="strategy_watcher_events")
    op.drop_table("strategy_watcher_events")
