"""Observed candle segments remain separate across stream connections."""

import sqlalchemy as sa
from alembic import op

revision = "e0d4fab65205"
down_revision = "d9c3efa54104"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "live_candle_segments",
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), primary_key=True),
        sa.Column("instrument_id", sa.String(), sa.ForeignKey("instruments.id"), primary_key=True),
        sa.Column("stream_id", sa.Uuid(), primary_key=True),
        sa.Column("opens_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index(
        "live_candles_account_range",
        "live_candle_segments",
        ["account_id", "instrument_id", "opens_at"],
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM live_candle_segments)")):
        raise RuntimeError("Preserve observed candle evidence before downgrade")
    op.drop_index("live_candles_account_range", table_name="live_candle_segments")
    op.drop_table("live_candle_segments")
