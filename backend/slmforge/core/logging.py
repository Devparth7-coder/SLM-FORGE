"""Structured logging for SLM-Forge.

Every important operation gets timestamp, request_id, experiment_id, dataset_id,
model_id, status, duration. API keys/tokens/passwords are never logged.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog

from slmforge.core.config import settings

# Context variables for request-scoped metadata
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
experiment_id_var: ContextVar[Optional[str]] = ContextVar("experiment_id", default=None)
dataset_id_var: ContextVar[Optional[str]] = ContextVar("dataset_id", default=None)
model_id_var: ContextVar[Optional[str]] = ContextVar("model_id", default=None)

_SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "hf_token",
    "wandb_api_key",
    "secret_key",
    "private_key",
    "access_token",
    "refresh_token",
}


def _redact_sensitive(_: Any, __: Any, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive keys from log entries."""
    for key in list(event_dict.keys()):
        lower = key.lower().replace("-", "_")
        if any(s in lower for s in _SENSITIVE_KEYS):
            event_dict[key] = "***REDACTED***"
    return event_dict


def setup_logging() -> None:
    """Configure structlog for the application."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_sensitive,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a structured logger bound to current context."""
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables for the current execution scope."""
    structlog.contextvars.clear_contextvars()
    for k, v in kwargs.items():
        if k == "request_id":
            request_id_var.set(v)
        elif k == "experiment_id":
            experiment_id_var.set(v)
        elif k == "dataset_id":
            dataset_id_var.set(v)
        elif k == "model_id":
            model_id_var.set(v)
    structlog.contextvars.bind_contextvars(**kwargs)
