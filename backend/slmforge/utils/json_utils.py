"""Robust JSON parsing and structured output validation for model outputs."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

# Canonical schema for vulnerability classification outputs.
VULN_SCHEMA_REQUIRED = {"vulnerable", "category", "severity", "evidence"}
VULN_CATEGORIES = {
    "SQL_INJECTION", "XSS", "COMMAND_INJECTION", "PATH_TRAVERSAL",
    "BUFFER_OVERFLOW", "INSECURE_CRYPTO", "HARDCODED_SECRET", "INTEGER_OVERFLOW",
    "RACE_CONDITION", "DESERIALIZATION", "AUTH_BYPASS", "INFORMATION_DISCLOSURE",
    "NULL_DEREFERENCE", "USE_AFTER_FREE", "MEMORY_LEAK", "IMPROPER_AUTH",
    "CROSS_SITE_REQUEST_FORGERY", "SSRF", "OPEN_REDIRECT", "INSECURE_CONFIG",
    "MISSING_AUTH", "CODE_INJECTION", "FORMAT_STRING", "OTHER", "NONE",
}
VULN_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "NONE"}


def extract_json_from_text(text: str) -> Optional[str]:
    """Extract the first JSON object {...} or array [...] from a model output.

    Handles cases where the model wraps the JSON in markdown fences, explanatory
    text, or produces extra output before/after the JSON.
    """
    if not text:
        return None
    # Try fenced code blocks first: ```json ... ```
    fenced = re.search(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    # Find the first { ... } that parses
    brace_start = text.find("{")
    bracket_start = text.find("[")
    start = min(p for p in [brace_start, bracket_start] if p >= 0) if (brace_start >= 0 or bracket_start >= 0) else -1
    if start < 0:
        return None
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_json_output(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse a model's raw text output into (parsed_json, error_message).

    Returns (None, error_message) on failure; returns (dict, None) on success.
    """
    extracted = extract_json_from_text(text)
    if extracted is None:
        return None, "NO_JSON_FOUND"
    try:
        parsed = json.loads(extracted)
    except json.JSONDecodeError as e:
        return None, f"JSON_DECODE_ERROR: {e.msg} at position {e.pos}"
    if not isinstance(parsed, dict):
        return None, f"EXPECTED_OBJECT_GOT_{type(parsed).__name__.upper()}"
    return parsed, None


def validate_structured_output(
    parsed: Dict[str, Any],
    schema_required: set = VULN_SCHEMA_REQUIRED,
    valid_categories: set = VULN_CATEGORIES,
    valid_severities: set = VULN_SEVERITIES,
) -> Tuple[bool, list[str]]:
    """Validate a parsed structured output against the canonical schema.

    Returns (is_valid, list_of_issues).
    """
    issues: list[str] = []
    missing = schema_required - parsed.keys()
    if missing:
        issues.append(f"Missing fields: {sorted(missing)}")
    if "vulnerable" in parsed:
        if not isinstance(parsed["vulnerable"], bool):
            issues.append("'vulnerable' must be boolean")
    if "category" in parsed:
        cat = parsed["category"]
        if not isinstance(cat, str):
            issues.append("'category' must be string")
        elif cat.upper() not in valid_categories:
            # Allow unknown categories but flag them
            issues.append(f"Unknown category: {cat}")
    if "severity" in parsed:
        sev = parsed["severity"]
        if not isinstance(sev, str):
            issues.append("'severity' must be string")
        elif sev.upper() not in valid_severities:
            issues.append(f"Unknown severity: {sev}")
    if "evidence" in parsed and not isinstance(parsed["evidence"], str):
        issues.append("'evidence' must be string")
    return (len(issues) == 0, issues)
