"""Data quality analysis and reporting.

Generates comprehensive quality reports: label distribution, length statistics,
malformed code detection, class balance, leakage warnings.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from slmforge.services.data.validation import VALID_VULN_LABELS, VALID_CATEGORIES, VALID_SEVERITIES


@dataclass
class QualityReport:
    total_samples: int = 0
    missing_fields_count: int = 0
    invalid_labels_count: int = 0
    duplicate_count: int = 0
    near_duplicate_count: int = 0
    duplicate_rate: float = 0.0
    near_duplicate_rate: float = 0.0
    short_samples_count: int = 0
    long_samples_count: int = 0
    malformed_code_count: int = 0
    train_test_overlap: int = 0
    potential_leakage: bool = False
    label_distribution: Dict[str, int] = field(default_factory=dict)
    category_distribution: Dict[str, int] = field(default_factory=dict)
    severity_distribution: Dict[str, int] = field(default_factory=dict)
    length_stats: Dict[str, float] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "missing_fields_count": self.missing_fields_count,
            "invalid_labels_count": self.invalid_labels_count,
            "duplicate_count": self.duplicate_count,
            "near_duplicate_count": self.near_duplicate_count,
            "duplicate_rate": self.duplicate_rate,
            "near_duplicate_rate": self.near_duplicate_rate,
            "short_samples_count": self.short_samples_count,
            "long_samples_count": self.long_samples_count,
            "malformed_code_count": self.malformed_code_count,
            "train_test_overlap": self.train_test_overlap,
            "potential_leakage": self.potential_leakage,
            "label_distribution": self.label_distribution,
            "category_distribution": self.category_distribution,
            "severity_distribution": self.severity_distribution,
            "length_stats": self.length_stats,
            "issues": self.issues,
        }


class DataQualityService:
    """Analyse a cleaned dataset and produce a quality report."""

    SHORT_SAMPLE_THRESHOLD = 30    # characters
    LONG_SAMPLE_THRESHOLD = 8000   # characters

    def __init__(
        self,
        short_threshold: int = SHORT_SAMPLE_THRESHOLD,
        long_threshold: int = LONG_SAMPLE_THRESHOLD,
    ) -> None:
        self.short_threshold = short_threshold
        self.long_threshold = long_threshold

    def analyse(
        self,
        samples: List[Dict[str, Any]],
        *,
        duplicate_count: int = 0,
        near_duplicate_count: int = 0,
        invalid_count: int = 0,
        train_test_overlap: int = 0,
    ) -> QualityReport:
        """Generate a quality report for a list of canonical samples."""
        report = QualityReport(total_samples=len(samples))
        report.duplicate_count = duplicate_count
        report.near_duplicate_count = near_duplicate_count
        report.invalid_labels_count = invalid_count
        report.train_test_overlap = train_test_overlap
        report.potential_leakage = train_test_overlap > 0

        if samples:
            report.duplicate_rate = round(duplicate_count / len(samples), 4) if len(samples) > 0 else 0
            report.near_duplicate_rate = round(near_duplicate_count / len(samples), 4) if len(samples) > 0 else 0

        label_counts: Counter = Counter()
        category_counts: Counter = Counter()
        severity_counts: Counter = Counter()
        lengths: List[int] = []

        for sample in samples:
            # Missing fields
            missing = [f for f in ("input", "label") if not sample.get(f)]
            if missing:
                report.missing_fields_count += 1

            label = sample.get("label")
            if label:
                label_counts[label] += 1

            cat = sample.get("category")
            if cat:
                category_counts[cat] += 1

            sev = sample.get("severity")
            if sev:
                severity_counts[sev] += 1

            inp = str(sample.get("input", ""))
            length = len(inp)
            lengths.append(length)
            if length < self.short_threshold:
                report.short_samples_count += 1
            if length > self.long_threshold:
                report.long_samples_count += 1

            # Heuristic malformed code detection
            if self._looks_like_code(inp) and self._is_malformed_code(inp):
                report.malformed_code_count += 1

        report.label_distribution = dict(label_counts)
        report.category_distribution = dict(category_counts)
        report.severity_distribution = dict(severity_counts)

        if lengths:
            report.length_stats = {
                "mean": round(statistics.mean(lengths), 2),
                "median": round(statistics.median(lengths), 2),
                "stdev": round(statistics.stdev(lengths), 2) if len(lengths) > 1 else 0.0,
                "min": min(lengths),
                "max": max(lengths),
                "p5": round(sorted(lengths)[max(0, int(len(lengths) * 0.05))], 2),
                "p95": round(sorted(lengths)[min(len(lengths) - 1, int(len(lengths) * 0.95))], 2),
            }

        # ── Issue generation ─────────────────────────────────────────────
        total = len(samples)
        if total > 0:
            for lbl, count in label_counts.items():
                ratio = count / total
                if ratio > 0.95:
                    report.issues.append({
                        "severity": "warning",
                        "code": "SEVERE_CLASS_IMBALANCE",
                        "message": f"Label '{lbl}' dominates ({ratio:.1%}) — classification may be degenerate.",
                    })
            if report.duplicate_rate > 0.1:
                report.issues.append({
                    "severity": "warning",
                    "code": "HIGH_DUPLICATE_RATE",
                    "message": f"Duplicate rate is {report.duplicate_rate:.1%}.",
                })
            if report.near_duplicate_rate > 0.1:
                report.issues.append({
                    "severity": "warning",
                    "code": "HIGH_NEAR_DUPLICATE_RATE",
                    "message": f"Near-duplicate rate is {report.near_duplicate_rate:.1%}.",
                })
            if train_test_overlap > 0:
                report.issues.append({
                    "severity": "error",
                    "code": "TRAIN_TEST_LEAKAGE",
                    "message": f"{train_test_overlap} samples appear in both train and test splits.",
                })
            if report.short_samples_count > total * 0.05:
                report.issues.append({
                    "severity": "info",
                    "code": "MANY_SHORT_SAMPLES",
                    "message": f"{report.short_samples_count} samples are unusually short (<{self.short_threshold} chars).",
                })
            if report.malformed_code_count > 0:
                report.issues.append({
                    "severity": "info",
                    "code": "MALFORMED_CODE",
                    "message": f"{report.malformed_code_count} samples look like malformed code.",
                })

        return report

    @staticmethod
    def _looks_like_code(text: str) -> bool:
        """Heuristic: does the text look like source code?"""
        code_indicators = ["def ", "function", "class ", "import ", "#include", "<?php",
                           "public ", "private ", "return ", "if ", "for ", "while ",
                           "var ", "let ", "const ", "{", "}", ";", "()"]
        hits = sum(1 for ind in code_indicators if ind in text)
        return hits >= 2

    @staticmethod
    def _is_malformed_code(text: str) -> bool:
        """Simple heuristic for malformed/truncated code."""
        # Unbalanced brackets
        if text.count("{") != text.count("}"):
            return True
        if text.count("(") != text.count(")"):
            return True
        if text.count("[") != text.count("]"):
            return True
        # Truncated mid-statement
        stripped = text.rstrip()
        if stripped.endswith(("=", "+", "-", "*", "/", ",", ".", "&&", "||")):
            return True
        return False
