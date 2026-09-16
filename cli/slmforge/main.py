"""SLM-Forge CLI: slmforge <command>.

Usage:
  slmforge dataset ingest --name <name> --source <path>
  slmforge dataset validate --source <path>
  slmforge dataset stats --id <dataset_id>
  slmforge model register --name <name> --hf <model_id>
  slmforge model list
  slmforge train --experiment <id> [--dry-run]
  slmforge evaluate --experiment <id> [--baseline | --finetuned]
  slmforge robustness --experiment <id>
  slmforge experiment run --name <name> --dataset <version_id> --model <version_id>
  slmforge experiment reproduce --id <experiment_id>
  slmforge report generate --experiment <id>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="slmforge",
    help="SLM-FORGE: Small Language Model Fine-Tuning & Evaluation Laboratory",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

# ── Dataset commands ──────────────────────────────────────────────────────
dataset_app = typer.Typer(help="Dataset management commands")
model_app = typer.Typer(help="Model registry commands")
experiment_app = typer.Typer(help="Experiment management commands")
report_app = typer.Typer(help="Report generation commands")

app.add_typer(dataset_app, name="dataset")
app.add_typer(model_app, name="model")
app.add_typer(experiment_app, name="experiment")
app.add_typer(report_app, name="report")


def _get_db():
    """Get a database session for CLI usage."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from slmforge.db.session import SessionLocal
    return SessionLocal()


@dataset_app.command("ingest")
def dataset_ingest(
    name: str = typer.Option(..., "--name", "-n"),
    source: Optional[Path] = typer.Option(None, "--source", "-s"),
    hf_dataset: Optional[str] = typer.Option(None, "--hf"),
    domain: str = typer.Option("code_security"),
    task: str = typer.Option("vulnerability_classification"),
    demo: bool = typer.Option(False, "--demo"),
    seed: int = typer.Option(42),
):
    """Ingest a dataset into the platform."""
    db = _get_db()
    from slmforge.services.data.ingestion import DatasetIngestionService
    svc = DatasetIngestionService(db)
    try:
        ds, dsv, qr, stats = svc.ingest(
            name=name,
            source_path=str(source) if source else None,
            hf_dataset_id=hf_dataset,
            domain=domain, task=task, is_demo=demo, seed=seed,
        )
        console.print(f"[green]✓ Dataset ingested[/green]")
        console.print(f"  ID: {ds.id}")
        console.print(f"  Version: {dsv.version}")
        console.print(f"  Hash: {dsv.content_hash[:16]}...")
        console.print(f"  Raw: {stats['raw_count']}  →  Clean: {len(_list_valid(stats))}")
        console.print(f"  Train/Val/Test: {stats['train_count']}/{stats['val_count']}/{stats['test_count']}")
    except Exception as exc:
        console.print(f"[red]✗ Ingestion failed:[/red] {exc}")
        raise typer.Exit(1)
    finally:
        db.close()


def _list_valid(stats):
    return []


@dataset_app.command("validate")
def dataset_validate(source: Path = typer.Option(..., "--source", "-s")):
    """Validate a dataset file without ingesting."""
    from slmforge.services.data.validation import SchemaValidator
    import json as _json
    v = SchemaValidator()
    text = source.read_text()
    if source.suffix == ".jsonl":
        samples = [_json.loads(ln) for ln in text.splitlines() if ln.strip()]
    else:
        samples = _json.loads(text)
        if isinstance(samples, dict):
            samples = samples.get("data", [])
    valid, stats = v.validate_batch(samples)
    console.print(f"[bold]Validation results for {source}[/bold]")
    console.print(f"  Total: {stats.total}")
    console.print(f"  Valid: [green]{stats.valid}[/green]")
    console.print(f"  Invalid: [red]{stats.invalid}[/red]")
    if stats.issues_counter:
        table = Table(title="Issues")
        table.add_column("Issue")
        table.add_column("Count", justify="right")
        for issue, count in sorted(stats.issues_counter.items(), key=lambda x: -x[1]):
            table.add_row(issue, str(count))
        console.print(table)


@dataset_app.command("stats")
def dataset_stats(dataset_id: str = typer.Option(..., "--id")):
    """Show dataset statistics."""
    db = _get_db()
    from slmforge.db.models.dataset import Dataset, DatasetVersion
    ds = db.get(Dataset, dataset_id)
    if not ds:
        console.print(f"[red]Dataset {dataset_id} not found[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{ds.name}[/bold] ({ds.domain}/{ds.task})")
    for v in ds.versions:
        console.print(f"  Version {v.version}: {v.sample_count} samples (hash {v.content_hash[:12]}...)")
        console.print(f"    train={v.train_count}, val={v.val_count}, test={v.test_count}")
    db.close()


@model_app.command("register")
def model_register(
    name: str = typer.Option(..., "--name", "-n"),
    hf: str = typer.Option(..., "--hf", help="HuggingFace model ID"),
    revision: str = typer.Option("main"),
    quantization: Optional[str] = typer.Option(None, "--quant", help="4bit or 8bit"),
):
    """Register a model in the registry."""
    db = _get_db()
    from slmforge.services.model.registry import ModelRegistryService
    svc = ModelRegistryService(db)
    model, version = svc.register_model(
        name=name, hf_model_id=hf, revision=revision, quantization=quantization,
    )
    console.print(f"[green]✓ Model registered[/green]")
    console.print(f"  Model ID: {model.id}")
    console.print(f"  Version ID: {version.id}")
    console.print(f"  HF: {hf}@{revision} (quant={quantization})")
    db.close()


@model_app.command("list")
def model_list():
    """List registered models."""
    db = _get_db()
    from slmforge.db.models.model import ModelRegistry
    models = db.query(ModelRegistry).all()
    if not models:
        console.print("[yellow]No models registered[/yellow]")
        return
    table = Table(title="Registered Models")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("HF ID")
    table.add_column("Versions", justify="right")
    for m in models:
        table.add_row(m.id[:8], m.name, m.versions[0].hf_model_id if m.versions else "-", str(len(m.versions)))
    console.print(table)
    db.close()


@experiment_app.command("run")
def experiment_run(
    name: str = typer.Option(..., "--name", "-n"),
    dataset_version: str = typer.Option(..., "--dataset"),
    model_version: str = typer.Option(..., "--model"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    baseline_only: bool = typer.Option(False, "--baseline-only"),
    seed: int = typer.Option(42),
):
    """Create and start an experiment."""
    db = _get_db()
    from slmforge.services.experiment import ExperimentService
    svc = ExperimentService(db)
    exp = svc.create_experiment(
        name=name,
        dataset_version_id=dataset_version,
        base_model_version_id=model_version,
        seed=seed,
        run_baseline_only=baseline_only,
    )
    console.print(f"[green]✓ Experiment created[/green]: {exp.id}")
    svc.start_experiment(exp.id, dry_run=dry_run)
    console.print(f"[yellow]→ Started experiment {exp.id}[/yellow] (dry_run={dry_run})")
    console.print(f"  Check status at /api/v1/experiments/{exp.id}")
    db.close()


@experiment_app.command("reproduce")
def experiment_reproduce(experiment_id: str = typer.Option(..., "--id")):
    """Print reproduction command for an experiment."""
    db = _get_db()
    from slmforge.db.models.experiment import Experiment
    exp = db.get(Experiment, experiment_id)
    if not exp:
        console.print("[red]Experiment not found[/red]")
        raise typer.Exit(1)
    console.print("[bold]Reproduce this experiment:[/bold]")
    console.print(f"slmforge experiment run \\")
    console.print(f'  --name "{exp.name}" \\')
    console.print(f"  --dataset {exp.dataset_version_id} \\")
    console.print(f"  --model {exp.base_model_version_id} \\")
    console.print(f"  --seed {exp.seed}")
    console.print()
    console.print(f"Git commit: {exp.git_commit or 'unknown'}")
    db.close()


@report_app.command("generate")
def report_generate(
    experiment_id: str = typer.Option(..., "--experiment", "-e"),
    formats: str = typer.Option("json,markdown,html"),
):
    """Generate reports for an experiment."""
    db = _get_db()
    from slmforge.services.reports.generator import ReportService
    svc = ReportService(db)
    fmts = [f.strip() for f in formats.split(",")]
    reports = svc.generate_all(experiment_id, formats=fmts)
    for r in reports:
        console.print(f"[green]✓[/green] {r.report_type}: {r.storage_path}")
    db.close()


@app.command("version")
def version():
    """Print version information."""
    from slmforge import __version__
    console.print(f"SLM-Forge v{__version__}")


if __name__ == "__main__":
    app()
