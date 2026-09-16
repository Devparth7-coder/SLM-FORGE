"""Artifact Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ArtifactOut(BaseModel):
    id: str
    experiment_id: Optional[str] = None
    artifact_type: str
    name: str
    storage_backend: str
    storage_path: str
    size_bytes: Optional[int] = None
    content_hash: Optional[str] = None
    mime_type: Optional[str] = None
    metadata: Dict[str, Any] = {}
    version: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
