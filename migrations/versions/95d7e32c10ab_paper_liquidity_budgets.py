"""Persistent conservative depth budgets and fill consumption evidence."""

import sqlalchemy as sa
from alembic import op

revision = "95d7e32c10ab"
down_revision = "84c6d21b09fa"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM paper_fills WHERE execution_version <> 'legacy-immediate-v1') THEN
            RAISE EXCEPTION 'Existing durable fills need a reviewed liquidity-evidence migration';
        END IF;
    END $$;""")
    op.create_table(
        "paper_liquidity_levels",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("session_key", sa.Date(), nullable=False),
        sa.Column("instrument_id", sa.String(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("displayed", sa.BigInteger(), nullable=False),
        sa.Column("capacity", sa.BigInteger(), nullable=False),
        sa.Column("consumed", sa.BigInteger(), nullable=False),
        sa.Column("observation_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("config_version", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "account_id",
            "session_key",
            "instrument_id",
            "side",
            "price",
            name="liquidity_level_scope",
        ),
        sa.CheckConstraint(
            "capacity >= 0 AND consumed >= 0 AND consumed <= capacity AND displayed >= 0",
            name="liquidity_capacity_bounds",
        ),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="liquidity_side"),
    )
    op.create_index(
        "ix_paper_liquidity_levels_account_id", "paper_liquidity_levels", ["account_id"]
    )
    op.create_table(
        "paper_liquidity_uses",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "level_id", sa.Uuid(), sa.ForeignKey("paper_liquidity_levels.id"), nullable=False
        ),
        sa.Column("fill_id", sa.Uuid(), sa.ForeignKey("paper_fills.id"), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("raw_price", sa.Numeric(18, 4), nullable=False),
        sa.UniqueConstraint("fill_id", name="one_liquidity_use_per_fill"),
        sa.CheckConstraint("quantity > 0", name="liquidity_use_positive"),
    )
    op.create_index("ix_paper_liquidity_uses_level_id", "paper_liquidity_uses", ["level_id"])


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM paper_liquidity_uses) THEN
            RAISE EXCEPTION 'Liquidity fill history exists; restore a reviewed backup instead';
        END IF;
    END $$;""")
    op.drop_table("paper_liquidity_uses")
    op.drop_table("paper_liquidity_levels")
