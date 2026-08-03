from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal, create_schema
from .knowledge import process_ingestion_job
from .models import IngestionJob
from .observability import configure_logging, exception_stack, get_logger, log_event
from .storage import get_storage


settings = get_settings()
configure_logging(settings)
logger = get_logger("knowledge_worker")
storage = get_storage()


async def run_once() -> bool:
    async with SessionLocal() as db:
        statement = select(IngestionJob).where(IngestionJob.status == "queued").order_by(IngestionJob.created_at).limit(1)
        if db.bind and db.bind.dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        job = await db.scalar(statement)
        if not job:
            return False
        log_event(logger, logging.INFO, "knowledge.ingestion_started", job_id=job.id, version_id=job.version_id)
        try:
            await process_ingestion_job(db, storage, job)
        except Exception as exc:
            log_event(logger, logging.ERROR, "knowledge.ingestion_failed", job_id=job.id, version_id=job.version_id, error_type=type(exc).__name__, stack=exception_stack(exc))
        else:
            log_event(logger, logging.INFO, "knowledge.ingestion_completed", job_id=job.id, version_id=job.version_id)
        return True


async def main() -> None:
    await create_schema()
    log_event(logger, logging.INFO, "knowledge.worker_started")
    while True:
        handled = await run_once()
        if not handled:
            await asyncio.sleep(settings.knowledge_worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
