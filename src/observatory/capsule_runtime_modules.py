"""Exact installed native-module identities for the spawn capsule campaign."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.observatory.trace_store import stable_file_sha256


EXPECTED_RUNTIME_MODULES = {
    "capsule_observer": {
        "filename": (
            "itb_observatory_spawn_coordinate_capsule_hw_observer_"
            "bb099e829df74d4d7e1841a5ac70174bbdd2712ddfcdc0b2c9f633d32e0f17b9.dll"
        ),
        "size": 28_672,
        "sha256": (
            "bb099e829df74d4d7e1841a5ac70174bbdd2712ddfcdc0b2c9f633d32e0f17b9"
        ),
    },
    "continue_helper": {
        "filename": (
            "itb_observatory_continue_"
            "e0c6766f6d2150616fc10224fa2d1d53c051a7171fd2e107267f1383a4fcc91a.dll"
        ),
        "size": 78_848,
        "sha256": (
            "e0c6766f6d2150616fc10224fa2d1d53c051a7171fd2e107267f1383a4fcc91a"
        ),
    },
    "rng_seed_helper": {
        "filename": (
            "itb_observatory_rng_seed_"
            "bd6501c701b8c5f21dbaec309573ab654c7cf01a5705423e2c0ee554dd0e2787.dll"
        ),
        "size": 73_728,
        "sha256": (
            "bd6501c701b8c5f21dbaec309573ab654c7cf01a5705423e2c0ee554dd0e2787"
        ),
    },
}


class CapsuleRuntimeModuleError(RuntimeError):
    """Raised when a required native module is absent, misplaced, or changed."""


def _stable_identity(path: Path, role: str) -> dict[str, Any]:
    candidate = Path(os.path.abspath(path))
    if candidate.is_symlink() or not candidate.is_file():
        raise CapsuleRuntimeModuleError(
            f"{role} is not an installed regular file: {candidate}"
        )
    before = candidate.stat()
    digest = stable_file_sha256(candidate)
    after = candidate.stat()
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise CapsuleRuntimeModuleError(f"{role} changed while read")
    return {
        "path": str(candidate.resolve()),
        "size": before.st_size,
        "sha256": digest,
    }


def validate_capsule_runtime_modules(
    executable: Path,
    capsule_module: Path,
) -> dict[str, dict[str, Any]]:
    """Require all three exact modules in the executable's scripts directory."""
    executable_path = Path(os.path.abspath(executable))
    scripts_dir = executable_path.parent / "scripts"
    if scripts_dir.is_symlink() or not scripts_dir.is_dir():
        raise CapsuleRuntimeModuleError(
            f"game scripts directory is unavailable: {scripts_dir}"
        )
    scripts_dir = scripts_dir.resolve()
    supplied_capsule = Path(os.path.abspath(capsule_module))
    identities: dict[str, dict[str, Any]] = {}
    for role, expected in EXPECTED_RUNTIME_MODULES.items():
        expected_path = scripts_dir / str(expected["filename"])
        candidate = supplied_capsule if role == "capsule_observer" else expected_path
        if os.path.normcase(str(candidate)) != os.path.normcase(str(expected_path)):
            raise CapsuleRuntimeModuleError(
                f"{role} is not installed at its exact content-addressed path"
            )
        identity = _stable_identity(candidate, role)
        if (
            identity["size"] != expected["size"]
            or identity["sha256"] != expected["sha256"]
        ):
            raise CapsuleRuntimeModuleError(f"{role} identity differs")
        identities[role] = identity
    return identities
