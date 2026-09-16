"""Experiments API endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from slmforge.db.models.experiment import EvaluationRun, Experiment, TrainingRun
from slmforge.db.session import get_db
from slmforge.schemas.experiment import ExperimentCreate, ExperimentOut
from slmforge.services.experiment import ExperimentService
from slmforge.services.model.inference import InferenceService
from slmforge.services.evaluation.engine import EvaluationService
from slmforge.services.robustness.engine import RobustnessService
from slmforge.db.models.model import ModelVersion

router = APIRouter()


@router.get("", response_model=List[ExperimentOut])
def list_experiments(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Experiment).options(
        joinedload(Experiment.training_run),
        joinedload(Experiment.evaluation_runs),
        joinedload(Experiment.robustness_runs),
    )
    if status:
        q = q.filter(Experiment.status == status)
    return q.order_by(Experiment.created_at.desc()).limit(limit).all()


@router.post("", response_model=ExperimentOut)
def create_experiment(request: ExperimentCreate, db: Session = Depends(get_db)):
    svc = ExperimentService(db)
    exp = svc.create_experiment(
        name=request.name,
        dataset_version_id=request.dataset_version_id,
        base_model_version_id=request.base_model_version_id,
        description=request.description,
        training_config=request.training_config.model_dump() if hasattr(request.training_config, "model_dump") else dict(request.training_config),
        evaluation_config=request.evaluation_config.model_dump() if hasattr(request.evaluation_config, "model_dump") else dict(request.evaluation_config),
        seed=request.seed,
        run_baseline_only=request.run_baseline_only,
        tags=request.tags,
    )
    db.refresh(exp)
    return exp


@router.get("/{experiment_id}", response_model=ExperimentOut)
def get_experiment(experiment_id: str, db: Session = Depends(get_db)):
    exp = db.query(Experiment).options(
        joinedload(Experiment.training_run),
        joinedload(Experiment.evaluation_runs),
        joinedload(Experiment.robustness_runs),
    ).get(experiment_id)
    if not exp:
        raise HTTPException(404, f"Experiment {experiment_id} not found")
    return exp


@router.post("/{experiment_id}/start", response_model=ExperimentOut)
def start_experiment(experiment_id: str, dry_run: bool = Query(False), db: Session = Depends(get_db)):
    svc = ExperimentService(db)
    exp = svc.start_experiment(experiment_id, dry_run=dry_run)
    db.refresh(exp)
    return exp


@router.post("/{experiment_id}/cancel", response_model=ExperimentOut)
def cancel_experiment(experiment_id: str, db: Session = Depends(get_db)):
    svc = ExperimentService(db)
    return svc.cancel_experiment(experiment_id)


@router.get("/{experiment_id}/comparison")
def get_comparison(experiment_id: str, db: Session = Depends(get_db)):
    """Return base vs fine-tuned metric comparison."""
    evals = db.query(EvaluationRun).filter(
        EvaluationRun.experiment_id == experiment_id
    ).all()
    baseline = next((e for e in evals if e.is_baseline), None)
    finetuned = next((e for e in evals if not e.is_baseline), None)
    from slmforge.services.evaluation.metrics import MetricReport, compare_metrics
    bm = MetricReport(**{**MetricReport().to_dict(), **(baseline.metrics_json if baseline else {})})
    if finetuned:
        fm = MetricReport(**{**MetricReport().to_dict(), **finetuned.metrics_json})
        metrics = compare_metrics(bm, fm)
    else:
        metrics = []
    return {
        "experiment_id": experiment_id,
        "metrics": metrics,
        "baseline_completed": baseline is not None and baseline.status == "COMPLETED",
        "finetuned_completed": finetuned is not None and finetuned.status == "COMPLETED",
        "baseline_eval_run_id": baseline.id if baseline else None,
        "finetuned_eval_run_id": finetuned.id if finetuned else None,
        "notes": [
            "Δ = Fine-tuned − Base. For lower-is-better metrics, delta is sign-inverted so positive always means better.",
        ] if baseline and finetuned else ["Awaiting both baseline and fine-tuned results."],
    }


@router.post("/{experiment_id}/robustness")
def run_robustness(experiment_id: str, is_baseline: bool = True,
                   max_samples: Optional[int] = None, db: Session = Depends(get_db)):
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    mv_id = exp.base_model_version_id if is_baseline else exp.fine_tuned_model_version_id
    if not mv_id:
        raise HTTPException(400, "No model version available for robustness testing")
    mv = db.get(ModelVersion, mv_id)
    inference = InferenceService()
    # Load model
    inference.load_model(mv)
    # Get baseline macro_f1 for scoring
    baseline_eval = db.query(EvaluationRun).filter(
        EvaluationRun.experiment_id == experiment_id,
        EvaluationRun.is_baseline == is_baseline,
        EvaluationRun.status == "COMPLETED",
    ).first()
    baseline_f1 = None
    if baseline_eval:
        baseline_f1 = baseline_eval.metrics_json.get("macro_f1")
    svc = RobustnessService(db, inference)
    runs = svc.run_all_perturbations(
        exp, mv, is_baseline=is_baseline,
        baseline_macro_f1=baseline_f1, max_samples=max_samples,
    )
    return {"status": "completed", "runs": len(runs)}
