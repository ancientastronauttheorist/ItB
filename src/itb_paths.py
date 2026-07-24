"""Platform-specific file locations for Into the Breach live data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT_ENV = "ITB_ARTIFACT_ROOT"
PYTEST_RUNTIME_GUARD_ENV = "ITB_PYTEST_RUNTIME_GUARD"


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser()


def get_artifact_root(
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the root for mutable bot artifacts."""
    environment = os.environ if environ is None else environ
    override = environment.get(ARTIFACT_ROOT_ENV)
    if override:
        root = Path(override).expanduser()
        if not root.is_absolute():
            raise ValueError(f"{ARTIFACT_ROOT_ENV} must be an absolute path")
    else:
        root = REPO_ROOT
    root_resolved = root.resolve()
    repo_resolved = REPO_ROOT.resolve()
    if environment.get(PYTEST_RUNTIME_GUARD_ENV) == "1":
        unsafe = (
            root_resolved == repo_resolved
            or root_resolved.is_relative_to(repo_resolved)
            or repo_resolved.is_relative_to(root_resolved)
        )
        if unsafe:
            raise RuntimeError(
                "pytest runtime guard refused an artifact root overlapping "
                "the repository"
            )
    return root


def get_artifact_path(
    *parts: str,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve a mutable artifact beneath the configured artifact root."""
    root = get_artifact_root(environ)
    candidate = root.joinpath(*parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"artifact path escapes {ARTIFACT_ROOT_ENV}: {candidate}"
        ) from exc
    return candidate


def _first_existing(candidates: list[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def get_save_dir() -> Path:
    """Return the Into the Breach profile root for this platform."""
    override = _env_path("ITB_SAVE_DIR")
    if override is not None:
        return override

    home = Path.home()
    if os.name == "nt":
        userprofile = Path(os.environ.get("USERPROFILE", str(home)))
        return _first_existing([
            userprofile / "Documents" / "My Games" / "Into The Breach",
            userprofile / "Documents" / "My Games" / "Into the Breach",
            home / "Documents" / "My Games" / "Into The Breach",
            home / "Documents" / "My Games" / "Into the Breach",
        ])

    return home / "Library" / "Application Support" / "IntoTheBreach"


def get_bridge_dir() -> Path:
    """Return the Lua bridge IPC directory for this platform."""
    override = _env_path("ITB_BRIDGE_DIR")
    if override is not None:
        return override

    if os.name == "nt":
        return get_save_dir() / "itb_bridge"
    return Path("/tmp")


def get_profile_dir(profile: str = "Alpha") -> Path:
    return get_save_dir() / f"profile_{profile}"


def get_save_file(filename: str, profile: str = "Alpha") -> Path:
    return get_profile_dir(profile) / filename
