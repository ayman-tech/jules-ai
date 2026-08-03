"""Add editable generated artifacts and organization brand kits."""

from alembic import op
import sqlalchemy as sa

from app import models  # noqa: F401
from app.database import Base


revision = "0006_generated_artifacts"
down_revision = "0005_web_search_default"
branch_labels = None
depends_on = None


NEW_TABLES = (
    "organization_brand_kits",
    "generated_artifacts",
    "artifact_versions",
    "artifact_jobs",
    "artifact_citations",
)


def upgrade() -> None:
    connection = op.get_bind()
    existing = set(sa.inspect(connection).get_table_names())
    for table_name in NEW_TABLES:
        if table_name not in existing:
            Base.metadata.tables[table_name].create(bind=connection, checkfirst=True)


def downgrade() -> None:
    for table_name in reversed(NEW_TABLES):
        op.drop_table(table_name)
