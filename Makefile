.PHONY: help dev dev-backend dev-frontend down test lint format migrate seed build clean setup install-backend install-frontend demo

PYTHON ?= python3
PIP ?= pip3

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: install-backend install-frontend ## Install all dependencies
	@echo "Setup complete. Copy .env.example to .env and configure."

install-backend: ## Install backend Python dependencies
	cd backend && $(PIP) install -e ".[dev]"
	$(PIP) install -e cli/

install-frontend: ## Install frontend npm dependencies
	cd frontend && npm install

dev: ## Start everything with docker-compose
	docker-compose up --build

dev-backend: ## Start backend only (requires postgres running)
	cd backend && uvicorn slmforge.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev

down: ## Stop docker-compose services
	docker-compose down

build: ## Build docker images
	docker-compose build

migrate: ## Run database migrations
	cd backend && alembic upgrade head

migrate-create: ## Create a new migration
	cd backend && alembic revision --autogenerate -m "$(msg)"

seed: ## Load demo data
	cd backend && $(PYTHON) -c "
import sys; sys.path.insert(0, '.')
from slmforge.db.session import SessionLocal
from slmforge.services.data.ingestion import DatasetIngestionService
db = SessionLocal()
svc = DatasetIngestionService(db)
ds, dsv, qr, stats = svc.ingest(
    name='vulnerability-detection-demo',
    source_path='../demo_data/vulnerability_demo.json',
    is_demo=True,
    description='DEMO DATASET - for pipeline verification only',
    train_ratio=0.7, val_ratio=0.15, test_ratio=0.15,
)
print(f'DEMO dataset registered: id={ds.id} version={dsv.version}')
print(f'Samples: {stats}')
db.close()
"

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd backend && pytest -v --tb=short

test-frontend: ## Run frontend tests (Playwright e2e not auto-run)
	cd frontend && npm test -- --watchAll=false || true

lint: ## Run linters (ruff)
	cd backend && ruff check slmforge tests
	cd frontend && npm run lint 2>/dev/null || true

format: ## Format code (black + ruff --fix)
	cd backend && ruff check --fix slmforge tests
	cd backend && black slmforge tests
	cd frontend && npm run format 2>/dev/null || true

clean: ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/*.egg-info cli/*.egg-info

logs: ## Tail all docker logs
	docker-compose logs -f

psql: ## Connect to postgres
	docker-compose exec postgres psql -U slmforge -d slmforge

shell: ## Open a Python shell with backend context
	cd backend && $(PYTHON) -i -c "
import sys; sys.path.insert(0, '.')
from slmforge.db.session import SessionLocal
db = SessionLocal()
print('Database session available as `db`')
"
