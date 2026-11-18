from alembic import context

import services.worker.models  # noqa: F401 -- register worker tables for Alembic metadata
from services.core.database import make_engine
from services.core.models import Base

config = context.config


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        dialect_name="postgresql",
        target_metadata=Base.metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    engine = make_engine()
    with engine.connect() as connection:
        run(connection)
    engine.dispose()
