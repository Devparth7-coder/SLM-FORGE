"""Model registry API endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from slmforge.db.models.model import ModelRegistry, ModelVersion
from slmforge.db.session import get_db
from slmforge.schemas.model import ModelCreate, ModelOut, ModelVersionOut
from slmforge.services.model.registry import ModelRegistryService

router = APIRouter()


@router.get("", response_model=List[ModelOut])
def list_models(db: Session = Depends(get_db)):
    return db.query(ModelRegistry).options(joinedload(ModelRegistry.versions)).order_by(
        ModelRegistry.created_at.desc()
    ).all()


@router.post("", response_model=ModelOut)
def register_model(request: ModelCreate, db: Session = Depends(get_db)):
    svc = ModelRegistryService(db)
    model, version = svc.register_model(
        name=request.name,
        hf_model_id=request.hf_model_id,
        revision=request.revision,
        quantization=request.quantization,
        provider=request.provider,
        architecture=request.architecture,
        domain=request.domain,
        task_type=request.task_type,
        description=request.description,
        license=request.license,
        tags=request.tags,
    )
    db.refresh(model)
    return model


@router.get("/{model_id}", response_model=ModelOut)
def get_model(model_id: str, db: Session = Depends(get_db)):
    m = db.query(ModelRegistry).options(joinedload(ModelRegistry.versions)).get(model_id)
    if not m:
        raise HTTPException(404, f"Model {model_id} not found")
    return m


@router.get("/{model_id}/versions", response_model=List[ModelVersionOut])
def list_model_versions(model_id: str, db: Session = Depends(get_db)):
    versions = db.query(ModelVersion).filter(
        ModelVersion.model_id == model_id
    ).order_by(ModelVersion.created_at.desc()).all()
    return versions
