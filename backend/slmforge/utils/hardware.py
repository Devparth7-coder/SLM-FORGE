"""Hardware detection and model feasibility estimation."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import psutil

from slmforge.core.config import settings
from slmforge.schemas.common import HardwareInfo


def detect_hardware() -> HardwareInfo:
    """Detect available CPU, RAM, GPU, VRAM, CUDA."""
    info: Dict[str, Any] = {
        "cpu_count_logical": os.cpu_count() or 1,
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "total_ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "available_ram_gb": round(psutil.virtual_memory().available / (1024 ** 3), 2),
        "gpu_available": False,
        "warnings": [],
    }

    try:
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if info["cuda_available"] and not settings.force_cpu:
            info["gpu_available"] = True
            info["gpu_count"] = torch.cuda.device_count()
            info["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["vram_total_mb"] = round(props.total_memory / (1024 ** 2), 2)
            info["cuda_version"] = torch.version.cuda
        else:
            info["gpu_count"] = 0
            info["cuda_available"] = False
            if settings.force_cpu:
                info["warnings"].append("FORCE_CPU is set; GPU usage disabled.")
            if not info.get("cuda_available", False) and not settings.force_cpu:
                info["warnings"].append("CUDA not available; running on CPU.")
    except ImportError:
        info["torch_version"] = None
        info["cuda_available"] = False
        info["gpu_count"] = 0
        info["warnings"].append("PyTorch not installed; cannot detect GPU.")

    if info["total_ram_gb"] < 8:
        info["warnings"].append(
            f"Low system RAM ({info['total_ram_gb']} GB). Large model training may fail."
        )

    return HardwareInfo(**info)


# ── Feasibility heuristics ────────────────────────────────────────────────
# Rough VRAM estimates for common model sizes (in GB, 4-bit QLoRA inference)
_VRAM_FOOTPRINT_GB = {
    "0.5B": {"4bit": 1.2, "8bit": 2.0, "full": 4.0},
    "1.5B": {"4bit": 2.5, "8bit": 4.5, "full": 8.0},
    "3B":   {"4bit": 4.0, "8bit": 7.0, "full": 14.0},
    "7B":   {"4bit": 6.0, "8bit": 10.0, "full": 28.0},
    "8B":   {"4bit": 7.0, "8bit": 12.0, "full": 32.0},
    "14B":  {"4bit": 10.0, "8bit": 18.0, "full": 56.0},
}


def estimate_model_feasibility(
    parameter_count_str: str,
    quantization: Optional[str] = None,
) -> Dict[str, Any]:
    """Estimate whether a model/quantization combo fits on the current hardware.

    Returns a dict with keys: feasible, warnings, vram_required_gb, vram_available_gb.
    These are HEURISTIC estimates, not guarantees.
    """
    hw = detect_hardware()
    warnings: List[str] = []
    quant_key = {"4bit": "4bit", "8bit": "8bit"}.get(quantization or "", "full")

    size_key = parameter_count_str
    if size_key not in _VRAM_FOOTPRINT_GB:
        warnings.append(
            f"No heuristic for model size '{size_key}'; feasibility unknown."
        )
        return {
            "feasible": None,
            "warnings": warnings,
            "vram_required_gb": None,
            "vram_available_gb": hw.vram_total_mb and hw.vram_total_mb / 1024,
        }

    required = _VRAM_FOOTPRINT_GB[size_key][quant_key]
    available = (hw.vram_total_mb or 0) / 1024 if hw.gpu_available else 0

    if hw.gpu_available and available >= required * 1.2:  # 20% headroom
        feasible = True
    elif not hw.gpu_available:
        feasible = False
        warnings.append("No GPU available; training will be extremely slow on CPU.")
    elif available >= required:
        feasible = True
        warnings.append("GPU memory is tight; consider smaller batch size or more aggressive quantization.")
    else:
        feasible = False
        warnings.append(
            f"Estimated VRAM need ({required} GB) exceeds available ({available:.1f} GB)."
        )

    return {
        "feasible": feasible,
        "warnings": warnings,
        "vram_required_gb": required,
        "vram_available_gb": available,
        "quantization": quant_key,
    }
