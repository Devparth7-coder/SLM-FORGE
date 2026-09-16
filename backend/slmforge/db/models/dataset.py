"""Dataset-related database models."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from slmforge.db.base import Base


class Dataset(Base):
    """A registered dataset (logical collection; versions hold actual data)."""

    __tablename__ = "datasets"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, default="code_security")
    task: Mapped[str] = mapped_column(String(100), nullable=False, default="vulnerability_classification")
    license: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pipeline_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tags: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    versions: Mapped[list["DatasetVersion"]] = relationship(
        "DatasetVersion", back_populates="dataset", cascade="all, delete-orphan"
    )
    samples: Mapped[list["DatasetSample"]] = relationship(
        "DatasetSample", back_populates="dataset", cascade="all, delete-orphan"
    )
    quality_reports: Mapped[list["DatasetQualityReport"]] = relationship(
        "DatasetQualityReport", back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetVersion(Base):
    """A specific versioned snapshot of a dataset."""

    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version", name="uq_dataset_version"),)

    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "v1.0.0"
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    train_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    val_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    test_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    manifest_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    split_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    stats: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="versions")
    samples: Mapped[list["DatasetSample"]] = relationship("DatasetSample", back_populates="version")
    quality_reports: Mapped[list["DatasetQualityReport"]] = relationship(
        "DatasetQualityReport", back_populates="version"
    )


class DatasetSample(Base):
    """An individual sample within a dataset version."""

    __tablename__ = "dataset_samples"
    __table_args__ = (UniqueConstraint("version_id", "sample_index", name="uq_sample_index"),)

    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), nullable=False, index=True)
    sample_index: Mapped[int] = mapped_column(Integer, nullable=False)
    split: Mapped[str] = mapped_column(String(20), nullable=False, default="train")  # train/val/test
    sample_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)  # external id
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. "vulnerable"/"safe"
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    synthetic_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="samples")
    version: Mapped["DatasetVersion"] = relationship("DatasetVersion", back_populates="samples")


class DatasetQualityReport(Base):
    """Quality metrics for a dataset version."""

    __tablename__ = "dataset_quality_reports"

    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), nullable=False, index=True)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_fields_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_labels_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    near_duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    near_duplicate_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    short_samples_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    long_samples_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    malformed_code_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    train_test_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    potential_leakage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    label_distribution: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    category_distribution: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    severity_distribution: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    length_stats: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    issues: Mapped[list[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="quality_reports")
    version: Mapped["DatasetVersion"] = relationship("DatasetVersion", back_populates="quality_reports")
