from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from .database import Base
from .model_catalog import DEFAULT_MODEL_ID


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    avatar_url: Mapped[str | None] = mapped_column(String(1000))


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180))
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)


class Membership(Base, TimestampMixin):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Invitation(Base, TimestampMixin):
    __tablename__ = "organization_invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    custom_instructions: Mapped[str] = mapped_column(Text, default="")
    theme: Mapped[str] = mapped_column(String(16), default="system")
    default_model: Mapped[str] = mapped_column(String(120), default=DEFAULT_MODEL_ID)
    default_effort: Mapped[str] = mapped_column(String(16), default="medium")
    web_search_default: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversation_scope", "organization_id", "user_id", "updated_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240), default="New conversation")
    model: Mapped[str] = mapped_column(String(120), default=DEFAULT_MODEL_ID)
    effort: Mapped[str] = mapped_column(String(16), default="medium")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    knowledge_base_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    web_search_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_message_scope", "organization_id", "user_id", "conversation_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="completed")
    knowledge_base_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    web_search_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    grounding_status: Mapped[str] = mapped_column(String(32), default="not_requested")


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachment_scope", "organization_id", "user_id", "conversation_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(String(320))
    mime_type: Mapped[str] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True)
    scan_status: Mapped[str] = mapped_column(String(16), default="clean")


class Prompt(Base, TimestampMixin):
    __tablename__ = "prompts"
    __table_args__ = (Index("ix_prompt_organization_archived", "organization_id", "archived"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    last_editor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "version_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    edited_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PromptFavorite(Base):
    __tablename__ = "prompt_favorites"
    __table_args__ = (UniqueConstraint("prompt_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class ModelConfiguration(Base, TimestampMixin):
    __tablename__ = "model_configurations"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(180))
    supports_effort: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_files: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class OrganizationModelPolicy(Base, TimestampMixin):
    __tablename__ = "organization_model_policies"
    __table_args__ = (UniqueConstraint("organization_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    allowed_models_json: Mapped[str] = mapped_column(Text, default="[]")
    default_model: Mapped[str] = mapped_column(String(120), default=DEFAULT_MODEL_ID)
    maximum_effort: Mapped[str] = mapped_column(String(16), default="high")


class OrganizationBrandKit(Base, TimestampMixin):
    __tablename__ = "organization_brand_kits"
    __table_args__ = (UniqueConstraint("organization_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    logo_storage_key: Mapped[str | None] = mapped_column(String(1000), unique=True)
    logo_file_name: Mapped[str | None] = mapped_column(String(320))
    logo_mime_type: Mapped[str | None] = mapped_column(String(160))
    primary_color: Mapped[str] = mapped_column(String(7), default="#4C1D95")
    accent_color: Mapped[str] = mapped_column(String(7), default="#7C3AED")
    heading_font: Mapped[str] = mapped_column(String(80), default="Aptos Display")
    body_font: Mapped[str] = mapped_column(String(80), default="Aptos")
    footer_text: Mapped[str] = mapped_column(String(240), default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(120))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class KnowledgeBase(Base, TimestampMixin):
    __tablename__ = "knowledge_bases"
    __table_args__ = (Index("ix_knowledge_base_scope", "organization_id", "archived"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeBaseAccess(Base, TimestampMixin):
    __tablename__ = "knowledge_base_access"
    __table_args__ = (UniqueConstraint("knowledge_base_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    granted_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text, default="")


class KnowledgeDocument(Base, TimestampMixin):
    __tablename__ = "knowledge_documents"
    __table_args__ = (Index("ix_knowledge_document_scope", "organization_id", "knowledge_base_id", "archived"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(320))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeDocumentVersion(Base, TimestampMixin):
    __tablename__ = "knowledge_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number"),
        Index("ix_knowledge_version_hash", "organization_id", "knowledge_base_id", "sha256"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String(320))
    mime_type: Mapped[str] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    normalized_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    extraction_status: Mapped[str] = mapped_column(String(24), default="queued")
    extraction_quality: Mapped[str] = mapped_column(String(24), default="pending")
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class KnowledgeSection(Base, TimestampMixin):
    __tablename__ = "knowledge_sections"
    __table_args__ = (Index("ix_knowledge_section_scope", "organization_id", "knowledge_base_id", "document_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500), default="Document")
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)


class KnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (Index("ix_knowledge_chunk_scope", "organization_id", "knowledge_base_id", "document_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[str] = mapped_column(ForeignKey("knowledge_sections.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="text")
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768).with_variant(JSON, "sqlite"))


class IngestionJob(Base, TimestampMixin):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (Index("ix_ingestion_job_status", "status", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GeneratedArtifact(Base, TimestampMixin):
    __tablename__ = "generated_artifacts"
    __table_args__ = (Index("ix_generated_artifact_scope", "organization_id", "user_id", "conversation_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    format: Mapped[str] = mapped_column(String(8))
    template_id: Mapped[str] = mapped_column(String(80), default="auto")
    use_brand_kit: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    source_scope_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text)


class ArtifactVersion(Base, TimestampMixin):
    __tablename__ = "artifact_versions"
    __table_args__ = (
        UniqueConstraint("artifact_id", "version_number"),
        Index("ix_artifact_version_scope", "organization_id", "artifact_id", "version_number"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("generated_artifacts.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    instructions: Mapped[str] = mapped_column(Text)
    source_scope_json: Mapped[str] = mapped_column(Text, default="{}")
    storage_key: Mapped[str | None] = mapped_column(String(1000), unique=True)
    file_name: Mapped[str | None] = mapped_column(String(320))
    mime_type: Mapped[str | None] = mapped_column(String(160))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    preview_keys_json: Mapped[str] = mapped_column(Text, default="[]")
    page_count: Mapped[int | None] = mapped_column(Integer)
    content_spec_json: Mapped[str] = mapped_column(Text, default="{}")
    qa_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text)


class ArtifactJob(Base, TimestampMixin):
    __tablename__ = "artifact_jobs"
    __table_args__ = (Index("ix_artifact_job_status", "status", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("generated_artifacts.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArtifactCitation(Base, TimestampMixin):
    __tablename__ = "artifact_citations"
    __table_args__ = (Index("ix_artifact_citation_version", "version_id", "ordinal"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("artifact_versions.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(16))
    knowledge_base_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="SET NULL"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="SET NULL"))
    document_version_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_document_versions.id", ondelete="SET NULL"))
    chunk_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_chunks.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(1000))
    location: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(2000))
    publisher: Mapped[str | None] = mapped_column(String(500))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class KnowledgeConflict(Base, TimestampMixin):
    __tablename__ = "knowledge_conflicts"
    __table_args__ = (Index("ix_knowledge_conflict_review", "organization_id", "status", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    left_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"), index=True)
    right_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"), index=True)
    conflict_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="open")
    summary: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped[str | None] = mapped_column(Text)
    applies_when: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class KnowledgeProposal(Base, TimestampMixin):
    __tablename__ = "knowledge_proposals"
    __table_args__ = (Index("ix_knowledge_proposal_review", "organization_id", "status", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    proposed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(Text)


class ConversationSummary(Base, TimestampMixin):
    __tablename__ = "conversation_summaries"
    __table_args__ = (UniqueConstraint("conversation_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")


class PrivateChatMemory(Base, TimestampMixin):
    __tablename__ = "private_chat_memories"
    __table_args__ = (Index("ix_private_memory_scope", "organization_id", "user_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768).with_variant(JSON, "sqlite"))


class MessageCitation(Base, TimestampMixin):
    __tablename__ = "message_citations"
    __table_args__ = (Index("ix_message_citation_message", "message_id", "ordinal"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    ordinal: Mapped[int] = mapped_column(Integer)
    knowledge_base_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="SET NULL"))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="SET NULL"))
    version_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_document_versions.id", ondelete="SET NULL"))
    chunk_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_chunks.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(2000))
    publisher: Mapped[str | None] = mapped_column(String(320))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class UnansweredQuestion(Base, TimestampMixin):
    __tablename__ = "unanswered_questions"
    __table_args__ = (Index("ix_unanswered_review", "organization_id", "status", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(120), default="no_evidence")
    status: Mapped[str] = mapped_column(String(24), default="open")


class AnswerFeedback(Base, TimestampMixin):
    __tablename__ = "answer_feedback"
    __table_args__ = (UniqueConstraint("message_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    rating: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text, default="")
