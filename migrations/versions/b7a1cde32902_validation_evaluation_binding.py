"""Bind in-flight analysis to its original validation session."""

import sqlalchemy as sa
from alembic import op

revision = "b7a1cde32902"
down_revision = "a6f0bce21801"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "evaluation_slots",
        sa.Column("validation_id", sa.Uuid(), sa.ForeignKey("paper_validations.id")),
    )


def downgrade():
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM evaluation_slots WHERE validation_id IS NOT NULL) THEN RAISE EXCEPTION 'Preserve evaluation binding before downgrade'; END IF; END $$;"
    )
    op.drop_column("evaluation_slots", "validation_id")
