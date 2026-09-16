"""Dataset Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source: Optional[str] = None
    source_uri: Optional[str] = None
    domain: str = "code_security"
    task: str = "vulnerability_classification"
    license: Optional[str] = None
    is_demo: bool = False
    tags: Dict[str, Any] = {}


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None


class DatasetVersionCreate(BaseModel):
    version: str = Field(..., pattern=r"^v\d+\.\d+\.\d+.*$")
    description: Optional[str] = None


class DatasetVersionOut(BaseModel):
    id: str
    dataset_id: str
    version: str
    content_hash: str
    sample_count: int
    train_count: int
    val_count: int
    test_count: int
    raw_count: int
    duplicates_removed: int
    invalid_removed: int
    manifest_path: Optional[str] = None
    stats: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetSampleOut(BaseModel):
    id: str
    version_id: str
    sample_index: int
    split: str
    sample_id: str
    input_text: str
    label: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    evidence: Optional[str] = None
    is_synthetic: bool = False
    quality_score: Optional[float] = None
    content_hash: str
    metadata: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class DatasetQualityReportOut(BaseModel):
    id: str
    dataset_id: str
    version_id: str
    total_samples: int
    missing_fields_count: int
    invalid_labels_count: int
    duplicate_count: int
    near_duplicate_count: int
    duplicate_rate: float
    near_duplicate_rate: float
    short_samples_count: int
    long_samples_count: int
    malformed_code_count: int
    train_test_overlap: int
    potential_leakage: bool
    label_distribution: Dict[str, Any] = {}
    category_distribution: Dict[str, Any] = {}
    severity_distribution: Dict[str, Any] = {}
    length_stats: Dict[str, Any] = {}
    issues: List[Dict[str, Any]] = []
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    source: Optional[str] = None
    source_uri: Optional[str] = None
    domain: str
    task: str
    license: Optional[str] = None
    is_demo: bool
    pipeline_version: Optional[str] = None
    tags: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    versions: List[DatasetVersionOut] = []

    class Config:
        from_attributes = True


class DatasetStatsOut(BaseModel):
    dataset_id: str
    version_id: str
    total_samples: int
    split_counts: Dict[str, int]
    label_distribution: Dict[str, Any]
    category_distribution: Dict[str, Any]
    severity_distribution: Dict[str, Any]
    avg_length: float
    median_length: float
    quality_metrics: Dict[str, Any]


class IngestRequest(BaseModel):
    name: str = Field(..., min_length=1)
    source_path: Optional[str] = None
    file_format: Optional[str] = None  # json, jsonl, csv, parquet, hf
    hf_dataset_id: Optional[str] = None
    hf_dataset_config: Optional[str] = None
    hf_dataset_split: Optional[str] = None
    domain: str = "code_security"
    task: str = "vulnerability_classification"
    description: Optional[str] = None
    is_demo: bool = False
    train_ratio: float = Field(default=0.8, ge=0.5, le=0.95)
    val_ratio: float = Field(default=0.1, ge=0.05, le=0.3)
    test_ratio: float = Field(default=0.1, ge=0.05, le=0.3)
    deduplicate: bool = True
    detect_leakage: bool = True
    seed: int = 42


class IngestResult(BaseModel):
    dataset_id: str
    version_id: str
    version: str
    content_hash: str
    raw_count: int
    clean_count: int
    duplicates_removed: int
    invalid_removed: int
    final_train_count: int
    final_val_count: int
    final_test_count: int
    quality_report_id: str
    status: str
    warnings: List[str] = []
    stats: Dict[str, Any] = {}
