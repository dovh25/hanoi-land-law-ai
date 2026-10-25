"""Adopt the existing Phase A schema without dropping or rewriting user tables."""
from alembic import op
from sqlalchemy import inspect

revision = "0001_application"
down_revision = None
branch_labels = depends_on = None

# Frozen baseline, intentionally independent of evolving ORM classes.
TABLES = {
    "users": "id INTEGER NOT NULL PRIMARY KEY, username VARCHAR(50) NOT NULL, password_hash VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL",
    "chat_sessions": "id VARCHAR(36) NOT NULL PRIMARY KEY, user_id INTEGER NOT NULL, title VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL",
    "messages": "id INTEGER NOT NULL PRIMARY KEY, session_id VARCHAR(36) NOT NULL, role VARCHAR(20) NOT NULL, content TEXT NOT NULL, timestamp DATETIME NOT NULL",
    "message_sources": "id INTEGER NOT NULL PRIMARY KEY, message_id INTEGER NOT NULL, document_id VARCHAR(50), document_type VARCHAR(100), document_title VARCHAR(500), phan VARCHAR(255), chuong VARCHAR(255), muc VARCHAR(255), dieu VARCHAR(255), chapter VARCHAR(255), section VARCHAR(255), article VARCHAR(100), article_title VARCHAR(500), clause VARCHAR(255), source_text TEXT",
}
FOREIGN_KEYS = {"chat_sessions": ("user_id", "users"), "messages": ("session_id", "chat_sessions"),
                "message_sources": ("message_id", "messages")}
INDEXES = {
    "users": [("id", False), ("username", True)],
    "chat_sessions": [("user_id", False)],
    "messages": [("id", False), ("session_id", False)],
    "message_sources": [("id", False), ("message_id", False)],
}


def upgrade():
    connection = op.get_bind()
    existing = set(inspect(connection).get_table_names())
    # Check all existing shapes first; never silently stamp an incompatible legacy DB.
    for name, ddl in TABLES.items():
        if name in existing:
            expected = {entry.strip().split()[0] for entry in ddl.split(",")}
            columns = {column["name"] for column in inspect(connection).get_columns(name)}
            if not expected <= columns:
                raise RuntimeError("Legacy application schema differs from the supported baseline")
            actual = {column["name"]: column for column in inspect(connection).get_columns(name)}
            for entry in ddl.split(","):
                parts = entry.strip().split()
                column, expected_type = parts[0], parts[1].split("(")[0]
                actual_type = str(actual[column]["type"]).split("(")[0]
                if actual_type.upper() != expected_type.upper() or ("NOT NULL" in entry and actual[column]["nullable"]):
                    raise RuntimeError("Legacy column type/nullability needs explicit migration review")
            if inspect(connection).get_pk_constraint(name)["constrained_columns"] != ["id"]:
                raise RuntimeError("Legacy primary key needs explicit migration review")
    for name, ddl in TABLES.items():
        definition = ",\n".join(entry.strip() for entry in ddl.split(","))
        if name in FOREIGN_KEYS:
            column, target = FOREIGN_KEYS[name]
            definition += f",\nFOREIGN KEY({column}) REFERENCES {target} (id) ON DELETE CASCADE"
        connection.exec_driver_sql(f"CREATE TABLE IF NOT EXISTS {name} (\n{definition}\n)")
        for column, unique in INDEXES[name]:
            connection.exec_driver_sql(f"CREATE {'UNIQUE ' if unique else ''}INDEX IF NOT EXISTS ix_{name}_{column} ON {name} ({column})")


def downgrade():
    raise RuntimeError("Downgrade is disabled: existing users and conversations must be preserved")
