# SLM-FORGE
## Small Language Model Fine-Tuning & Evaluation Laboratory

> **"Train less. Measure more. Prove whether fine-tuning actually works."**

SLM-FORGE is a production-grade, reproducible ML research platform for adapting small
foundation models to narrow domain-specific tasks. It is **not** a generic chatbot — it is
an **experimental system** that implements the full lifecycle from raw data to
reproducible report, with rigorous baseline comparison and scientific honesty at its core.

The first reference task is **source-code vulnerability identification**: given a code
snippet, classify whether it contains a vulnerability and return structured JSON
output. The architecture is domain-agnostic; additional tasks (financial extraction,
legal classification, medical imaging, etc.) can be added without changing the platform.

---

## Why This Project Exists

Most "fine-tuning demos" show a few cherry-picked examples, fake loss curves, or
post-training screenshots that don't isolate the effect of fine-tuning. SLM-FORGE exists
to enforce a single methodological rule:

> A base model and a fine-tuned model must be evaluated on the **exact same held-out test
> set** using the **exact same evaluation harness**. No exceptions.

Every metric is **measured from actual runs** — never fabricated. Every experiment is
**reproducible** from its configuration and dataset version. Every result is traceable to:
experiment ID, model version, dataset version, dataset hash, training config, evaluation
config, software environment, random seed, and git commit.

---

## Research Question

> Does parameter-efficient fine-tuning (LoRA/QLoRA) produce measurable improvement on a
> narrow domain-specific task while preserving acceptable inference efficiency?

- **H0 (null):** Fine-tuning does not produce a meaningful improvement over the base model.
- **H1 (alternative):** Fine-tuning produces measurable improvement on the target task.

SLM-FORGE does **not** automatically declare H0 or H1 supported. The evidence comes from
actual experiments. The same test set is used for both models; confidence intervals are
provided via bootstrap; class imbalance, data leakage, and robustness degradation are all
reported.

---

## Architecture

```
        ┌────────────────────┐
        │    Raw Dataset     │
        └─────────┬──────────┘
                  ↓
        ┌────────────────────┐
        │ Data Ingestion     │
        └─────────┬──────────┘
                  ↓
        ┌────────────────────┐
        │ Cleaning / Schema  │
        │ Normalization      │
        └─────────┬──────────┘
                  ↓
        ┌────────────────────┐
        │ Deduplication      │
        │ Leakage Detection  │
        └─────────┬──────────┘
                  ↓
        ┌────────────────────┐
        │ Synthetic Data     │  ← (modular, validated before entering dataset)
        └─────────┬──────────┘
                  ↓
        ┌────────────────────┐
        │ Dataset Versioning │  ← content hash + manifest
        └─────────┬──────────┘
                  ↓
       ┌──────────┴──────────┐
       ↓                     ↓
┌──────────────┐     ┌──────────────┐
│ Base Model   │     │ LoRA/QLoRA   │
│ Evaluation   │     │ Fine-Tuning  │
└──────┬───────┘     └──────┬───────┘
       │                    │
       └─────────┬──────────┘
                 ↓
        ┌────────────────────┐
        │ Evaluation Engine  │  ← SAME harness for both models
        └─────────┬──────────┘
                 ↓
        ┌────────────────────┐
        │ Robustness Tests   │  ← perturbations, degradation scores
        └─────────┬──────────┘
                 ↓
        ┌────────────────────┐
        │ Failure Analysis   │  ← FP/FN/wrong-category/malformed-JSON
        └─────────┬──────────┘
                 ↓
        ┌────────────────────┐
        │ Reproducible       │
        │ Experiment Report  │  ← JSON + Markdown + HTML
        └────────────────────┘
```

---

## Pipeline: RAW DATA → REPORT

1. **Ingest** JSON / JSONL / CSV / Parquet / HF datasets / code directories
2. **Validate** against canonical schema; normalise field names and labels
3. **Deduplicate** (exact + near-duplicate detection)
4. **Check leakage** between train/val/test splits
5. **Score quality** (class balance, length distribution, malformed samples)
6. **Version** the dataset (content hash + immutable manifest)
7. **Evaluate baseline** model on test set
8. **Fine-tune** with LoRA/QLoRA (PEFT + TRL) with optional W&B tracking
9. **Evaluate fine-tuned** model on the **same** test set
10. **Run robustness** perturbations (formatting, renaming, truncation, etc.)
11. **Analyse failures** (false positive, false negative, malformed output, etc.)
12. **Compare** base vs fine-tuned with deltas and confidence intervals
13. **Generate report** (JSON, Markdown, HTML) with reproduction instructions

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL |
| ML | PyTorch, HuggingFace Transformers, Datasets, PEFT, TRL, Accelerate, bitsandbytes, scikit-learn |
| Tracking | Weights & Biases (optional — runs locally without it) |
| Frontend | Next.js 14, TypeScript, React, Tailwind CSS, Recharts |
| Infra | Docker, Docker Compose, PostgreSQL 16, Redis 7, local storage (S3-ready abstraction) |
| Testing | pytest, (Playwright-ready) |
| Quality | Ruff, Black, mypy |
| CLI | Typer + Rich |

---

## Installation

### Prerequisites
- Docker and Docker Compose (for the easiest start)
- Or: Python 3.11+, Node 20+, PostgreSQL 16, optionally Redis

### Quick Start with Docker

```bash
git clone <repo>
cd slm-forge
cp .env.example .env
docker-compose up --build
```

- Backend API: http://localhost:8000  (docs: http://localhost:8000/docs)
- Frontend UI: http://localhost:3000

### Local Development (no Docker)

```bash
# Backend
cd backend
pip install -e ".[dev]"
cd ..
pip install -e cli/

# Frontend
cd frontend
npm install
npm run dev

# Run Postgres separately (or use Docker for just DB):
docker-compose up -d postgres redis

# Run migrations
cd backend && alembic upgrade head
```

### Seed the demo dataset

```bash
make seed
```

This registers the DEMO dataset (20 labelled vulnerability snippets). **Demo data is
included only to verify the pipeline. Published performance claims must be generated from
a valid evaluation dataset.**

### Common Make targets

| Command | What it does |
|---------|-------------|
| `make dev` | Start all services via docker-compose |
| `make install-backend` | Install Python dependencies |
| `make install-frontend` | Install npm dependencies |
| `make migrate` | Run Alembic migrations |
| `make seed` | Load demo dataset |
| `make test-backend` | Run backend tests |
| `make lint` | Run Ruff linter |
| `make format` | Format code (Black + Ruff) |

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql://slmforge:slmforge@localhost:5432/slmforge` | PostgreSQL connection |
| `REDIS_URL` | — | Optional Redis for async jobs |
| `MODEL_NAME` | `Qwen/Qwen2.5-0.5B-Instruct` | Default model |
| `MODEL_REVISION` | `main` | HF revision |
| `HF_TOKEN` | — | HuggingFace token (for gated models) |
| `WANDB_ENABLED` | `false` | Enable W&B tracking |
| `WANDB_API_KEY` | — | W&B API key |
| `STORAGE_BACKEND` | `local` | Storage backend (`local`; S3 coming) |
| `STORAGE_LOCAL_ROOT` | `./data/artifacts` | Local artifact directory |
| `MAX_UPLOAD_SIZE_MB` | `100` | Upload size limit |
| `AUTH_ENABLED` | `false` | Enable JWT auth |
| `FORCE_CPU` | `false` | Force CPU-only (even if GPU present) |

---

## CLI

```bash
slmforge --help

# Dataset commands
slmforge dataset ingest --name my-ds --source data/train.json
slmforge dataset validate --source data/train.json
slmforge dataset stats --id <dataset_id>

# Model registry
slmforge model register --name "Qwen-0.5B" --hf Qwen/Qwen2.5-0.5B-Instruct --quant 4bit
slmforge model list

# Experiments
slmforge experiment run --name "exp1" --dataset <version_id> --model <version_id> [--dry-run]
slmforge experiment reproduce --id <experiment_id>

# Reports
slmforge report generate --experiment <id> --formats json,markdown,html
```

---

## Dataset Format

The canonical sample schema is:

```json
{
  "id": "sample-001",
  "input": "def get_user(username):\n    query = \"SELECT * FROM users WHERE username = '\" + username + \"'\"",
  "label": "vulnerable",
  "category": "SQL_INJECTION",
  "severity": "HIGH",
  "evidence": "User-controlled input concatenated into SQL query.",
  "metadata": {"source": "manual"}
}
```

Common field aliases are auto-normalised: `code`→`input`, `is_vulnerable`→`label`,
`vuln_type`→`category`, etc.

Accepted labels: `vulnerable`/`safe` (aliases: 1/0, true/false, yes/no, etc.)

Accepted categories: `SQL_INJECTION`, `XSS`, `COMMAND_INJECTION`, `PATH_TRAVERSAL`,
`INSECURE_CRYPTO`, `HARDCODED_SECRET`, `DESERIALIZATION`, `CODE_INJECTION`, etc.

Accepted severities: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`, `NONE`.

---

## REST API

All endpoints are under `/api/v1`. FastAPI auto-generates OpenAPI docs at `/docs`.

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Health & hardware status |
| `GET /datasets` | List datasets |
| `POST /datasets/ingest` | Ingest dataset from path or HF ID |
| `POST /datasets/upload` | Upload dataset file |
| `GET /datasets/{id}` | Get dataset |
| `GET /datasets/{id}/quality` | Quality reports |
| `GET /datasets/{id}/statistics` | Dataset statistics |
| `GET /models` | List registered models |
| `POST /models` | Register a model |
| `GET /experiments` | List experiments |
| `POST /experiments` | Create experiment |
| `POST /experiments/{id}/start` | Start experiment |
| `POST /experiments/{id}/cancel` | Cancel experiment |
| `GET /experiments/{id}/comparison` | Base vs fine-tuned comparison |
| `GET /evaluations` | List evaluations |
| `GET /evaluations/{id}` | Get evaluation + metrics |
| `GET /evaluations/{id}/predictions` | Predictions for inspection |
| `GET /failures` | Failure analysis entries |
| `POST /experiments/{id}/robustness` | Run robustness tests |
| `GET /robustness` | List robustness runs |
| `POST /reports/generate` | Generate reports |
| `GET /reports` | List reports |
| `GET /hardware` | Hardware detection |

---

## Metrics (Defined Mathematically)

For classification tasks we report:

- **Accuracy** = (TP + TN) / N
- **Precision** = TP / (TP + FP)
- **Recall** = TP / (TP + FN)
- **F1** = 2 · (P · R) / (P + R)
- **Macro F1** = mean of per-class F1
- **Weighted F1** = support-weighted mean of per-class F1
- **JSON Validity Rate** = fraction of outputs parseable as JSON
- **Schema Validity Rate** = fraction matching the required schema
- **Category Accuracy** = fraction of vulnerable samples with correct category
- **Severity Accuracy** = fraction with correct severity
- **Malformed Output Rate** = fraction with parse/schema errors
- **Confusion Matrix** = 2×2 matrix of true vs predicted labels
- **Bootstrap 95% CI** = 1000 bootstrap resamples for accuracy & macro F1

### Robustness Metrics

For each perturbation type *p*:

```
RobustnessScore(p)        = Macro-F1(p) / Macro-F1(baseline)
PerformanceDegradation(p) = Macro-F1(baseline) − Macro-F1(p)
OverallRobustnessScore    = mean_p(RobustnessScore(p))
```

A score of 1.0 means no degradation; < 1.0 indicates the model's performance drops under
that perturbation.

### Comparison Deltas

```
Δ = Fine-tuned value − Base value
```

For metrics where **lower is better** (latency, malformed rate, degradation), the delta is
sign-inverted for display so that positive always means "better". Nothing is labelled
"improved" unless the metric direction supports that conclusion.

---

## Failure Categories

| Category | Meaning |
|----------|---------|
| `false_positive` | Safe code flagged as vulnerable |
| `false_negative` | Vulnerable code flagged as safe |
| `wrong_category` | Correct detection, wrong vulnerability type |
| `wrong_severity` | Correct detection, wrong severity level |
| `malformed_json` | Output could not be parsed as valid JSON |
| `missing_evidence` | JSON valid but evidence field empty/too short |
| `uncertain_prediction` | Low confidence or abstention |
| `robustness_failure` | Correct on clean input, wrong after perturbation |

---

## Reproducibility

Every experiment has a **"Reproduce This Experiment"** section in its report, containing:

```bash
slmforge experiment run \
  --dataset-version <version> \
  --base-model <hf-id>@<revision> \
  --seed <seed>
```

Plus:

- Python version
- Key package versions (torch, transformers, peft, trl, etc.)
- CUDA version and GPU information
- Git commit SHA (with warning if working tree is dirty)
- Dataset content hash and split hash
- Full training + evaluation configuration YAML

---

## Scientific Honesty Guarantees

SLM-FORGE will **never**:

- Fabricate accuracy, F1, loss curves, dataset sizes, GPU performance, or training times
- Present screenshots with fake metrics
- Call simulated/dry-run results "empirical results"
- Claim fine-tuning improved performance unless the evaluation demonstrates it
- Hide train/test leakage, class imbalance, or data quality issues
- Delete data silently — every transformation generates statistics
- Execute source code from uploaded datasets

When data does not exist the UI shows **N/A**, **Not measured**, or **Pending experiment** —
never a made-up number.

- Demo data is clearly labelled **DEMO** everywhere it appears.
- Dry-run (no-GPU) runs are labelled **DRY RUN** in training status and reports.
- External benchmarks are labelled **EXTERNAL BENCHMARK** when imported.

---

## Security

- No hard-coded secrets (all configuration via environment variables)
- Input validation on all API endpoints via Pydantic
- File-type validation + upload size limits
- Path traversal protection in storage layer
- JWT authentication architecture (toggle with `AUTH_ENABLED`)
- Structured logging redacts passwords, tokens, API keys
- **The platform never executes source code from uploaded datasets**

---

## Project Structure

```
slm-forge/
├── backend/
│   └── slmforge/
│       ├── api/v1/              # FastAPI routers
│       ├── core/               # Config, logging, exceptions, security
│       ├── db/                 # SQLAlchemy models, session, migrations
│       ├── services/           # Business logic: data, model, training, eval, reports
│       ├── storage/            # Storage abstraction (local + S3-ready)
│       ├── schemas/            # Pydantic request/response models
│       └── utils/              # Hardware, hashing, git, json, seeding
├── cli/slmforge/               # Typer CLI: slmforge ...
├── frontend/
│   └── src/
│       ├── app/                # Next.js App Router pages
│       ├── components/         # UI, charts, layout, page components
│       └── lib/                # API client, utilities
├── data/                       # Datasets, artifacts, cache, reports
├── demo_data/                  # DEMO dataset (pipeline verification only)
├── configs/                    # YAML configuration examples
├── docs/                       # Architecture and methodology docs
├── scripts/                    # Helper scripts
├── deploy/                     # Deployment configs
├── docker-compose.yml
├── pyproject.toml
├── Makefile
└── README.md
```

---

## Testing

```bash
# Backend unit tests
make test-backend

# Integration tests (require running Postgres)
cd backend && pytest tests/integration -v
```

Unit tests cover schema validation, deduplication, metrics calculation, and JSON parsing.
Integration tests cover dataset ingestion, experiment creation, and report generation.

---

## Deployment

### Render / Vercel

Configuration files are provided in `deploy/`:

- **Backend (Render):** `deploy/render-backend.yaml` — deploy as a Web Service using Docker
- **Frontend (Vercel):** `deploy/vercel.json` — deploy frontend pointing to backend URL
- **Database:** Use Render PostgreSQL or a managed PostgreSQL service
- **Redis (optional):** Upstash or Render Redis

Set the production environment variables (especially `SECRET_KEY`, `DATABASE_URL`,
`HF_TOKEN`, `WANDB_API_KEY`) in your hosting dashboard.

**Important:** Training GPU jobs require a CUDA-capable worker; the Render/Vercel deployment
is suitable for the UI and API only in production. For GPU training, use a dedicated GPU
instance (Lambda Labs, RunPod, AWS p3/g5, GCP a2, etc.) with the same codebase.

---

## Limitations

- SLM-FORGE is a research platform, not a production inference serving system.
- Small models (0.5B–3B parameters) work well on single-GPU setups; larger models need
  appropriate hardware and may require tensor-parallelism (not yet implemented).
- The vulnerability classification task uses a simple prompt template; improving prompting
  or switching to chat templates is a configuration change, not a code change.
- Synthetic data generation scaffolding is present in the architecture; the seed example
  generator is extensible but is not yet a fully fledged data augmentation engine.
- Vision, multimodal, embedding, and retrieval tasks are architecturally supported by
  extending the task registry but are not implemented in v1.

---

## Ethics

Vulnerability detection tools can be dual-use: they can help defenders patch code, but
they can also help attackers find bugs. SLM-FORGE is intended for **defensive security
research, model evaluation, and educational use**. Users are responsible for their
application of the system.

No model or dataset in this repository should be construed as providing production-grade
security guarantees. Always verify findings with manual review and established security
tooling (SAST/DAST scanners, code review, penetration testing).

---

## Future Work

- Additional domain adapters (financial, legal, medical, support tickets)
- Full synthetic-data generation pipeline with human review queue
- Multi-seed ablation support and automated statistical significance testing
- S3/GCS storage backend
- Async job queue via Redis/Celery for distributed training
- Vision transformer and multimodal task support
- Interactive Playwright E2E test suite
- Model comparison across multiple experiments (ablation tables)
- SHAP/attention-based error explanation in Failure Analysis

---

## Documentation

Additional documentation is in the `docs/` directory:

- `docs/architecture.md`
- `docs/data-pipeline.md`
- `docs/training.md`
- `docs/evaluation.md`
- `docs/metrics.md`
- `docs/reproducibility.md`
- `docs/deployment.md`
- `docs/research-methodology.md`

---

## License

Copyright (c) 2025 **Dev Parth** — Proprietary license. See `LICENSE` for full terms.

---

## Data Flow Summary

```
RAW DATA
  → CLEAN DATA
  → VERIFIED DATASET
  → BASELINE
  → LoRA/QLoRA
  → TRAINING
  → EVALUATION
  → ROBUSTNESS
  → FAILURE ANALYSIS
  → BASE VS FINE-TUNED
  → REPRODUCIBLE REPORT
```
