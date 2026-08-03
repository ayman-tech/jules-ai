from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from .model_catalog import DEFAULT_MODEL_ID


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./jules-ai.db"
    auth_mode: str = "development"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    gemini_model: str = DEFAULT_MODEL_ID
    google_api_key: str | None = None
    google_cloud_project: str | None = None
    google_cloud_storage_bucket: str | None = None
    document_ai_processor_name: str | None = None
    firebase_project_id: str | None = None
    max_upload_bytes: int = 50 * 1024 * 1024
    local_upload_dir: Path = Path("./uploads")
    log_level: str = "INFO"
    log_dir: Path = Path("./logs")
    log_chat_transcripts: bool = True
    knowledge_worker_poll_seconds: float = 2.0
    knowledge_chunk_size: int = 1400
    knowledge_chunk_overlap: int = 180
    knowledge_retrieval_limit: int = 10
    embedding_model: str = "gemini-embedding-2"
    artifact_generation_enabled: bool = True
    artifact_worker_poll_seconds: float = 2.0
    artifact_max_slides: int = 20
    artifact_max_doc_pages: int = 30
    artifact_max_bytes: int = 50 * 1024 * 1024
    artifact_qa_retry_count: int = 2
    artifact_render_timeout_seconds: int = 120

    @property
    def allowed_origins(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
