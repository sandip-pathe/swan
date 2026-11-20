"""Account-owned saved contract watchlist."""

import sqlalchemy as sa
from alembic import op

revision = "a2f6bcd87407"
down_revision = "f1e5abc76306"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "watchlist_items",
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), primary_key=True),
        sa.Column("instrument_id", sa.String(), sa.ForeignKey("instruments.id"), primary_key=True),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM watchlist_items)")):
        raise RuntimeError("Preserve saved watchlists before downgrade")
    op.drop_table("watchlist_items")
