"""Prediction, failure, and metric result models."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from slmforge.db.base import Base


class Prediction(Base):
    """A single model prediction for a dataset sample."""

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id", "sample_id", name="uq_prediction_sample"
        ),
    )

    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id"), nullable=False, index=True
    )
    sample_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ground_truth_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ground_truth_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ground_truth_severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    predicted_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    predicted_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    predicted_severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    predicted_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_output: Mapped[Dict[str, Any]] = mapped_column("parsed_output_json", JSON, default=dict, nullable=False)
    is_json_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_schema_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    severity_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    robustness_perturbation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class FailureEntry(Base):
    """Categorised failure entry for a single sample."""

    __tablename__ = "failures"

    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id"), nullable=False, index=True
    )
    sample_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    failure_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ground_truth: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    base_prediction: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)
    finetuned_prediction: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    robustness_test: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MetricEntry(Base):
    """A single named metric value (for flexible metric storage)."""

    __tablename__ = "metrics"

    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id"), nullable=False, index=True
    )
    training_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("training_runs.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_type: Mapped[str] = mapped_column(String(30), nullable=False, default="evaluation")
    step: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
