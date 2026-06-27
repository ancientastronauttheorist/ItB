"""Pytest configuration for ItB tests.

Registers the `regression` marker for slow full-corpus replay tests.
Run only fast unit tests: `pytest -m "not regression"`.
Run only regression tests:  `pytest -m regression`.
"""

from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_ACTIVE_SESSION_FILE = _REPO_ROOT / "sessions" / "active_session.json"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "regression: slow full-corpus replay tests",
    )


@pytest.fixture(autouse=True)
def preserve_live_active_session_file():
    """Keep unit tests from leaving the live run pointer on a fixture session."""
    existed = _ACTIVE_SESSION_FILE.exists()
    original = _ACTIVE_SESSION_FILE.read_bytes() if existed else None
    yield
    if existed:
        _ACTIVE_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        _ACTIVE_SESSION_FILE.write_bytes(original or b"")
    else:
        try:
            _ACTIVE_SESSION_FILE.unlink()
        except FileNotFoundError:
            pass
