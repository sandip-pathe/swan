"""Durable bounded agent assignments and shared artifacts."""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("request_key", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_refs", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.JSON()),
        sa.UniqueConstraint("account_id", "request_key", name="one_agent_assignment_per_request"),
    )
    op.create_index("ix_agent_assignments_account_id", "agent_assignments", ["account_id"])
    op.create_index("agent_assignment_account_created", "agent_assignments", ["account_id", "created_at"])
    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assignment_id", sa.Uuid(), sa.ForeignKey("agent_assignments.id"), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_agent_artifacts_assignment_id", "agent_artifacts", ["assignment_id"])
    op.create_index("agent_artifact_assignment_created", "agent_artifacts", ["assignment_id", "created_at"])


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM agent_artifacts)")) or bind.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM agent_assignments)")):
        raise RuntimeError("Preserve agent assignment and artifact history before downgrade")
    op.drop_index("agent_artifact_assignment_created", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_assignment_id", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
    op.drop_index("agent_assignment_account_created", table_name="agent_assignments")
    op.drop_index("ix_agent_assignments_account_id", table_name="agent_assignments")
    op.drop_table("agent_assignments")
