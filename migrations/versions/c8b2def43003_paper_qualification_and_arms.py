"""Scoped qualification and explicit paper arming; historical evidence stays unbound."""

import sqlalchemy as sa
from alembic import op

revision = "c8b2def43003"
down_revision = "b7a1cde32902"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("paper_validations", sa.Column("qualification_binding", sa.String()))
    op.create_table(
        "paper_qualifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("binding", sa.String(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("matrix_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
    )
    op.create_index("ix_paper_qualifications_account_id", "paper_qualifications", ["account_id"])
    op.create_table(
        "paper_arms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column(
            "qualification_id", sa.Uuid(), sa.ForeignKey("paper_qualifications.id"), nullable=False
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        sa.Column("stop_reason", sa.String()),
        sa.Column("stream_generation", sa.Integer(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'STOPPED')", name="paper_arm_status"),
    )
    op.create_index("ix_paper_arms_account_id", "paper_arms", ["account_id"])
    op.create_index(
        "one_active_paper_arm",
        "paper_arms",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.add_column("paper_orders", sa.Column("arm_id", sa.Uuid(), sa.ForeignKey("paper_arms.id")))
    op.create_index("ix_paper_orders_arm_id", "paper_orders", ["arm_id"])
    op.add_column(
        "evaluation_slots", sa.Column("arm_id", sa.Uuid(), sa.ForeignKey("paper_arms.id"))
    )


def downgrade():
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM paper_qualifications) OR EXISTS (SELECT 1 FROM paper_arms) THEN RAISE EXCEPTION 'Preserve qualification and arming evidence before downgrade'; END IF; END $$;"
    )
    op.drop_column("evaluation_slots", "arm_id")
    op.drop_index("ix_paper_orders_arm_id", table_name="paper_orders")
    op.drop_column("paper_orders", "arm_id")
    op.drop_table("paper_arms")
    op.drop_table("paper_qualifications")
    op.drop_column("paper_validations", "qualification_binding")
