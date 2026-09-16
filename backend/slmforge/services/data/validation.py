"""Dataset schema validation and normalization.

Every sample must conform to a canonical schema before entering the pipeline.
Malformed records are counted and reported -- never silently deleted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

VALID_VULN_LABELS = {"vulnerable", "safe"}
VALID_CATEGORIES = {
    "SQL_INJECTION", "XSS", "COMMAND_INJECTION", "PATH_TRAVERSAL",
    "BUFFER_OVERFLOW", "INSECURE_CRYPTO", "HARDCODED_SECRET", "INTEGER_OVERFLOW",
    "RACE_CONDITION", "DESERIALIZATION", "AUTH_BYPASS", "INFORMATION_DISCLOSURE",
    "NULL_DEREFERENCE", "USE_AFTER_FREE", "MEMORY_LEAK", "IMPROPER_AUTH",
    "CSRF", "SSRF", "OPEN_REDIRECT", "INSECURE_CONFIG",
    "CODE_INJECTION", "FORMAT_STRING", "OTHER", "NONE",
    "",  # Allow empty for safe samples
}
VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "NONE", ""}

CANONICAL_SAMPLE_FIELDS = {"id", "input", "label", "category", "severity", "evidence", "metadata"}


@dataclass
class ValidationResult:
    """Result of validating a single sample."""
    is_valid: bool
    normalized: Optional[Dict[str, Any]] = None
    issues: List[str] = field(default_factory=list)


@dataclass
class BatchValidationStats:
    """Aggregate statistics for a batch of validated samples."""
    total: int = 0
    valid: int = 0
    invalid: int = 0
    issues_counter: Dict[str, int] = field(default_factory=dict)
    invalid_samples: List[Tuple[int, Dict[str, Any], List[str]]] = field(default_factory=list)


class SchemaValidator:
    """Validates and normalizes samples to the canonical schema.

    Canonical sample (after normalization):
    {
        "id": str,
        "input": str,
        "label": str,          # "vulnerable" | "safe"
        "category": str,       # CWE-style category or "NONE"
        "severity": str,       # CRITICAL/HIGH/MEDIUM/LOW/INFO/NONE
        "evidence": str,       # human-readable explanation
        "metadata": dict,
    }
    """

    def __init__(
        self,
        required_fields: set = frozenset({"id", "input", "label"}),
        field_aliases: Optional[Dict[str, str]] = None,
    ) -> None:
        self.required_fields = required_fields
        self.field_aliases = field_aliases or self._default_aliases()

    @staticmethod
    def _default_aliases() -> Dict[str, str]:
        """Map common alternate field names to canonical names."""
        return {
            "code": "input", "snippet": "input", "source": "input", "text": "input",
            "source_code": "input", "function": "input",
            "is_vulnerable": "label", "vuln": "label", "target": "label",
            "vuln_type": "category", "cwe": "category", "type": "category",
            "vulnerability_type": "category",
            "sev": "severity", "impact": "severity",
            "reason": "evidence", "explanation": "evidence", "description": "evidence",
            "sample_id": "id", "idx": "id", "index": "id",
        }

    def normalize_field_names(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """Rename alias fields to canonical names (case-insensitive)."""
        normalized: Dict[str, Any] = {}
        rev_alias = {k.lower(): v for k, v in self.field_aliases.items()}
        for key, val in sample.items():
            low = key.lower()
            canonical = rev_alias.get(low, key.lower())
            normalized[canonical] = val
        return normalized

    def validate_sample(self, sample: Dict[str, Any], idx: int = 0) -> ValidationResult:
        """Validate a single sample; return a result with normalized data or issues."""
        issues: List[str] = []

        if not isinstance(sample, dict):
            return ValidationResult(is_valid=False, issues=["not_a_dictionary"])

        norm = self.normalize_field_names(sample)

        # Check required fields
        for fld in self.required_fields:
            if fld not in norm or norm[fld] is None or (isinstance(norm[fld], str) and not norm[fld].strip()):
                issues.append(f"missing_or_empty_field:{fld}")

        # 'input' must be a non-empty string
        if "input" in norm and norm["input"] is not None:
            if not isinstance(norm["input"], str):
                issues.append("input_not_string")
                norm["input"] = str(norm["input"])
            elif len(norm["input"].strip()) < 5:
                issues.append("input_too_short")

        # 'id' must be serializable
        if "id" in norm:
            norm["id"] = str(norm["id"])

        # Normalize 'label' to "vulnerable"/"safe"
        if "label" in norm and norm["label"] is not None:
            label_raw = str(norm["label"]).strip().lower()
            if label_raw in {"1", "true", "vulnerable", "yes", "vuln", "positive", "bad"}:
                norm["label"] = "vulnerable"
            elif label_raw in {"0", "false", "safe", "no", "benign", "negative", "good", "none", "clean"}:
                norm["label"] = "safe"
            elif label_raw == "":
                issues.append("empty_label")
            else:
                issues.append(f"invalid_label:{label_raw}")
        else:
            norm["label"] = None

        # Category normalization
        if "category" in norm and norm["category"] is not None:
            cat = str(norm["category"]).strip().upper().replace(" ", "_").replace("-", "_")
            if cat in VALID_CATEGORIES or cat == "":
                norm["category"] = cat if cat else "NONE"
            else:
                # Accept unknown categories but note them
                norm["category"] = cat
                issues.append(f"unknown_category:{cat}")
        elif norm.get("label") == "vulnerable":
            issues.append("vulnerable_without_category")
            norm["category"] = "OTHER"
        else:
            norm["category"] = "NONE"

        # Severity normalization
        if "severity" in norm and norm["severity"] is not None:
            sev = str(norm["severity"]).strip().upper()
            if sev in VALID_SEVERITIES:
                norm["severity"] = sev if sev else "NONE"
            else:
                norm["severity"] = "NONE"
                issues.append(f"unknown_severity:{sev}")
        elif norm.get("label") == "vulnerable":
            norm["severity"] = "MEDIUM"  # default
        else:
            norm["severity"] = "NONE"

        # Evidence
        if "evidence" not in norm or norm["evidence"] is None:
            norm["evidence"] = ""

        # Metadata
        if "metadata" not in norm or not isinstance(norm.get("metadata"), dict):
            norm["metadata"] = {}

        # Make sure all canonical fields exist
        canonical = {
            "id": norm.get("id", f"sample_{idx}"),
            "input": norm.get("input", ""),
            "label": norm.get("label"),
            "category": norm.get("category", "NONE"),
            "severity": norm.get("severity", "NONE"),
            "evidence": norm.get("evidence", ""),
            "metadata": norm.get("metadata", {}),
        }
        # Preserve extra fields as metadata
        for k, v in norm.items():
            if k not in CANONICAL_SAMPLE_FIELDS:
                canonical["metadata"][k] = v

        is_valid = not any(
            issue.startswith("missing_") or issue.startswith("input_not_string")
            or issue.startswith("empty_label")
            for issue in issues
        )

        return ValidationResult(is_valid=is_valid, normalized=canonical, issues=issues)

    def validate_batch(self, samples: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], BatchValidationStats]:
        """Validate a list of samples; return (valid_samples, stats)."""
        stats = BatchValidationStats(total=len(samples))
        valid: List[Dict[str, Any]] = []
        for idx, sample in enumerate(samples):
            result = self.validate_sample(sample, idx=idx)
            if result.is_valid and result.normalized is not None:
                valid.append(result.normalized)
                stats.valid += 1
            else:
                stats.invalid += 1
                stats.invalid_samples.append((idx, sample, result.issues))
            for issue in result.issues:
                stats.issues_counter[issue] = stats.issues_counter.get(issue, 0) + 1
        return valid, stats
