"""Experiment Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LoraConfig(BaseModel):
    r: int = Field(default=16, ge=1, le=256)
    alpha: int = Field(default=32, ge=1, le=512)
    dropout: float = Field(default=0.05, ge=0.0, le=0.9)
    target_modules: List[str] = ["q_proj", "v_proj"]
    bias: str = "none"
    task_type: str = "CAUSAL_LM"


class BitsAndBytesConfig(BaseModel):
    load_in_4bit: bool = True
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_use_double_quant: bool = True


class TrainingConfig(BaseModel):
    method: str = Field(default="qlora", pattern=r"^(lora|qlora|full)$")
    learning_rate: float = Field(default=2e-4, gt=0)
    epochs: float = Field(default=3.0, gt=0, le=100)
    batch_size: int = Field(default=2, ge=1, le=256)
    gradient_accumulation_steps: int = Field(default=8, ge=1, le=128)
    warmup_ratio: float = Field(default=0.03, ge=0.0, le=0.5)
    max_seq_length: int = Field(default=1024, ge=32, le=8192)
    weight_decay: float = Field(default=0.01, ge=0.0)
    scheduler: str = Field(default="cosine", pattern=r"^(cosine|linear|constant|cosine_with_restarts)$")
    mixed_precision: str = Field(default="bf16", pattern=r"^(bf16|fp16|no)$")
    gradient_checkpointing: bool = True
    seed: int = 42
    lora: LoraConfig = LoraConfig()
    bnb: Optional[BitsAndBytesConfig] = BitsAndBytesConfig()
    logging_steps: int = Field(default=10, ge=1)
    eval_steps: int = Field(default=100, ge=1)
    save_steps: int = Field(default=100, ge=1)
    early_stopping_patience: Optional[int] = None
    max_grad_norm: float = Field(default=1.0, gt=0)
    optim: str = "paged_adamw_8bit"


class EvaluationConfig(BaseModel):
    batch_size: int = Field(default=4, ge=1, le=64)
    max_new_tokens: int = Field(default=256, ge=16, le=2048)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    split: str = Field(default="test", pattern=r"^(test|val|train)$")
    max_samples: Optional[int] = Field(default=None, ge=1)
    compute_confusion_matrix: bool = True
    latency_measurement: bool = True
    robustness_tests: List[str] = []


class ExperimentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    dataset_version_id: str
    base_model_version_id: str
    training_config: TrainingConfig = TrainingConfig()
    evaluation_config: EvaluationConfig = EvaluationConfig()
    seed: int = 42
    run_baseline_only: bool = False
    tags: Dict[str, Any] = {}


class ExperimentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None


class TrainingRunOut(BaseModel):
    id: str
    experiment_id: str
    status: str
    method: str
    current_step: int
    total_steps: int
    current_epoch: float
    total_epochs: float
    train_loss: Optional[float] = None
    val_loss: Optional[float] = None
    learning_rate: Optional[float] = None
    gradient_norm: Optional[float] = None
    tokens_per_sec: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    best_val_loss: Optional[float] = None
    final_adapter_path: Optional[str] = None
    metrics_history: List[Dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvaluationRunOut(BaseModel):
    id: str
    experiment_id: str
    model_version_id: str
    dataset_version_id: str
    is_baseline: bool
    status: str
    split: str
    sample_count: int
    metrics_json: Dict[str, Any] = {}
    confusion_matrix: Dict[str, Any] = {}
    latency_stats_ms: Dict[str, Any] = {}
    error_distribution: Dict[str, Any] = {}
    predictions_path: Optional[str] = None
    failures_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RobustnessRunOut(BaseModel):
    id: str
    experiment_id: str
    model_version_id: str
    is_baseline: bool
    status: str
    perturbation_type: str
    perturbation_config: Dict[str, Any] = {}
    metrics_json: Dict[str, Any] = {}
    robustness_score: Optional[float] = None
    performance_degradation: Optional[float] = None
    sample_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExperimentOut(BaseModel):
    id: str
    name: str
    status: str
    description: Optional[str] = None
    dataset_version_id: Optional[str] = None
    base_model_version_id: Optional[str] = None
    fine_tuned_model_version_id: Optional[str] = None
    seed: int
    git_commit: Optional[str] = None
    training_config: Dict[str, Any] = {}
    evaluation_config: Dict[str, Any] = {}
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    wandb_run_url: Optional[str] = None
    tags: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    training_run: Optional[TrainingRunOut] = None
    evaluation_runs: List[EvaluationRunOut] = []
    robustness_runs: List[RobustnessRunOut] = []

    class Config:
        from_attributes = True
