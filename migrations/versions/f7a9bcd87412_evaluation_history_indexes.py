"""Index owned evaluation and request history without copying private payloads."""

import sqlalchemy as sa
from alembic import op

revision = "f7a9bcd87412"
down_revision = "e6d0fab21811"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "audit_evaluation_history",
        "audit_events",
        [
            "account_id",
            "kind",
            sa.text("CAST(details ->> 'evaluation_id' AS VARCHAR)"),
            "timestamp",
            "id",
        ],
    )
    op.create_index(
        "audit_request_history",
        "audit_events",
        [
            "account_id",
            "kind",
            sa.text("CAST((details -> 'request') ->> 'evaluation_id' AS VARCHAR)"),
            "timestamp",
            "id",
        ],
    )


def downgrade():
    op.drop_index("audit_request_history", table_name="audit_events")
    op.drop_index("audit_evaluation_history", table_name="audit_events")
