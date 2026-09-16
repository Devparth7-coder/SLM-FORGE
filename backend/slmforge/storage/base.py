"""Abstract artifact storage backend.

Supports local filesystem first; S3-compatible storage can be added later
by implementing this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional


class StorageBackend(ABC):
    """Abstract interface for artifact storage."""

    @abstractmethod
    def store_bytes(self, key: str, data: bytes, *, content_type: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store raw bytes; return a resolvable URI or path."""

    @abstractmethod
    def store_file(self, key: str, source_path: Path, *, content_type: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store a file from disk; return URI."""

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        """Retrieve raw bytes."""

    @abstractmethod
    def get_file(self, key: str, dest_path: Path) -> Path:
        """Download a stored object to dest_path; return dest_path."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check whether an object exists."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete an object; return True if deleted."""

    @abstractmethod
    def list_prefix(self, prefix: str) -> List[str]:
        """List all keys under a prefix."""

    @abstractmethod
    def get_size(self, key: str) -> Optional[int]:
        """Return size in bytes if known."""

    @abstractmethod
    def get_uri(self, key: str) -> str:
        """Return a public/resolvable URI for the object."""

    @abstractmethod
    def open_read(self, key: str) -> BinaryIO:
        """Open an object for binary reading."""
