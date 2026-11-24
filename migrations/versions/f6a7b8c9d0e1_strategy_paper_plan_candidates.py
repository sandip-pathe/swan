"""Persist blocked, review-linked paper-plan candidates."""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strategy_paper_plan_candidates",
        sa.Column("candidate_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "assessment_id", sa.String(length=64),
            sa.ForeignKey("strategy_assessments.id"), nullable=False,
        ),
        sa.Column(
            "source_plan_id", sa.String(length=64),
            sa.ForeignKey("strategy_plan_drafts.plan_id"), nullable=False,
        ),
        sa.Column(
            "review_assignment_id", sa.Uuid(),
            sa.ForeignKey("agent_assignments.id"), nullable=False,
        ),
        sa.Column(
            "review_artifact_id", sa.Uuid(),
            sa.ForeignKey("agent_artifacts.id"), nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "source_plan_id", "review_artifact_id", name="one_reviewed_plan_candidate"
        ),
        sa.CheckConstraint("status = 'BLOCKED'", name="paper_candidate_blocked"),
        sa.CheckConstraint(
            "(payload ->> 'execution_eligible') = 'false'",
            name="paper_candidate_non_executable",
        ),
    )
    op.create_index(
        "strategy_paper_candidate_created",
        "strategy_paper_plan_candidates",
        ["created_at"],
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM strategy_paper_plan_candidates)")
    ):
        raise RuntimeError("Preserve reviewed paper-plan candidate evidence before downgrade")
    op.drop_index(
        "strategy_paper_candidate_created", table_name="strategy_paper_plan_candidates"
    )
    op.drop_table("strategy_paper_plan_candidates")
