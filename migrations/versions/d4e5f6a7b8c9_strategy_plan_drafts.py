"""Persist research-only strategy plan drafts linked to assessments."""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strategy_plan_drafts",
        sa.Column(
            "assessment_id", sa.String(length=64),
            sa.ForeignKey("strategy_assessments.id"), primary_key=True,
        ),
        sa.Column("plan_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("strategy_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("session_key", sa.Date(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('FIT', 'DOES_NOT_FIT', 'INSUFFICIENT_DATA', 'OUT_OF_SCOPE')",
            name="strategy_plan_outcome",
        ),
        sa.CheckConstraint(
            "(payload ->> 'execution_eligible') = 'false'",
            name="strategy_plan_non_executable",
        ),
    )
    op.create_index("strategy_plan_session_asof", "strategy_plan_drafts", ["session_key", "as_of"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM strategy_plan_drafts)")):
        raise RuntimeError("Preserve strategy plan evidence before downgrade")
    op.drop_index("strategy_plan_session_asof", table_name="strategy_plan_drafts")
    op.drop_table("strategy_plan_drafts")
