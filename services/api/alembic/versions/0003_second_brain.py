"""Add internal knowledge, citations, memory, review, and web-search state."""

from alembic import op
import sqlalchemy as sa

from app import models  # noqa: F401
from app.database import Base


revision = "0003_second_brain"
down_revision = "0002_private_model_labels"
branch_labels = None
depends_on = None


NEW_TABLES = (
    "knowledge_bases",
    "knowledge_base_access",
    "knowledge_documents",
    "knowledge_document_versions",
    "knowledge_sections",
    "knowledge_chunks",
    "ingestion_jobs",
    "knowledge_conflicts",
    "knowledge_proposals",
    "conversation_summaries",
    "private_chat_memories",
    "message_citations",
    "unanswered_questions",
    "answer_feedback",
)


def _column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if column.name not in _column_names(table):
        op.add_column(table, column)


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    existing = set(sa.inspect(connection).get_table_names())
    for table_name in NEW_TABLES:
        if table_name not in existing:
            Base.metadata.tables[table_name].create(bind=connection, checkfirst=True)

    if connection.dialect.name == "postgresql":
        op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"))
        op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_content_fts ON knowledge_chunks USING gin (to_tsvector('english', content))"))

    _add_column_if_missing("user_settings", sa.Column("web_search_default", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing("conversations", sa.Column("knowledge_base_ids_json", sa.Text(), nullable=False, server_default="[]"))
    _add_column_if_missing("conversations", sa.Column("web_search_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing("messages", sa.Column("knowledge_base_ids_json", sa.Text(), nullable=False, server_default="[]"))
    _add_column_if_missing("messages", sa.Column("web_search_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing("messages", sa.Column("grounding_status", sa.String(length=32), nullable=False, server_default="not_requested"))


def downgrade() -> None:
    for table_name in reversed(NEW_TABLES):
        op.drop_table(table_name)
    op.drop_column("messages", "grounding_status")
    op.drop_column("messages", "web_search_enabled")
    op.drop_column("messages", "knowledge_base_ids_json")
    op.drop_column("conversations", "web_search_enabled")
    op.drop_column("conversations", "knowledge_base_ids_json")
    op.drop_column("user_settings", "web_search_default")
