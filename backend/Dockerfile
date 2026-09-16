# SLM-Forge Backend — PRODUCTION (Render / cloud deployment)
# Build context = repo root (.)
# Dockerfile path = backend/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FORCE_CPU=true \
    WANDB_ENABLED=false \
    PYTHONPATH=/app \
    APP_ENV=production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# CPU-only PyTorch (smaller, no CUDA)
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.2.0"

# All paths relative to build context = repo root (.)
COPY backend/requirements-runtime.txt /app/requirements-runtime.txt
RUN pip install -r /app/requirements-runtime.txt

COPY backend/slmforge /app/slmforge
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/alembic.ini
COPY demo_data /app/demo_data

RUN mkdir -p /app/data/artifacts /app/data/cache/models /app/data/datasets /app/data/reports

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn slmforge.main:app --host 0.0.0.0 --port 8000 --workers 1"]
