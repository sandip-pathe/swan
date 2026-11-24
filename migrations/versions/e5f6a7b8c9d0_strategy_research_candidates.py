"""Store inactive, versioned strategy research candidates."""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strategy_research_candidates",
        sa.Column("candidate_id", sa.String(length=64), primary_key=True),
        sa.Column("strategy_id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("strategy_id", "version", name="one_research_candidate_version"),
        sa.CheckConstraint(
            "(payload ->> 'status') = 'INACTIVE_RESEARCH'",
            name="strategy_candidate_inactive",
        ),
    )
    op.create_index(
        "strategy_candidate_created", "strategy_research_candidates", ["created_at"]
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM strategy_research_candidates)")):
        raise RuntimeError("Preserve strategy research evidence before downgrade")
    op.drop_index("strategy_candidate_created", table_name="strategy_research_candidates")
    op.drop_table("strategy_research_candidates")
