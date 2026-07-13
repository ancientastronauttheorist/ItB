"""Pytest configuration for ItB tests.

Registers the `regression` marker for slow full-corpus replay tests.
Run only fast unit tests: `pytest -m "not regression"`.
Run only regression tests:  `pytest -m regression`.
"""

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from src.loop.session import _lock_file, _unlock_file


_REPO_ROOT = Path(__file__).resolve().parents[1]
_ACTIVE_SESSION_FILE = _REPO_ROOT / "sessions" / "active_session.json"
_ACTIVE_SESSION_TEST_LOCK = Path(tempfile.gettempdir()) / (
    "itb_pytest_active_session_"
    + hashlib.sha256(str(_REPO_ROOT).encode()).hexdigest()[:12]
    + ".lock"
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "regression: slow full-corpus replay tests",
    )


@pytest.fixture(scope="session", autouse=True)
def serialize_live_active_session_test_suites():
    """Keep concurrent pytest processes from racing on the live session.

    The function-scoped preservation fixture below is sufficient inside one
    pytest process, but two independently launched suites can otherwise read
    each other's transient fixture session and restore it over the live run.
    Hold a repo-specific cross-process lock for the entire suite.
    """
    _ACTIVE_SESSION_TEST_LOCK.parent.mkdir(parents=True, exist_ok=True)
    handle = open(_ACTIVE_SESSION_TEST_LOCK, "a+b")
    deadline = time.monotonic() + 300.0
    locked = False
    try:
        while True:
            try:
                handle.seek(0)
                _lock_file(handle)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    pytest.fail(
                        "timed out waiting for another pytest process to "
                        "release the live-session preservation lock"
                    )
                time.sleep(0.05)
        yield
    finally:
        if locked:
            _unlock_file(handle)
        handle.close()


@pytest.fixture(autouse=True)
def preserve_live_active_session_file():
    """Keep unit tests from leaving the live run pointer on a fixture session."""
    existed = _ACTIVE_SESSION_FILE.exists()
    original = _ACTIVE_SESSION_FILE.read_bytes() if existed else None
    if existed:
        if not original:
            pytest.fail("live active_session.json was empty before the test")
        try:
            json.loads(original)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            pytest.fail(f"live active_session.json was invalid before the test: {exc}")
    try:
        yield
    finally:
        if existed:
            _ACTIVE_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = _ACTIVE_SESSION_FILE.parent / (
                f".pytest.{os.getpid()}.{_ACTIVE_SESSION_FILE.name}.tmp"
            )
            try:
                tmp_path.write_bytes(original)
                os.replace(tmp_path, _ACTIVE_SESSION_FILE)
            finally:
                try:
                    tmp_path.unlink()
                except FileNotFoundError:
                    pass
        else:
            try:
                _ACTIVE_SESSION_FILE.unlink()
            except FileNotFoundError:
                pass
