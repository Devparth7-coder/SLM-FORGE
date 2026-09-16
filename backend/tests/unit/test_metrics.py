"""Tests for metrics calculation."""

import pytest
import sys
import importlib.util
spec = importlib.util.spec_from_file_location(
    "metrics", "/home/user/slm-forge/backend/slmforge/services/evaluation/metrics.py"
)
metrics = importlib.util.module_from_spec(spec)
sys.modules["metrics"] = metrics
spec.loader.exec_module(metrics)
MetricsCalculator = metrics.MetricsCalculator


def _make_prediction(gt, pr, json_valid=True, latency=10.0):
    return {
        "ground_truth_label": gt,
        "predicted_label": pr,
        "predicted_category": "NONE",
        "predicted_severity": "NONE",
        "predicted_evidence": "ev",
        "is_json_valid": json_valid,
        "is_schema_valid": json_valid,
        "latency_ms": latency,
    }


def approx(v):
    return pytest.approx(v, abs=0.01)


def test_perfect_classification():
    calc = MetricsCalculator()
    preds = [
        _make_prediction("vulnerable", "vulnerable"),
        _make_prediction("safe", "safe"),
        _make_prediction("vulnerable", "vulnerable"),
        _make_prediction("safe", "safe"),
    ]
    report = calc.compute(preds, bootstrap_ci=False)
    assert report.accuracy == 1.0
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.f1 == 1.0


def test_all_wrong():
    calc = MetricsCalculator()
    preds = [
        _make_prediction("vulnerable", "safe"),
        _make_prediction("safe", "vulnerable"),
    ]
    report = calc.compute(preds, bootstrap_ci=False)
    assert report.accuracy == 0.0
    assert report.f1 == 0.0


def test_latency_stats():
    calc = MetricsCalculator()
    preds = [
        _make_prediction("vulnerable", "vulnerable", latency=10),
        _make_prediction("safe", "safe", latency=20),
        _make_prediction("vulnerable", "vulnerable", latency=30),
        _make_prediction("safe", "safe", latency=40),
    ]
    report = calc.compute(preds, bootstrap_ci=False)
    assert report.n_samples == 4
    assert report.latency_mean_ms == 25.0
    assert report.latency_p50_ms == approx(25.0)


def test_json_validity_rate():
    calc = MetricsCalculator()
    preds = [
        _make_prediction("vulnerable", "vulnerable", json_valid=True),
        _make_prediction("safe", "safe", json_valid=False),
        _make_prediction("vulnerable", "vulnerable", json_valid=True),
        _make_prediction("safe", "safe", json_valid=True),
    ]
    report = calc.compute(preds, bootstrap_ci=False)
    assert report.json_validity_rate == 0.75
