from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Package directory is `tax_calculator_demo/` at the book repository root.
_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parent
_DEFAULT_TRACE_DB = _PACKAGE_DIR / "data" / "traces.sqlite"
_DEFAULT_RAG_ROOT = _REPO_ROOT / "rag_federal_individual"


class Settings(BaseSettings):
    """Runtime configuration: env vars and `.env` files (later paths override earlier)."""

    model_config = SettingsConfigDict(
        env_file=(
            _REPO_ROOT / "code" / ".env",
            _PACKAGE_DIR / ".env",
            Path.cwd() / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Empty is allowed so `list-runs` / `show` work without a key; `run` validates before calling OpenAI.
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_CHAT_MODEL")
    openai_timeout_seconds: float = Field(default=120.0, ge=5.0, validation_alias="OPENAI_TIMEOUT_SECONDS")
    max_execution_steps: int = Field(default=12, ge=1, le=64, validation_alias="MAX_EXECUTION_STEPS")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    trace_db_path: Path = Field(default=_DEFAULT_TRACE_DB, validation_alias="TRACE_DB_PATH")

    # Corpus lives in `rag_federal_individual` (embeddings built by that folder's scripts).
    rag_root: Path = Field(default=_DEFAULT_RAG_ROOT, validation_alias="RAG_ROOT")
    rag_top_k: int = Field(default=5, ge=1, le=20, validation_alias="RAG_TOP_K")
    rag_embed_model: str = Field(default="text-embedding-3-small", validation_alias="RAG_EMBED_MODEL")
    rag_embed_dimensions: int = Field(default=512, validation_alias="RAG_EMBED_DIMENSIONS")

    def resolved_trace_db(self) -> Path:
        p = self.trace_db_path
        if not p.is_absolute():
            return (Path.cwd() / p).resolve()
        return p.resolve()

    def resolved_rag_root(self) -> Path:
        p = self.rag_root
        if not p.is_absolute():
            return (Path.cwd() / p).resolve()
        return p.resolve()
