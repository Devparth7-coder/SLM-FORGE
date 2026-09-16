"""Content hashing utilities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def compute_hash(data: bytes) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def compute_file_hash(filepath: Path, chunk_size: int = 65536) -> str:
    """Stream SHA-256 of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_json_hash(obj: Any) -> str:
    """Stable hash of a JSON-serializable object (canonical serialization)."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return compute_hash(canonical.encode("utf-8"))


def compute_dataset_hash(samples: Iterable[dict]) -> str:
    """Content hash for a collection of samples (order-independent)."""
    h = hashlib.sha256()
    hashes = sorted(compute_json_hash(s) for s in samples)
    for sh in hashes:
        h.update(sh.encode("utf-8"))
    return h.hexdigest()
