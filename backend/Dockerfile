# SLM-Forge Backend
# ────────────────────────────────────────────────────────────────────────
# This Dockerfile works for BOTH:
#   (a) docker-compose dev:  context = ./backend, source mounted as volume
#   (b) Render production:   context = .  (repo root), Dockerfile = backend/Dockerfile
#
# It auto-detects via the presence of /app/slmforge (dev mount) vs /
# needing to copy from backend/. In production mode (BUILD_CONTEXT=repo),
# we COPY from backend/; in dev mode (BUILD_CONTEXT=backend or default)
# we assume the source is already mounted into /app.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FORCE_CPU=true \
    WANDB_ENABLED=false \
    PYTHONPATH=/app \
    APP_ENV=${APP_ENV:-development}

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Install CPU-only PyTorch (keeps images small on CPU-only hosts)
# Skips entirely if TORCH_INSTALL_URL set to 'skip' (sandbox already has torch)
ARG TORCH_INSTALL_URL=https://download.pytorch.org/whl/cpu
RUN if [ "$TORCH_INSTALL_URL" != "skip" ]; then \
        pip install --index-url $TORCH_INSTALL_URL "torch==2.2.0"; \
    fi

# Try to copy requirements from two possible locations (dev context vs repo context)
COPY requirements-runtime.txt /app/requirements-runtime.txt 2>/dev/null || \
    COPY backend/requirements-runtime.txt /app/requirements-runtime.txt
RUN pip install -r /app/requirements-runtime.txt

# Copy source if available (in production / Render builds);
# in docker-compose dev, the volume mount provides /app/slmforge live.
COPY slmforge /app/slmforge 2>/dev/null || COPY backend/slmforge /app/slmforge 2>/dev/null || true
COPY alembic /app/alembic 2>/dev/null || COPY backend/alembic /app/alembic 2>/dev/null || true
COPY alembic.ini /app/alembic.ini 2>/dev/null || COPY backend/alembic.ini /app/alembic.ini 2>/dev/null || true
COPY demo_data /app/demo_data 2>/dev/null || true

RUN mkdir -p /app/data/artifacts /app/data/cache/models /app/data/datasets /app/data/reports

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command (overridden in docker-compose for dev hot-reload)
CMD ["sh", "-c", "alembic upgrade head && uvicorn slmforge.main:app --host 0.0.0.0 --port 8000 --workers 1"]
