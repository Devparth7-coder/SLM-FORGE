"""Evaluation engine: run baseline or fine-tuned evaluation with the same harness."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from slmforge.core.config import settings
from slmforge.core.exceptions import EvaluationError, NotFoundError
from slmforge.core.logging import get_logger
from slmforge.db.models.dataset import DatasetSample, DatasetVersion
from slmforge.db.models.experiment import EvaluationRun, Experiment
from slmforge.db.models.model import ModelVersion
from slmforge.db.models.result import FailureEntry, MetricEntry, Prediction
from slmforge.services.evaluation.metrics import MetricsCalculator, MetricReport
from slmforge.services.model.inference import InferenceService
from slmforge.storage import get_storage_backend
from slmforge.utils.seeding import set_seed

logger = get_logger(__name__)

# ── Failure categories ────────────────────────────────────────────────────
FAILURE_CATEGORIES = {
    "false_positive", "false_negative", "wrong_category", "wrong_severity",
    "malformed_json", "missing_evidence", "uncertain_prediction", "robustness_failure",
}


def _categorise_failure(prediction_record: Dict[str, Any]) -> Optional[str]:
    """Categorise a failure based on prediction details."""
    if not prediction_record.get("is_json_valid"):
        return "malformed_json"
    gt = prediction_record.get("ground_truth_label")
    pr = prediction_record.get("predicted_label")
    if gt == "vulnerable" and pr != "vulnerable":
        return "false_negative"
    if gt == "safe" and pr == "vulnerable":
        return "false_positive"
    if gt == pr == "vulnerable":
        gt_cat = prediction_record.get("ground_truth_category")
        pr_cat = prediction_record.get("predicted_category")
        if gt_cat and pr_cat and gt_cat.upper() != pr_cat.upper():
            return "wrong_category"
        gt_sev = prediction_record.get("ground_truth_severity")
        pr_sev = prediction_record.get("predicted_severity")
        if gt_sev and pr_sev and gt_sev.upper() != pr_sev.upper():
            return "wrong_severity"
    ev = prediction_record.get("predicted_evidence")
    if not ev or len(str(ev).strip()) < 5:
        return "missing_evidence"
    return None


class EvaluationService:
    """Run standardised evaluation against a dataset version.

    The same harness is used for baseline and fine-tuned models — this is the
    single point of comparison, ensuring identical evaluation procedure.
    """

    def __init__(self, db: Session, inference: Optional[InferenceService] = None) -> None:
        self.db = db
        self.inference = inference or InferenceService()
        self.metrics = MetricsCalculator()
        self.storage = get_storage_backend()

    def run_evaluation(
        self,
        evaluation_run: EvaluationRun,
        *,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> MetricReport:
        """Execute an evaluation run and persist all results.

        Returns the computed MetricReport.
        """
        set_seed(42)
        eval_run = evaluation_run
        model_version: ModelVersion = self.db.get(ModelVersion, eval_run.model_version_id)
        if not model_version:
            raise NotFoundError(f"Model version {eval_run.model_version_id} not found")
        dataset_version: DatasetVersion = self.db.get(DatasetVersion, eval_run.dataset_version_id)
        if not dataset_version:
            raise NotFoundError(f"Dataset version {eval_run.dataset_version_id} not found")

        eval_run.status = "RUNNING"
        self.db.commit()

        try:
            # Load test samples
            query = (
                self.db.query(DatasetSample)
                .filter(DatasetSample.version_id == dataset_version.id)
                .filter(DatasetSample.split == eval_run.split)
                .order_by(DatasetSample.sample_index)
            )
            samples = query.all()
            if not samples:
                raise EvaluationError(f"No samples in split '{eval_run.split}'")

            predictions: List[Dict[str, Any]] = []
            prediction_rows: List[Prediction] = []
            failure_rows: List[FailureEntry] = []
            latencies: List[float] = []
            total = len(samples)
            eval_run.sample_count = total
            self.db.commit()

            logger.info("evaluation.start", eval_run=eval_run.id, n_samples=total,
                        baseline=eval_run.is_baseline)

            for idx, sample in enumerate(samples):
                try:
                    result = self.inference.predict(
                        model_version,
                        sample.input_text,
                        max_new_tokens=256,
                        temperature=0.0,
                    )
                    latencies.append(result.latency_ms)

                    parsed = result.parsed_output or {}
                    pred_label = None
                    pred_category = None
                    pred_severity = None
                    pred_evidence = None
                    if parsed:
                        pred_label = "vulnerable" if parsed.get("vulnerable") else "safe"
                        pred_category = parsed.get("category")
                        pred_severity = parsed.get("severity")
                        pred_evidence = parsed.get("evidence")

                    is_correct = (pred_label == sample.label)
                    category_correct = None
                    if sample.category and pred_category:
                        category_correct = (sample.category.upper() == (pred_category or "").upper())
                    severity_correct = None
                    if sample.severity and pred_severity:
                        severity_correct = (sample.severity.upper() == (pred_severity or "").upper())

                    record = {
                        "sample_id": sample.sample_id,
                        "ground_truth_label": sample.label,
                        "ground_truth_category": sample.category,
                        "ground_truth_severity": sample.severity,
                        "predicted_label": pred_label,
                        "predicted_category": pred_category,
                        "predicted_severity": pred_severity,
                        "predicted_evidence": pred_evidence,
                        "raw_output": result.raw_output,
                        "parsed_output": parsed,
                        "is_json_valid": result.is_json_valid,
                        "is_schema_valid": result.is_schema_valid,
                        "is_correct": is_correct,
                        "category_correct": category_correct,
                        "severity_correct": severity_correct,
                        "latency_ms": result.latency_ms,
                        "tokens_per_sec": result.tokens_per_sec,
                        "peak_memory_mb": result.peak_memory_mb,
                        "error_type": result.error,
                    }
                    predictions.append(record)

                    pred_row = Prediction(
                        evaluation_run_id=eval_run.id,
                        sample_id=sample.sample_id,
                        ground_truth_label=sample.label,
                        ground_truth_category=sample.category,
                        ground_truth_severity=sample.severity,
                        predicted_label=pred_label,
                        predicted_category=pred_category,
                        predicted_severity=pred_severity,
                        predicted_evidence=pred_evidence,
                        raw_output=result.raw_output,
                        parsed_output=parsed,
                        is_json_valid=result.is_json_valid,
                        is_schema_valid=result.is_schema_valid,
                        is_correct=is_correct,
                        category_correct=category_correct,
                        severity_correct=severity_correct,
                        latency_ms=result.latency_ms,
                        error_type=result.error,
                    )
                    prediction_rows.append(pred_row)

                    failure_type = _categorise_failure(record)
                    if failure_type:
                        failure_rows.append(FailureEntry(
                            evaluation_run_id=eval_run.id,
                            sample_id=sample.sample_id,
                            failure_type=failure_type,
                            input_preview=sample.input_text[:500],
                            ground_truth={
                                "label": sample.label,
                                "category": sample.category,
                                "severity": sample.severity,
                                "evidence": sample.evidence,
                            },
                            category=sample.category,
                            severity=sample.severity,
                            latency_ms=result.latency_ms,
                            notes=None,
                        ))
                except Exception as exc:
                    logger.error("evaluation.sample_failed", sample=sample.sample_id, error=str(exc))
                    continue

                if progress_callback and (idx % 5 == 0 or idx == total - 1):
                    progress_callback(idx + 1, total)

            # Compute metrics
            report = self.metrics.compute(predictions)

            # Persist predictions as JSONL artifact
            pred_key = f"evaluations/{eval_run.id}/predictions.jsonl"
            lines = [json.dumps(p, default=str) for p in predictions]
            self.storage.store_bytes(pred_key, "\n".join(lines).encode("utf-8"),
                                     content_type="application/x-jsonlines")

            failures_key = f"evaluations/{eval_run.id}/failures.json"
            failure_list = [{
                "sample_id": f.sample_id,
                "failure_type": f.failure_type,
                "category": f.category,
                "severity": f.severity,
            } for f in failure_rows]
            self.storage.store_bytes(failures_key, json.dumps(failure_list, indent=2).encode("utf-8"),
                                     content_type="application/json")

            # Update eval run
            eval_run.status = "COMPLETED"
            eval_run.metrics_json = report.to_dict()
            eval_run.confusion_matrix = report.confusion_matrix
            eval_run.latency_stats_ms = {
                "mean": report.latency_mean_ms,
                "p50": report.latency_p50_ms,
                "p95": report.latency_p95_ms,
                "p99": report.latency_p99_ms,
            }
            eval_run.error_distribution = report.error_distribution
            eval_run.predictions_path = pred_key
            eval_run.failures_path = failures_key

            # Insert rows (bulk)
            self.db.bulk_save_objects(prediction_rows)
            self.db.bulk_save_objects(failure_rows)

            # Insert metric rows
            metric_names = [
                "accuracy", "precision", "recall", "f1", "macro_f1", "weighted_f1",
                "json_validity_rate", "schema_validity_rate", "category_accuracy",
                "severity_accuracy", "malformed_output_rate", "abstention_rate",
                "latency_mean_ms", "latency_p95_ms",
            ]
            metric_rows = []
            for name in metric_names:
                val = getattr(report, name, None)
                if val is not None:
                    metric_rows.append(MetricEntry(
                        evaluation_run_id=eval_run.id,
                        name=name,
                        value=float(val),
                        metric_type="evaluation",
                    ))
            self.db.bulk_save_objects(metric_rows)

            self.db.commit()
            logger.info("evaluation.complete", eval_run=eval_run.id, accuracy=report.accuracy,
                        f1=report.f1, macro_f1=report.macro_f1)
            return report

        except Exception as exc:
            eval_run.status = "FAILED"
            eval_run.error_message = str(exc)
            self.db.commit()
            logger.error("evaluation.failed", eval_run=eval_run.id, error=str(exc))
            raise EvaluationError(f"Evaluation failed: {exc}", cause=exc) from exc
