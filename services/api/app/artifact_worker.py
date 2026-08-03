from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select, update

from .artifacts import mark_job_failed, process_artifact_job
from .config import get_settings
from .database import SessionLocal, create_schema
from .document_templates import mark_template_job_failed, process_storage_cleanup_job, process_template_validation_job
from .models import ArtifactJob, DocumentTemplateValidationJob, StorageCleanupJob
from .observability import configure_logging, get_logger, log_event
from .storage import get_storage


settings = get_settings()
configure_logging(settings)
logger = get_logger("artifact_worker")
storage = get_storage()


async def recover_interrupted_jobs() -> None:
    async with SessionLocal() as db:
        await db.execute(
            update(ArtifactJob)
            .where(ArtifactJob.status.in_(["planning", "rendering", "validating"]))
            .values(status="queued", progress=0, error=None)
        )
        await db.execute(
            update(DocumentTemplateValidationJob)
            .where(DocumentTemplateValidationJob.status == "validating")
            .values(status="queued", progress=0, error=None)
        )
        await db.commit()


async def run_once() -> bool:
    async with SessionLocal() as db:
        statement = select(ArtifactJob).where(ArtifactJob.status == "queued").order_by(ArtifactJob.created_at).limit(1)
        if db.bind and db.bind.dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        job = await db.scalar(statement)
        if job:
            log_event(logger, logging.INFO, "artifact.generation_started", artifact_id=job.artifact_id, version_id=job.version_id, job_id=job.id)
            try:
                await process_artifact_job(db, storage, job)
            except asyncio.CancelledError:
                log_event(logger, logging.INFO, "artifact.generation_cancelled", artifact_id=job.artifact_id, version_id=job.version_id, job_id=job.id)
            except Exception as exc:
                await mark_job_failed(db, job, exc)
            return True

        template_statement = select(DocumentTemplateValidationJob).where(
            DocumentTemplateValidationJob.status == "queued"
        ).order_by(DocumentTemplateValidationJob.created_at).limit(1)
        if db.bind and db.bind.dialect.name == "postgresql":
            template_statement = template_statement.with_for_update(skip_locked=True)
        template_job = await db.scalar(template_statement)
        if template_job:
            log_event(logger, logging.INFO, "document_template.validation_started", template_version_id=template_job.template_version_id, job_id=template_job.id)
            try:
                await process_template_validation_job(db, storage, template_job)
            except Exception as exc:
                await mark_template_job_failed(db, template_job, exc)
            return True

        cleanup_job = await db.scalar(select(StorageCleanupJob).order_by(StorageCleanupJob.created_at).limit(1))
        if cleanup_job:
            try:
                await process_storage_cleanup_job(db, storage, cleanup_job)
            except Exception as exc:
                log_event(logger, logging.WARNING, "storage.cleanup_failed", cleanup_job_id=cleanup_job.id, error_type=type(exc).__name__)
            return True
        return False


async def main() -> None:
    await create_schema()
    await recover_interrupted_jobs()
    log_event(logger, logging.INFO, "artifact.worker_started")
    while True:
        handled = await run_once()
        if not handled:
            await asyncio.sleep(settings.artifact_worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
