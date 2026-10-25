"""Explicit backup-and-rehearse helper. Never upgrades/downgrades the source database."""
from pathlib import Path
import shutil
import sqlite3

from alembic import command
from alembic.config import Config

from backend.core.database import create_engine_only
from backend.db.migrate import upgrade_database
from batch.archive import safe_root
from batch.contracts import canonical, digest
from batch.files import atomic_bytes, file_hash

LEGACY = ("users", "chat_sessions", "messages", "message_sources")


def legacy_facts(connection):
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    facts = {}
    for table in LEGACY:
        if table in tables:
            rows = connection.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
            normalized = [[value.hex() if isinstance(value, bytes) else value for value in row] for row in rows]
            facts[table] = {"rows": len(rows), "sha256": digest(canonical(normalized))}
    return facts


def rehearsal(source, destination):
    source, destination = safe_root(source), safe_root(destination)
    if not source.is_file(): raise ValueError("Identify a real SQLite file before requesting rehearsal")
    if destination.exists(): raise ValueError("Use a fresh backup/staging directory; prior backups are never replaced")
    destination.mkdir(parents=True)
    backup = destination / "verified-backup.sqlite3"
    # Read-only URI plus SQLite's backup API includes WAL state consistently.
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as original, sqlite3.connect(backup) as snapshot:
        before = legacy_facts(original)
        original.backup(snapshot)
        if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or legacy_facts(snapshot) != before:
            raise ValueError("Backup verification failed; stop and investigate before any upgrade")
    stage = destination / "upgrade-staging.sqlite3"
    shutil.copyfile(backup, stage)
    engine = create_engine_only(f"sqlite:///{stage.resolve()}")
    try:
        upgrade_database(engine)
        cfg = Config()
        cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "backend/db/migrations"))
        rollback = "not_attempted"
        try:
            with engine.begin() as conn:
                cfg.attributes["connection"] = conn
                command.downgrade(cfg, "base")
        except RuntimeError:
            rollback = "destructive_downgrade_refused; restore verified backup to a new file instead"
    finally:
        engine.dispose()
    with sqlite3.connect(stage) as checked:
        preserved = legacy_facts(checked) == before
        integrity = checked.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        foreign_keys = checked.execute("PRAGMA foreign_key_check").fetchall() == []
        revision = checked.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    result = dict(status="pass" if preserved and integrity and foreign_keys else "fail", legacy_preserved=preserved,
        integrity_ok=integrity, foreign_keys_ok=foreign_keys, revision=revision, rollback=rollback,
        backup_sha256=file_hash(backup), original_migrated=False)
    atomic_bytes(destination / "migration-report.json", (canonical(result) + "\n").encode())
    if result["status"] != "pass": raise ValueError("Staged migration failed validation; original untouched, inspect migration-report.json")
    return result
