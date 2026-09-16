"""Classification and structured-output metrics.

All metrics are computed from actual predictions — nothing is fabricated.
Confidence intervals are provided via bootstrap where statistically appropriate.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
)


@dataclass
class MetricReport:
    """Complete evaluation report."""
    n_samples: int = 0
    # Classification
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    macro_f1: float = 0.0
    weighted_f1: float = 0.0
    confusion_matrix: Dict[str, Any] = field(default_factory=dict)
    # Structured output
    json_validity_rate: float = 0.0
    schema_validity_rate: float = 0.0
    category_accuracy: float = 0.0
    severity_accuracy: float = 0.0
    evidence_presence_rate: float = 0.0
    # Efficiency
    latency_mean_ms: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    tokens_per_sec_mean: Optional[float] = None
    peak_memory_mb_mean: Optional[float] = None
    # Reliability
    malformed_output_rate: float = 0.0
    abstention_rate: float = 0.0
    # Confidence intervals (bootstrap)
    confidence_intervals: Dict[str, Any] = field(default_factory=dict)
    # Error breakdown
    error_distribution: Dict[str, int] = field(default_factory=dict)
    per_class_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_samples": self.n_samples,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "macro_f1": self.macro_f1,
            "weighted_f1": self.weighted_f1,
            "confusion_matrix": self.confusion_matrix,
            "json_validity_rate": self.json_validity_rate,
            "schema_validity_rate": self.schema_validity_rate,
            "category_accuracy": self.category_accuracy,
            "severity_accuracy": self.severity_accuracy,
            "evidence_presence_rate": self.evidence_presence_rate,
            "latency_mean_ms": self.latency_mean_ms,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "tokens_per_sec_mean": self.tokens_per_sec_mean,
            "peak_memory_mb_mean": self.peak_memory_mb_mean,
            "malformed_output_rate": self.malformed_output_rate,
            "abstention_rate": self.abstention_rate,
            "confidence_intervals": self.confidence_intervals,
            "error_distribution": self.error_distribution,
            "per_class_metrics": self.per_class_metrics,
        }


class MetricsCalculator:
    """Compute classification, structured-output, and efficiency metrics."""

    POSITIVE_LABEL = "vulnerable"
    NEGATIVE_LABEL = "safe"
    LABELS = ["safe", "vulnerable"]

    def compute(
        self,
        predictions: List[Dict[str, Any]],
        *,
        bootstrap_ci: bool = True,
        n_bootstrap: int = 1000,
        seed: int = 42,
    ) -> MetricReport:
        """Compute full metric report from a list of prediction records.

        Each prediction record should have keys:
            ground_truth_label, predicted_label, is_json_valid, is_schema_valid,
            predicted_category, ground_truth_category, predicted_severity,
            ground_truth_severity, predicted_evidence, latency_ms, tokens_per_sec,
            peak_memory_mb, error_type.
        """
        n = len(predictions)
        report = MetricReport(n_samples=n)
        if n == 0:
            return report

        y_true: List[str] = []
        y_pred: List[str] = []
        latencies: List[float] = []
        tpsec: List[float] = []
        peak_mem: List[float] = []
        errors: Dict[str, int] = {}
        cat_correct = 0
        cat_total = 0
        sev_correct = 0
        sev_total = 0
        json_valid = 0
        schema_valid = 0
        evidence_present = 0
        malformed = 0
        abstained = 0

        for p in predictions:
            gt = p.get("ground_truth_label")
            pr = p.get("predicted_label")
            y_true.append(gt or "safe")
            y_pred.append(pr if pr in self.LABELS else "safe")  # default to safe on failure

            latencies.append(float(p.get("latency_ms", 0)))

            tps = p.get("tokens_per_sec")
            if tps is not None:
                tpsec.append(float(tps))

            pm = p.get("peak_memory_mb")
            if pm is not None:
                peak_mem.append(float(pm))

            if p.get("is_json_valid"):
                json_valid += 1
            if p.get("is_schema_valid"):
                schema_valid += 1
            else:
                malformed += 1

            ev = p.get("predicted_evidence")
            if ev and isinstance(ev, str) and len(ev.strip()) > 5:
                evidence_present += 1

            err_type = p.get("error_type")
            if err_type:
                errors[err_type] = errors.get(err_type, 0) + 1

            # Category / severity accuracy (only count when ground truth exists)
            gt_cat = p.get("ground_truth_category")
            pr_cat = p.get("predicted_category")
            if gt_cat and gt_cat != "NONE":
                cat_total += 1
                if pr_cat and pr_cat.upper() == gt_cat.upper():
                    cat_correct += 1

            gt_sev = p.get("ground_truth_severity")
            pr_sev = p.get("predicted_severity")
            if gt_sev and gt_sev != "NONE":
                sev_total += 1
                if pr_sev and pr_sev.upper() == gt_sev.upper():
                    sev_correct += 1

            if err_type == "ABSTENTION" or pr is None:
                abstained += 1

        # ── Classification metrics ──────────────────────────────────────
        report.accuracy = float(accuracy_score(y_true, y_pred))
        labels = self.LABELS
        report.precision = float(precision_score(y_true, y_pred, pos_label=self.POSITIVE_LABEL,
                                                  zero_division=0))
        report.recall = float(recall_score(y_true, y_pred, pos_label=self.POSITIVE_LABEL,
                                            zero_division=0))
        report.f1 = float(f1_score(y_true, y_pred, pos_label=self.POSITIVE_LABEL, zero_division=0))
        report.macro_f1 = float(f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0))
        report.weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", labels=labels, zero_division=0))

        cm = confusion_matrix(y_true, y_pred, labels=labels)
        report.confusion_matrix = {
            "labels": labels,
            "matrix": cm.tolist(),
        }

        # Per-class breakdown
        try:
            report.per_class_metrics = classification_report(
                y_true, y_pred, labels=labels, output_dict=True, zero_division=0
            )
        except Exception:
            report.per_class_metrics = {}

        # ── Structured output ───────────────────────────────────────────
        report.json_validity_rate = json_valid / n
        report.schema_validity_rate = schema_valid / n
        report.category_accuracy = (cat_correct / cat_total) if cat_total > 0 else 0.0
        report.severity_accuracy = (sev_correct / sev_total) if sev_total > 0 else 0.0
        report.evidence_presence_rate = evidence_present / n

        # ── Efficiency ──────────────────────────────────────────────────
        if latencies:
            arr = np.array(latencies)
            report.latency_mean_ms = float(arr.mean())
            report.latency_p50_ms = float(np.percentile(arr, 50))
            report.latency_p95_ms = float(np.percentile(arr, 95))
            report.latency_p99_ms = float(np.percentile(arr, 99))
        if tpsec:
            report.tokens_per_sec_mean = float(np.mean(tpsec))
        if peak_mem:
            report.peak_memory_mb_mean = float(np.mean(peak_mem))

        # ── Reliability ─────────────────────────────────────────────────
        report.malformed_output_rate = malformed / n
        report.abstention_rate = abstained / n
        report.error_distribution = errors

        # ── Bootstrap CIs ───────────────────────────────────────────────
        if bootstrap_ci and n >= 30:
            report.confidence_intervals = self._bootstrap_ci(
                y_true, y_pred, n_bootstrap=n_bootstrap, seed=seed
            )

        return report

    def _bootstrap_ci(
        self,
        y_true: List[str],
        y_pred: List[str],
        n_bootstrap: int = 1000,
        seed: int = 42,
        alpha: float = 0.05,
    ) -> Dict[str, Any]:
        """Bootstrap 95% confidence intervals for macro F1 and accuracy."""
        rng = random.Random(seed)
        n = len(y_true)
        accs, f1s = [], []
        for _ in range(n_bootstrap):
            idx = [rng.randint(0, n - 1) for _ in range(n)]
            yt = [y_true[i] for i in idx]
            yp = [y_pred[i] for i in idx]
            try:
                accs.append(accuracy_score(yt, yp))
                f1s.append(f1_score(yt, yp, average="macro", labels=self.LABELS, zero_division=0))
            except Exception:
                continue
        if not accs:
            return {}
        accs.sort()
        f1s.sort()
        lo, hi = int(n_bootstrap * alpha / 2), int(n_bootstrap * (1 - alpha / 2))
        return {
            "accuracy_95ci": [round(accs[lo], 4), round(accs[min(hi, len(accs) - 1)], 4)],
            "macro_f1_95ci": [round(f1s[lo], 4), round(f1s[min(hi, len(f1s) - 1)], 4)],
            "n_bootstrap": n_bootstrap,
        }


def compare_metrics(base: MetricReport, finetuned: MetricReport) -> List[Dict[str, Any]]:
    """Generate delta comparison between base and fine-tuned reports.

    Returns a list of {name, base_value, finetuned_value, delta, higher_is_better, unit}.
    Delta = Finetuned - Base.
    """
    METRIC_SPEC = [
        ("accuracy", True, None),
        ("precision", True, None),
        ("recall", True, None),
        ("f1", True, None),
        ("macro_f1", True, None),
        ("weighted_f1", True, None),
        ("json_validity_rate", True, None),
        ("schema_validity_rate", True, None),
        ("category_accuracy", True, None),
        ("severity_accuracy", True, None),
        ("evidence_presence_rate", True, None),
        ("malformed_output_rate", False, None),
        ("abstention_rate", False, None),
        ("latency_mean_ms", False, "ms"),
        ("latency_p95_ms", False, "ms"),
        ("tokens_per_sec_mean", True, "tokens/s"),
    ]
    results = []
    for name, higher_is_better, unit in METRIC_SPEC:
        bv = getattr(base, name, None)
        fv = getattr(finetuned, name, None)
        delta: Optional[float] = None
        note: Optional[str] = None
        if bv is not None and fv is not None:
            delta = round(fv - bv, 6)
            if not higher_is_better:
                # Reverse sign for display so positive always means "better"
                delta = -delta
                note = "lower is better (delta inverted for comparison)"
        results.append({
            "name": name,
            "base_value": bv,
            "finetuned_value": fv,
            "delta": delta,
            "higher_is_better": higher_is_better,
            "unit": unit,
            "note": note,
        })
    return results
