"""Add editable generated artifacts and organization brand kits."""

from alembic import op
import sqlalchemy as sa


revision = "0006_generated_artifacts"
down_revision = "0005_web_search_default"
branch_labels = None
depends_on = None


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    artifact_tables = {"generated_artifacts", "artifact_versions", "artifact_jobs", "artifact_citations"}
    if artifact_tables.issubset(existing):
        return
    op.create_table(
        "organization_brand_kits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logo_storage_key", sa.String(length=1000), unique=True),
        sa.Column("logo_file_name", sa.String(length=320)),
        sa.Column("logo_mime_type", sa.String(length=160)),
        sa.Column("primary_color", sa.String(length=7), nullable=False),
        sa.Column("accent_color", sa.String(length=7), nullable=False),
        sa.Column("heading_font", sa.String(length=80), nullable=False),
        sa.Column("body_font", sa.String(length=80), nullable=False),
        sa.Column("footer_text", sa.String(length=240), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index("ix_organization_brand_kits_organization_id", "organization_brand_kits", ["organization_id"])

    op.create_table(
        "generated_artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.String(length=36), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("template_id", sa.String(length=80), nullable=False),
        sa.Column("use_brand_kit", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("source_scope_json", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        *timestamps(),
    )
    for column in ("organization_id", "user_id", "conversation_id", "message_id"):
        op.create_index(f"ix_generated_artifacts_{column}", "generated_artifacts", [column])
    op.create_index("ix_generated_artifact_scope", "generated_artifacts", ["organization_id", "user_id", "conversation_id", "created_at"])

    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), sa.ForeignKey("generated_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("source_scope_json", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), unique=True),
        sa.Column("file_name", sa.String(length=320)),
        sa.Column("mime_type", sa.String(length=160)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("sha256", sa.String(length=64)),
        sa.Column("preview_keys_json", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer()),
        sa.Column("content_spec_json", sa.Text(), nullable=False),
        sa.Column("qa_json", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        *timestamps(),
        sa.UniqueConstraint("artifact_id", "version_number"),
    )
    for column in ("organization_id", "user_id", "artifact_id", "sha256"):
        op.create_index(f"ix_artifact_versions_{column}", "artifact_versions", [column])
    op.create_index("ix_artifact_version_scope", "artifact_versions", ["organization_id", "artifact_id", "version_number"])

    op.create_table(
        "artifact_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), sa.ForeignKey("generated_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("artifact_versions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *timestamps(),
    )
    for column in ("organization_id", "artifact_id"):
        op.create_index(f"ix_artifact_jobs_{column}", "artifact_jobs", [column])
    op.create_index("ix_artifact_job_status", "artifact_jobs", ["status", "created_at"])

    op.create_table(
        "artifact_citations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("artifact_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), sa.ForeignKey("knowledge_bases.id", ondelete="SET NULL")),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("knowledge_documents.id", ondelete="SET NULL")),
        sa.Column("document_version_id", sa.String(length=36), sa.ForeignKey("knowledge_document_versions.id", ondelete="SET NULL")),
        sa.Column("chunk_id", sa.String(length=36), sa.ForeignKey("knowledge_chunks.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("location", sa.String(length=500)),
        sa.Column("url", sa.String(length=2000)),
        sa.Column("publisher", sa.String(length=500)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        *timestamps(),
    )
    for column in ("organization_id", "version_id", "knowledge_base_id"):
        op.create_index(f"ix_artifact_citations_{column}", "artifact_citations", [column])
    op.create_index("ix_artifact_citation_version", "artifact_citations", ["version_id", "ordinal"])


def downgrade() -> None:
    for table_name in (
        "artifact_citations",
        "artifact_jobs",
        "artifact_versions",
        "generated_artifacts",
        "organization_brand_kits",
    ):
        op.drop_table(table_name)
