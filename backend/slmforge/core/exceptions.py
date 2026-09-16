"""Strongly typed exception hierarchy for SLM-Forge.

All exceptions are human-readable and carry structured context for the API layer
and logs. Nothing silently fails.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class SLMForgeError(Exception):
    """Base exception for all SLM-Forge errors."""

    error_code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str = "",
        *,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.message = message or self.__class__.__doc__ or self.error_code
        self.details = details or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(SLMForgeError):
    """Invalid configuration provided."""
    error_code = "CONFIGURATION_ERROR"
    status_code = 500


class NotFoundError(SLMForgeError):
    """Requested resource was not found."""
    error_code = "NOT_FOUND"
    status_code = 404


class DatasetValidationError(SLMForgeError):
    """Dataset failed validation (schema, format, or content issues)."""
    error_code = "DATASET_VALIDATION_FAILED"
    status_code = 422


class DatasetIngestionError(SLMForgeError):
    """Failed to ingest dataset."""
    error_code = "DATASET_INGESTION_FAILED"
    status_code = 400


class ModelNotAvailableError(SLMForgeError):
    """Specified model is not available or cannot be loaded."""
    error_code = "MODEL_NOT_AVAILABLE"
    status_code = 400


class InsufficientMemoryError(SLMForgeError):
    """Insufficient memory/VRAM for requested operation."""
    error_code = "INSUFFICIENT_MEMORY"
    status_code = 400


class InvalidTrainingConfigError(SLMForgeError):
    """Training configuration is invalid."""
    error_code = "INVALID_TRAINING_CONFIG"
    status_code = 422


class TrainingError(SLMForgeError):
    """Training run failed."""
    error_code = "TRAINING_FAILED"
    status_code = 500


class EvaluationError(SLMForgeError):
    """Evaluation run failed."""
    error_code = "EVALUATION_FAILED"
    status_code = 500


class ArtifactError(SLMForgeError):
    """Artifact storage operation failed."""
    error_code = "ARTIFACT_UPLOAD_FAILED"
    status_code = 500


class SecurityError(SLMForgeError):
    """Security violation detected."""
    error_code = "SECURITY_VIOLATION"
    status_code = 403


class ValidationError(SLMForgeError):
    """Input validation failed."""
    error_code = "VALIDATION_ERROR"
    status_code = 422


class ExperimentStateError(SLMForgeError):
    """Invalid operation for current experiment state."""
    error_code = "EXPERIMENT_STATE_ERROR"
    status_code = 409


class ConcurrencyError(SLMForgeError):
    """Operation cannot proceed due to concurrency conflict."""
    error_code = "CONCURRENCY_ERROR"
    status_code = 409
