"""Reuse caller transactions; CLI uses root settings without logging URLs."""
from alembic import context
from backend.db.base import Base
from backend.db import models  # noqa: F401


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Migration adoption checks require an online SQLite connection; no external services")
connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    from backend.core.config import get_settings
    from backend.core.database import create_engine_only
    engine = create_engine_only(get_settings().DATABASE_URL)
    try:
        with engine.begin() as connection:
            run(connection)
    finally:
        engine.dispose()
