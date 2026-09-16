"""Tests for JSON parsing utilities."""

import json

from slmforge.utils.json_utils import (
    extract_json_from_text, parse_json_output, validate_structured_output,
)


def test_extract_plain_json():
    text = '{"vulnerable": true, "category": "SQL_INJECTION", "severity": "HIGH", "evidence": "test"}'
    extracted = extract_json_from_text(text)
    assert extracted is not None
    parsed = json.loads(extracted)
    assert parsed["vulnerable"] is True


def test_extract_fenced_json():
    text = '''Some explanation text.
```json
{"vulnerable": false, "category": "NONE", "severity": "NONE", "evidence": "safe"}
```
'''
    extracted = extract_json_from_text(text)
    assert extracted is not None
    parsed = json.loads(extracted)
    assert parsed["vulnerable"] is False


def test_extract_json_with_prefix_text():
    text = '''I've analysed the code and determined it is safe.
{"vulnerable": false, "category": "NONE", "severity": "NONE", "evidence": "clean code"}'''
    extracted = extract_json_from_text(text)
    assert extracted is not None
    parsed = json.loads(extracted)
    assert parsed["vulnerable"] is False


def test_parse_valid():
    parsed, err = parse_json_output(
        '{"vulnerable": true, "category": "SQL_INJECTION", "severity": "HIGH", "evidence": "sqli"}'
    )
    assert err is None
    assert parsed is not None
    assert parsed["vulnerable"] is True


def test_parse_invalid():
    parsed, err = parse_json_output("no json here at all")
    assert parsed is None
    assert err == "NO_JSON_FOUND"


def test_validate_valid_output():
    obj = {"vulnerable": True, "category": "SQL_INJECTION", "severity": "HIGH", "evidence": "sqli"}
    is_valid, issues = validate_structured_output(obj)
    assert is_valid
    assert issues == []


def test_validate_missing_fields():
    obj = {"vulnerable": True}
    is_valid, issues = validate_structured_output(obj)
    assert not is_valid
    assert any("Missing fields" in i for i in issues)
