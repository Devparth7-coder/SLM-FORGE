"""Failure analysis API endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from slmforge.db.models.result import FailureEntry
from slmforge.db.session import get_db

router = APIRouter()


@router.get("")
def list_failures(
    evaluation_run_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
    failure_type: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    from slmforge.db.models.experiment import EvaluationRun
    q = db.query(FailureEntry)
    if evaluation_run_id:
        q = q.filter(FailureEntry.evaluation_run_id == evaluation_run_id)
    if experiment_id:
        eval_ids = [e.id for e in db.query(EvaluationRun).filter(
            EvaluationRun.experiment_id == experiment_id).all()]
        q = q.filter(FailureEntry.evaluation_run_id.in_(eval_ids))
    if failure_type:
        q = q.filter(FailureEntry.failure_type == failure_type)
    if category:
        q = q.filter(FailureEntry.category == category)
    if severity:
        q = q.filter(FailureEntry.severity == severity)
    return q.order_by(FailureEntry.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{failure_id}")
def get_failure(failure_id: str, db: Session = Depends(get_db)):
    f = db.get(FailureEntry, failure_id)
    if not f:
        raise HTTPException(404, "Failure entry not found")
    return f
