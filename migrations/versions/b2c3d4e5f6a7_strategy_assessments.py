"""Persist deterministic strategy assessments against exact source snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strategy_assessments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(length=64),
            sa.ForeignKey("index_history_batches.snapshot_id"),
            nullable=False,
        ),
        sa.Column("strategy_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("definition_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("session_key", sa.Date(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "snapshot_id", "strategy_id", "version", name="one_assessment_per_snapshot_version"
        ),
    )
    op.create_index(
        "strategy_assessment_session_asof", "strategy_assessments", ["session_key", "as_of"]
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM strategy_assessments)")):
        raise RuntimeError("Preserve strategy assessment evidence before downgrade")
    op.drop_index("strategy_assessment_session_asof", table_name="strategy_assessments")
    op.drop_table("strategy_assessments")
