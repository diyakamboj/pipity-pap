"""Pytest configuration for HRAgent tests."""
import os
import sys
from pathlib import Path

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set JOB_TMP for test scripts that need it
os.environ.setdefault("JOB_TMP", str(Path(__file__).parent))


@pytest.fixture(scope="session")
def job_tmp() -> Path:
    """Fixture providing the test temporary directory."""
    return Path(os.environ.get("JOB_TMP", str(Path(__file__).parent)))


@pytest.fixture(scope="session")
def mock_base_url() -> str:
    """Base URL for the mock LLM server."""
    return "http://127.0.0.1:8347/v1"