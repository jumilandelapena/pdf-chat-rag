"""Application settings, loaded from the environment and the repo-root ``.env`` file."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
MIB = 1024 * 1024


class Settings(BaseSettings):
    """All knobs of the service. Environment variable names are the upper-cased field names."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider
    llm_provider: Literal["anthropic", "mock"] = "mock"
    anthropic_api_key: str | None = None
    answer_model: str = "claude-haiku-5-5"
    rewrite_model: str = "claude-haiku-5-5"
    judge_model: str = "claude-haiku-5-5"
    answer_effort: Literal["low", "medium", "high"] = "low"
    answer_max_tokens: int = 8192
    rewrite_max_tokens: int = 1024
    judge_max_tokens: int = 2048

    # Embeddings
    embeddings_provider: Literal["local", "fake"] = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    embedding_model_path: Path | None = None

    # Storage and limits
    data_dir: Path = Path("data")
    max_upload_mb: float = 50
    max_upload_files: int = 5

    # Chunking
    chunk_tokens: int = 800
    chunk_overlap: float = 0.15
    max_chunk_chars: int = 4800
    embed_window_tokens: int = 480

    # Retrieval
    top_k_vector: int = 20
    top_k_bm25: int = 20
    top_k_final: int = 8
    history_turns: int = 6

    # HTTP
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "info"

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("embedding_model_path", mode="before")
    @classmethod
    def _blank_path_is_none(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @model_validator(mode="after")
    def _require_key_for_anthropic(self) -> Settings:
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic "
                "(put it in the repo-root .env)"
            )
        return self

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * MIB)

    @property
    def body_limit_bytes(self) -> int:
        return self.max_upload_files * (self.max_upload_bytes + MIB)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{(self.data_dir.resolve() / 'app.db').as_posix()}"


def get_settings() -> Settings:
    """Build a fresh Settings object (no caching, so tests can override freely)."""
    return Settings()
