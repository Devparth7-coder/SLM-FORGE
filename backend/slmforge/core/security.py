"""Security utilities: authentication, input validation, file validation."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from jose import JWTError, jwt
from passlib.context import CryptContext

from slmforge.core.config import settings
from slmforge.core.exceptions import SecurityError

# ── Password hashing ────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ─────────────────────────────────────────────────────────────────────
ALGORITHM = "HS256"


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise SecurityError(f"Invalid token: {exc}") from exc


# ── File validation ─────────────────────────────────────────────────────────
_DANGEROUS_EXTENSIONS = {
    ".exe", ".sh", ".bat", ".cmd", ".ps1", ".msi", ".com",
    ".jar", ".dll", ".so", ".dylib",
}


def validate_upload_filename(filename: str) -> str:
    """Validate an uploaded filename; return the safe basename.

    Blocks path traversal and dangerous extensions.
    """
    base = os.path.basename(filename)
    if not base or base in {".", ".."}:
        raise SecurityError(f"Invalid filename: {filename!r}")
    # No path traversal
    if "/" in base or "\\" in base or base.startswith("."):
        raise SecurityError(f"Invalid filename: {filename!r}")
    ext = Path(base).suffix.lower()
    if ext in _DANGEROUS_EXTENSIONS:
        raise SecurityError(f"File extension not allowed: {ext}")
    if settings.allowed_upload_extensions and ext not in settings.allowed_upload_extensions:
        raise SecurityError(f"File extension not allowed: {ext}")
    return base


def validate_file_size(size_bytes: int) -> None:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise SecurityError(
            f"File too large: {size_bytes} bytes exceeds {max_bytes} byte limit"
        )


def safe_join_path(base_dir: Path, relative_path: str) -> Path:
    """Safely join a relative path to a base directory (prevent path traversal)."""
    base = base_dir.resolve()
    target = (base / relative_path).resolve()
    if not str(target).startswith(str(base)):
        raise SecurityError(f"Path traversal attempt: {relative_path!r}")
    return target


# ── Content hashing ─────────────────────────────────────────────────────────
def compute_content_hash(content: bytes) -> str:
    """Return SHA-256 hex digest of content."""
    return hashlib.sha256(content).hexdigest()


def compute_file_hash(filepath: Path, chunk_size: int = 65536) -> str:
    """Stream-compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ── Input sanitisation ──────────────────────────────────────────────────────
_PATTERN_CODE_EXEC = re.compile(
    r"(?:exec|eval|subprocess|os\.system|os\.popen|__import__)\s*\(",
    re.IGNORECASE,
)


def detect_code_execution_attempt(text: str) -> bool:
    """Heuristic: detect if a string appears to attempt Python code execution.

    This is used to prevent arbitrary code execution through the web API
    (e.g. a dataset field containing Python that the platform might accidentally exec).
    The platform NEVER executes source code from uploaded datasets, but this is an
    additional defense-in-depth layer for future code paths.
    """
    return bool(_PATTERN_CODE_EXEC.search(text))
