"""Evaluations API endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from slmforge.db.models.experiment import EvaluationRun
from slmforge.db.models.result import MetricEntry, Prediction
from slmforge.db.session import get_db
from slmforge.schemas.experiment import EvaluationRunOut

router = APIRouter()


@router.get("", response_model=List[EvaluationRunOut])
def list_evaluations(
    experiment_id: Optional[str] = None,
    is_baseline: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(EvaluationRun)
    if experiment_id:
        q = q.filter(EvaluationRun.experiment_id == experiment_id)
    if is_baseline is not None:
        q = q.filter(EvaluationRun.is_baseline == is_baseline)
    return q.order_by(EvaluationRun.created_at.desc()).all()


@router.get("/{eval_id}", response_model=EvaluationRunOut)
def get_evaluation(eval_id: str, db: Session = Depends(get_db)):
    ev = db.get(EvaluationRun, eval_id)
    if not ev:
        raise HTTPException(404, "Evaluation run not found")
    return ev


@router.get("/{eval_id}/metrics")
def get_eval_metrics(eval_id: str, db: Session = Depends(get_db)):
    ev = db.get(EvaluationRun, eval_id)
    if not ev:
        raise HTTPException(404, "Evaluation run not found")
    return ev.metrics_json


@router.get("/{eval_id}/predictions")
def get_predictions(
    eval_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    correct: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Prediction).filter(Prediction.evaluation_run_id == eval_id)
    if correct is not None:
        q = q.filter(Prediction.is_correct == correct)
    preds = q.order_by(Prediction.created_at.desc()).offset(offset).limit(limit).all()
    return preds
