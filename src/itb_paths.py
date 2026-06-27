"""Platform-specific file locations for Into the Breach live data."""

from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser()


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
