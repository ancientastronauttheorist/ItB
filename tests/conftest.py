"""Pytest configuration for ItB tests.

Registers the `regression` marker for slow full-corpus replay tests.
Run only fast unit tests: `pytest -m "not regression"`.
Run only regression tests:  `pytest -m regression`.

All live-data overrides are installed before importing application modules.
This makes import-time paths, call-time resolvers, and inherited subprocess
environments point at one process-unique temporary runtime.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LIVE_ACTIVE_SESSION_FILE = _REPO_ROOT / "sessions" / "active_session.json"
_TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="itb_pytest_runtime_")
_TEST_RUNTIME_ROOT = Path(_TEST_RUNTIME.name).resolve()
_TEST_SESSION_FILE = _TEST_RUNTIME_ROOT / "sessions" / "active_session.json"
_TEST_SAVE_DIR = _TEST_RUNTIME_ROOT / "save"
_TEST_BRIDGE_DIR = _TEST_RUNTIME_ROOT / "bridge"
_TEST_ARTIFACT_ROOT = _TEST_RUNTIME_ROOT / "artifacts"

for directory in (
    _TEST_SESSION_FILE.parent,
    _TEST_SAVE_DIR,
    _TEST_BRIDGE_DIR,
    _TEST_ARTIFACT_ROOT,
):
    directory.mkdir(parents=True, exist_ok=True)

os.environ["ITB_SESSION_FILE"] = str(_TEST_SESSION_FILE)
os.environ["ITB_PYTEST_SESSION_GUARD"] = "1"
os.environ["ITB_SAVE_DIR"] = str(_TEST_SAVE_DIR)
os.environ["ITB_BRIDGE_DIR"] = str(_TEST_BRIDGE_DIR)
os.environ["ITB_ARTIFACT_ROOT"] = str(_TEST_ARTIFACT_ROOT)
os.environ["ITB_PYTEST_RUNTIME_GUARD"] = "1"

# Seed mutable corpora from a stable snapshot. Tests can read and mutate these
# copies without racing the active achievement run.
for relative in (
    Path("recordings/failure_db.jsonl"),
    Path("data/achievements_detailed.json"),
    Path("data/weapon_penalty_log.json"),
    Path("data/weapon_overrides.json"),
    Path("data/weapon_overrides_staged.jsonl"),
    Path("data/weapon_overrides_rejected.jsonl"),
    Path("data/weapon_def_mismatches.jsonl"),
    Path("diagnoses/rejections.jsonl"),
):
    source = _REPO_ROOT / relative
    target = _TEST_ARTIFACT_ROOT / relative
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

# Import only after every override and corpus snapshot exists.
from src.loop.session import DEFAULT_SESSION_FILE, _release_lock  # noqa: E402
from src.itb_paths import get_artifact_root  # noqa: E402

if DEFAULT_SESSION_FILE.resolve() != _TEST_SESSION_FILE:
    raise RuntimeError(
        "src.loop.session was imported before pytest runtime isolation"
    )
if DEFAULT_SESSION_FILE.resolve() == _LIVE_ACTIVE_SESSION_FILE.resolve():
    raise RuntimeError("pytest session path resolves to the live run")
if get_artifact_root().resolve() != _TEST_ARTIFACT_ROOT:
    raise RuntimeError("pytest artifact root resolves to the live run")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "regression: slow full-corpus replay tests",
    )


@pytest.fixture(scope="session", autouse=True)
def isolate_live_runtime():
    """Fail closed unless pytest is detached from live session/save/IPC paths."""
    expected = {
        "ITB_SESSION_FILE": _TEST_SESSION_FILE,
        "ITB_SAVE_DIR": _TEST_SAVE_DIR,
        "ITB_BRIDGE_DIR": _TEST_BRIDGE_DIR,
        "ITB_ARTIFACT_ROOT": _TEST_ARTIFACT_ROOT,
    }
    for name, path in expected.items():
        configured = Path(os.environ[name]).resolve()
        if configured != path:
            pytest.fail(f"{name} escaped the isolated pytest runtime")
    if os.environ.get("ITB_PYTEST_SESSION_GUARD") != "1":
        pytest.fail("ITB_PYTEST_SESSION_GUARD is not enabled")
    if os.environ.get("ITB_PYTEST_RUNTIME_GUARD") != "1":
        pytest.fail("ITB_PYTEST_RUNTIME_GUARD is not enabled")
    try:
        yield
    finally:
        _release_lock()
        _TEST_RUNTIME.cleanup()
