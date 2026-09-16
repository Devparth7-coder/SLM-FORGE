"""Environment / package version utilities for reproducibility."""

from __future__ import annotations

import importlib
import platform
import sys
from typing import Any, Dict, Optional

RELEVANT_PACKAGES = [
    "torch", "transformers", "datasets", "accelerate", "peft", "trl",
    "bitsandbytes", "scikit-learn", "numpy", "pandas", "evaluate",
    "sentencepiece", "protobuf", "wandb",
]


def get_python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_package_versions(packages: Optional[list[str]] = None) -> Dict[str, str]:
    """Return installed versions for relevant packages."""
    versions: Dict[str, str] = {}
    for name in (packages or RELEVANT_PACKAGES):
        try:
            mod = importlib.import_module(name)
            versions[name] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[name] = "not-installed"
    return versions


def get_cuda_info() -> Dict[str, Any]:
    """Return CUDA/PyTorch GPU info."""
    info: Dict[str, Any] = {"cuda_available": False}
    try:
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if info["cuda_available"]:
            info["cuda_version"] = torch.version.cuda
            info["cuDNN_version"] = torch.backends.cudnn.version()
            info["device_count"] = torch.cuda.device_count()
            info["devices"] = []
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                info["devices"].append({
                    "index": i,
                    "name": props.name,
                    "total_memory_mb": round(props.total_memory / (1024 ** 2), 2),
                    "compute_capability": f"{props.major}.{props.minor}",
                })
    except ImportError:
        pass
    return info


def get_platform_info() -> Dict[str, str]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": get_python_version(),
        "python_implementation": platform.python_implementation(),
    }
