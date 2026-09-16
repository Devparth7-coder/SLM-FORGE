"""SLM-Forge FastAPI application entry point."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from slmforge.api.v1 import (
    datasets, models, experiments, evaluations, failures, reports,
    health, artifacts, hardware, robustness as robustness_router,
)
from slmforge.core.config import settings
from slmforge.core.exceptions import SLMForgeError
from slmforge.core.logging import get_logger, setup_logging, bind_context
from slmforge.db import engine, SessionLocal
from slmforge.db.base import Base

logger = get_logger("slmforge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("app.startup", env=settings.app_env, version=settings.app_version)
    # Create tables if they don't exist (in production use alembic migrations)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("db.schema_ready")
    except Exception as exc:
        logger.error("db.schema_failed", error=str(exc))
    yield
    logger.info("app.shutdown")


app = FastAPI(
    title="SLM-FORGE",
    description="Small Language Model Fine-Tuning & Evaluation Laboratory",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request middleware: request_id, logging ───────────────────────────────
@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    t0 = time.perf_counter()
    bind_context(request_id=request_id)
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response


# ── Exception handlers ────────────────────────────────────────────────────
@app.exception_handler(SLMForgeError)
async def slmforge_error_handler(request: Request, exc: SLMForgeError):
    logger.error("api.error", error_code=exc.error_code, message=exc.message,
                 details=exc.details, path=str(request.url.path))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"errors": exc.errors()},
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────
api_prefix = settings.api_prefix
app.include_router(health.router, prefix=api_prefix, tags=["health"])
app.include_router(datasets.router, prefix=f"{api_prefix}/datasets", tags=["datasets"])
app.include_router(models.router, prefix=f"{api_prefix}/models", tags=["models"])
app.include_router(experiments.router, prefix=f"{api_prefix}/experiments", tags=["experiments"])
app.include_router(evaluations.router, prefix=f"{api_prefix}/evaluations", tags=["evaluations"])
app.include_router(failures.router, prefix=f"{api_prefix}/failures", tags=["failures"])
app.include_router(reports.router, prefix=f"{api_prefix}/reports", tags=["reports"])
app.include_router(artifacts.router, prefix=f"{api_prefix}/artifacts", tags=["artifacts"])
app.include_router(hardware.router, prefix=f"{api_prefix}/hardware", tags=["hardware"])
app.include_router(robustness_router.router, prefix=f"{api_prefix}/robustness", tags=["robustness"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "tagline": "Train less. Measure more. Prove whether fine-tuning actually works.",
        "docs": "/docs",
    }
