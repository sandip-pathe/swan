"""Retain broker index observations separately from executable instruments."""

import sqlalchemy as sa
from alembic import op

revision = "c4b8def09609"
down_revision = "b3a7cde98508"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "underlying_references",
        sa.Column("underlying", sa.String(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("underlying_references")
