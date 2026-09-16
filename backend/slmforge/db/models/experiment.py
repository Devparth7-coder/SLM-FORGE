"""Experiment-related database models."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from slmforge.db.base import Base


class Experiment(Base):
    """Top-level experiment container: one dataset version, one training config, one eval config."""

    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dataset_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=True, index=True
    )
    base_model_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("model_versions.id"), nullable=True, index=True
    )
    fine_tuned_model_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("model_versions.id"), nullable=True
    )
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    git_commit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    training_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evaluation_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wandb_run_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    training_run: Mapped[Optional["TrainingRun"]] = relationship(
        "TrainingRun", back_populates="experiment", uselist=False, cascade="all, delete-orphan"
    )
    evaluation_runs: Mapped[list["EvaluationRun"]] = relationship(
        "EvaluationRun", back_populates="experiment", cascade="all, delete-orphan"
    )
    robustness_runs: Mapped[list["RobustnessRun"]] = relationship(
        "RobustnessRun", back_populates="experiment", cascade="all, delete-orphan"
    )


class TrainingRun(Base):
    """A single training job associated with an experiment."""

    __tablename__ = "training_runs"

    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="qlora")  # lora, qlora, full
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_epoch: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_epochs: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    train_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    val_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    learning_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gradient_norm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tokens_per_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gpu_memory_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    elapsed_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peak_vram_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peak_ram_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_val_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_adapter_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metrics_history: Mapped[list[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="training_run")


class EvaluationRun(Base):
    """An evaluation run: either base model or fine-tuned model evaluation."""

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id", "model_version_id", "is_baseline", name="uq_eval_run"
        ),
    )

    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id"), nullable=False, index=True
    )
    model_version_id: Mapped[str] = mapped_column(
        ForeignKey("model_versions.id"), nullable=False, index=True
    )
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=False, index=True
    )
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    split: Mapped[str] = mapped_column(String(20), nullable=False, default="test")
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confusion_matrix: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    latency_stats_ms: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_distribution: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    predictions_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failures_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="evaluation_runs")


class RobustnessRun(Base):
    """A robustness evaluation run with perturbations."""

    __tablename__ = "robustness_runs"

    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id"), nullable=False, index=True
    )
    model_version_id: Mapped[str] = mapped_column(
        ForeignKey("model_versions.id"), nullable=False, index=True
    )
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    perturbation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    perturbation_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metrics_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    robustness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    performance_degradation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="robustness_runs")
