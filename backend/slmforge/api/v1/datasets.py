"""Datasets API endpoints."""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session, joinedload

from slmforge.core.exceptions import NotFoundError
from slmforge.core.logging import get_logger
from slmforge.core.security import validate_file_size, validate_upload_filename
from slmforge.db.models.dataset import Dataset, DatasetQualityReport, DatasetSample, DatasetVersion
from slmforge.db.session import get_db
from slmforge.schemas.dataset import (
    DatasetOut,
    DatasetQualityReportOut,
    DatasetSampleOut,
    DatasetStatsOut,
    DatasetVersionOut,
    IngestRequest,
    IngestResult,
)
from slmforge.services.data.ingestion import DatasetIngestionService

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=List[DatasetOut])
def list_datasets(db: Session = Depends(get_db)):
    datasets = db.query(Dataset).options(joinedload(Dataset.versions)).order_by(
        Dataset.created_at.desc()
    ).all()
    return datasets


@router.post("/ingest", response_model=IngestResult)
async def ingest_dataset(request: IngestRequest, db: Session = Depends(get_db)):
    svc = DatasetIngestionService(db)
    try:
        ds, dsv, qr, stats = svc.ingest(
            name=request.name,
            source_path=request.source_path,
            file_format=None,
            hf_dataset_id=request.hf_dataset_id,
            hf_dataset_config=request.hf_dataset_config,
            hf_dataset_split=request.hf_dataset_split,
            domain=request.domain,
            task=request.task,
            description=request.description,
            is_demo=request.is_demo,
            train_ratio=request.train_ratio,
            val_ratio=request.val_ratio,
            test_ratio=request.test_ratio,
            deduplicate=request.deduplicate,
            detect_leakage=request.detect_leakage,
            seed=request.seed,
        )
        return IngestResult(
            dataset_id=ds.id, version_id=dsv.id, version=dsv.version,
            content_hash=dsv.content_hash, raw_count=stats["raw_count"],
            clean_count=stats["clean_count"], duplicates_removed=stats["duplicates_removed"],
            invalid_removed=stats["invalid_removed"],
            final_train_count=stats["train_count"], final_val_count=stats["val_count"],
            final_test_count=stats["test_count"], quality_report_id=qr.id,
            status="completed", stats=stats,
        )
    except Exception as exc:
        logger.error("dataset.ingest.api_failed", error=str(exc))
        raise


@router.post("/upload", response_model=IngestResult)
async def upload_dataset(
    name: str,
    file: UploadFile = File(...),
    domain: str = "code_security",
    task: str = "vulnerability_classification",
    is_demo: bool = False,
    seed: int = 42,
    db: Session = Depends(get_db),
):
    filename = validate_upload_filename(file.filename or "upload.json")
    content = await file.read()
    validate_file_size(len(content))

    import io
    svc = DatasetIngestionService(db)
    try:
        ds, dsv, qr, stats = svc.ingest(
            name=name,
            uploaded_file=io.BytesIO(content),
            uploaded_filename=filename,
            domain=domain, task=task, is_demo=is_demo, seed=seed,
        )
        return IngestResult(
            dataset_id=ds.id, version_id=dsv.id, version=dsv.version,
            content_hash=dsv.content_hash, raw_count=stats["raw_count"],
            clean_count=stats["clean_count"], duplicates_removed=stats["duplicates_removed"],
            invalid_removed=stats["invalid_removed"],
            final_train_count=stats["train_count"], final_val_count=stats["val_count"],
            final_test_count=stats["test_count"], quality_report_id=qr.id,
            status="completed", stats=stats,
        )
    except Exception as exc:
        logger.error("dataset.upload.api_failed", error=str(exc))
        raise


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: str, db: Session = Depends(get_db)):
    ds = db.query(Dataset).options(joinedload(Dataset.versions)).get(dataset_id)
    if not ds:
        raise HTTPException(404, f"Dataset {dataset_id} not found")
    return ds


@router.get("/{dataset_id}/quality", response_model=List[DatasetQualityReportOut])
def get_dataset_quality(dataset_id: str, db: Session = Depends(get_db)):
    reports = db.query(DatasetQualityReport).filter(
        DatasetQualityReport.dataset_id == dataset_id
    ).order_by(DatasetQualityReport.created_at.desc()).all()
    return reports


@router.get("/{dataset_id}/statistics")
def get_dataset_statistics(dataset_id: str, version_id: Optional[str] = None,
                           db: Session = Depends(get_db)):
    if version_id:
        dsv = db.get(DatasetVersion, version_id)
    else:
        dsv = db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id
        ).order_by(DatasetVersion.created_at.desc()).first()
    if not dsv:
        raise HTTPException(404, "No dataset version found")
    qr = db.query(DatasetQualityReport).filter(
        DatasetQualityReport.version_id == dsv.id
    ).first()
    return DatasetStatsOut(
        dataset_id=dataset_id, version_id=dsv.id,
        total_samples=dsv.sample_count,
        split_counts={"train": dsv.train_count, "val": dsv.val_count, "test": dsv.test_count},
        label_distribution=qr.label_distribution if qr else {},
        category_distribution=qr.category_distribution if qr else {},
        severity_distribution=qr.severity_distribution if qr else {},
        avg_length=qr.length_stats.get("mean", 0) if qr else 0,
        median_length=qr.length_stats.get("median", 0) if qr else 0,
        quality_metrics=qr.to_dict() if qr else {},
    )


@router.get("/{dataset_id}/samples", response_model=List[DatasetSampleOut])
def list_samples(
    dataset_id: str,
    version_id: Optional[str] = None,
    split: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(DatasetSample).filter(DatasetSample.dataset_id == dataset_id)
    if version_id:
        q = q.filter(DatasetSample.version_id == version_id)
    if split:
        q = q.filter(DatasetSample.split == split)
    return q.order_by(DatasetSample.sample_index).offset(offset).limit(limit).all()
