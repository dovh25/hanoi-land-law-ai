"""Database resources are owned by the application lifespan, not module imports."""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

def create_engine_only(url: str):
    parsed = make_url(url)
    kwargs = {}
    if parsed.get_backend_name() == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
        if parsed.database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool
        else:
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, **kwargs)
    if parsed.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")
        @event.listens_for(engine, "begin")
        def begin(connection):
            connection.exec_driver_sql("BEGIN")
    else:
        raise ValueError("This project currently supports SQLite only")
    return engine


def create_database(url: str):
    engine = create_engine_only(url)
    from backend.db import models  # noqa: F401
    from backend.db.migrate import upgrade_database
    try:
        upgrade_database(engine)
    except Exception:
        engine.dispose()
        raise
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
