"""Expiring selected-chart display interest."""

import sqlalchemy as sa
from alembic import op

revision = "b3a7cde98508"
down_revision = "a2f6bcd87407"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "display_selections",
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), primary_key=True),
        sa.Column("instrument_id", sa.String(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("display_selections")
