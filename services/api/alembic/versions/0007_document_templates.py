"""Replace organization brand kits with validated DOCX templates."""

from alembic import op
import sqlalchemy as sa

from app import models  # noqa: F401
from app.database import Base


revision = "0007_document_templates"
down_revision = "0006_generated_artifacts"
branch_labels = None
depends_on = None


NEW_TABLES = (
    "organization_document_templates",
    "organization_document_template_versions",
    "document_template_validation_jobs",
    "storage_cleanup_jobs",
)


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing = set(inspector.get_table_names())
    for table_name in NEW_TABLES:
        if table_name not in existing:
            Base.metadata.tables[table_name].create(bind=connection, checkfirst=True)

    artifact_columns = {item["name"] for item in inspector.get_columns("generated_artifacts")}
    with op.batch_alter_table("generated_artifacts") as batch:
        if "use_document_template" not in artifact_columns:
            batch.add_column(sa.Column("use_document_template", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "use_brand_kit" in artifact_columns:
        connection.execute(sa.text(
            "UPDATE generated_artifacts SET use_document_template = use_brand_kit"
        ))
        with op.batch_alter_table("generated_artifacts") as batch:
            batch.drop_column("use_brand_kit")

    inspector = sa.inspect(connection)
    version_columns = {item["name"] for item in inspector.get_columns("artifact_versions")}
    with op.batch_alter_table("artifact_versions") as batch:
        if "document_template_version_id" not in version_columns:
            batch.add_column(sa.Column("document_template_version_id", sa.String(length=36), nullable=True))
            batch.create_index("ix_artifact_versions_document_template_version_id", ["document_template_version_id"])
            batch.create_foreign_key(
                "fk_artifact_version_document_template",
                "organization_document_template_versions",
                ["document_template_version_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "document_template_snapshot_json" not in version_columns:
            batch.add_column(sa.Column("document_template_snapshot_json", sa.Text(), nullable=False, server_default="{}"))

    if "organization_brand_kits" in set(sa.inspect(connection).get_table_names()):
        rows = connection.execute(sa.text(
            "SELECT logo_storage_key FROM organization_brand_kits WHERE logo_storage_key IS NOT NULL"
        )).fetchall()
        cleanup = Base.metadata.tables["storage_cleanup_jobs"]
        for (storage_key,) in rows:
            connection.execute(cleanup.insert().values(
                id=models.new_id(),
                storage_key=storage_key,
                reason="brand_kit_removed",
                attempts=0,
            ))
        op.drop_table("organization_brand_kits")


def downgrade() -> None:
    op.create_table(
        "organization_brand_kits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logo_storage_key", sa.String(length=1000), unique=True),
        sa.Column("logo_file_name", sa.String(length=320)),
        sa.Column("logo_mime_type", sa.String(length=160)),
        sa.Column("primary_color", sa.String(length=7), nullable=False, server_default="#4C1D95"),
        sa.Column("accent_color", sa.String(length=7), nullable=False, server_default="#7C3AED"),
        sa.Column("heading_font", sa.String(length=80), nullable=False, server_default="Aptos Display"),
        sa.Column("body_font", sa.String(length=80), nullable=False, server_default="Aptos"),
        sa.Column("footer_text", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index("ix_organization_brand_kits_organization_id", "organization_brand_kits", ["organization_id"])

    with op.batch_alter_table("generated_artifacts") as batch:
        batch.add_column(sa.Column("use_brand_kit", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute("UPDATE generated_artifacts SET use_brand_kit = use_document_template")
    with op.batch_alter_table("generated_artifacts") as batch:
        batch.drop_column("use_document_template")

    with op.batch_alter_table("artifact_versions") as batch:
        batch.drop_constraint("fk_artifact_version_document_template", type_="foreignkey")
        batch.drop_index("ix_artifact_versions_document_template_version_id")
        batch.drop_column("document_template_snapshot_json")
        batch.drop_column("document_template_version_id")

    for table_name in reversed(NEW_TABLES):
        op.drop_table(table_name)
