from __future__ import annotations

import os
import logging
from pathlib import Path
from time import perf_counter

from fastapi import UploadFile

from .config import get_settings
from .observability import exception_stack, get_logger, log_event


logger = get_logger("storage")


class StorageService:
    async def save(self, key: str, upload: UploadFile) -> int:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def read(self, key: str) -> bytes:
        raise NotImplementedError

    async def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> int:
        raise NotImplementedError


class LocalStorageService(StorageService):
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Unsafe storage key")
        return path

    async def save(self, key: str, upload: UploadFile) -> int:
        started = perf_counter()
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        try:
            with path.open("wb") as target:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    target.write(chunk)
        except Exception as exc:
            log_event(logger, logging.ERROR, "storage.operation_failed", provider="local", operation="save", key=key, error_type=type(exc).__name__, stack=exception_stack(exc))
            raise
        log_event(logger, logging.INFO, "storage.operation_completed", provider="local", operation="save", key=key, size_bytes=size, duration_ms=round((perf_counter() - started) * 1000, 2))
        return size

    async def delete(self, key: str) -> None:
        started = perf_counter()
        path = self._path(key)
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:
            log_event(logger, logging.ERROR, "storage.operation_failed", provider="local", operation="delete", key=key, error_type=type(exc).__name__, stack=exception_stack(exc))
            raise
        log_event(logger, logging.INFO, "storage.operation_completed", provider="local", operation="delete", key=key, duration_ms=round((perf_counter() - started) * 1000, 2))

    async def read(self, key: str) -> bytes:
        started = perf_counter()
        try:
            data = self._path(key).read_bytes()
        except Exception as exc:
            log_event(logger, logging.ERROR, "storage.operation_failed", provider="local", operation="read", key=key, error_type=type(exc).__name__, stack=exception_stack(exc))
            raise
        log_event(logger, logging.INFO, "storage.operation_completed", provider="local", operation="read", key=key, size_bytes=len(data), duration_ms=round((perf_counter() - started) * 1000, 2))
        return data

    async def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> int:
        started = perf_counter()
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(data)
        except Exception as exc:
            log_event(logger, logging.ERROR, "storage.operation_failed", provider="local", operation="save_bytes", key=key, error_type=type(exc).__name__, stack=exception_stack(exc))
            raise
        log_event(logger, logging.INFO, "storage.operation_completed", provider="local", operation="save_bytes", key=key, size_bytes=len(data), duration_ms=round((perf_counter() - started) * 1000, 2))
        return len(data)


class GcsStorageService(StorageService):
    def __init__(self, bucket_name: str):
        from google.cloud import storage

        self.bucket = storage.Client().bucket(bucket_name)

    async def save(self, key: str, upload: UploadFile) -> int:
        started = perf_counter()
        data = await upload.read()
        try:
            self.bucket.blob(key).upload_from_string(data, content_type=upload.content_type)
        except Exception as exc:
            log_event(logger, logging.ERROR, "storage.operation_failed", provider="gcs", operation="save", key=key, error_type=type(exc).__name__, stack=exception_stack(exc))
            raise
        log_event(logger, logging.INFO, "storage.operation_completed", provider="gcs", operation="save", key=key, size_bytes=len(data), duration_ms=round((perf_counter() - started) * 1000, 2))
        return len(data)

    async def delete(self, key: str) -> None:
        started = perf_counter()
        try:
            self.bucket.blob(key).delete(if_generation_match=None)
        except Exception as exc:
            from google.api_core.exceptions import NotFound

            if isinstance(exc, NotFound):
                log_event(logger, logging.INFO, "storage.operation_completed", provider="gcs", operation="delete", key=key, already_missing=True, duration_ms=round((perf_counter() - started) * 1000, 2))
                return
            log_event(logger, logging.ERROR, "storage.operation_failed", provider="gcs", operation="delete", key=key, error_type=type(exc).__name__, stack=exception_stack(exc))
            raise
        log_event(logger, logging.INFO, "storage.operation_completed", provider="gcs", operation="delete", key=key, duration_ms=round((perf_counter() - started) * 1000, 2))

    async def read(self, key: str) -> bytes:
        started = perf_counter()
        try:
            data = self.bucket.blob(key).download_as_bytes()
        except Exception as exc:
            log_event(logger, logging.ERROR, "storage.operation_failed", provider="gcs", operation="read", key=key, error_type=type(exc).__name__, stack=exception_stack(exc))
            raise
        log_event(logger, logging.INFO, "storage.operation_completed", provider="gcs", operation="read", key=key, size_bytes=len(data), duration_ms=round((perf_counter() - started) * 1000, 2))
        return data

    async def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> int:
        started = perf_counter()
        try:
            self.bucket.blob(key).upload_from_string(data, content_type=content_type)
        except Exception as exc:
            log_event(logger, logging.ERROR, "storage.operation_failed", provider="gcs", operation="save_bytes", key=key, error_type=type(exc).__name__, stack=exception_stack(exc))
            raise
        log_event(logger, logging.INFO, "storage.operation_completed", provider="gcs", operation="save_bytes", key=key, size_bytes=len(data), duration_ms=round((perf_counter() - started) * 1000, 2))
        return len(data)


def get_storage() -> StorageService:
    settings = get_settings()
    if settings.google_cloud_storage_bucket:
        return GcsStorageService(settings.google_cloud_storage_bucket)
    return LocalStorageService(settings.local_upload_dir)


def safe_file_name(name: str | None) -> str:
    return os.path.basename(name or "attachment").replace("\x00", "")[:240]
