"""Storage backend factory."""

from __future__ import annotations

from functools import lru_cache

from slmforge.core.config import settings
from slmforge.storage.base import StorageBackend
from slmforge.storage.local import LocalStorageBackend


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend singleton.

    Currently supports: 'local' (default).
    Future: 's3' for S3-compatible storage.
    """
    backend_name = settings.storage_backend.lower()
    if backend_name == "local":
        return LocalStorageBackend()
    # Extend here for S3/GCS/etc.
    raise ValueError(f"Unsupported storage backend: {backend_name}")
