"""Persist deterministic underlying exit policy on paper positions."""

import sqlalchemy as sa
from alembic import op

revision = "f8c1d2e3a4b5"
down_revision = ("f6a7b8c9d0e1", "f7a9bcd87412")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("paper_positions", sa.Column("underlying_exit_policy", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("paper_positions", "underlying_exit_policy")
