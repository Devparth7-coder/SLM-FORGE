"""Artifact download/list endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from slmforge.db.models.artifact import Artifact
from slmforge.db.session import get_db
from slmforge.storage import get_storage_backend

router = APIRouter()


@router.get("")
def list_artifacts(experiment_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Artifact)
    if experiment_id:
        q = q.filter(Artifact.experiment_id == experiment_id)
    return q.order_by(Artifact.created_at.desc()).all()


@router.get("/{artifact_id}/download")
def download_artifact(artifact_id: str, db: Session = Depends(get_db)):
    a = db.get(Artifact, artifact_id)
    if not a:
        raise HTTPException(404, "Artifact not found")
    storage = get_storage_backend()
    data = storage.get_bytes(a.storage_path)
    return Response(
        content=data,
        media_type=a.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{a.name}"'},
    )
