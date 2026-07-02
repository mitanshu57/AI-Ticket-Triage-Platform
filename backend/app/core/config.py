"""Application settings, loaded from environment / .env (ADR-0003)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "local"
    log_level: str = "INFO"
    api_port: int = 8000

    # Async SQLAlchemy URL (asyncpg driver). Overridden in tests with SQLite.
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/triage"

    # Comma-separated list of allowed CORS origins.
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- AI triage (Phase 2, ADR-0006) ---
    # If unset, the app falls back to a deterministic stub engine (also used in
    # tests) so the system runs end-to-end without an API key.
    anthropic_api_key: str | None = None
    # Tiered model selection: cheap/fast model for classification, strong model
    # for reply drafting.
    model_classify: str = "claude-haiku-4-5"
    model_draft: str = "claude-opus-4-8"

    # --- Async processing + realtime (Phase 3, ADR-0005/0008) ---
    # If set, triage is enqueued to the ARQ worker and realtime events use Redis
    # pub/sub (multi-process). If unset, triage runs inline and realtime uses an
    # in-process broker (single-process dev + the test suite).
    redis_url: str | None = None

    # --- RAG / retrieval (Phase 4, ADR-0004/0007) ---
    # Embeddings provider. "hash" is a deterministic, dependency-free fallback
    # (also used in tests); "voyage" uses Voyage AI (Anthropic's recommended
    # embeddings partner) when voyage_api_key is set.
    embedding_provider: str = "hash"
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-3"
    rag_top_k: int = 4
    # Below this top-result cosine score, the draft is flagged for human review.
    rag_min_score: float = 0.25

    # --- Observability (Phase 5, ADR-0008) ---
    metrics_enabled: bool = True
    worker_metrics_port: int = 9100
    # OpenTelemetry: traces/metrics export via the OTLP/HTTP collector.
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4318"
    otel_service_name: str = "triage-api"
    # Langfuse (LLM observability) — no-op unless both keys are set.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
