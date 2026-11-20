"""Explicit human entry source on the existing durable ledger."""

import sqlalchemy as sa
from alembic import op

revision = "e6d0fab21811"
down_revision = "d5c9efa10710"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "manual_paper_intents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False, index=True
        ),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("manual_paper_plans.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
    )
    op.add_column(
        "paper_orders",
        sa.Column("manual_intent_id", sa.Uuid(), sa.ForeignKey("manual_paper_intents.id")),
    )
    op.create_unique_constraint("one_entry_per_manual_intent", "paper_orders", ["manual_intent_id"])
    op.create_check_constraint(
        "exclusive_entry_source", "paper_orders", "decision_id IS NULL OR manual_intent_id IS NULL"
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM manual_paper_intents)")):
        raise RuntimeError("Preserve manual entry history before downgrade")
    op.drop_constraint("exclusive_entry_source", "paper_orders", type_="check")
    op.drop_constraint("one_entry_per_manual_intent", "paper_orders", type_="unique")
    op.drop_column("paper_orders", "manual_intent_id")
    op.drop_table("manual_paper_intents")
