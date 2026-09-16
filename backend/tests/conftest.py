"""Shared pytest fixtures."""

import sys
from pathlib import Path

import pytest

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def demo_samples():
    """Load demo samples for testing."""
    import json
    demo_path = Path(__file__).resolve().parents[2] / "demo_data" / "vulnerability_demo.json"
    if demo_path.exists():
        with open(demo_path) as f:
            data = json.load(f)
        return data.get("data", [])
    return []
