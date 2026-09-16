"""Model registry Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModelVersionCreate(BaseModel):
    hf_model_id: Optional[str] = None
    revision: str = "main"
    quantization: Optional[str] = Field(None, pattern=r"^(4bit|8bit|None)?$")
    local_path: Optional[str] = None
    is_base_model: bool = True
    base_model_version_id: Optional[str] = None
    adapter_type: Optional[str] = Field(None, pattern=r"^(lora|qlora)?$")
    adapter_path: Optional[str] = None


class ModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = "huggingface"
    hf_model_id: Optional[str] = None
    revision: str = "main"
    quantization: Optional[str] = None
    architecture: Optional[str] = None
    domain: str = "code"
    task_type: str = "causal_lm"
    description: Optional[str] = None
    license: Optional[str] = None
    tags: Dict[str, Any] = {}


class ModelVersionOut(BaseModel):
    id: str
    model_id: str
    revision: str
    quantization: Optional[str] = None
    local_path: Optional[str] = None
    artifact_uri: Optional[str] = None
    hf_model_id: Optional[str] = None
    parameter_count: Optional[int] = None
    parameter_count_str: Optional[str] = None
    is_local: bool = False
    is_downloaded: bool = False
    is_base_model: bool = True
    base_model_version_id: Optional[str] = None
    adapter_type: Optional[str] = None
    adapter_size_bytes: Optional[int] = None
    adapter_trainable_params: Optional[int] = None
    hardware_info: Dict[str, Any] = {}
    software_versions: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class ModelOut(BaseModel):
    id: str
    name: str
    provider: str
    architecture: Optional[str] = None
    domain: str
    task_type: str
    description: Optional[str] = None
    license: Optional[str] = None
    tags: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    versions: List[ModelVersionOut] = []

    class Config:
        from_attributes = True
