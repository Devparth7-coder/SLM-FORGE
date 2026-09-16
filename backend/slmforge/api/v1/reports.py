"""Report generation API endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from slmforge.db.models.artifact import ReportEntry
from slmforge.db.session import get_db
from slmforge.schemas.report import ReportGenerateRequest, ReportOut
from slmforge.services.reports.generator import ReportService

router = APIRouter()


@router.get("", response_model=List[ReportOut])
def list_reports(experiment_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(ReportEntry)
    if experiment_id:
        q = q.filter(ReportEntry.experiment_id == experiment_id)
    return q.order_by(ReportEntry.created_at.desc()).all()


@router.post("/generate", response_model=List[ReportOut])
def generate_reports(request: ReportGenerateRequest, db: Session = Depends(get_db)):
    svc = ReportService(db)
    return svc.generate_all(request.experiment_id, formats=request.formats)


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: str, db: Session = Depends(get_db)):
    r = db.get(ReportEntry, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    return r
