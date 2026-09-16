"""Deterministic seeding for reproducible experiments."""

from __future__ import annotations

import os
import random
from typing import Optional


def set_seed(seed: int = 42, deterministic: bool = True) -> None:
    """Set RNG seeds for Python, NumPy, PyTorch.

    If deterministic=True, also configure CUDA to use deterministic algorithms
    where supported (may reduce performance).
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass

    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        if deterministic:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
            try:
                torch.use_deterministic_algorithms(True, warn_only=True)
            except Exception:
                pass
    except ImportError:
        pass
