"""Tests for schema validation."""

from slmforge.services.data.validation import SchemaValidator


def test_valid_vulnerable_sample():
    v = SchemaValidator()
    sample = {
        "id": "t1",
        "input": "import os; os.system(user_input)",
        "label": "vulnerable",
        "category": "COMMAND_INJECTION",
        "severity": "HIGH",
        "evidence": "Command injection",
    }
    result = v.validate_sample(sample)
    assert result.is_valid
    assert result.normalized is not None
    assert result.normalized["label"] == "vulnerable"


def test_valid_safe_sample():
    v = SchemaValidator()
    sample = {
        "id": "t2",
        "input": "print('hello')",
        "label": "safe",
    }
    result = v.validate_sample(sample)
    assert result.is_valid
    assert result.normalized["label"] == "safe"
    assert result.normalized["category"] == "NONE"


def test_missing_input():
    v = SchemaValidator()
    result = v.validate_sample({"id": "t3", "label": "safe"})
    assert not result.is_valid
    assert any("missing_or_empty_field:input" in i for i in result.issues)


def test_label_normalization():
    v = SchemaValidator()
    for val in ["1", "true", "YES", "Vulnerable", "bad"]:
        r = v.validate_sample({"id": "x", "input": "code", "label": val})
        assert r.normalized["label"] == "vulnerable"
    for val in ["0", "false", "NO", "benign", "clean"]:
        r = v.validate_sample({"id": "x", "input": "code", "label": val})
        assert r.normalized["label"] == "safe"


def test_field_aliasing():
    v = SchemaValidator()
    sample = {
        "sample_id": "t4",
        "code": "SELECT * FROM users",
        "is_vulnerable": True,
        "vuln_type": "SQL_INJECTION",
        "sev": "HIGH",
        "reason": "SQLi",
    }
    result = v.validate_sample(sample)
    assert result.is_valid
    assert result.normalized["id"] == "t4"
    assert result.normalized["input"] == "SELECT * FROM users"
    assert result.normalized["label"] == "vulnerable"
    assert result.normalized["category"] == "SQL_INJECTION"
    assert result.normalized["severity"] == "HIGH"


def test_batch_validation_counts(demo_samples):
    v = SchemaValidator()
    if not demo_samples:
        return
    valid, stats = v.validate_batch(demo_samples)
    assert stats.total == len(demo_samples)
    assert stats.valid > 0
    assert stats.valid + stats.invalid == stats.total
