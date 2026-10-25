"""Root-relative, typed configuration. Importing this module does no I/O."""

from functools import lru_cache
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore",
        hide_input_in_errors=True, frozen=True,
    )

    APP_MODE: Literal["development", "production", "test"] = "development"
    APP_NAME: str = "Hanoi Land Law AI"
    API_STR: str = "/api/v1"
    SERVER_HOST: str = "http://127.0.0.1:8000"
    PROJECT_NAME: str = "hanoi-land-law-ai"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    GEMINI_API_KEY: SecretStr = SecretStr("")
    MODEL: str = "gemini-2.5-flash-lite"
    ENABLE_LIVE_LLM: bool = False
    MAX_LLM_CALLS_PER_TURN: int = Field(default=5, ge=1, le=20)
    MAX_LLM_OUTPUT_TOKENS: int = Field(default=1024, ge=1, le=8192)
    MAX_LLM_CALLS_PER_DAY: int = Field(default=20, ge=1)
    LLM_REQUEST_TIMEOUT_SECONDS: float = Field(default=20, gt=0, le=120)
    LLM_MAX_RETRIES: int = Field(default=0, ge=0, le=2)
    LLM_USAGE_DB: Path = ROOT / "data/llm-usage.sqlite3"
    JWT_SECRET_KEY: SecretStr = SecretStr("")
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=10080)
    DATABASE_URL: str = "sqlite:///./data/law.db"
    MAX_HISTORY_MESSAGES: int = Field(default=20, ge=2, le=100)
    MAX_HISTORY_CHARACTERS: int = Field(default=20000, ge=100, le=100000)
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = Field(default=6333, ge=1, le=65535)
    COLLECTION_NAME: str = "laws"
    DOCS_ROOT: Path = ROOT / "law_crawler/vbpl_documents"
    EMBEDDING_DEVICE: Literal["cpu", "cuda", "auto"] = "cpu"
    ALLOW_MODEL_DOWNLOADS: bool = False
    ALLOW_REMOTE_MODEL_CODE: bool = False
    EMBEDDING_MODEL_NAME: str = "Alibaba-NLP/gte-multilingual-base"
    VIETNAMESE_EMBEDDING_MODEL: str = "AITeamVN/Vietnamese_Embedding_v2"
    VIETNAMESE_COLLECTION_NAME: str = "laws"
    VIETNAMESE_DENSE_VECTOR_SIZE: int = 1024
    BGEM3_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    BGEM3_COLLECTION_NAME: str = "laws_bge_m3"
    BGEM3_DENSE_VECTOR_SIZE: int = 1024
    RETRIEVAL_MODE: Literal["dense", "hybrid", "sparse"] = "dense"
    RETRIEVAL_K: int = Field(default=10, ge=1, le=100)
    TOP_K: int = Field(default=3, ge=1, le=100)
    EMBEDDINGS_FILE: str = "data/embeddings.pkl"
    DOCS_FILE: str = "data/documents.json"

    # Isolated MVP demo (lexical corpus, no Qdrant, no embeddings).
    MVP_ENABLED: bool = True
    MVP_DEMO_CORPUS_PATH: Path = ROOT / "backend/resources/mvp_demo_corpus.jsonl"
    MVP_TOP_K: int = Field(default=6, ge=1, le=12)
    MVP_MIN_SCORE: float = Field(default=5.0, ge=0)
    MVP_MIN_COVERAGE: float = Field(default=0.5, ge=0, le=1)
    MVP_RATE_LIMIT_PER_MINUTE: int = Field(default=6, ge=1)
    MVP_RATE_LIMIT_PER_DAY: int = Field(default=60, ge=1)
    MVP_MAX_MESSAGE_CHARS: int = Field(default=1000, ge=50, le=5000)
    MVP_MAX_HISTORY_MESSAGES: int = Field(default=6, ge=0, le=20)
    MVP_MAX_HISTORY_CHARS: int = Field(default=4000, ge=0, le=20000)

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_origins(cls, origins):
        from urllib.parse import urlsplit
        for origin in origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password or parsed.path
                    or parsed.query or parsed.fragment or "*" in origin):
                raise ValueError("CORS origins must be explicit HTTP(S) origins")
        return origins

    @model_validator(mode="after")
    def validate_runtime(self):
        secret = self.JWT_SECRET_KEY.get_secret_value()
        if (len(secret) < 32 or len(set(secret)) < 12
                or any(word in secret.lower() for word in ("change-me", "placeholder", "your-secret", "replace-with"))):
            raise ValueError("Set a strong JWT_SECRET_KEY (at least 32 characters)")
        if self.ENABLE_LIVE_LLM and not self.GEMINI_API_KEY.get_secret_value().strip():
            raise ValueError("GEMINI_API_KEY is required only when live LLM use is enabled")
        if self.TOP_K > self.RETRIEVAL_K:
            raise ValueError("TOP_K must not exceed RETRIEVAL_K")
        if self.APP_MODE == "test" and self.ENABLE_LIVE_LLM:
            raise ValueError("Live LLM use is forbidden in test mode")
        if self.DATABASE_URL.startswith("sqlite:///./"):
            object.__setattr__(self, "DATABASE_URL", "sqlite:///" + str(ROOT / self.DATABASE_URL[len("sqlite:///./"):]))
        for name in ("DOCS_ROOT", "LLM_USAGE_DB", "MVP_DEMO_CORPUS_PATH"):
            value = Path(getattr(self, name))
            if not value.is_absolute():
                object.__setattr__(self, name, ROOT / value)
        return self


_active_settings: ContextVar[Config | None] = ContextVar("active_settings", default=None)


@lru_cache
def _environment_settings() -> Config:
    return Config()


def get_settings() -> Config:
    return _active_settings.get() or _environment_settings()


@contextmanager
def settings_context(settings: Config):
    token = _active_settings.set(settings)
    try:
        yield
    finally:
        _active_settings.reset(token)


class _LazyConfig:
    """Compatibility for existing pipelines without import-time settings loading."""
    def __getattr__(self, name):
        return getattr(get_settings(), name)


config = _LazyConfig()
