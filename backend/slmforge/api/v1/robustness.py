"""Robustness results API endpoint."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from slmforge.db.models.experiment import RobustnessRun
from slmforge.db.session import get_db
from slmforge.schemas.experiment import RobustnessRunOut

router = APIRouter()


@router.get("", response_model=List[RobustnessRunOut])
def list_robustness_runs(experiment_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(RobustnessRun)
    if experiment_id:
        q = q.filter(RobustnessRun.experiment_id == experiment_id)
    return q.order_by(RobustnessRun.created_at.desc()).all()
