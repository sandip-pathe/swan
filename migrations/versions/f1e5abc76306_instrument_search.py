"""Cache the supported public instrument catalog for search."""

import sqlalchemy as sa
from alembic import op

revision = "f1e5abc76306"
down_revision = "e0d4fab65205"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "listed_instruments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("catalog_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_listed_instruments_catalog_at", "listed_instruments", ["catalog_at"])


def downgrade():
    op.drop_index("ix_listed_instruments_catalog_at", table_name="listed_instruments")
    op.drop_table("listed_instruments")
