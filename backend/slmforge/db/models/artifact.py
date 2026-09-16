"""Artifact and report storage models."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import JSON, BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from slmforge.db.base import Base


class Artifact(Base):
    """Any persisted artifact: adapter, checkpoint, predictions, configs, plots."""

    __tablename__ = "artifacts"

    experiment_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("experiments.id"), nullable=True, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class ReportEntry(Base):
    """Generated report (HTML/JSON/Markdown)."""

    __tablename__ = "reports"

    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(20), nullable=False)  # html, json, markdown
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
