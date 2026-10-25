"""Add immutable legal metadata and sealed corpus releases."""
from alembic import op
from backend.db.legal_schema_v1 import metadata, install_guards

revision = "0002_legal_domain"
down_revision = "0001_application"
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    # Legal schema must be migration-owned; do not adopt arbitrary preexisting tables.
    from sqlalchemy import inspect
    if set(metadata.tables) & set(inspect(connection).get_table_names()):
        raise RuntimeError("Unversioned legal tables require manual schema review")
    metadata.create_all(connection)
    install_guards(connection)


def downgrade():
    raise RuntimeError("Legal history cannot be dropped by an automatic downgrade")
