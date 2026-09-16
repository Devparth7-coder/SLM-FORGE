"""Local filesystem storage backend."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional

from slmforge.core.config import settings
from slmforge.core.exceptions import ArtifactError, SecurityError
from slmforge.core.security import safe_join_path
from slmforge.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Store artifacts on the local filesystem under settings.storage_local_root."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or settings.storage_local_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        key = key.lstrip("/")
        if "\\" in key or ".." in Path(key).parts:
            raise SecurityError(f"Invalid storage key: {key!r}")
        target = (self.root / key).resolve()
        if not str(target).startswith(str(self.root)):
            raise SecurityError(f"Path traversal attempt in key: {key!r}")
        return target

    def store_bytes(self, key: str, data: bytes, *, content_type: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def store_file(self, key: str, source_path: Path, *, content_type: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        src = Path(source_path).resolve()
        if not src.is_file():
            raise ArtifactError(f"Source file does not exist: {source_path}")
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, path)
        return str(path)

    def get_bytes(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise ArtifactError(f"Object not found: {key}")
        return path.read_bytes()

    def get_file(self, key: str, dest_path: Path) -> Path:
        path = self._resolve(key)
        if not path.is_file():
            raise ArtifactError(f"Object not found: {key}")
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        return dest

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> bool:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()
            return True
        return False

    def list_prefix(self, prefix: str) -> List[str]:
        base = self._resolve(prefix)
        if not base.exists():
            return []
        if base.is_file():
            return [prefix]
        results: List[str] = []
        for p in base.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.root)
                results.append(str(rel))
        return sorted(results)

    def get_size(self, key: str) -> Optional[int]:
        path = self._resolve(key)
        if path.is_file():
            return path.stat().st_size
        return None

    def get_uri(self, key: str) -> str:
        path = self._resolve(key)
        return f"file://{path}"

    def open_read(self, key: str) -> BinaryIO:
        path = self._resolve(key)
        if not path.is_file():
            raise ArtifactError(f"Object not found: {key}")
        return open(path, "rb")
