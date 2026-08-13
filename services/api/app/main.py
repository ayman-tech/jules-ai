from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import re
import secrets
from contextlib import asynccontextmanager
from datetime import timedelta, timezone
from time import perf_counter
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from starlette.datastructures import Headers
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .agent import AgentRequest, AttachmentPayload, get_chat_provider
from .auth import AuthIdentity, RequestContext, get_auth_identity, get_context, get_identity_user, require_role, require_verified_user
from .config import get_settings
from .database import SessionLocal, create_schema, get_db
from .models import (
    AnswerFeedback,
    ArtifactCitation,
    ArtifactJob,
    ArtifactVersion,
    Attachment,
    AuditEvent,
    Conversation,
    ConversationSummary,
    DocumentTemplateValidationJob,
    GeneratedArtifact,
    IngestionJob,
    Invitation,
    KnowledgeBase,
    KnowledgeBaseAccess,
    KnowledgeChunk,
    KnowledgeConflict,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeProposal,
    Membership,
    Message,
    MessageCitation,
    ModelConfiguration,
    Organization,
    OrganizationDocumentTemplate,
    OrganizationDocumentTemplateVersion,
    OrganizationModelPolicy,
    Prompt,
    PromptFavorite,
    PromptVersion,
    PrivateChatMemory,
    UnansweredQuestion,
    User,
    UserSettings,
    new_id,
    utc_now,
)
from .artifacts import FORMAT_SUFFIXES, MIME_TYPES, choose_template, delete_artifact_files, detect_requested_format
from .document_templates import (
    DOCX_MIME_TYPE,
    TemplateValidationError,
    delete_document_template_files,
    document_template_json,
    validate_template_package,
)
from .knowledge import authorized_knowledge_base_ids, embedding_for, format_internal_context, retrieve_company_knowledge
from .model_catalog import DEFAULT_MODEL_ID, MODEL_CATALOG, MODEL_IDS
from .observability import (
    RequestLoggingMiddleware,
    configure_logging,
    exception_stack,
    get_logger,
    log_event,
    log_transcript,
)
from .seed import seed_development_data
from .scanner import get_scanner
from .storage import get_storage, safe_file_name


settings = get_settings()
configure_logging(settings)
logger = get_logger("api")
storage_service = get_storage()
malware_scanner = get_scanner()
ALLOWED_ATTACHMENT_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_event(
        logger,
        logging.INFO,
        "application.starting",
        environment=settings.app_env,
        chat_provider="google_adk" if settings.google_api_key else "demo",
        storage_provider="gcs" if settings.google_cloud_storage_bucket else "local",
        transcripts_enabled=settings.app_env == "development" and settings.log_chat_transcripts,
    )
    try:
        await create_schema()
        if settings.app_env == "development":
            async with SessionLocal() as session:
                await seed_development_data(session)
        log_event(logger, logging.INFO, "application.started")
        yield
    except BaseException as exc:
        log_event(
            logger,
            logging.ERROR,
            "application.failed",
            error_type=type(exc).__name__,
            stack=exception_stack(exc),
        )
        raise
    finally:
        log_event(logger, logging.INFO, "application.stopped")


app = FastAPI(title="Jules AI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> PlainTextResponse:
    log_event(
        logger,
        logging.ERROR,
        "request.unhandled_exception",
        error_type=type(exc).__name__,
        stack=exception_stack(exc),
    )
    return PlainTextResponse("Internal Server Error", status_code=500)


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)


class AuthBootstrap(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)


class OrganizationUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=180)


class OwnershipTransfer(BaseModel):
    user_id: str


class OrganizationDelete(BaseModel):
    confirmation_name: str


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class RoleUpdate(BaseModel):
    role: Literal["admin", "member"]


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", max_length=240)
    model: str = DEFAULT_MODEL_ID
    effort: Literal["low", "medium", "high"] = "medium"
    knowledge_base_ids: list[str] | None = None
    web_search_enabled: bool | None = None


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    pinned: bool | None = None
    archived: bool | None = None
    model: str | None = None
    effort: Literal["low", "medium", "high"] | None = None
    knowledge_base_ids: list[str] | None = None
    web_search_enabled: bool | None = None


class ArtifactRequest(BaseModel):
    format: Literal["docx", "pptx"]
    template_id: str = Field(default="auto", min_length=1, max_length=80)
    use_document_template: bool = True


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)
    model: str | None = None
    effort: Literal["low", "medium", "high"] | None = None
    attachment_ids: list[str] = Field(default_factory=list, max_length=20)
    knowledge_base_ids: list[str] | None = Field(default=None, max_length=100)
    web_search_enabled: bool | None = None
    artifact_request: ArtifactRequest | None = None


class ArtifactRevisionCreate(BaseModel):
    instructions: str = Field(min_length=1, max_length=100_000)
    use_current_document_template: bool = False


class ArtifactSaveKnowledge(BaseModel):
    knowledge_base_id: str
    title: str | None = Field(default=None, max_length=320)


class PromptCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=2_000)
    body: str = Field(min_length=1, max_length=50_000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class PromptUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=2_000)
    body: str | None = Field(default=None, min_length=1, max_length=50_000)
    tags: list[str] | None = Field(default=None, max_length=20)
    archived: bool | None = None


class SettingsUpdate(BaseModel):
    custom_instructions: str | None = Field(default=None, max_length=12_000)
    theme: Literal["light", "dark", "system"] | None = None
    default_model: str | None = None
    default_effort: Literal["low", "medium", "high"] | None = None
    web_search_default: bool | None = None


class KnowledgeBaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=4000)
    member_ids: list[str] = Field(default_factory=list, max_length=500)


class KnowledgeBaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    archived: bool | None = None


class KnowledgeAccessUpdate(BaseModel):
    user_ids: list[str] = Field(max_length=500)
    reason: str = Field(default="", max_length=1000)


class AccessReason(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ConflictResolution(BaseModel):
    action: Literal["supersede", "authoritative", "keep_both", "archive", "dismiss"]
    note: str = Field(default="", max_length=4000)
    authoritative_version_id: str | None = None
    applies_when: str | None = Field(default=None, max_length=4000)


class KnowledgeProposalCreate(BaseModel):
    knowledge_base_id: str
    conversation_id: str | None = None
    message_id: str | None = None
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=50000)


class ProposalReview(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=4000)


class FeedbackCreate(BaseModel):
    rating: Literal["helpful", "incorrect", "outdated"]
    note: str = Field(default="", max_length=4000)


class ModelPolicyUpdate(BaseModel):
    allowed_models: list[str]
    default_model: str
    maximum_effort: Literal["low", "medium", "high"]


def as_iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "organization"


def normalize_email(value: str) -> str:
    return value.strip().lower()


def invitation_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def valid_invitation_token(token: str) -> bool:
    return 20 <= len(token) <= 128 and bool(re.fullmatch(r"[A-Za-z0-9_-]+", token))


def masked_email(value: str) -> str:
    local, separator, domain = value.partition("@")
    if not separator:
        return "•••"
    return f"{local[:1]}{'•' * max(3, min(len(local) - 1, 8))}@{domain}"


async def organization_memberships_json(db: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(Organization, Membership)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user_id, Membership.active.is_(True))
        .order_by(Organization.name)
    )).all()
    return [{"id": org.id, "name": org.name, "slug": org.slug, "role": membership.role} for org, membership in rows]


def validate_model_id(model: str) -> None:
    if model not in MODEL_IDS:
        raise HTTPException(status_code=400, detail="Unsupported model")


async def require_knowledge_access(db: AsyncSession, context: RequestContext, knowledge_base_id: str) -> KnowledgeBase:
    row = await db.scalar(
        select(KnowledgeBase)
        .join(KnowledgeBaseAccess, KnowledgeBaseAccess.knowledge_base_id == KnowledgeBase.id)
        .where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.organization_id == context.organization_id,
            KnowledgeBase.archived.is_(False),
            KnowledgeBaseAccess.user_id == context.user_id,
            KnowledgeBaseAccess.organization_id == context.organization_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return row


async def knowledge_base_json(db: AsyncSession, row: KnowledgeBase, context: RequestContext) -> dict[str, Any]:
    document_count = await db.scalar(select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.knowledge_base_id == row.id, KnowledgeDocument.archived.is_(False)))
    member_count = await db.scalar(select(func.count(KnowledgeBaseAccess.id)).where(KnowledgeBaseAccess.knowledge_base_id == row.id))
    has_access = bool(await db.scalar(select(KnowledgeBaseAccess.id).where(KnowledgeBaseAccess.knowledge_base_id == row.id, KnowledgeBaseAccess.user_id == context.user_id)))
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "archived": row.archived,
        "document_count": document_count or 0,
        "member_count": member_count or 0,
        "can_manage": context.role in {"owner", "admin"},
        "has_access": has_access,
        "created_at": as_iso(row.created_at),
        "updated_at": as_iso(row.updated_at),
    }


async def document_json(db: AsyncSession, row: KnowledgeDocument) -> dict[str, Any]:
    versions = (await db.scalars(select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.document_id == row.id).order_by(KnowledgeDocumentVersion.version_number.desc()))).all()
    return {
        "id": row.id,
        "knowledge_base_id": row.knowledge_base_id,
        "title": row.title,
        "current_version": row.current_version,
        "archived": row.archived,
        "created_by": row.created_by,
        "created_at": as_iso(row.created_at),
        "updated_at": as_iso(row.updated_at),
        "versions": [{
            "id": version.id,
            "version_number": version.version_number,
            "file_name": version.file_name,
            "mime_type": version.mime_type,
            "size_bytes": version.size_bytes,
            "extraction_status": version.extraction_status,
            "extraction_quality": version.extraction_quality,
            "effective_at": as_iso(version.effective_at),
            "authoritative": version.authoritative,
            "created_at": as_iso(version.created_at),
        } for version in versions],
    }


async def audit(db: AsyncSession, context: RequestContext, action: str, target_type: str, target_id: str, metadata: dict[str, Any] | None = None) -> None:
    db.add(AuditEvent(
        organization_id=context.organization_id,
        actor_user_id=context.user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=json.dumps(metadata or {}),
    ))


async def scoped_conversation(db: AsyncSession, context: RequestContext, conversation_id: str) -> Conversation:
    conversation = await db.scalar(select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.organization_id == context.organization_id,
        Conversation.user_id == context.user_id,
    ))
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


async def scoped_artifact(db: AsyncSession, context: RequestContext, artifact_id: str, *, require_sources: bool = True) -> GeneratedArtifact:
    artifact = await db.scalar(select(GeneratedArtifact).where(
        GeneratedArtifact.id == artifact_id,
        GeneratedArtifact.organization_id == context.organization_id,
        GeneratedArtifact.user_id == context.user_id,
    ))
    if not artifact:
        raise HTTPException(status_code=404, detail="Generated file not found")
    if require_sources:
        version = await db.scalar(select(ArtifactVersion).where(
            ArtifactVersion.artifact_id == artifact.id,
            ArtifactVersion.version_number == artifact.current_version,
        ))
        scope = json.loads(version.source_scope_json if version else artifact.source_scope_json or "{}")
        requested = set(scope.get("knowledge_base_ids") or [])
        if requested:
            allowed = set((await db.scalars(select(KnowledgeBaseAccess.knowledge_base_id).where(
                KnowledgeBaseAccess.organization_id == context.organization_id,
                KnowledgeBaseAccess.user_id == context.user_id,
                KnowledgeBaseAccess.knowledge_base_id.in_(requested),
            ))).all())
            if allowed != requested:
                raise HTTPException(status_code=403, detail="Access to a source used by this file has been removed")
    return artifact


def conversation_json(row: Conversation) -> dict[str, Any]:
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "user_id": row.user_id,
        "title": row.title,
        "model": row.model,
        "effort": row.effort,
        "pinned": row.pinned,
        "archived": row.archived,
        "knowledge_base_ids": json.loads(row.knowledge_base_ids_json or "[]"),
        "web_search_enabled": row.web_search_enabled,
        "created_at": as_iso(row.created_at),
        "updated_at": as_iso(row.updated_at),
    }


async def artifact_json(db: AsyncSession, row: GeneratedArtifact) -> dict[str, Any]:
    versions = (await db.scalars(select(ArtifactVersion).where(
        ArtifactVersion.artifact_id == row.id,
    ).order_by(ArtifactVersion.version_number.desc()))).all()
    current = next((item for item in versions if item.version_number == row.current_version), versions[0] if versions else None)
    job = await db.scalar(select(ArtifactJob).where(ArtifactJob.artifact_id == row.id).order_by(ArtifactJob.created_at.desc()))

    async def version_value(item: ArtifactVersion) -> dict[str, Any]:
        citations = (await db.scalars(select(ArtifactCitation).where(
            ArtifactCitation.version_id == item.id,
        ).order_by(ArtifactCitation.ordinal))).all()
        preview_keys = json.loads(item.preview_keys_json or "[]")
        return {
            "id": item.id,
            "version_number": item.version_number,
            "status": item.status,
            "file_name": item.file_name,
            "mime_type": item.mime_type,
            "size_bytes": item.size_bytes,
            "page_count": item.page_count,
            "preview_count": len(preview_keys),
            "qa": json.loads(item.qa_json or "{}"),
            "document_template_version_id": item.document_template_version_id,
            "document_template_snapshot": json.loads(item.document_template_snapshot_json or "{}"),
            "error": item.error,
            "created_at": as_iso(item.created_at),
            "citations": [{
                "id": citation.id,
                "ordinal": citation.ordinal,
                "source_type": citation.source_type,
                "knowledge_base_id": citation.knowledge_base_id,
                "document_id": citation.document_id,
                "version_id": citation.document_version_id,
                "chunk_id": citation.chunk_id,
                "title": citation.title,
                "location": citation.location,
                "url": citation.url,
                "publisher": citation.publisher,
                "retrieved_at": as_iso(citation.retrieved_at),
                "metadata": json.loads(citation.metadata_json or "{}"),
            } for citation in citations],
        }

    version_values = [await version_value(item) for item in versions]
    current_value = next((item for item in version_values if item["version_number"] == row.current_version), version_values[0] if version_values else None)
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "message_id": row.message_id,
        "title": row.title,
        "format": row.format,
        "template_id": row.template_id,
        "use_document_template": row.use_document_template,
        "status": row.status,
        "current_version": row.current_version,
        "progress": job.progress if job else (100 if row.status == "ready" else 0),
        "error": row.error,
        "version": current_value,
        "versions": version_values,
        "created_at": as_iso(row.created_at),
        "updated_at": as_iso(row.updated_at),
    }


async def queue_artifact(
    db: AsyncSession,
    *,
    context: RequestContext,
    conversation: Conversation,
    message_id: str,
    instructions: str,
    format_name: str,
    template_id: str,
    use_document_template: bool,
    model: str,
    effort: str,
    knowledge_base_ids: list[str],
    web_search_enabled: bool,
    attachment_ids: list[str],
) -> GeneratedArtifact:
    if not settings.artifact_generation_enabled:
        raise HTTPException(status_code=503, detail="File generation is disabled")
    scope = {
        "knowledge_base_ids": knowledge_base_ids,
        "web_search_enabled": web_search_enabled,
        "attachment_ids": attachment_ids,
        "model": model,
        "effort": effort,
    }
    document_template_version: OrganizationDocumentTemplateVersion | None = None
    document_template_snapshot: dict[str, Any] = {}
    if format_name == "docx" and use_document_template:
        organization_template = await db.scalar(select(OrganizationDocumentTemplate).where(
            OrganizationDocumentTemplate.organization_id == context.organization_id,
            OrganizationDocumentTemplate.enabled.is_(True),
        ))
        if organization_template and organization_template.active_version_id:
            candidate = await db.get(OrganizationDocumentTemplateVersion, organization_template.active_version_id)
            if candidate and candidate.organization_id == context.organization_id and candidate.status == "ready":
                document_template_version = candidate
                document_template_snapshot = {
                    "id": candidate.id,
                    "version_number": candidate.version_number,
                    "file_name": candidate.file_name,
                    "sha256": candidate.sha256,
                }
    title = re.sub(r"\s+", " ", instructions).strip()[:100].rstrip(" .") or "Jules AI file"
    artifact = GeneratedArtifact(
        organization_id=context.organization_id,
        user_id=context.user_id,
        conversation_id=conversation.id,
        message_id=message_id,
        title=title,
        format=format_name,
        template_id=choose_template(format_name, instructions, template_id),
        use_document_template=use_document_template,
        source_scope_json=json.dumps(scope),
    )
    db.add(artifact)
    await db.flush()
    version = ArtifactVersion(
        organization_id=context.organization_id,
        user_id=context.user_id,
        artifact_id=artifact.id,
        version_number=1,
        instructions=instructions,
        source_scope_json=json.dumps(scope),
        document_template_version_id=document_template_version.id if document_template_version else None,
        document_template_snapshot_json=json.dumps(document_template_snapshot),
    )
    db.add(version)
    await db.flush()
    db.add(ArtifactJob(organization_id=context.organization_id, artifact_id=artifact.id, version_id=version.id))
    await audit(db, context, "artifact.queued", "artifact", artifact.id, {"format": format_name, "template_id": artifact.template_id, "document_template_version_id": document_template_version.id if document_template_version else None})
    await db.commit()
    log_event(logger, logging.INFO, "artifact.queued", artifact_id=artifact.id, version_id=version.id, conversation_id=conversation.id, format=format_name, template_id=artifact.template_id, document_template_version_id=document_template_version.id if document_template_version else None, knowledge_base_count=len(knowledge_base_ids), attachment_count=len(attachment_ids), web_search_enabled=web_search_enabled)
    return artifact


async def message_json(db: AsyncSession, row: Message) -> dict[str, Any]:
    citations = (await db.scalars(select(MessageCitation).where(MessageCitation.message_id == row.id).order_by(MessageCitation.ordinal))).all()
    artifacts = (await db.scalars(select(GeneratedArtifact).where(GeneratedArtifact.message_id == row.id).order_by(GeneratedArtifact.created_at))).all()
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "status": row.status,
        "created_at": as_iso(row.created_at),
        "knowledge_base_ids": json.loads(row.knowledge_base_ids_json or "[]"),
        "web_search_enabled": row.web_search_enabled,
        "grounding_status": row.grounding_status,
        "citations": [{
            "id": item.id,
            "ordinal": item.ordinal,
            "source_type": item.source_type,
            "knowledge_base_id": item.knowledge_base_id,
            "document_id": item.document_id,
            "version_id": item.version_id,
            "chunk_id": item.chunk_id,
            "title": item.title,
            "location": item.location,
            "url": item.url,
            "publisher": item.publisher,
            "retrieved_at": as_iso(item.retrieved_at),
            "metadata": json.loads(item.metadata_json or "{}"),
        } for item in citations],
        "artifacts": [await artifact_json(db, item) for item in artifacts],
    }


async def prompt_json(db: AsyncSession, row: Prompt, user_id: str) -> dict[str, Any]:
    favorite = await db.scalar(select(PromptFavorite.id).where(PromptFavorite.prompt_id == row.id, PromptFavorite.user_id == user_id))
    editor = await db.get(User, row.last_editor_id)
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "body": row.body,
        "tags": json.loads(row.tags_json),
        "favorite": bool(favorite),
        "archived": row.archived,
        "version_number": row.version_number,
        "last_editor": editor.display_name if editor else "Unknown",
        "updated_at": as_iso(row.updated_at),
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "agent_mode": "google-adk" if settings.google_api_key else "demo"}


@app.get("/v1/me")
async def me(context: RequestContext = Depends(get_context)) -> dict[str, Any]:
    return {
        "id": context.user_id,
        "email": context.user.email,
        "display_name": context.user.display_name,
        "avatar_url": context.user.avatar_url,
        "active_organization_id": context.organization_id,
        "role": context.role,
    }


@app.post("/v1/auth/bootstrap")
async def bootstrap_auth(
    payload: AuthBootstrap | None = None,
    identity: AuthIdentity = Depends(get_auth_identity),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if settings.auth_mode == "development":
        user = await db.scalar(select(User).where(User.id == identity.uid, User.display_name != "Deleted user"))
        if not user:
            raise HTTPException(status_code=401, detail="Development user is not provisioned")
    else:
        if not identity.email:
            raise HTTPException(status_code=400, detail="The identity token does not contain an email address")
        user = await db.scalar(select(User).where(User.firebase_uid == identity.uid, User.display_name != "Deleted user"))
        email_user = await db.scalar(
            select(User).where(func.lower(User.email) == identity.email, User.display_name != "Deleted user")
        )
        if user and email_user and user.id != email_user.id:
            raise HTTPException(status_code=409, detail="This email is linked to another account")
        if not user and email_user:
            if email_user.firebase_uid and email_user.firebase_uid != identity.uid:
                raise HTTPException(status_code=409, detail="This email is linked to another account")
            user = email_user
            user.firebase_uid = identity.uid
        if not user:
            display_name = (payload.display_name.strip() if payload and payload.display_name else None) or identity.display_name or identity.email.split("@", 1)[0]
            user = User(firebase_uid=identity.uid, email=identity.email, display_name=display_name)
            db.add(user)
            await db.flush()
        elif payload and payload.display_name:
            user.display_name = payload.display_name.strip()
        user.email = identity.email
        await db.commit()

    organizations = await organization_memberships_json(db, user.id)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
        },
        "email_verified": identity.email_verified,
        "organizations": organizations,
        "requires_onboarding": len(organizations) == 0,
    }


@app.get("/v1/organizations")
async def list_organizations(user: User = Depends(get_identity_user), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return await organization_memberships_json(db, user.id)


@app.post("/v1/organizations", status_code=201)
async def create_organization(payload: OrganizationCreate, user: User = Depends(require_verified_user), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Organization name must contain at least two characters")
    base_slug = slugify(name)
    slug = base_slug
    suffix = 1
    while await db.scalar(select(Organization.id).where(Organization.slug == slug)):
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    organization = Organization(name=name, slug=slug)
    db.add(organization)
    await db.flush()
    membership = Membership(organization_id=organization.id, user_id=user.id, role="owner")
    db.add(membership)
    db.add(UserSettings(organization_id=organization.id, user_id=user.id))
    db.add(OrganizationModelPolicy(
        organization_id=organization.id,
        allowed_models_json=json.dumps([item["id"] for item in MODEL_CATALOG]),
        default_model=DEFAULT_MODEL_ID,
        maximum_effort="high",
    ))
    await db.flush()
    await audit(db, RequestContext(user=user, membership=membership), "organization.created", "organization", organization.id, {"name": name})
    await db.commit()
    return {"id": organization.id, "name": organization.name, "slug": organization.slug, "role": "owner"}


@app.patch("/v1/organizations/current")
async def update_organization(payload: OrganizationUpdate, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    organization = await db.get(Organization, context.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization.name = payload.name.strip()
    await audit(db, context, "organization.updated", "organization", organization.id, {"name": organization.name})
    await db.commit()
    return {"id": organization.id, "name": organization.name, "slug": organization.slug, "role": context.role}


@app.get("/v1/organizations/current/document-template")
async def get_document_template(context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await db.scalar(select(OrganizationDocumentTemplate).where(
        OrganizationDocumentTemplate.organization_id == context.organization_id,
    ))
    return await document_template_json(db, row, can_manage=context.role in {"owner", "admin"})


@app.post("/v1/organizations/current/document-template", status_code=202)
async def upload_document_template(
    upload: UploadFile = File(...),
    context: RequestContext = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    file_name = safe_file_name(upload.filename)
    suffix = Path(file_name).suffix.lower()
    if suffix == ".dotx":
        raise HTTPException(status_code=415, detail="Save the template as a Word Document (.docx), then upload it again")
    if suffix != ".docx":
        raise HTTPException(status_code=415, detail="Organization document templates must be Word Document (.docx) files")
    data = await upload.read(settings.document_template_max_bytes + 1)
    if len(data) > settings.document_template_max_bytes:
        raise HTTPException(status_code=413, detail="Document template exceeds the 15 MB limit")
    scan_status = await malware_scanner.scan(name=file_name, mime_type=upload.content_type or DOCX_MIME_TYPE, data=data)
    if scan_status == "infected" or (scan_status == "unavailable" and settings.app_env != "development"):
        raise HTTPException(status_code=422 if scan_status == "infected" else 503, detail="Document template could not be accepted")
    try:
        validation = validate_template_package(data)
    except TemplateValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    template = await db.scalar(select(OrganizationDocumentTemplate).where(
        OrganizationDocumentTemplate.organization_id == context.organization_id,
    ))
    if not template:
        template = OrganizationDocumentTemplate(organization_id=context.organization_id, enabled=True)
        db.add(template)
        await db.flush()
    version_number = max((await db.scalars(select(OrganizationDocumentTemplateVersion.version_number).where(
        OrganizationDocumentTemplateVersion.template_id == template.id,
    ))).all(), default=0) + 1
    version = OrganizationDocumentTemplateVersion(
        organization_id=context.organization_id,
        template_id=template.id,
        version_number=version_number,
        file_name=file_name,
        mime_type=DOCX_MIME_TYPE,
        size_bytes=len(data),
        storage_key=f"organizations/{context.organization_id}/document-templates/{template.id}/v{version_number}/{file_name}",
        sha256=validation["sha256"],
        validation_report_json=json.dumps(validation),
        uploaded_by=context.user_id,
    )
    db.add(version)
    await db.flush()
    await storage_service.save_bytes(version.storage_key, data, DOCX_MIME_TYPE)
    job = DocumentTemplateValidationJob(organization_id=context.organization_id, template_version_id=version.id)
    db.add(job)
    await audit(db, context, "document_template.uploaded", "document_template_version", version.id, {
        "version_number": version_number,
        "file_name": file_name,
        "size_bytes": len(data),
        "sha256": version.sha256,
    })
    await db.commit()
    log_event(logger, logging.INFO, "document_template.queued", organization_id=context.organization_id, template_id=template.id, template_version_id=version.id, version_number=version_number, size_bytes=len(data))
    return await document_template_json(db, template, can_manage=True)


async def scoped_document_template_version(
    db: AsyncSession,
    context: RequestContext,
    version_id: str,
) -> tuple[OrganizationDocumentTemplate, OrganizationDocumentTemplateVersion]:
    version = await db.scalar(select(OrganizationDocumentTemplateVersion).where(
        OrganizationDocumentTemplateVersion.id == version_id,
        OrganizationDocumentTemplateVersion.organization_id == context.organization_id,
    ))
    if not version:
        raise HTTPException(status_code=404, detail="Document template version not found")
    template = await db.get(OrganizationDocumentTemplate, version.template_id)
    if not template or template.organization_id != context.organization_id:
        raise HTTPException(status_code=404, detail="Document template not found")
    return template, version


@app.get("/v1/organizations/current/document-template/versions/{version_id}/download")
async def download_document_template(
    version_id: str,
    context: RequestContext = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _, version = await scoped_document_template_version(db, context, version_id)
    return Response(await storage_service.read(version.storage_key), media_type=DOCX_MIME_TYPE, headers={
        "Content-Disposition": f'attachment; filename="{safe_file_name(version.file_name)}"',
        "Cache-Control": "private, no-store",
    })


@app.get("/v1/organizations/current/document-template/versions/{version_id}/previews/{preview_number}")
async def preview_document_template(
    version_id: str,
    preview_number: int,
    context: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _, version = await scoped_document_template_version(db, context, version_id)
    preview_keys = json.loads(version.preview_keys_json or "[]")
    if preview_number < 1 or preview_number > len(preview_keys):
        raise HTTPException(status_code=404, detail="Document template preview not found")
    return Response(await storage_service.read(preview_keys[preview_number - 1]), media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@app.post("/v1/organizations/current/document-template/versions/{version_id}/activate")
async def activate_document_template(
    version_id: str,
    context: RequestContext = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    template, version = await scoped_document_template_version(db, context, version_id)
    if version.status != "ready":
        raise HTTPException(status_code=409, detail="Only a validated document template can be activated")
    template.active_version_id = version.id
    template.enabled = True
    version.activated_at = utc_now()
    await audit(db, context, "document_template.activated", "document_template_version", version.id, {"version_number": version.version_number})
    await db.commit()
    return await document_template_json(db, template, can_manage=True)


@app.post("/v1/organizations/current/document-template/disable")
async def disable_document_template(
    context: RequestContext = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    template = await db.scalar(select(OrganizationDocumentTemplate).where(
        OrganizationDocumentTemplate.organization_id == context.organization_id,
    ))
    if not template:
        raise HTTPException(status_code=404, detail="Document template not found")
    template.enabled = False
    await audit(db, context, "document_template.disabled", "document_template", template.id)
    await db.commit()
    return await document_template_json(db, template, can_manage=True)


@app.post("/v1/organizations/current/transfer-ownership")
async def transfer_ownership(payload: OwnershipTransfer, context: RequestContext = Depends(require_role("owner")), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    target = await db.scalar(select(Membership).where(
        Membership.organization_id == context.organization_id,
        Membership.user_id == payload.user_id,
        Membership.active.is_(True),
    ))
    if not target or target.user_id == context.user_id:
        raise HTTPException(status_code=400, detail="Choose another active organization member")
    context.membership.role = "admin"
    target.role = "owner"
    await audit(db, context, "organization.ownership_transferred", "user", target.user_id)
    await db.commit()
    return {"status": "transferred", "owner_user_id": target.user_id}


async def cleanup_organization(organization_id: str) -> None:
    async with SessionLocal() as db:
        attachments = (await db.scalars(select(Attachment).where(Attachment.organization_id == organization_id))).all()
        for attachment in attachments:
            await storage_service.delete(attachment.storage_key)
        knowledge_versions = (await db.scalars(select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.organization_id == organization_id))).all()
        for version in knowledge_versions:
            await storage_service.delete(version.storage_key)
        artifacts = (await db.scalars(select(GeneratedArtifact).where(GeneratedArtifact.organization_id == organization_id))).all()
        for artifact in artifacts:
            await delete_artifact_files(db, storage_service, artifact.id)
        await delete_document_template_files(db, storage_service, organization_id)
        organization = await db.get(Organization, organization_id)
        if organization:
            await db.delete(organization)
            await db.commit()


@app.post("/v1/organizations/current/delete", status_code=202)
async def delete_organization(payload: OrganizationDelete, tasks: BackgroundTasks, context: RequestContext = Depends(require_role("owner")), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    organization = await db.get(Organization, context.organization_id)
    if not organization or payload.confirmation_name.strip() != organization.name:
        raise HTTPException(status_code=400, detail="Organization name confirmation does not match")
    tasks.add_task(cleanup_organization, organization.id)
    return {"status": "cleanup_queued", "organization_id": organization.id}


@app.get("/v1/organizations/current/members")
async def list_members(context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.organization_id == context.organization_id, Membership.active.is_(True))
        .order_by(User.display_name)
    )).all()
    return [{"id": user.id, "display_name": user.display_name, "email": user.email, "role": membership.role} for user, membership in rows]


@app.patch("/v1/organizations/current/members/{user_id}")
async def update_member_role(user_id: str, payload: RoleUpdate, context: RequestContext = Depends(require_role("owner")), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    membership = await db.scalar(select(Membership).where(Membership.organization_id == context.organization_id, Membership.user_id == user_id, Membership.active.is_(True)))
    if not membership or membership.role == "owner":
        raise HTTPException(status_code=404, detail="Eligible member not found")
    membership.role = payload.role
    await audit(db, context, "membership.role_changed", "user", user_id, {"role": payload.role})
    await db.commit()
    return {"status": "updated"}


@app.delete("/v1/organizations/current/members/{user_id}", status_code=204)
async def remove_member(user_id: str, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> None:
    membership = await db.scalar(select(Membership).where(Membership.organization_id == context.organization_id, Membership.user_id == user_id, Membership.active.is_(True)))
    if not membership or membership.role == "owner":
        raise HTTPException(status_code=404, detail="Removable member not found")
    membership.active = False
    await audit(db, context, "membership.removed", "user", user_id)
    await db.commit()


@app.delete("/v1/organizations/current/membership", status_code=204)
async def leave_organization(context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> None:
    if context.role == "owner":
        raise HTTPException(status_code=409, detail="Transfer ownership or delete the organization before leaving")
    await audit(db, context, "membership.left", "user", context.user_id)
    context.membership.active = False
    await db.commit()


@app.get("/v1/organizations/current/invitations")
async def list_invitations(context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.scalars(select(Invitation).where(Invitation.organization_id == context.organization_id).order_by(Invitation.created_at.desc()))).all()
    return [{"id": row.id, "email": row.email, "role": row.role, "status": row.status, "expires_at": as_iso(row.expires_at)} for row in rows]


@app.post("/v1/organizations/current/invitations", status_code=201)
async def invite_member(payload: InvitationCreate, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    email = normalize_email(payload.email)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    active_member = await db.scalar(
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.organization_id == context.organization_id,
            Membership.active.is_(True),
            func.lower(User.email) == email,
        )
    )
    if active_member:
        raise HTTPException(status_code=409, detail="This person is already an active organization member")
    invitation = await db.scalar(
        select(Invitation).where(
            Invitation.organization_id == context.organization_id,
            func.lower(Invitation.email) == email,
            Invitation.status == "pending",
        ).order_by(Invitation.created_at.desc())
    )
    token = secrets.token_urlsafe(32)
    if invitation:
        invitation.token_hash = invitation_token_hash(token)
        invitation.expires_at = utc_now() + timedelta(days=7)
        invitation.invited_by = context.user_id
    else:
        invitation = Invitation(
            organization_id=context.organization_id,
            email=email,
            role="member",
            token_hash=invitation_token_hash(token),
            expires_at=utc_now() + timedelta(days=7),
            invited_by=context.user_id,
        )
        db.add(invitation)
    await db.flush()
    await audit(db, context, "invitation.created", "invitation", invitation.id, {"email": email})
    await db.commit()
    return {
        "id": invitation.id,
        "email": invitation.email,
        "role": invitation.role,
        "status": invitation.status,
        "expires_at": as_iso(invitation.expires_at),
        "acceptance_token": token,
    }


@app.get("/v1/invitations/{token}/preview")
async def preview_invitation(token: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if not valid_invitation_token(token):
        raise HTTPException(status_code=404, detail="Invitation not found")
    row = await db.execute(
        select(Invitation, Organization)
        .join(Organization, Organization.id == Invitation.organization_id)
        .where(Invitation.token_hash == invitation_token_hash(token))
    )
    result = row.first()
    if not result:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation, organization = result
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    computed_status = "expired" if invitation.status == "pending" and expires_at < utc_now() else invitation.status
    return {
        "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug},
        "invited_email": masked_email(invitation.email),
        "role": invitation.role,
        "status": computed_status,
        "expires_at": as_iso(expires_at),
    }


@app.post("/v1/invitations/{token}/accept")
async def accept_invitation(token: str, user: User = Depends(require_verified_user), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if not valid_invitation_token(token):
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation = await db.scalar(select(Invitation).where(Invitation.token_hash == invitation_token_hash(token)))
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    expires_at = invitation.expires_at if invitation else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if normalize_email(invitation.email) != normalize_email(user.email):
        raise HTTPException(status_code=403, detail="Sign in with the email address that was invited")
    existing = await db.scalar(select(Membership).where(Membership.organization_id == invitation.organization_id, Membership.user_id == user.id))
    if invitation.status == "accepted":
        if not existing or not existing.active:
            raise HTTPException(status_code=410, detail="This invitation has already been used")
        organization = await db.get(Organization, invitation.organization_id)
        return {
            "organization_id": invitation.organization_id,
            "status": "accepted",
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "slug": organization.slug,
                "role": existing.role,
            },
        }
    if invitation.status == "revoked":
        raise HTTPException(status_code=410, detail="This invitation was revoked")
    if not expires_at or expires_at < utc_now():
        raise HTTPException(status_code=410, detail="This invitation has expired")
    if existing:
        existing.active = True
        existing.role = invitation.role
    else:
        existing = Membership(organization_id=invitation.organization_id, user_id=user.id, role=invitation.role)
        db.add(existing)
    if not await db.scalar(select(UserSettings.id).where(UserSettings.organization_id == invitation.organization_id, UserSettings.user_id == user.id)):
        db.add(UserSettings(organization_id=invitation.organization_id, user_id=user.id))
    invitation.status = "accepted"
    await db.flush()
    await audit(db, RequestContext(user=user, membership=existing), "invitation.accepted", "invitation", invitation.id)
    await db.commit()
    organization = await db.get(Organization, invitation.organization_id)
    return {
        "organization_id": invitation.organization_id,
        "status": "accepted",
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "role": existing.role,
        },
    }


@app.delete("/v1/organizations/current/invitations/{invitation_id}", status_code=204)
async def revoke_invitation(invitation_id: str, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> None:
    invitation = await db.scalar(select(Invitation).where(Invitation.id == invitation_id, Invitation.organization_id == context.organization_id))
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.status = "revoked"
    await audit(db, context, "invitation.revoked", "invitation", invitation.id)
    await db.commit()


@app.post("/v1/organizations/current/invitations/{invitation_id}/resend")
async def resend_invitation(invitation_id: str, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    invitation = await db.scalar(select(Invitation).where(Invitation.id == invitation_id, Invitation.organization_id == context.organization_id))
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.status = "pending"
    token = secrets.token_urlsafe(32)
    invitation.token_hash = invitation_token_hash(token)
    invitation.expires_at = utc_now() + timedelta(days=7)
    await audit(db, context, "invitation.resent", "invitation", invitation.id, {"email": invitation.email})
    await db.commit()
    return {
        "id": invitation.id,
        "email": invitation.email,
        "role": invitation.role,
        "status": invitation.status,
        "expires_at": as_iso(invitation.expires_at),
        "acceptance_token": token,
    }


@app.get("/v1/knowledge-bases")
async def list_knowledge_bases(context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.scalars(
        select(KnowledgeBase)
        .join(KnowledgeBaseAccess, KnowledgeBaseAccess.knowledge_base_id == KnowledgeBase.id)
        .where(
            KnowledgeBase.organization_id == context.organization_id,
            KnowledgeBase.archived.is_(False),
            KnowledgeBaseAccess.user_id == context.user_id,
        )
        .order_by(KnowledgeBase.title)
    )).all()
    return [await knowledge_base_json(db, row, context) for row in rows]


@app.get("/v1/knowledge-bases-management")
async def list_managed_knowledge_bases(context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.scalars(select(KnowledgeBase).where(
        KnowledgeBase.organization_id == context.organization_id,
        KnowledgeBase.archived.is_(False),
    ).order_by(KnowledgeBase.title))).all()
    return [await knowledge_base_json(db, row, context) for row in rows]


@app.post("/v1/knowledge-bases", status_code=201)
async def create_knowledge_base(payload: KnowledgeBaseCreate, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    member_ids = set(payload.member_ids) | {context.user_id}
    valid_members = set((await db.scalars(select(Membership.user_id).where(
        Membership.organization_id == context.organization_id,
        Membership.user_id.in_(member_ids),
        Membership.active.is_(True),
    ))).all())
    if valid_members != member_ids:
        raise HTTPException(status_code=400, detail="One or more users are not active organization members")
    row = KnowledgeBase(
        organization_id=context.organization_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        created_by=context.user_id,
    )
    db.add(row)
    await db.flush()
    db.add_all([
        KnowledgeBaseAccess(
            organization_id=context.organization_id,
            knowledge_base_id=row.id,
            user_id=user_id,
            granted_by=context.user_id,
            reason="Knowledge base created" if user_id == context.user_id else "Granted during creation",
        ) for user_id in member_ids
    ])
    await audit(db, context, "knowledge_base.created", "knowledge_base", row.id, {"member_count": len(member_ids)})
    await db.commit()
    return await knowledge_base_json(db, row, context)


@app.get("/v1/knowledge-bases/{knowledge_base_id}")
async def get_knowledge_base(knowledge_base_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await require_knowledge_access(db, context, knowledge_base_id)
    result = await knowledge_base_json(db, row, context)
    documents = (await db.scalars(select(KnowledgeDocument).where(
        KnowledgeDocument.knowledge_base_id == row.id,
        KnowledgeDocument.organization_id == context.organization_id,
        KnowledgeDocument.archived.is_(False),
    ).order_by(KnowledgeDocument.updated_at.desc()))).all()
    result["documents"] = [await document_json(db, document) for document in documents]
    if context.role in {"owner", "admin"}:
        members = (await db.execute(
            select(User, KnowledgeBaseAccess)
            .join(KnowledgeBaseAccess, KnowledgeBaseAccess.user_id == User.id)
            .where(KnowledgeBaseAccess.knowledge_base_id == row.id)
            .order_by(User.display_name)
        )).all()
        result["members"] = [{"id": user.id, "display_name": user.display_name, "email": user.email, "reason": access.reason} for user, access in members]
    return result


@app.patch("/v1/knowledge-bases/{knowledge_base_id}")
async def update_knowledge_base(knowledge_base_id: str, payload: KnowledgeBaseUpdate, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.organization_id == context.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    await audit(db, context, "knowledge_base.updated", "knowledge_base", row.id, {"archived": row.archived})
    await db.commit()
    return await knowledge_base_json(db, row, context)


@app.put("/v1/knowledge-bases/{knowledge_base_id}/access")
async def replace_knowledge_access(knowledge_base_id: str, payload: KnowledgeAccessUpdate, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.organization_id == context.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    requested = set(payload.user_ids)
    if context.user_id in requested and not payload.reason.strip():
        existing = await db.scalar(select(KnowledgeBaseAccess.id).where(KnowledgeBaseAccess.knowledge_base_id == row.id, KnowledgeBaseAccess.user_id == context.user_id))
        if not existing:
            raise HTTPException(status_code=400, detail="An audited reason is required when granting yourself access")
    valid = set((await db.scalars(select(Membership.user_id).where(
        Membership.organization_id == context.organization_id,
        Membership.user_id.in_(requested),
        Membership.active.is_(True),
    ))).all()) if requested else set()
    if valid != requested:
        raise HTTPException(status_code=400, detail="One or more users are not active organization members")
    previous_users = set((await db.scalars(select(KnowledgeBaseAccess.user_id).where(KnowledgeBaseAccess.knowledge_base_id == row.id))).all())
    removed_users = previous_users - requested
    if removed_users:
        affected_conversations = (await db.scalars(select(Conversation).where(
            Conversation.organization_id == context.organization_id,
            Conversation.user_id.in_(removed_users),
        ))).all()
        for conversation in affected_conversations:
            conversation.knowledge_base_ids_json = json.dumps([item for item in json.loads(conversation.knowledge_base_ids_json or "[]") if item != row.id])
    await db.execute(delete(KnowledgeBaseAccess).where(KnowledgeBaseAccess.knowledge_base_id == row.id))
    db.add_all([KnowledgeBaseAccess(
        organization_id=context.organization_id,
        knowledge_base_id=row.id,
        user_id=user_id,
        granted_by=context.user_id,
        reason=payload.reason.strip(),
    ) for user_id in requested])
    await audit(db, context, "knowledge_base.access_replaced", "knowledge_base", row.id, {"user_ids": sorted(requested), "reason": payload.reason.strip()})
    await db.commit()
    return {"status": "updated", "user_ids": sorted(requested)}


@app.post("/v1/knowledge-bases/{knowledge_base_id}/self-grant", status_code=201)
async def self_grant_knowledge_access(knowledge_base_id: str, payload: AccessReason, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    row = await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.organization_id == context.organization_id, KnowledgeBase.archived.is_(False)))
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    access = await db.scalar(select(KnowledgeBaseAccess).where(KnowledgeBaseAccess.knowledge_base_id == row.id, KnowledgeBaseAccess.user_id == context.user_id))
    if not access:
        access = KnowledgeBaseAccess(organization_id=context.organization_id, knowledge_base_id=row.id, user_id=context.user_id, granted_by=context.user_id, reason=payload.reason.strip())
        db.add(access)
        await audit(db, context, "knowledge_base.self_granted", "knowledge_base", row.id, {"reason": payload.reason.strip()})
        await db.commit()
    return {"status": "granted"}


async def store_knowledge_upload(
    db: AsyncSession,
    context: RequestContext,
    knowledge_base: KnowledgeBase,
    upload: UploadFile,
    document: KnowledgeDocument | None = None,
) -> KnowledgeDocument:
    file_name = safe_file_name(upload.filename)
    suffix = Path(file_name).suffix.lower()
    supported = {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md"}
    if suffix not in supported:
        raise HTTPException(status_code=415, detail=f"Unsupported knowledge file type: {suffix or 'unknown'}")
    if upload.size and upload.size > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Document exceeds the 50 MB limit")
    document = document or KnowledgeDocument(
        organization_id=context.organization_id,
        knowledge_base_id=knowledge_base.id,
        title=file_name,
        created_by=context.user_id,
        current_version=1,
    )
    if document.id is None:
        document.id = new_id()
    version_number = document.current_version if not document.created_at else document.current_version + 1
    if document.created_at:
        document.current_version = version_number
    version_id = new_id()
    key = f"organizations/{context.organization_id}/knowledge-bases/{knowledge_base.id}/documents/{document.id}/versions/{version_id}/{file_name}"
    size = await storage_service.save(key, upload)
    data = await storage_service.read(key)
    digest = hashlib.sha256(data).hexdigest()
    duplicate = await db.scalar(select(KnowledgeDocumentVersion).where(
        KnowledgeDocumentVersion.organization_id == context.organization_id,
        KnowledgeDocumentVersion.knowledge_base_id == knowledge_base.id,
        KnowledgeDocumentVersion.sha256 == digest,
    ))
    if duplicate:
        await storage_service.delete(key)
        raise HTTPException(status_code=409, detail="This exact file already exists in the knowledge base")
    mime_type = upload.content_type or "application/octet-stream"
    scan_status = await malware_scanner.scan(name=file_name, mime_type=mime_type, data=data)
    if scan_status == "infected" or (scan_status == "unavailable" and settings.app_env != "development"):
        await storage_service.delete(key)
        raise HTTPException(status_code=422 if scan_status == "infected" else 503, detail="Document failed security scanning")
    db.add(document)
    await db.flush()
    version = KnowledgeDocumentVersion(
        id=version_id,
        organization_id=context.organization_id,
        knowledge_base_id=knowledge_base.id,
        document_id=document.id,
        version_number=version_number,
        file_name=file_name,
        mime_type=mime_type,
        size_bytes=size,
        storage_key=key,
        sha256=digest,
        uploaded_by=context.user_id,
    )
    db.add(version)
    await db.flush()
    db.add(IngestionJob(organization_id=context.organization_id, version_id=version.id))
    if version_number > 1:
        previous = await db.scalar(select(KnowledgeDocumentVersion).where(
            KnowledgeDocumentVersion.document_id == document.id,
            KnowledgeDocumentVersion.version_number == version_number - 1,
        ))
        if previous:
            db.add(KnowledgeConflict(
                organization_id=context.organization_id,
                knowledge_base_id=knowledge_base.id,
                left_version_id=previous.id,
                right_version_id=version.id,
                conflict_type="superseding_policy",
                summary="A new immutable version was uploaded. Confirm whether it supersedes the prior version or whether both apply.",
            ))
    log_event(logger, logging.INFO, "knowledge.upload_queued", knowledge_base_id=knowledge_base.id, document_id=document.id, version_id=version.id, file_name=file_name, mime_type=mime_type, size_bytes=size)
    return document


@app.post("/v1/knowledge-bases/{knowledge_base_id}/documents", status_code=202)
async def upload_knowledge_documents(knowledge_base_id: str, uploads: list[UploadFile] = File(...), context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    knowledge_base = await require_knowledge_access(db, context, knowledge_base_id)
    if len(uploads) > 20:
        raise HTTPException(status_code=400, detail="Upload at most 20 files at once")
    documents = [await store_knowledge_upload(db, context, knowledge_base, upload) for upload in uploads]
    await audit(db, context, "knowledge_documents.uploaded", "knowledge_base", knowledge_base.id, {"document_ids": [row.id for row in documents]})
    await db.commit()
    return [await document_json(db, document) for document in documents]


@app.post("/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/versions", status_code=202)
async def upload_knowledge_version(knowledge_base_id: str, document_id: str, upload: UploadFile = File(...), context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    knowledge_base = await require_knowledge_access(db, context, knowledge_base_id)
    document = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id, KnowledgeDocument.knowledge_base_id == knowledge_base.id, KnowledgeDocument.archived.is_(False)))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    await store_knowledge_upload(db, context, knowledge_base, upload, document)
    await audit(db, context, "knowledge_document.version_uploaded", "knowledge_document", document.id, {"version": document.current_version})
    await db.commit()
    return await document_json(db, document)


@app.post("/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/reprocess", status_code=202)
async def reprocess_document(knowledge_base_id: str, document_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await require_knowledge_access(db, context, knowledge_base_id)
    version = await db.scalar(select(KnowledgeDocumentVersion).where(
        KnowledgeDocumentVersion.document_id == document_id,
        KnowledgeDocumentVersion.knowledge_base_id == knowledge_base_id,
    ).order_by(KnowledgeDocumentVersion.version_number.desc()))
    if not version:
        raise HTTPException(status_code=404, detail="Document not found")
    job = await db.scalar(select(IngestionJob).where(IngestionJob.version_id == version.id))
    if job:
        job.status, job.progress, job.error = "queued", 0, None
    else:
        job = IngestionJob(organization_id=context.organization_id, version_id=version.id)
        db.add(job)
    version.extraction_status = "queued"
    await db.commit()
    return {"status": "queued", "job_id": job.id}


@app.delete("/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}", status_code=204)
async def archive_knowledge_document(knowledge_base_id: str, document_id: str, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> None:
    document = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id, KnowledgeDocument.knowledge_base_id == knowledge_base_id, KnowledgeDocument.organization_id == context.organization_id))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    document.archived = True
    await audit(db, context, "knowledge_document.archived", "knowledge_document", document.id)
    await db.commit()


@app.get("/v1/knowledge/search")
async def search_knowledge(q: str = Query(min_length=2, max_length=1000), knowledge_base_ids: list[str] = Query(default=[]), context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    results = await retrieve_company_knowledge(db, context.organization_id, context.user_id, knowledge_base_ids, q)
    return {"results": [{**item.citation(index), "excerpt": item.content[:700], "score": item.score} for index, item in enumerate(results, start=1)]}


@app.get("/v1/knowledge/sources/{chunk_id}")
async def preview_knowledge_source(chunk_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    chunk = await db.get(KnowledgeChunk, chunk_id)
    if not chunk or chunk.organization_id != context.organization_id:
        raise HTTPException(status_code=404, detail="Source not found")
    await require_knowledge_access(db, context, chunk.knowledge_base_id)
    document = await db.get(KnowledgeDocument, chunk.document_id)
    version = await db.get(KnowledgeDocumentVersion, chunk.version_id)
    return {"chunk_id": chunk.id, "title": document.title if document else "Document", "content": chunk.content, "page_number": chunk.page_number, "version": version.version_number if version else None, "kind": chunk.kind}


@app.get("/v1/knowledge/documents/{document_id}/versions/{version_id}/content")
async def download_knowledge_version(document_id: str, version_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> Response:
    version = await db.scalar(select(KnowledgeDocumentVersion).where(
        KnowledgeDocumentVersion.id == version_id,
        KnowledgeDocumentVersion.document_id == document_id,
        KnowledgeDocumentVersion.organization_id == context.organization_id,
    ))
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")
    await require_knowledge_access(db, context, version.knowledge_base_id)
    data = await storage_service.read(version.storage_key)
    return Response(content=data, media_type=version.mime_type, headers={"Content-Disposition": f'inline; filename="{safe_file_name(version.file_name)}"'})


@app.get("/v1/knowledge-review")
async def knowledge_review(context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    conflicts = (await db.scalars(select(KnowledgeConflict).where(KnowledgeConflict.organization_id == context.organization_id, KnowledgeConflict.status == "open").order_by(KnowledgeConflict.created_at.desc()))).all()
    proposals = (await db.scalars(select(KnowledgeProposal).where(KnowledgeProposal.organization_id == context.organization_id, KnowledgeProposal.status == "pending").order_by(KnowledgeProposal.created_at.desc()))).all()
    unanswered = (await db.scalars(select(UnansweredQuestion).where(UnansweredQuestion.organization_id == context.organization_id, UnansweredQuestion.status == "open").order_by(UnansweredQuestion.created_at.desc()))).all()
    failed_jobs = (await db.scalars(select(IngestionJob).where(IngestionJob.organization_id == context.organization_id, IngestionJob.status == "failed").order_by(IngestionJob.updated_at.desc()))).all()
    low_quality_versions = (await db.scalars(select(KnowledgeDocumentVersion).where(
        KnowledgeDocumentVersion.organization_id == context.organization_id,
        KnowledgeDocumentVersion.extraction_quality == "low",
    ).order_by(KnowledgeDocumentVersion.updated_at.desc()))).all()
    feedback_rows = (await db.execute(select(AnswerFeedback, Message).join(Message, Message.id == AnswerFeedback.message_id).where(
        AnswerFeedback.organization_id == context.organization_id,
        AnswerFeedback.rating.in_(["incorrect", "outdated"]),
    ).order_by(AnswerFeedback.updated_at.desc()))).all()
    conflict_items = []
    for item in conflicts:
        left = await db.get(KnowledgeDocumentVersion, item.left_version_id)
        right = await db.get(KnowledgeDocumentVersion, item.right_version_id)
        left_chunk = await db.scalar(select(KnowledgeChunk).where(KnowledgeChunk.version_id == item.left_version_id).order_by(KnowledgeChunk.created_at).limit(1))
        right_chunk = await db.scalar(select(KnowledgeChunk).where(KnowledgeChunk.version_id == item.right_version_id).order_by(KnowledgeChunk.created_at).limit(1))
        conflict_items.append({"id": item.id, "knowledge_base_id": item.knowledge_base_id, "conflict_type": item.conflict_type, "summary": item.summary, "left": {"version_id": left.id, "file_name": left.file_name, "version": left.version_number, "uploader_id": left.uploaded_by, "date": as_iso(left.created_at), "page": left_chunk.page_number if left_chunk else None, "excerpt": left_chunk.content[:500] if left_chunk else None} if left else None, "right": {"version_id": right.id, "file_name": right.file_name, "version": right.version_number, "uploader_id": right.uploaded_by, "date": as_iso(right.created_at), "page": right_chunk.page_number if right_chunk else None, "excerpt": right_chunk.content[:500] if right_chunk else None} if right else None, "created_at": as_iso(item.created_at)})
    return {
        "conflicts": conflict_items,
        "proposals": [{"id": item.id, "knowledge_base_id": item.knowledge_base_id, "title": item.title, "content": item.content, "proposed_by": item.proposed_by, "created_at": as_iso(item.created_at)} for item in proposals],
        "unanswered_questions": [{"id": item.id, "question": item.question, "reason": item.reason, "conversation_id": item.conversation_id, "created_at": as_iso(item.created_at)} for item in unanswered],
        "failed_ingestions": [{"id": item.id, "version_id": item.version_id, "error": item.error, "updated_at": as_iso(item.updated_at)} for item in failed_jobs],
        "reported_answers": [{"id": feedback.id, "message_id": message.id, "rating": feedback.rating, "note": feedback.note, "answer": message.content, "created_at": as_iso(feedback.created_at)} for feedback, message in feedback_rows],
        "low_quality_extractions": [{"version_id": item.id, "file_name": item.file_name, "mime_type": item.mime_type, "updated_at": as_iso(item.updated_at)} for item in low_quality_versions],
    }


@app.post("/v1/knowledge-conflicts/{conflict_id}/resolve")
async def resolve_knowledge_conflict(conflict_id: str, payload: ConflictResolution, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    conflict = await db.scalar(select(KnowledgeConflict).where(KnowledgeConflict.id == conflict_id, KnowledgeConflict.organization_id == context.organization_id, KnowledgeConflict.status == "open"))
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    left = await db.get(KnowledgeDocumentVersion, conflict.left_version_id)
    right = await db.get(KnowledgeDocumentVersion, conflict.right_version_id)
    if payload.action == "authoritative":
        if payload.authoritative_version_id not in {conflict.left_version_id, conflict.right_version_id}:
            raise HTTPException(status_code=400, detail="Choose one of the conflicting versions")
        if left:
            left.authoritative = left.id == payload.authoritative_version_id
        if right:
            right.authoritative = right.id == payload.authoritative_version_id
    elif payload.action == "supersede" and right and left:
        left.authoritative, right.authoritative = False, True
    elif payload.action == "archive" and left:
        document = await db.get(KnowledgeDocument, left.document_id)
        if document:
            document.archived = True
    conflict.status = "dismissed" if payload.action == "dismiss" else "resolved"
    conflict.resolution = f"{payload.action}: {payload.note}".strip()
    conflict.applies_when = payload.applies_when
    conflict.resolved_by = context.user_id
    await audit(db, context, "knowledge_conflict.resolved", "knowledge_conflict", conflict.id, {"action": payload.action})
    await db.commit()
    return {"status": conflict.status}


@app.post("/v1/knowledge-proposals", status_code=201)
async def create_knowledge_proposal(payload: KnowledgeProposalCreate, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    await require_knowledge_access(db, context, payload.knowledge_base_id)
    if payload.conversation_id:
        await scoped_conversation(db, context, payload.conversation_id)
    if payload.message_id:
        message = await db.scalar(select(Message).where(Message.id == payload.message_id, Message.user_id == context.user_id, Message.organization_id == context.organization_id))
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
    row = KnowledgeProposal(organization_id=context.organization_id, proposed_by=context.user_id, **payload.model_dump())
    db.add(row)
    await audit(db, context, "knowledge_proposal.created", "knowledge_proposal", row.id, {"knowledge_base_id": row.knowledge_base_id})
    await db.commit()
    return {"id": row.id, "status": row.status, "title": row.title}


@app.post("/v1/knowledge-proposals/{proposal_id}/review")
async def review_knowledge_proposal(proposal_id: str, payload: ProposalReview, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    proposal = await db.scalar(select(KnowledgeProposal).where(KnowledgeProposal.id == proposal_id, KnowledgeProposal.organization_id == context.organization_id, KnowledgeProposal.status == "pending"))
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if payload.decision == "approved":
        knowledge_base = await db.get(KnowledgeBase, proposal.knowledge_base_id)
        if not knowledge_base:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        content = proposal.content.encode()
        upload = UploadFile(filename=f"{safe_file_name(proposal.title)}.md", file=io.BytesIO(content), headers=Headers({"content-type": "text/markdown"}))
        await store_knowledge_upload(db, context, knowledge_base, upload)
    proposal.status = payload.decision
    proposal.reviewed_by = context.user_id
    proposal.review_note = payload.note
    await audit(db, context, f"knowledge_proposal.{payload.decision}", "knowledge_proposal", proposal.id)
    await db.commit()
    return {"status": proposal.status}


@app.post("/v1/messages/{message_id}/feedback", status_code=201)
async def create_answer_feedback(message_id: str, payload: FeedbackCreate, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    message = await db.scalar(select(Message).where(Message.id == message_id, Message.organization_id == context.organization_id, Message.user_id == context.user_id, Message.role == "assistant"))
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    row = await db.scalar(select(AnswerFeedback).where(AnswerFeedback.message_id == message.id, AnswerFeedback.user_id == context.user_id))
    if not row:
        row = AnswerFeedback(organization_id=context.organization_id, user_id=context.user_id, message_id=message.id, rating=payload.rating, note=payload.note)
        db.add(row)
    else:
        row.rating, row.note = payload.rating, payload.note
    await db.commit()
    return {"status": "recorded"}


@app.get("/v1/conversations")
async def list_conversations(archived: bool = False, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.scalars(select(Conversation).where(
        Conversation.organization_id == context.organization_id,
        Conversation.user_id == context.user_id,
        Conversation.archived.is_(archived),
    ).order_by(Conversation.pinned.desc(), Conversation.updated_at.desc()))).all()
    return [conversation_json(row) for row in rows]


@app.post("/v1/conversations", status_code=201)
async def create_conversation(payload: ConversationCreate, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    validate_model_id(payload.model)
    settings_row = await db.scalar(select(UserSettings).where(UserSettings.organization_id == context.organization_id, UserSettings.user_id == context.user_id))
    requested = payload.knowledge_base_ids
    if requested is None:
        requested = await authorized_knowledge_base_ids(db, context.organization_id, context.user_id)
    allowed = await authorized_knowledge_base_ids(db, context.organization_id, context.user_id, requested)
    if len(set(allowed)) != len(set(requested)):
        raise HTTPException(status_code=403, detail="One or more knowledge sources are unavailable")
    row = Conversation(
        organization_id=context.organization_id,
        user_id=context.user_id,
        title=payload.title,
        model=payload.model,
        effort=payload.effort,
        knowledge_base_ids_json=json.dumps(allowed),
        web_search_enabled=payload.web_search_enabled if payload.web_search_enabled is not None else bool(settings_row and settings_row.web_search_default),
    )
    db.add(row)
    await db.commit()
    return conversation_json(row)


@app.get("/v1/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await scoped_conversation(db, context, conversation_id)
    messages = (await db.scalars(select(Message).where(
        Message.conversation_id == row.id,
        Message.organization_id == context.organization_id,
        Message.user_id == context.user_id,
    ).order_by(Message.created_at))).all()
    result = conversation_json(row)
    result["messages"] = [await message_json(db, message) for message in messages]
    return result


@app.patch("/v1/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, payload: ConversationUpdate, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await scoped_conversation(db, context, conversation_id)
    if payload.model is not None:
        validate_model_id(payload.model)
    values = payload.model_dump(exclude_unset=True)
    if "knowledge_base_ids" in values:
        requested = values.pop("knowledge_base_ids") or []
        allowed = await authorized_knowledge_base_ids(db, context.organization_id, context.user_id, requested)
        if len(set(allowed)) != len(set(requested)):
            raise HTTPException(status_code=403, detail="One or more knowledge sources are unavailable")
        row.knowledge_base_ids_json = json.dumps(allowed)
    for key, value in values.items():
        setattr(row, key, value)
    await db.commit()
    return conversation_json(row)


@app.delete("/v1/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> None:
    row = await scoped_conversation(db, context, conversation_id)
    attachments = (await db.scalars(select(Attachment).where(Attachment.conversation_id == row.id, Attachment.user_id == context.user_id))).all()
    for attachment in attachments:
        await storage_service.delete(attachment.storage_key)
    artifacts = (await db.scalars(select(GeneratedArtifact).where(GeneratedArtifact.conversation_id == row.id, GeneratedArtifact.user_id == context.user_id))).all()
    for artifact in artifacts:
        await delete_artifact_files(db, storage_service, artifact.id)
    await db.delete(row)
    await db.commit()


@app.post("/v1/conversations/{conversation_id}/attachments", status_code=201)
async def upload_attachment(conversation_id: str, upload: UploadFile = File(...), context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    await scoped_conversation(db, context, conversation_id)
    if upload.size and upload.size > settings.max_upload_bytes:
        log_event(logger, logging.WARNING, "attachment.rejected", conversation_id=conversation_id, reason="size_limit", declared_size_bytes=upload.size)
        raise HTTPException(status_code=413, detail="Attachment exceeds the 50 MB limit")
    file_name = safe_file_name(upload.filename)
    suffix = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if suffix not in ALLOWED_ATTACHMENT_SUFFIXES:
        log_event(logger, logging.WARNING, "attachment.rejected", conversation_id=conversation_id, reason="unsupported_type", file_name=file_name, mime_type=upload.content_type)
        raise HTTPException(status_code=415, detail="Unsupported attachment type")
    attachment_id = new_id()
    key = f"organizations/{context.organization_id}/users/{context.user_id}/conversations/{conversation_id}/{attachment_id}/{file_name}"
    log_event(logger, logging.INFO, "attachment.upload_started", attachment_id=attachment_id, conversation_id=conversation_id, file_name=file_name, mime_type=upload.content_type)
    try:
        size = await storage_service.save(key, upload)
    except Exception as exc:
        log_event(logger, logging.ERROR, "attachment.storage_failed", attachment_id=attachment_id, conversation_id=conversation_id, operation="save", error_type=type(exc).__name__, stack=exception_stack(exc))
        raise
    if size > settings.max_upload_bytes:
        await storage_service.delete(key)
        log_event(logger, logging.WARNING, "attachment.rejected", attachment_id=attachment_id, conversation_id=conversation_id, reason="size_limit", size_bytes=size)
        raise HTTPException(status_code=413, detail="Attachment exceeds the 50 MB limit")
    mime_type = upload.content_type or "application/octet-stream"
    try:
        scan_status = await malware_scanner.scan(name=file_name, mime_type=mime_type, data=await storage_service.read(key))
    except Exception as exc:
        log_event(logger, logging.ERROR, "attachment.scan_failed", attachment_id=attachment_id, conversation_id=conversation_id, error_type=type(exc).__name__, stack=exception_stack(exc))
        raise
    if scan_status == "infected":
        await storage_service.delete(key)
        log_event(logger, logging.WARNING, "attachment.rejected", attachment_id=attachment_id, conversation_id=conversation_id, reason="infected", size_bytes=size, mime_type=mime_type)
        raise HTTPException(status_code=422, detail="Attachment was rejected by malware scanning")
    if scan_status == "unavailable" and settings.app_env != "development":
        await storage_service.delete(key)
        log_event(logger, logging.WARNING, "attachment.rejected", attachment_id=attachment_id, conversation_id=conversation_id, reason="scanner_unavailable", size_bytes=size, mime_type=mime_type)
        raise HTTPException(status_code=503, detail="Attachment scanning is temporarily unavailable")
    row = Attachment(id=attachment_id, organization_id=context.organization_id, user_id=context.user_id, conversation_id=conversation_id, file_name=file_name, mime_type=mime_type, size_bytes=size, storage_key=key, scan_status=scan_status)
    db.add(row)
    await db.commit()
    log_event(logger, logging.INFO, "attachment.upload_completed", attachment_id=row.id, conversation_id=conversation_id, file_name=row.file_name, mime_type=row.mime_type, size_bytes=row.size_bytes, scan_status=row.scan_status)
    return {"id": row.id, "file_name": row.file_name, "mime_type": row.mime_type, "size_bytes": row.size_bytes, "scan_status": row.scan_status}


@app.delete("/v1/attachments/{attachment_id}", status_code=204)
async def delete_attachment(attachment_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> None:
    row = await db.scalar(select(Attachment).where(Attachment.id == attachment_id, Attachment.organization_id == context.organization_id, Attachment.user_id == context.user_id))
    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")
    await storage_service.delete(row.storage_key)
    await db.delete(row)
    await db.commit()


@app.post("/v1/conversations/{conversation_id}/messages/stream")
async def stream_message(conversation_id: str, payload: MessageCreate, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    conversation = await scoped_conversation(db, context, conversation_id)
    settings_row = await db.scalar(select(UserSettings).where(UserSettings.organization_id == context.organization_id, UserSettings.user_id == context.user_id))
    model = payload.model or conversation.model
    validate_model_id(model)
    policy = await db.scalar(select(OrganizationModelPolicy).where(OrganizationModelPolicy.organization_id == context.organization_id))
    allowed_models = set(json.loads(policy.allowed_models_json)) if policy else set(MODEL_IDS)
    if model not in allowed_models:
        raise HTTPException(status_code=400, detail="Model is not available for this organization")
    effort = payload.effort or conversation.effort
    requested_knowledge_ids = payload.knowledge_base_ids if payload.knowledge_base_ids is not None else json.loads(conversation.knowledge_base_ids_json or "[]")
    knowledge_base_ids = await authorized_knowledge_base_ids(db, context.organization_id, context.user_id, requested_knowledge_ids)
    if payload.knowledge_base_ids is not None and len(set(knowledge_base_ids)) != len(set(requested_knowledge_ids)):
        raise HTTPException(status_code=403, detail="One or more knowledge sources are unavailable")
    web_search_enabled = payload.web_search_enabled if payload.web_search_enabled is not None else conversation.web_search_enabled
    conversation.knowledge_base_ids_json = json.dumps(knowledge_base_ids)
    conversation.web_search_enabled = web_search_enabled
    attachment_payloads: tuple[AttachmentPayload, ...] = ()
    if payload.attachment_ids:
        attachments = (await db.scalars(select(Attachment).where(
            Attachment.id.in_(payload.attachment_ids),
            Attachment.organization_id == context.organization_id,
            Attachment.user_id == context.user_id,
            Attachment.conversation_id == conversation.id,
        ))).all()
        if len(attachments) != len(set(payload.attachment_ids)):
            raise HTTPException(status_code=400, detail="One or more attachments are unavailable")
        attachment_payloads = tuple(AttachmentPayload(name=item.file_name, mime_type=item.mime_type, data=await storage_service.read(item.storage_key)) for item in attachments)

    user_message = Message(
        organization_id=context.organization_id,
        user_id=context.user_id,
        conversation_id=conversation.id,
        role="user",
        content=payload.content,
        knowledge_base_ids_json=json.dumps(knowledge_base_ids),
        web_search_enabled=web_search_enabled,
        grounding_status="pending",
    )
    db.add(user_message)
    if conversation.title == "New conversation":
        conversation.title = payload.content.strip().splitlines()[0][:64]
    conversation.model = model
    conversation.effort = effort
    await db.commit()
    recent_messages = (await db.scalars(select(Message).where(
        Message.conversation_id == conversation.id,
        Message.organization_id == context.organization_id,
        Message.user_id == context.user_id,
        Message.id != user_message.id,
    ).order_by(Message.created_at.desc()).limit(12))).all()
    recent_messages.reverse()
    history = "\n".join(f"{item.role}: {item.content}" for item in recent_messages)
    summary = await db.scalar(select(ConversationSummary).where(ConversationSummary.conversation_id == conversation.id))
    history_context = f"Summary: {summary.summary}\n{history}" if summary and summary.summary else history
    memory_candidates = (await db.scalars(select(PrivateChatMemory).where(
        PrivateChatMemory.organization_id == context.organization_id,
        PrivateChatMemory.user_id == context.user_id,
        PrivateChatMemory.conversation_id != conversation.id,
    ).order_by(PrivateChatMemory.created_at.desc()).limit(100))).all()
    query_terms = set(re.findall(r"[a-z0-9]+", payload.content.lower()))
    memory_candidates.sort(key=lambda item: len(query_terms & set(re.findall(r"[a-z0-9]+", item.content.lower()))), reverse=True)
    private_memory = "\n".join(item.content for item in memory_candidates[:3] if query_terms & set(re.findall(r"[a-z0-9]+", item.content.lower())))

    clarification = None
    lower = payload.content.strip().lower()
    detected_artifact_format = detect_requested_format(payload.content)
    artifact_format = payload.artifact_request.format if payload.artifact_request else (detected_artifact_format if detected_artifact_format in {"docx", "pptx"} else None)
    unsupported_pdf = detected_artifact_format == "pdf" and payload.artifact_request is None
    generic_artifact_request = bool(re.fullmatch(
        r"(please\s+)?(create|make|generate|build|prepare)(\s+me)?(\s+an?|\s+the)?\s+(powerpoint|presentation|slide deck|slides|word document|docx|editable document)(\s+file)?[.!]?",
        lower,
    ))
    ambiguous_phrases = {"what is the policy", "what did we decide", "is this allowed", "what is our process", "what should i do about it"}
    if artifact_format and generic_artifact_request:
        clarification = "What should the file cover, who is it for, and roughly how detailed should it be?"
    elif len(knowledge_base_ids) > 1 and any(lower.rstrip("?.") == phrase for phrase in ambiguous_phrases):
        clarification = "Which team, region, time period, or specific policy should I use? That scope could materially change the company answer."

    retrieval_started = perf_counter()
    internal_results = [] if clarification or artifact_format or unsupported_pdf else await retrieve_company_knowledge(db, context.organization_id, context.user_id, knowledge_base_ids, payload.content)
    retrieval_duration_ms = round((perf_counter() - retrieval_started) * 1000, 2)
    internal_citations = [item.citation(index) for index, item in enumerate(internal_results, start=1)]
    retrieved_version_ids = {item.version_id for item in internal_results}
    conflicts = []
    if retrieved_version_ids:
        conflicts = (await db.scalars(select(KnowledgeConflict).where(
            KnowledgeConflict.organization_id == context.organization_id,
            KnowledgeConflict.status == "open",
            or_(KnowledgeConflict.left_version_id.in_(retrieved_version_ids), KnowledgeConflict.right_version_id.in_(retrieved_version_ids)),
        ))).all()
    internal_context = format_internal_context(internal_results)
    if conflicts:
        internal_context += "\n\nUNRESOLVED COMPANY CONFLICTS: " + " | ".join(item.summary or item.conflict_type for item in conflicts) + ". Do not silently choose one side; disclose the conflict."

    provider = get_chat_provider(model, web_search_enabled=web_search_enabled)
    provider_name = "google_adk" if provider.__class__.__name__ == "GoogleAdkChatProvider" else "demo"
    request = AgentRequest(
        user_id=context.user_id,
        session_id=conversation.id,
        message=payload.content,
        custom_instructions=settings_row.custom_instructions if settings_row else "",
        model=model,
        effort=effort,
        attachments=attachment_payloads,
        history=history_context,
        private_memory=private_memory,
        internal_context=internal_context if knowledge_base_ids else "",
        internal_citation_count=len(internal_citations),
        web_search_enabled=web_search_enabled,
    )

    async def events():
        assistant_message_id = new_id()
        stream_started = perf_counter()
        attachment_metadata = [
            {"file_name": item.name, "mime_type": item.mime_type, "size_bytes": len(item.data)}
            for item in attachment_payloads
        ]
        common_transcript_fields = {
            "conversation_id": conversation.id,
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message_id,
            "provider": provider_name,
            "model": model,
            "effort": effort,
            "user_message": payload.content,
            "custom_instructions": settings_row.custom_instructions if settings_row else "",
            "attachments": attachment_metadata,
            "knowledge_base_ids": knowledge_base_ids,
            "web_search_enabled": web_search_enabled,
        }
        log_event(
            logger,
            logging.INFO,
            "chat.stream_started",
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message_id,
            provider=provider_name,
            model=model,
            effort=effort,
            attachment_count=len(attachment_payloads),
        )
        chunks: list[str] = []
        web_citations: list[dict[str, Any]] = []
        try:
            yield f"event: message_started\ndata: {json.dumps({'message_id': assistant_message_id})}\n\n"
            if unsupported_pdf:
                response = "PDF export is not available yet. I can create an editable Word document (.docx) or PowerPoint presentation (.pptx) that you can export to PDF after downloading."
                chunks.append(response)
                async with SessionLocal() as stream_db:
                    stream_db.add(Message(
                        id=assistant_message_id,
                        organization_id=context.organization_id,
                        user_id=context.user_id,
                        conversation_id=conversation.id,
                        role="assistant",
                        content=response,
                        knowledge_base_ids_json=json.dumps(knowledge_base_ids),
                        web_search_enabled=web_search_enabled,
                        grounding_status="not_requested",
                    ))
                    await stream_db.commit()
                yield f"event: text_delta\ndata: {json.dumps({'text': response})}\n\n"
                yield f"event: grounding_status\ndata: {json.dumps({'status': 'not_requested'})}\n\n"
                yield f"event: message_completed\ndata: {json.dumps({'message_id': assistant_message_id, 'grounding_status': 'not_requested'})}\n\n"
                log_transcript(**common_transcript_fields, outcome="completed", assistant_response=response, duration_ms=round((perf_counter() - stream_started) * 1000, 2))
                return
            if artifact_format and not clarification:
                response = f"I’m creating an editable {'Word document' if artifact_format == 'docx' else 'PowerPoint presentation'}. You can follow its progress and download it from the file card below."
                async with SessionLocal() as stream_db:
                    stream_db.add(Message(
                        id=assistant_message_id,
                        organization_id=context.organization_id,
                        user_id=context.user_id,
                        conversation_id=conversation.id,
                        role="assistant",
                        content=response,
                        knowledge_base_ids_json=json.dumps(knowledge_base_ids),
                        web_search_enabled=web_search_enabled,
                        grounding_status="pending",
                    ))
                    await stream_db.flush()
                    queued = await queue_artifact(
                        stream_db,
                        context=context,
                        conversation=conversation,
                        message_id=assistant_message_id,
                        instructions=payload.content,
                        format_name=artifact_format,
                        template_id=payload.artifact_request.template_id if payload.artifact_request else "auto",
                        use_document_template=payload.artifact_request.use_document_template if payload.artifact_request else True,
                        model=model,
                        effort=effort,
                        knowledge_base_ids=knowledge_base_ids,
                        web_search_enabled=web_search_enabled,
                        attachment_ids=payload.attachment_ids,
                    )
                    queued_json = await artifact_json(stream_db, queued)
                chunks.append(response)
                yield f"event: text_delta\ndata: {json.dumps({'text': response})}\n\n"
                yield f"event: artifact_queued\ndata: {json.dumps({'artifact': queued_json})}\n\n"
                yield f"event: message_completed\ndata: {json.dumps({'message_id': assistant_message_id, 'grounding_status': 'pending'})}\n\n"
                log_transcript(**common_transcript_fields, outcome="artifact_queued", assistant_response=response, duration_ms=round((perf_counter() - stream_started) * 1000, 2))
                return
            if clarification:
                yield f"event: clarification_required\ndata: {json.dumps({'question': clarification})}\n\n"
                chunks.append(clarification)
            else:
                yield f"event: retrieval_started\ndata: {json.dumps({'knowledge_base_ids': knowledge_base_ids})}\n\n"
                if internal_citations:
                    yield f"event: internal_citations\ndata: {json.dumps({'citations': internal_citations})}\n\n"
                async for agent_event in provider.stream(request):
                    if agent_event.kind == "text":
                        chunks.append(agent_event.text)
                        yield f"event: text_delta\ndata: {json.dumps({'text': agent_event.text})}\n\n"
                    elif agent_event.kind == "web_citations":
                        seen = {(item.get('url'), item.get('title')) for item in web_citations}
                        for citation in agent_event.citations:
                            if (citation.get("url"), citation.get("title")) not in seen:
                                web_citations.append(dict(citation))
                                seen.add((citation.get("url"), citation.get("title")))
                        yield f"event: web_citations\ndata: {json.dumps({'citations': web_citations})}\n\n"
            grounding_status = (
                "clarification_required" if clarification else
                "grounded_mixed" if internal_citations and web_citations else
                "grounded_internal" if internal_citations else
                "grounded_web" if web_citations else
                "unsupported" if knowledge_base_ids or web_search_enabled else
                "not_requested"
            )
            async with SessionLocal() as stream_db:
                response = "".join(chunks).strip()
                assistant_row = Message(
                    id=assistant_message_id,
                    organization_id=context.organization_id,
                    user_id=context.user_id,
                    conversation_id=conversation.id,
                    role="assistant",
                    content=response,
                    knowledge_base_ids_json=json.dumps(knowledge_base_ids),
                    web_search_enabled=web_search_enabled,
                    grounding_status=grounding_status,
                )
                stream_db.add(assistant_row)
                await stream_db.flush()
                for citation in internal_citations:
                    stream_db.add(MessageCitation(
                        organization_id=context.organization_id,
                        message_id=assistant_message_id,
                        source_type="company",
                        ordinal=citation["ordinal"],
                        knowledge_base_id=citation["knowledge_base_id"],
                        document_id=citation["document_id"],
                        version_id=citation["version_id"],
                        chunk_id=citation["chunk_id"],
                        title=citation["title"],
                        location=citation["location"],
                        metadata_json=json.dumps({"knowledge_base_title": citation["knowledge_base_title"], "version": citation["version"], "effective_at": citation["effective_at"], "kind": citation["kind"]}),
                    ))
                for index, citation in enumerate(web_citations, start=len(internal_citations) + 1):
                    stream_db.add(MessageCitation(
                        organization_id=context.organization_id,
                        message_id=assistant_message_id,
                        source_type="web",
                        ordinal=index,
                        title=citation.get("title") or "Web source",
                        url=citation.get("url"),
                        publisher=citation.get("publisher"),
                        retrieved_at=utc_now(),
                    ))
                memory = PrivateChatMemory(
                    organization_id=context.organization_id,
                    user_id=context.user_id,
                    conversation_id=conversation.id,
                    message_id=assistant_message_id,
                    content=f"User: {payload.content}\nAssistant: {response}",
                    embedding=await embedding_for(f"{payload.content}\n{response}"),
                )
                stream_db.add(memory)
                all_messages = (await stream_db.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc()).limit(20))).all()
                summary_row = await stream_db.scalar(select(ConversationSummary).where(ConversationSummary.conversation_id == conversation.id))
                summary_text = "\n".join(f"{item.role}: {item.content[:500]}" for item in reversed(all_messages))[-8000:]
                if summary_row:
                    summary_row.summary = summary_text
                else:
                    stream_db.add(ConversationSummary(organization_id=context.organization_id, user_id=context.user_id, conversation_id=conversation.id, summary=summary_text))
                if grounding_status == "unsupported" and knowledge_base_ids:
                    stream_db.add(UnansweredQuestion(organization_id=context.organization_id, user_id=context.user_id, conversation_id=conversation.id, message_id=user_message.id, question=payload.content, reason="no_evidence"))
                await stream_db.commit()
            response = "".join(chunks).strip()
            duration_ms = round((perf_counter() - stream_started) * 1000, 2)
            log_event(
                logger,
                logging.INFO,
                "chat.stream_completed",
                conversation_id=conversation.id,
                assistant_message_id=assistant_message_id,
                provider=provider_name,
                model=model,
                duration_ms=duration_ms,
                response_bytes=len(response.encode("utf-8")),
                knowledge_base_count=len(knowledge_base_ids),
                internal_source_count=len(internal_citations),
                web_source_count=len(web_citations),
                web_search_enabled=web_search_enabled,
                retrieval_duration_ms=retrieval_duration_ms,
                grounding_status=grounding_status,
            )
            log_transcript(**common_transcript_fields, outcome="completed", assistant_response=response, duration_ms=duration_ms)
        except (asyncio.CancelledError, GeneratorExit):
            response = "".join(chunks).strip()
            duration_ms = round((perf_counter() - stream_started) * 1000, 2)
            log_event(
                logger,
                logging.WARNING,
                "chat.stream_cancelled",
                conversation_id=conversation.id,
                assistant_message_id=assistant_message_id,
                provider=provider_name,
                model=model,
                duration_ms=duration_ms,
                response_bytes=len(response.encode("utf-8")),
            )
            log_transcript(**common_transcript_fields, outcome="cancelled", assistant_response=response, duration_ms=duration_ms)
            raise
        except Exception as exc:
            response = "".join(chunks).strip()
            if response:
                async with SessionLocal() as stream_db:
                    stream_db.add(Message(
                        id=assistant_message_id,
                        organization_id=context.organization_id,
                        user_id=context.user_id,
                        conversation_id=conversation.id,
                        role="assistant",
                        content=response,
                        status="error",
                        knowledge_base_ids_json=json.dumps(knowledge_base_ids),
                        web_search_enabled=web_search_enabled,
                        grounding_status="failed",
                    ))
                    await stream_db.commit()
            duration_ms = round((perf_counter() - stream_started) * 1000, 2)
            log_event(
                logger,
                logging.ERROR,
                "chat.stream_failed",
                conversation_id=conversation.id,
                assistant_message_id=assistant_message_id,
                provider=provider_name,
                model=model,
                duration_ms=duration_ms,
                response_bytes=len(response.encode("utf-8")),
                error_type=type(exc).__name__,
                stack=exception_stack(exc),
            )
            log_transcript(**common_transcript_fields, outcome="failed", assistant_response=response, duration_ms=duration_ms, error_type=type(exc).__name__)
            yield f"event: error\ndata: {json.dumps({'message': 'The assistant could not complete this response.', 'detail': str(exc) if settings.app_env == 'development' else None})}\n\n"
        else:
            yield f"event: grounding_status\ndata: {json.dumps({'status': grounding_status})}\n\n"
            yield f"event: message_completed\ndata: {json.dumps({'message_id': assistant_message_id, 'grounding_status': grounding_status})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/v1/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    artifact = await scoped_artifact(db, context, artifact_id)
    return await artifact_json(db, artifact)


async def artifact_version_for_download(db: AsyncSession, artifact: GeneratedArtifact, version_number: int | None = None) -> ArtifactVersion:
    version = await db.scalar(select(ArtifactVersion).where(
        ArtifactVersion.artifact_id == artifact.id,
        ArtifactVersion.version_number == (version_number or artifact.current_version),
    ))
    if not version:
        raise HTTPException(status_code=404, detail="Generated file version not found")
    return version


@app.get("/v1/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str, version: int | None = Query(default=None, ge=1), context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> Response:
    artifact = await scoped_artifact(db, context, artifact_id)
    row = await artifact_version_for_download(db, artifact, version)
    if row.status != "ready" or not row.storage_key or not row.file_name:
        raise HTTPException(status_code=409, detail="Generated file is not ready to download")
    data = await storage_service.read(row.storage_key)
    log_event(logger, logging.INFO, "artifact.downloaded", artifact_id=artifact.id, version_id=row.id, format=artifact.format, size_bytes=len(data))
    return Response(data, media_type=row.mime_type or MIME_TYPES[artifact.format], headers={
        "Content-Disposition": f'attachment; filename="{safe_file_name(row.file_name)}"',
        "Cache-Control": "private, no-store",
    })


@app.get("/v1/artifacts/{artifact_id}/previews/{preview_number}")
async def preview_artifact(artifact_id: str, preview_number: int, version: int | None = Query(default=None, ge=1), context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> Response:
    artifact = await scoped_artifact(db, context, artifact_id)
    row = await artifact_version_for_download(db, artifact, version)
    preview_keys = json.loads(row.preview_keys_json or "[]")
    if preview_number < 1 or preview_number > len(preview_keys):
        raise HTTPException(status_code=404, detail="Generated file preview not found")
    return Response(await storage_service.read(preview_keys[preview_number - 1]), media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@app.post("/v1/artifacts/{artifact_id}/revisions", status_code=202)
async def revise_artifact(artifact_id: str, payload: ArtifactRevisionCreate, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    artifact = await scoped_artifact(db, context, artifact_id)
    current = await artifact_version_for_download(db, artifact)
    if current.status != "ready":
        raise HTTPException(status_code=409, detail="Wait for the current version to finish before revising it")
    source_scope = current.source_scope_json or artifact.source_scope_json
    document_template_version_id = current.document_template_version_id
    document_template_snapshot_json = current.document_template_snapshot_json or "{}"
    if payload.use_current_document_template and artifact.format == "docx" and artifact.use_document_template:
        organization_template = await db.scalar(select(OrganizationDocumentTemplate).where(
            OrganizationDocumentTemplate.organization_id == context.organization_id,
            OrganizationDocumentTemplate.enabled.is_(True),
        ))
        candidate = await db.get(OrganizationDocumentTemplateVersion, organization_template.active_version_id) if organization_template and organization_template.active_version_id else None
        if candidate and candidate.status == "ready":
            document_template_version_id = candidate.id
            document_template_snapshot_json = json.dumps({
                "id": candidate.id,
                "version_number": candidate.version_number,
                "file_name": candidate.file_name,
                "sha256": candidate.sha256,
            })
        else:
            document_template_version_id = None
            document_template_snapshot_json = "{}"
    next_version = max((await db.scalars(select(ArtifactVersion.version_number).where(ArtifactVersion.artifact_id == artifact.id))).all(), default=0) + 1
    version = ArtifactVersion(
        organization_id=context.organization_id,
        user_id=context.user_id,
        artifact_id=artifact.id,
        version_number=next_version,
        instructions=payload.instructions.strip(),
        source_scope_json=source_scope,
        document_template_version_id=document_template_version_id,
        document_template_snapshot_json=document_template_snapshot_json,
    )
    db.add(version)
    await db.flush()
    db.add(ArtifactJob(organization_id=context.organization_id, artifact_id=artifact.id, version_id=version.id))
    artifact.current_version = next_version
    artifact.status = "queued"
    artifact.error = None
    await audit(db, context, "artifact.revision_queued", "artifact", artifact.id, {"version": next_version, "document_template_version_id": document_template_version_id})
    await db.commit()
    log_event(logger, logging.INFO, "artifact.revision_queued", artifact_id=artifact.id, version_id=version.id, version_number=next_version, format=artifact.format)
    return await artifact_json(db, artifact)


@app.post("/v1/artifacts/{artifact_id}/retry", status_code=202)
async def retry_artifact(artifact_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    artifact = await scoped_artifact(db, context, artifact_id)
    version = await artifact_version_for_download(db, artifact)
    if version.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Only failed or cancelled generation can be retried")
    job = await db.scalar(select(ArtifactJob).where(ArtifactJob.version_id == version.id))
    if not job:
        job = ArtifactJob(organization_id=context.organization_id, artifact_id=artifact.id, version_id=version.id)
        db.add(job)
    else:
        job.status = "queued"
        job.progress = 0
        job.error = None
        job.cancellation_requested = False
        job.completed_at = None
    artifact.status = version.status = "queued"
    artifact.error = version.error = None
    await db.commit()
    return await artifact_json(db, artifact)


@app.post("/v1/artifacts/{artifact_id}/cancel")
async def cancel_artifact(artifact_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    artifact = await scoped_artifact(db, context, artifact_id, require_sources=False)
    version = await artifact_version_for_download(db, artifact)
    job = await db.scalar(select(ArtifactJob).where(ArtifactJob.version_id == version.id))
    if not job or job.status in {"ready", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Generation is no longer cancellable")
    job.cancellation_requested = True
    if job.status == "queued":
        job.status = artifact.status = version.status = "cancelled"
        job.completed_at = utc_now()
    await db.commit()
    return await artifact_json(db, artifact)


@app.post("/v1/artifacts/{artifact_id}/save-to-knowledge", status_code=202)
async def save_artifact_to_knowledge(artifact_id: str, payload: ArtifactSaveKnowledge, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    artifact = await scoped_artifact(db, context, artifact_id)
    knowledge_base = await require_knowledge_access(db, context, payload.knowledge_base_id)
    version = await artifact_version_for_download(db, artifact)
    if version.status != "ready" or not version.storage_key or not version.file_name:
        raise HTTPException(status_code=409, detail="Generated file is not ready")
    data = await storage_service.read(version.storage_key)
    file_name = safe_file_name(payload.title.strip() if payload.title else version.file_name)
    if Path(file_name).suffix.lower() != FORMAT_SUFFIXES[artifact.format]:
        file_name += FORMAT_SUFFIXES[artifact.format]
    upload = UploadFile(filename=file_name, file=io.BytesIO(data), headers=Headers({"content-type": version.mime_type or MIME_TYPES[artifact.format]}))
    document = await store_knowledge_upload(db, context, knowledge_base, upload)
    document.title = payload.title.strip() if payload.title else artifact.title
    await audit(db, context, "artifact.saved_to_knowledge", "artifact", artifact.id, {"knowledge_base_id": knowledge_base.id, "document_id": document.id})
    await db.commit()
    return await document_json(db, document)


@app.delete("/v1/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(artifact_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> None:
    artifact = await scoped_artifact(db, context, artifact_id, require_sources=False)
    await delete_artifact_files(db, storage_service, artifact.id)
    await db.delete(artifact)
    await db.commit()
    log_event(logger, logging.INFO, "artifact.deleted", artifact_id=artifact_id)


@app.get("/v1/prompts")
async def list_prompts(
    search: str = "",
    favorites: bool = False,
    archived: bool = False,
    context: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(Prompt).where(Prompt.organization_id == context.organization_id, Prompt.archived.is_(archived))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Prompt.title.ilike(pattern), Prompt.description.ilike(pattern), Prompt.body.ilike(pattern)))
    if favorites:
        query = query.join(PromptFavorite, PromptFavorite.prompt_id == Prompt.id).where(PromptFavorite.user_id == context.user_id)
    rows = (await db.scalars(query.order_by(Prompt.updated_at.desc()))).all()
    return [await prompt_json(db, row, context.user_id) for row in rows]


@app.post("/v1/prompts", status_code=201)
async def create_prompt(payload: PromptCreate, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    tags_json = json.dumps(payload.tags)
    row = Prompt(organization_id=context.organization_id, title=payload.title, description=payload.description, body=payload.body, tags_json=tags_json, creator_id=context.user_id, last_editor_id=context.user_id)
    db.add(row)
    await db.flush()
    db.add(PromptVersion(organization_id=context.organization_id, prompt_id=row.id, version_number=1, title=row.title, description=row.description, body=row.body, tags_json=tags_json, edited_by=context.user_id))
    await audit(db, context, "prompt.created", "prompt", row.id)
    await db.commit()
    return await prompt_json(db, row, context.user_id)


@app.patch("/v1/prompts/{prompt_id}")
async def update_prompt(prompt_id: str, payload: PromptUpdate, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await db.scalar(select(Prompt).where(Prompt.id == prompt_id, Prompt.organization_id == context.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt not found")
    values = payload.model_dump(exclude_unset=True)
    if "tags" in values:
        row.tags_json = json.dumps(values.pop("tags"))
    for key, value in values.items():
        setattr(row, key, value)
    row.version_number += 1
    row.last_editor_id = context.user_id
    db.add(PromptVersion(organization_id=context.organization_id, prompt_id=row.id, version_number=row.version_number, title=row.title, description=row.description, body=row.body, tags_json=row.tags_json, edited_by=context.user_id))
    await audit(db, context, "prompt.updated", "prompt", row.id, {"version": row.version_number})
    await db.commit()
    return await prompt_json(db, row, context.user_id)


@app.post("/v1/prompts/{prompt_id}/duplicate", status_code=201)
async def duplicate_prompt(prompt_id: str, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    source = await db.scalar(select(Prompt).where(Prompt.id == prompt_id, Prompt.organization_id == context.organization_id))
    if not source:
        raise HTTPException(status_code=404, detail="Prompt not found")
    row = Prompt(organization_id=context.organization_id, title=f"{source.title} copy", description=source.description, body=source.body, tags_json=source.tags_json, creator_id=context.user_id, last_editor_id=context.user_id)
    db.add(row)
    await db.flush()
    db.add(PromptVersion(organization_id=context.organization_id, prompt_id=row.id, version_number=1, title=row.title, description=row.description, body=row.body, tags_json=row.tags_json, edited_by=context.user_id))
    await audit(db, context, "prompt.duplicated", "prompt", row.id, {"source_prompt_id": source.id})
    await db.commit()
    return await prompt_json(db, row, context.user_id)


@app.post("/v1/prompts/{prompt_id}/favorite")
async def toggle_favorite(prompt_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    prompt = await db.scalar(select(Prompt.id).where(Prompt.id == prompt_id, Prompt.organization_id == context.organization_id))
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    favorite = await db.scalar(select(PromptFavorite).where(PromptFavorite.prompt_id == prompt_id, PromptFavorite.user_id == context.user_id))
    if favorite:
        await db.delete(favorite)
        active = False
    else:
        db.add(PromptFavorite(organization_id=context.organization_id, prompt_id=prompt_id, user_id=context.user_id))
        active = True
    await db.commit()
    return {"favorite": active}


@app.get("/v1/prompts/{prompt_id}/versions")
async def prompt_versions(prompt_id: str, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    prompt = await db.scalar(select(Prompt.id).where(Prompt.id == prompt_id, Prompt.organization_id == context.organization_id))
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    rows = (await db.scalars(select(PromptVersion).where(PromptVersion.prompt_id == prompt_id, PromptVersion.organization_id == context.organization_id).order_by(PromptVersion.version_number.desc()))).all()
    return [{"id": row.id, "version_number": row.version_number, "title": row.title, "body": row.body, "created_at": as_iso(row.created_at)} for row in rows]


@app.post("/v1/prompts/{prompt_id}/versions/{version_number}/restore")
async def restore_prompt(prompt_id: str, version_number: int, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    prompt = await db.scalar(select(Prompt).where(Prompt.id == prompt_id, Prompt.organization_id == context.organization_id))
    version = await db.scalar(select(PromptVersion).where(PromptVersion.prompt_id == prompt_id, PromptVersion.organization_id == context.organization_id, PromptVersion.version_number == version_number))
    if not prompt or not version:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    prompt.title, prompt.description, prompt.body, prompt.tags_json = version.title, version.description, version.body, version.tags_json
    prompt.version_number += 1
    prompt.last_editor_id = context.user_id
    db.add(PromptVersion(organization_id=context.organization_id, prompt_id=prompt.id, version_number=prompt.version_number, title=prompt.title, description=prompt.description, body=prompt.body, tags_json=prompt.tags_json, edited_by=context.user_id))
    await audit(db, context, "prompt.restored", "prompt", prompt.id, {"restored_version": version_number})
    await db.commit()
    return await prompt_json(db, prompt, context.user_id)


@app.delete("/v1/prompts/{prompt_id}", status_code=204)
async def archive_prompt(prompt_id: str, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> None:
    prompt = await db.scalar(select(Prompt).where(Prompt.id == prompt_id, Prompt.organization_id == context.organization_id))
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt.archived = True
    await audit(db, context, "prompt.archived", "prompt", prompt.id)
    await db.commit()


@app.get("/v1/settings")
async def get_user_settings(context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await db.scalar(select(UserSettings).where(UserSettings.organization_id == context.organization_id, UserSettings.user_id == context.user_id))
    if not row:
        row = UserSettings(organization_id=context.organization_id, user_id=context.user_id)
        db.add(row)
        await db.commit()
    return {"custom_instructions": row.custom_instructions, "theme": row.theme, "default_model": row.default_model, "default_effort": row.default_effort, "web_search_default": row.web_search_default}


@app.patch("/v1/settings")
async def update_user_settings(payload: SettingsUpdate, context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if payload.default_model is not None:
        validate_model_id(payload.default_model)
    row = await db.scalar(select(UserSettings).where(UserSettings.organization_id == context.organization_id, UserSettings.user_id == context.user_id))
    if not row:
        row = UserSettings(organization_id=context.organization_id, user_id=context.user_id)
        db.add(row)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await db.commit()
    return {"custom_instructions": row.custom_instructions, "theme": row.theme, "default_model": row.default_model, "default_effort": row.default_effort, "web_search_default": row.web_search_default}


@app.get("/v1/models")
async def list_models(context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    policy = await db.scalar(select(OrganizationModelPolicy).where(OrganizationModelPolicy.organization_id == context.organization_id))
    allowed = json.loads(policy.allowed_models_json) if policy else []
    rows = (await db.scalars(select(ModelConfiguration).where(ModelConfiguration.enabled.is_(True)))).all()
    enabled = {row.id for row in rows}
    models = [dict(item) for item in MODEL_CATALOG if item["id"] in enabled and (not allowed or item["id"] in allowed)]
    return {"models": models, "default_model": policy.default_model if policy else (models[0]["id"] if models else None), "maximum_effort": policy.maximum_effort if policy else "high"}


@app.patch("/v1/organizations/current/model-policy")
async def update_model_policy(payload: ModelPolicyUpdate, context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if not payload.allowed_models or any(model not in MODEL_IDS for model in payload.allowed_models):
        raise HTTPException(status_code=400, detail="One or more models are unsupported")
    if payload.default_model not in payload.allowed_models:
        raise HTTPException(status_code=400, detail="Default model must be allowed")
    policy = await db.scalar(select(OrganizationModelPolicy).where(OrganizationModelPolicy.organization_id == context.organization_id))
    if not policy:
        policy = OrganizationModelPolicy(organization_id=context.organization_id)
        db.add(policy)
    policy.allowed_models_json = json.dumps(payload.allowed_models)
    policy.default_model = payload.default_model
    policy.maximum_effort = payload.maximum_effort
    await audit(db, context, "model_policy.updated", "organization", context.organization_id)
    await db.commit()
    return payload.model_dump()


@app.get("/v1/audit-events")
async def list_audit_events(limit: int = Query(default=50, ge=1, le=200), context: RequestContext = Depends(require_role("owner", "admin")), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.scalars(select(AuditEvent).where(AuditEvent.organization_id == context.organization_id).order_by(AuditEvent.created_at.desc()).limit(limit))).all()
    return [{"id": row.id, "action": row.action, "target_type": row.target_type, "target_id": row.target_id, "metadata": json.loads(row.metadata_json), "created_at": as_iso(row.created_at)} for row in rows]


@app.get("/v1/exports/conversations")
async def export_conversations(context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> JSONResponse:
    conversations = (await db.scalars(select(Conversation).where(Conversation.organization_id == context.organization_id, Conversation.user_id == context.user_id).order_by(Conversation.created_at))).all()
    exported = []
    for conversation in conversations:
        messages = (await db.scalars(select(Message).where(Message.conversation_id == conversation.id, Message.user_id == context.user_id).order_by(Message.created_at))).all()
        exported.append({"conversation": conversation_json(conversation), "messages": [await message_json(db, row) for row in messages]})
    return JSONResponse(exported, headers={"Content-Disposition": "attachment; filename=jules-ai-conversations.json"})


@app.delete("/v1/conversations", status_code=204)
async def delete_all_conversations(context: RequestContext = Depends(get_context), db: AsyncSession = Depends(get_db)) -> None:
    attachments = (await db.scalars(select(Attachment).where(Attachment.organization_id == context.organization_id, Attachment.user_id == context.user_id))).all()
    for attachment in attachments:
        await storage_service.delete(attachment.storage_key)
    artifacts = (await db.scalars(select(GeneratedArtifact).where(GeneratedArtifact.organization_id == context.organization_id, GeneratedArtifact.user_id == context.user_id))).all()
    for artifact in artifacts:
        await delete_artifact_files(db, storage_service, artifact.id)
    await db.execute(delete(Conversation).where(Conversation.organization_id == context.organization_id, Conversation.user_id == context.user_id))
    await db.commit()


@app.delete("/v1/me", status_code=204)
async def delete_personal_account(user: User = Depends(get_identity_user), db: AsyncSession = Depends(get_db)) -> None:
    owns_organization = await db.scalar(select(Membership.id).where(Membership.user_id == user.id, Membership.role == "owner", Membership.active.is_(True)))
    if owns_organization:
        raise HTTPException(status_code=409, detail="Transfer ownership or delete your organizations before deleting your account")
    attachments = (await db.scalars(select(Attachment).where(Attachment.user_id == user.id))).all()
    for attachment in attachments:
        await storage_service.delete(attachment.storage_key)
    artifacts = (await db.scalars(select(GeneratedArtifact).where(GeneratedArtifact.user_id == user.id))).all()
    for artifact in artifacts:
        await delete_artifact_files(db, storage_service, artifact.id)
    await db.execute(delete(Attachment).where(Attachment.user_id == user.id))
    await db.execute(delete(Message).where(Message.user_id == user.id))
    await db.execute(delete(Conversation).where(Conversation.user_id == user.id))
    await db.execute(delete(UserSettings).where(UserSettings.user_id == user.id))
    await db.execute(delete(PromptFavorite).where(PromptFavorite.user_id == user.id))
    await db.execute(delete(Membership).where(Membership.user_id == user.id))
    user.email = f"deleted+{user.id}@invalid.local"
    user.display_name = "Deleted user"
    user.avatar_url = None
    user.firebase_uid = None
    await db.commit()
    IngestionJob,
    KnowledgeBase,
    KnowledgeBaseAccess,
    KnowledgeChunk,
    KnowledgeConflict,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeProposal,
    MessageCitation,
    PrivateChatMemory,
    UnansweredQuestion,
