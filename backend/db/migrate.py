"""Migration helper used by startup and isolated tests, never at module import."""
from pathlib import Path
from alembic import command
from alembic.config import Config


def upgrade_database(engine, revision="head"):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)
