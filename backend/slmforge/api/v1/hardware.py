"""Hardware detection endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from slmforge.schemas.common import HardwareInfo
from slmforge.utils.hardware import detect_hardware, estimate_model_feasibility

router = APIRouter()


@router.get("", response_model=HardwareInfo)
def get_hardware():
    return detect_hardware()


@router.get("/feasibility")
def check_feasibility(parameter_count_str: str = "0.5B", quantization: str | None = None):
    return estimate_model_feasibility(parameter_count_str, quantization)
