"""Centralized configuration management for SLM-Forge.

All settings are read from environment variables with sensible defaults for local development.
No secrets are hard-coded.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    app_name: str = "SLM-FORGE"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    api_prefix: str = "/api/v1"
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    allowed_origins: str = Field(default="*", alias="ALLOWED_ORIGINS")

    # ── Database ───────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+psycopg2://slmforge:slmforge@localhost:5432/slmforge",
        alias="DATABASE_URL",
    )
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, alias="DATABASE_MAX_OVERFLOW")

    # ── Redis (optional for async jobs) ───────────────────────────────────
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    # ── Storage ────────────────────────────────────────────────────────────
    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")
    storage_local_root: Path = Field(
        default=Path("./data/artifacts"), alias="STORAGE_LOCAL_ROOT"
    )
    storage_s3_bucket: Optional[str] = Field(default=None, alias="STORAGE_S3_BUCKET")
    storage_s3_region: Optional[str] = Field(default=None, alias="STORAGE_S3_REGION")
    storage_s3_access_key: Optional[str] = Field(default=None, alias="STORAGE_S3_ACCESS_KEY")
    storage_s3_secret_key: Optional[str] = Field(default=None, alias="STORAGE_S3_SECRET_KEY")
    storage_s3_endpoint_url: Optional[str] = Field(
        default=None, alias="STORAGE_S3_ENDPOINT_URL"
    )

    # ── Model defaults ─────────────────────────────────────────────────────
    model_name: str = Field(default="Qwen/Qwen2.5-0.5B-Instruct", alias="MODEL_NAME")
    model_revision: str = Field(default="main", alias="MODEL_REVISION")
    model_cache_dir: Path = Field(default=Path("./data/cache/models"), alias="MODEL_CACHE_DIR")

    # ── Hugging Face ───────────────────────────────────────────────────────
    hf_token: Optional[str] = Field(default=None, alias="HF_TOKEN")
    hf_endpoint: Optional[str] = Field(default=None, alias="HF_ENDPOINT")

    # ── Weights & Biases ───────────────────────────────────────────────────
    wandb_enabled: bool = Field(default=False, alias="WANDB_ENABLED")
    wandb_project: str = Field(default="slm-forge", alias="WANDB_PROJECT")
    wandb_entity: Optional[str] = Field(default=None, alias="WANDB_ENTITY")
    wandb_api_key: Optional[str] = Field(default=None, alias="WANDB_API_KEY")

    # ── Data paths ─────────────────────────────────────────────────────────
    data_root: Path = Field(default=Path("./data"), alias="DATA_ROOT")
    datasets_dir: Path = Field(default=Path("./data/datasets"), alias="DATASETS_DIR")
    artifacts_dir: Path = Field(default=Path("./data/artifacts"), alias="ARTIFACTS_DIR")
    reports_dir: Path = Field(default=Path("./data/reports"), alias="REPORTS_DIR")

    # ── Security ───────────────────────────────────────────────────────────
    max_upload_size_mb: int = Field(default=100, alias="MAX_UPLOAD_SIZE_MB")
    allowed_upload_extensions: List[str] = Field(
        default=[".json", ".jsonl", ".csv", ".parquet", ".py", ".zip"],
        alias="ALLOWED_UPLOAD_EXTENSIONS",
    )
    cors_allow_credentials: bool = True

    # ── Authentication (JWT) ───────────────────────────────────────────────
    access_token_expire_minutes: int = Field(
        default=60 * 24 * 7, alias="ACCESS_TOKEN_EXPIRE_MINUTES"  # 7 days
    )
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")

    # ── Hardware detection ─────────────────────────────────────────────────
    force_cpu: bool = Field(default=False, alias="FORCE_CPU")
    torch_num_threads: int = Field(default=4, alias="TORCH_NUM_THREADS")

    # ── Logging ────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    # ── Worker ─────────────────────────────────────────────────────────────
    worker_concurrency: int = Field(default=1, alias="WORKER_CONCURRENCY")

    @field_validator("storage_local_root", "model_cache_dir", "data_root", "datasets_dir",
                     "artifacts_dir", "reports_dir", mode="before")
    @classmethod
    def ensure_path(cls, v: Any) -> Path:
        p = Path(str(v))
        p.mkdir(parents=True, exist_ok=True)
        return p

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> str:
        if isinstance(v, str):
            return v
        return ",".join(v) if isinstance(v, list) else "*"

    @property
    def allowed_origins_list(self) -> List[str]:
        if self.allowed_origins == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def database_url_sync(self) -> str:
        """Return a synchronous database URL (alembic/init uses sync)."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


settings = Settings()
