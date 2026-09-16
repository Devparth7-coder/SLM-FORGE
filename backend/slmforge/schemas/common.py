"""Common Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthOut(BaseModel):
    status: str = "ok"
    app_name: str
    app_version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    database: str = "unknown"
    redis: Optional[str] = None
    gpu_available: bool = False
    gpu_info: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int


class HardwareInfo(BaseModel):
    cpu_count_logical: int
    cpu_count_physical: Optional[int] = None
    total_ram_gb: float
    available_ram_gb: float
    gpu_available: bool = False
    gpu_count: int = 0
    gpu_name: Optional[str] = None
    vram_total_mb: Optional[float] = None
    cuda_available: bool = False
    cuda_version: Optional[str] = None
    torch_version: Optional[str] = None
    warnings: List[str] = []
