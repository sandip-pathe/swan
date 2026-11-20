"""Durable human paper plans without order or AI approval semantics."""

import sqlalchemy as sa
from alembic import op

revision = "d5c9efa10710"
down_revision = "c4b8def09609"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "manual_paper_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False, index=True
        ),
        sa.Column("instrument_id", sa.String(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("instrument_payload", sa.JSON(), nullable=False),
        sa.Column("preview_payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("account_id", "idempotency_key", name="one_manual_plan_per_request"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM manual_paper_plans)")):
        raise RuntimeError("Preserve manual paper plans before downgrade")
    op.drop_table("manual_paper_plans")
