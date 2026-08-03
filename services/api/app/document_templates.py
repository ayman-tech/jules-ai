from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import (
    DocumentTemplateValidationJob,
    OrganizationDocumentTemplate,
    OrganizationDocumentTemplateVersion,
    StorageCleanupJob,
    utc_now,
)
from .observability import exception_stack, get_logger, log_event
from .storage import StorageService


logger = get_logger("document_templates")
settings = get_settings()
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
MAX_PACKAGE_FILES = 500
MAX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024


class TemplateValidationError(ValueError):
    pass


def validate_template_package(data: bytes) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise TemplateValidationError("The upload is not a valid Word DOCX package") from exc

    with archive:
        members = archive.infolist()
        if len(members) > MAX_PACKAGE_FILES:
            raise TemplateValidationError("The DOCX package contains too many files")
        if sum(item.file_size for item in members) > MAX_UNCOMPRESSED_BYTES:
            raise TemplateValidationError("The expanded DOCX package is too large")
        names = {item.filename for item in members}
        for item in members:
            path = PurePosixPath(item.filename)
            if path.is_absolute() or ".." in path.parts:
                raise TemplateValidationError("The DOCX package contains an unsafe file path")
        required = {"[Content_Types].xml", "word/document.xml", "_rels/.rels"}
        if not required.issubset(names):
            raise TemplateValidationError("The DOCX package is missing required Word components")

        lowered_names = {name.lower() for name in names}
        unsafe_parts = [
            name for name in lowered_names
            if "vbaproject" in name
            or name.startswith("word/activex/")
            or name.startswith("word/embeddings/")
            or name.startswith("customui/")
        ]
        if unsafe_parts:
            raise TemplateValidationError("Templates cannot contain macros, ActiveX controls, or embedded OLE objects")

        content_types = archive.read("[Content_Types].xml")
        if b"application/vnd.ms-word.template.macroEnabled" in content_types or b"application/vnd.ms-word.document.macroEnabled" in content_types:
            raise TemplateValidationError("Macro-enabled Word templates are not supported")
        if b"application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml" in content_types:
            raise TemplateValidationError("Save the template as a Word Document (.docx), then upload it again")
        if b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml" not in content_types:
            raise TemplateValidationError("The upload must be a Word Document (.docx)")

        for relationship_name in (name for name in names if name.endswith(".rels")):
            try:
                root = ElementTree.fromstring(archive.read(relationship_name))
            except ElementTree.ParseError as exc:
                raise TemplateValidationError("The DOCX package contains malformed relationships") from exc
            for relationship in root.iter(f"{{{RELATIONSHIP_NAMESPACE}}}Relationship"):
                if relationship.attrib.get("TargetMode", "").lower() == "external":
                    raise TemplateValidationError("Templates cannot contain external links or remote template relationships")

        try:
            document_root = ElementTree.fromstring(archive.read("word/document.xml"))
        except ElementTree.ParseError as exc:
            raise TemplateValidationError("The Word document body is malformed") from exc
        if document_root.find(f".//{{{WORD_NAMESPACE}}}altChunk") is not None:
            raise TemplateValidationError("Templates cannot contain imported altChunk content")
        section_count = len(document_root.findall(f".//{{{WORD_NAMESPACE}}}sectPr"))
        if section_count != 1:
            raise TemplateValidationError("Templates must contain exactly one Word section")

    from docx import Document

    try:
        parsed = Document(BytesIO(data))
    except Exception as exc:
        raise TemplateValidationError("Word could not open the uploaded DOCX structure") from exc
    if len(parsed.sections) != 1:
        raise TemplateValidationError("Templates must contain exactly one Word section")
    return {
        "package": "passed",
        "sha256": hashlib.sha256(data).hexdigest(),
        "package_parts": len(members),
        "section_count": 1,
        "sample_body_discarded": True,
        "unsafe_features": [],
    }


def _validation_sample():
    from .artifacts import ArtifactBlock, ArtifactPage, ArtifactSpec

    paragraphs = [
        "This representative paragraph verifies body typography, line spacing, margins, and continuation-page letterhead behavior. "
        "Organization templates supply the page shell while Jules supplies editable document content."
        for _ in range(8)
    ]
    return ArtifactSpec(
        title="Organization template preview",
        subtitle="Generated sample content is discarded after validation",
        pages=[
            ArtifactPage(
                title="Typography and content flow",
                blocks=[ArtifactBlock(kind="paragraph", heading=f"Sample section {index + 1}", text=text) for index, text in enumerate(paragraphs)],
            ),
            ArtifactPage(
                title="Tables and continuation pages",
                blocks=[
                    ArtifactBlock(
                        kind="table",
                        headers=["Item", "Purpose", "Status"],
                        rows=[[f"Check {index + 1}", "Verify reusable organization document styling", "Ready"] for index in range(12)],
                    ),
                    ArtifactBlock(kind="bullets", items=["Headers and footers remain intact", "Body sample content is removed", "Content flows without forced section breaks"]),
                ],
            ),
        ],
    )


async def process_template_validation_job(db: AsyncSession, storage: StorageService, job: DocumentTemplateValidationJob) -> None:
    from .artifacts import preview_layout_qa, render_docx, render_previews, structural_qa, visual_qa

    version = await db.get(OrganizationDocumentTemplateVersion, job.template_version_id)
    if not version:
        raise RuntimeError("Document template version is unavailable")
    template = await db.get(OrganizationDocumentTemplate, version.template_id)
    if not template or template.organization_id != version.organization_id:
        raise RuntimeError("Document template is unavailable")

    job.status = version.status = "validating"
    job.progress = 10
    job.attempts += 1
    job.started_at = job.started_at or utc_now()
    await db.commit()

    data = await storage.read(version.storage_key)
    report = validate_template_package(data)
    job.progress = 35
    version.validation_report_json = json.dumps(report)
    await db.commit()

    with tempfile.TemporaryDirectory(prefix="jules-docx-template-") as temp_name:
        work_dir = Path(temp_name)
        sample_path = work_dir / "template-preview.docx"
        await asyncio.to_thread(render_docx, _validation_sample(), sample_path, [], data)
        report.update(await asyncio.to_thread(structural_qa, sample_path, "docx", 2))
        preview_paths = await asyncio.to_thread(render_previews, sample_path, work_dir / "previews")
        report["layout"] = await asyncio.to_thread(preview_layout_qa, preview_paths)
        visual = await visual_qa(settings.gemini_model, preview_paths)
        if not visual.passed:
            raise TemplateValidationError("Template preview failed visual validation: " + "; ".join(visual.issues[:5]))
        report["visual_validation"] = "passed" if preview_paths else "unavailable_in_development"
        report["visual_issues"] = visual.issues
        report["preview_count"] = len(preview_paths)
        preview_keys: list[str] = []
        for index, preview_path in enumerate(preview_paths, start=1):
            key = f"organizations/{version.organization_id}/document-templates/{template.id}/v{version.version_number}/previews/{index}.png"
            await storage.save_bytes(key, preview_path.read_bytes(), "image/png")
            preview_keys.append(key)

    version.validation_report_json = json.dumps(report)
    version.preview_keys_json = json.dumps(preview_keys)
    version.status = "ready"
    version.error = None
    version.activated_at = utc_now()
    template.active_version_id = version.id
    template.enabled = True
    job.status = "ready"
    job.progress = 100
    job.error = None
    job.completed_at = utc_now()
    await db.commit()
    log_event(
        logger,
        logging.INFO,
        "document_template.validation_completed",
        organization_id=version.organization_id,
        template_id=template.id,
        template_version_id=version.id,
        version_number=version.version_number,
        size_bytes=version.size_bytes,
        preview_count=len(preview_keys),
    )


async def mark_template_job_failed(db: AsyncSession, job: DocumentTemplateValidationJob, exc: Exception) -> None:
    version = await db.get(OrganizationDocumentTemplateVersion, job.template_version_id)
    message = str(exc) if isinstance(exc, TemplateValidationError) else "Jules could not validate this document template."
    job.status = "failed"
    job.error = message
    job.completed_at = utc_now()
    if version:
        version.status = "failed"
        version.error = message
    await db.commit()
    log_event(
        logger,
        logging.ERROR,
        "document_template.validation_failed",
        template_version_id=job.template_version_id,
        error_type=type(exc).__name__,
        stack=exception_stack(exc),
    )


async def process_storage_cleanup_job(db: AsyncSession, storage: StorageService, job: StorageCleanupJob) -> None:
    job.attempts += 1
    try:
        await storage.delete(job.storage_key)
    except Exception as exc:
        job.error = type(exc).__name__
        await db.commit()
        raise
    await db.delete(job)
    await db.commit()


def template_version_json(version: OrganizationDocumentTemplateVersion, progress: int | None = None) -> dict[str, Any]:
    return {
        "id": version.id,
        "version_number": version.version_number,
        "file_name": version.file_name,
        "mime_type": version.mime_type,
        "size_bytes": version.size_bytes,
        "sha256": version.sha256,
        "status": version.status,
        "progress": 100 if version.status == "ready" else (progress or 0),
        "validation_report": json.loads(version.validation_report_json or "{}"),
        "preview_count": len(json.loads(version.preview_keys_json or "[]")),
        "uploaded_by": version.uploaded_by,
        "activated_at": version.activated_at.isoformat() if version.activated_at else None,
        "error": version.error,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


async def document_template_json(
    db: AsyncSession,
    template: OrganizationDocumentTemplate | None,
    *,
    can_manage: bool,
) -> dict[str, Any]:
    if not template:
        return {
            "id": None,
            "enabled": False,
            "active_version_id": None,
            "active_version": None,
            "pending_version": None,
            "versions": [],
            "can_manage": can_manage,
        }
    versions = (await db.scalars(select(OrganizationDocumentTemplateVersion).where(
        OrganizationDocumentTemplateVersion.template_id == template.id,
    ).order_by(OrganizationDocumentTemplateVersion.version_number.desc()))).all()
    jobs = (await db.scalars(select(DocumentTemplateValidationJob).where(
        DocumentTemplateValidationJob.template_version_id.in_([item.id for item in versions]),
    ))).all() if versions else []
    progress_by_version = {item.template_version_id: item.progress for item in jobs}
    active = next((item for item in versions if item.id == template.active_version_id), None)
    pending = next((item for item in versions if item.status in {"queued", "validating"}), None)
    visible = versions if can_manage else ([active] if active else [])
    return {
        "id": template.id,
        "enabled": template.enabled,
        "active_version_id": template.active_version_id,
        "active_version": template_version_json(active, progress_by_version.get(active.id)) if active else None,
        "pending_version": template_version_json(pending, progress_by_version.get(pending.id)) if pending else None,
        "versions": [template_version_json(item, progress_by_version.get(item.id)) for item in visible if item],
        "can_manage": can_manage,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


async def delete_document_template_files(db: AsyncSession, storage: StorageService, organization_id: str) -> None:
    versions = (await db.scalars(select(OrganizationDocumentTemplateVersion).where(
        OrganizationDocumentTemplateVersion.organization_id == organization_id,
    ))).all()
    for version in versions:
        await storage.delete(version.storage_key)
        for key in json.loads(version.preview_keys_json or "[]"):
            await storage.delete(key)
