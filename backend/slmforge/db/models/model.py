"""Model registry database models."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import JSON, BigInteger, Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from slmforge.db.base import Base


class ModelRegistry(Base):
    """A registered model (logical entry; versions hold actual checkpoints)."""

    __tablename__ = "models"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="huggingface")
    architecture: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, default="code")
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, default="causal_lm")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    versions: Mapped[list["ModelVersion"]] = relationship(
        "ModelVersion", back_populates="model", cascade="all, delete-orphan"
    )


class ModelVersion(Base):
    """A specific version/checkpoint of a registered model."""

    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_id", "revision", "quantization", name="uq_model_version"),
    )

    model_id: Mapped[str] = mapped_column(ForeignKey("models.id"), nullable=False, index=True)
    revision: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    quantization: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 4bit, 8bit, null
    local_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    artifact_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hf_model_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g. "Qwen/Qwen2.5-0.5B"
    parameter_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    parameter_count_str: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_downloaded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_base_model: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    base_model_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("model_versions.id"), nullable=True
    )
    adapter_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # lora, qlora
    adapter_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    adapter_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    adapter_trainable_params: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    tokenizer_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hardware_info: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    software_versions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    model: Mapped["ModelRegistry"] = relationship("ModelRegistry", back_populates="versions")
    base_model_version: Mapped[Optional["ModelVersion"]] = relationship(
        "ModelVersion", remote_side="ModelVersion.id"
    )
