"""Report Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ReportGenerateRequest(BaseModel):
    experiment_id: str
    formats: list[str] = ["json", "markdown", "html"]
    include_plots: bool = True


class ReportOut(BaseModel):
    id: str
    experiment_id: str
    report_type: str
    title: str
    storage_path: str
    size_bytes: Optional[int] = None
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True
