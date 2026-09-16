"""Health check endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from slmforge.core.config import settings
from slmforge.db.session import get_db
from slmforge.schemas.common import HealthOut
from slmforge.utils.hardware import detect_hardware

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health_check(db: Session = Depends(get_db)) -> HealthOut:
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    hw = detect_hardware()
    return HealthOut(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
        database=db_status,
        gpu_available=hw.gpu_available,
        gpu_info={
            "name": hw.gpu_name,
            "vram_mb": hw.vram_total_mb,
            "cuda_version": hw.cuda_version,
        } if hw.gpu_available else None,
    )
