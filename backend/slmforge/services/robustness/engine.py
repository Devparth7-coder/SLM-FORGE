"""Robustness evaluation engine.

For each perturbation type, re-runs inference on the perturbed test set and
compares metrics against baseline. Every metric is defined mathematically:

  RobustnessScore(p) = Macro-F1(p) / Macro-F1(baseline)   (range 0-1 typically; >1 = better)
  PerformanceDegradation(p) = Macro-F1(baseline) - Macro-F1(p)
  OverallRobustnessScore = mean over all perturbations of RobustnessScore(p)

All scores are computed from actual measurements.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from slmforge.core.logging import get_logger
from slmforge.db.models.dataset import DatasetSample, DatasetVersion
from slmforge.db.models.experiment import EvaluationRun, Experiment, RobustnessRun
from slmforge.db.models.model import ModelVersion
from slmforge.services.evaluation.metrics import MetricsCalculator
from slmforge.services.model.inference import InferenceService
from slmforge.services.robustness.perturbations import apply_perturbation, list_perturbations
from slmforge.utils.seeding import set_seed

logger = get_logger(__name__)


class RobustnessService:
    """Run robustness evaluations for a model across perturbation types."""

    def __init__(self, db: Session, inference: Optional[InferenceService] = None) -> None:
        self.db = db
        self.inference = inference or InferenceService()
        self.metrics = MetricsCalculator()

    def run_all_perturbations(
        self,
        experiment: Experiment,
        model_version: ModelVersion,
        *,
        is_baseline: bool,
        baseline_macro_f1: Optional[float] = None,
        max_samples: Optional[int] = None,
    ) -> List[RobustnessRun]:
        """Run all registered perturbations and persist results."""
        set_seed(experiment.seed)
        dataset_version = self.db.get(DatasetVersion, experiment.dataset_version_id)
        if not dataset_version:
            return []

        samples = (
            self.db.query(DatasetSample)
            .filter(DatasetSample.version_id == dataset_version.id)
            .filter(DatasetSample.split == "test")
            .order_by(DatasetSample.sample_index)
            .all()
        )
        if max_samples:
            samples = samples[:max_samples]

        runs: List[RobustnessRun] = []
        for perturb_name in list_perturbations():
            if perturb_name == "noop":
                continue
            run = self._run_single_perturbation(
                experiment, model_version, samples,
                perturb_name, is_baseline=is_baseline,
                baseline_macro_f1=baseline_macro_f1,
            )
            runs.append(run)
        return runs

    def _run_single_perturbation(
        self,
        experiment: Experiment,
        model_version: ModelVersion,
        samples: List[DatasetSample],
        perturbation_type: str,
        *,
        is_baseline: bool,
        baseline_macro_f1: Optional[float],
    ) -> RobustnessRun:
        run = RobustnessRun(
            experiment_id=experiment.id,
            model_version_id=model_version.id,
            is_baseline=is_baseline,
            status="RUNNING",
            perturbation_type=perturbation_type,
            perturbation_config={"seed": experiment.seed},
        )
        self.db.add(run)
        self.db.commit()

        try:
            predictions = []
            for sample in samples:
                perturbed_code = apply_perturbation(
                    sample.input_text, perturbation_type, seed=experiment.seed
                )
                result = self.inference.predict(
                    model_version, perturbed_code, max_new_tokens=256, temperature=0.0,
                    seed=experiment.seed,
                )
                parsed = result.parsed_output or {}
                pred_label = "vulnerable" if parsed.get("vulnerable") else "safe" if parsed else None
                predictions.append({
                    "sample_id": sample.sample_id,
                    "ground_truth_label": sample.label,
                    "ground_truth_category": sample.category,
                    "ground_truth_severity": sample.severity,
                    "predicted_label": pred_label,
                    "predicted_category": parsed.get("category"),
                    "predicted_severity": parsed.get("severity"),
                    "predicted_evidence": parsed.get("evidence"),
                    "is_json_valid": result.is_json_valid,
                    "is_schema_valid": result.is_schema_valid,
                    "is_correct": pred_label == sample.label,
                    "latency_ms": result.latency_ms,
                    "error_type": result.error,
                })

            report = self.metrics.compute(predictions, bootstrap_ci=False)
            run.metrics_json = report.to_dict()
            run.sample_count = len(samples)

            if baseline_macro_f1 is not None and baseline_macro_f1 > 0:
                run.robustness_score = report.macro_f1 / baseline_macro_f1
                run.performance_degradation = baseline_macro_f1 - report.macro_f1

            run.status = "COMPLETED"
            logger.info(
                "robustness.perturbation_done",
                type=perturbation_type, macro_f1=report.macro_f1,
                robustness=run.robustness_score,
            )
        except Exception as exc:
            run.status = "FAILED"
            run.error_message = str(exc)
            logger.error("robustness.perturbation_failed", type=perturbation_type, error=str(exc))

        self.db.commit()
        return run
