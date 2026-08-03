from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Settings


APP_LOGGER_NAME = "jules_ai"
TRANSCRIPT_LOGGER_NAME = "jules_ai.transcript"
MAX_LOG_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
INVITATION_PATH_PATTERN = re.compile(r"(/v1/invitations/)[^/]+")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
organization_id_var: ContextVar[str | None] = ContextVar("organization_id", default=None)
_transcripts_enabled = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event_name", record.getMessage()),
        }
        context = {
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
            "organization_id": organization_id_var.get(),
        }
        payload.update({key: value for key, value in context.items() if value is not None})
        payload.update(getattr(record, "event_data", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _close_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


def configure_logging(settings: Settings) -> None:
    global _transcripts_enabled

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = JsonFormatter()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    app_logger = logging.getLogger(APP_LOGGER_NAME)
    _close_handlers(app_logger)
    app_logger.setLevel(level)
    app_logger.propagate = False

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    app_logger.addHandler(console)

    api_file = RotatingFileHandler(
        log_dir / "api.jsonl",
        maxBytes=MAX_LOG_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    api_file.setFormatter(formatter)
    app_logger.addHandler(api_file)

    transcript_logger = logging.getLogger(TRANSCRIPT_LOGGER_NAME)
    _close_handlers(transcript_logger)
    transcript_logger.setLevel(logging.INFO)
    transcript_logger.propagate = False
    _transcripts_enabled = settings.app_env == "development" and settings.log_chat_transcripts
    if _transcripts_enabled:
        transcript_file = RotatingFileHandler(
            log_dir / "chat-transcripts.jsonl",
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        transcript_file.setFormatter(formatter)
        transcript_logger.addHandler(transcript_file)
    else:
        transcript_logger.addHandler(logging.NullHandler())

    # The request middleware emits richer access records without duplicating them.
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    logger.log(level, event, extra={"event_name": event, "event_data": fields})


def log_transcript(**fields: Any) -> None:
    if not _transcripts_enabled:
        return
    logger = logging.getLogger(TRANSCRIPT_LOGGER_NAME)
    logger.info("chat.turn", extra={"event_name": "chat.turn", "event_data": fields})


def bind_request_context(*, user_id: str | None = None, organization_id: str | None = None) -> None:
    if user_id is not None:
        user_id_var.set(user_id)
    if organization_id is not None:
        organization_id_var.set(organization_id)


def exception_stack(exc: BaseException) -> list[str]:
    """Return stack locations without source lines or messages, which may contain user data."""
    return [
        f'File "{frame.filename}", line {frame.lineno}, in {frame.name}'
        for frame in traceback.extract_tb(exc.__traceback__)
    ]


def _request_id(headers: list[tuple[bytes, bytes]]) -> str:
    for name, value in headers:
        if name.lower() == b"x-request-id":
            candidate = value.decode("latin-1")
            if REQUEST_ID_PATTERN.fullmatch(candidate):
                return candidate
            break
    return str(uuid4())


def _safe_path(path: str) -> str:
    return INVITATION_PATH_PATTERN.sub(r"\1[token]", path)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.logger = get_logger("request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope.get("headers", []))
        request_token = request_id_var.set(request_id)
        user_token = user_id_var.set(None)
        organization_token = organization_id_var.set(None)
        started = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
            log_event(
                self.logger,
                logging.WARNING if status_code >= 500 else logging.INFO,
                "request.completed",
                method=scope["method"],
                path=_safe_path(scope["path"]),
                status_code=status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
        except BaseException as exc:
            log_event(
                self.logger,
                logging.ERROR,
                "request.failed",
                method=scope["method"],
                path=_safe_path(scope["path"]),
                status_code=status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                error_type=type(exc).__name__,
                stack=exception_stack(exc),
            )
            raise
        finally:
            organization_id_var.reset(organization_token)
            user_id_var.reset(user_token)
            request_id_var.reset(request_token)
