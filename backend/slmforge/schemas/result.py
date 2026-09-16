"""Prediction, failure, comparison Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PredictionOut(BaseModel):
    id: str
    evaluation_run_id: str
    sample_id: str
    ground_truth_label: Optional[str] = None
    ground_truth_category: Optional[str] = None
    ground_truth_severity: Optional[str] = None
    predicted_label: Optional[str] = None
    predicted_category: Optional[str] = None
    predicted_severity: Optional[str] = None
    predicted_evidence: Optional[str] = None
    is_json_valid: bool
    is_schema_valid: bool
    is_correct: bool
    category_correct: Optional[bool] = None
    severity_correct: Optional[bool] = None
    latency_ms: float
    confidence: Optional[float] = None
    error_type: Optional[str] = None
    robustness_perturbation: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FailureOut(BaseModel):
    id: str
    evaluation_run_id: str
    sample_id: str
    failure_type: str
    input_preview: Optional[str] = None
    ground_truth: Dict[str, Any] = {}
    base_prediction: Optional[Dict[str, Any]] = None
    finetuned_prediction: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    latency_ms: float
    confidence: Optional[float] = None
    robustness_test: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MetricOut(BaseModel):
    id: str
    name: str
    value: float
    metric_type: str
    step: Optional[int] = None
    category: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class ComparisonMetricOut(BaseModel):
    name: str
    base_value: Optional[float] = None
    finetuned_value: Optional[float] = None
    delta: Optional[float] = None
    higher_is_better: bool = True
    unit: Optional[str] = None
    note: Optional[str] = None


class ComparisonOut(BaseModel):
    experiment_id: str
    metrics: List[ComparisonMetricOut]
    base_eval_run_id: Optional[str] = None
    finetuned_eval_run_id: Optional[str] = None
    baseline_completed: bool = False
    finetuned_completed: bool = False
    notes: List[str] = []
