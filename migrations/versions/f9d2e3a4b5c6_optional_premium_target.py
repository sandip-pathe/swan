"""Allow underlying-target strategies without a fictional premium target."""

import sqlalchemy as sa
from alembic import op

revision = "f9d2e3a4b5c6"
down_revision = "f8c1d2e3a4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("paper_positions", "target", existing_type=sa.Numeric(18, 4), nullable=True)


def downgrade():
    # Do not invent a target to make existing underlying-only positions fit.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM paper_positions WHERE target IS NULL")):
        raise RuntimeError("Underlying-only positions prevent removing nullable premium targets")
    op.alter_column("paper_positions", "target", existing_type=sa.Numeric(18, 4), nullable=False)
