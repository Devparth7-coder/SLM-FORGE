"""Code-perturbation transforms for robustness testing.

All transforms are deterministic given a seed.
"""

from __future__ import annotations

import random
import re
import string
from typing import Callable, Dict, List


# ── Individual perturbation functions ────────────────────────────────────

def whitespace_perturbation(code: str, rng: random.Random) -> str:
    """Randomise whitespace: add/remove blank lines, change indentation width."""
    lines = code.split("\n")
    out = []
    for line in lines:
        stripped = line.rstrip()
        if stripped == "" and rng.random() < 0.5:
            continue  # drop blank lines
        out.append(line)
        if rng.random() < 0.1:
            out.append("")  # extra blank line
    return "\n".join(out)


def variable_renaming(code: str, rng: random.Random) -> str:
    """Rename local variables to random names (best-effort regex)."""
    var_pattern = re.compile(r"\b([a-z_][a-z0-9_]{2,})\b")
    used_vars: Dict[str, str] = {}
    keywords = {"def", "class", "return", "if", "else", "for", "while", "in", "not",
                "and", "or", "True", "False", "None", "import", "from", "as", "with",
                "try", "except", "finally", "raise", "pass", "break", "continue",
                "print", "len", "str", "int", "list", "dict", "set", "open", "range"}

    def replacer(m: re.Match) -> str:
        name = m.group(1)
        if name in keywords:
            return name
        if name in used_vars:
            return used_vars[name]
        if rng.random() < 0.3:  # rename ~30% of variables
            new_name = "var_" + "".join(rng.choices(string.ascii_lowercase, k=6))
            used_vars[name] = new_name
            return new_name
        return name

    return var_pattern.sub(replacer, code)


def comment_insertion(code: str, rng: random.Random) -> str:
    """Insert harmless comments at random locations."""
    comments = [
        "// TODO: refactor later",
        "// NOTE: legacy code",
        "// temporary workaround",
        "# legacy",
        "# reviewed",
        "# backward compatibility",
        "/* performance optimization */",
        "/* safe */",
    ]
    lines = code.split("\n")
    out = []
    for line in lines:
        if rng.random() < 0.15:
            out.append(" " * rng.randint(0, 8) + rng.choice(comments))
        out.append(line)
    return "\n".join(out)


def irrelevant_code_insertion(code: str, rng: random.Random) -> str:
    """Append harmless irrelevant code at the end."""
    irrelevant_blocks = [
        "\n\n// logging helper (unused)\nvoid unused_log_helper(const char* msg) { (void)msg; }\n",
        "\n\n# unused utility\ndef _format_timestamp(t):\n    return str(t)\n",
        "\n\n// deprecated\nvar unusedCounter = 0;\n",
    ]
    return code + rng.choice(irrelevant_blocks)


def truncation(code: str, rng: random.Random) -> str:
    """Truncate the code (simulate partial snippets)."""
    if len(code) < 200:
        return code
    cut_point = rng.randint(len(code) // 2, int(len(code) * 0.9))
    return code[:cut_point]


def noop(code: str, rng: random.Random) -> str:
    return code


def noisy_formatting(code: str, rng: random.Random) -> str:
    """Add extra spaces and line breaks."""
    return code.replace(";", ";\n").replace("{", "{\n").replace("}", "\n}")


def long_context(code: str, rng: random.Random) -> str:
    """Prepend a long comment block to push important code later (simulate long context)."""
    filler = "\n".join([f"// Filler line {i}: " + "x" * 60 for i in range(50)])
    return filler + "\n\n" + code


def character_noise(code: str, rng: random.Random) -> str:
    """Insert subtle character-level noise that doesn't change semantics for Python/JS."""
    # Add trailing spaces, replace single quotes with double where safe, etc.
    lines = code.split("\n")
    out = []
    for line in lines:
        if rng.random() < 0.2:
            line = line + " " * rng.randint(1, 5)
        out.append(line)
    return "\n".join(out)


def tab_newline_swap(code: str, rng: random.Random) -> str:
    """Convert tabs to spaces and vice versa."""
    if "\t" in code:
        return code.replace("\t", "    ")
    return code.replace("    ", "\t", 100)


# ── Registry ──────────────────────────────────────────────────────────────
PERTURBATIONS: Dict[str, Callable[[str, random.Random], str]] = {
    "formatting": whitespace_perturbation,
    "whitespace": whitespace_perturbation,
    "variable_renaming": variable_renaming,
    "comment_insertion": comment_insertion,
    "irrelevant_code": irrelevant_code_insertion,
    "truncation": truncation,
    "noop": noop,
    "noisy_formatting": noisy_formatting,
    "long_context": long_context,
    "character_noise": character_noise,
    "tab_swap": tab_newline_swap,
}


def apply_perturbation(
    code: str,
    perturbation_type: str,
    *,
    seed: int = 42,
) -> str:
    """Apply a named perturbation to code; returns perturbed code."""
    rng = random.Random(seed)
    fn = PERTURBATIONS.get(perturbation_type, noop)
    return fn(code, rng)


def list_perturbations() -> List[str]:
    return sorted(PERTURBATIONS.keys())
