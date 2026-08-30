from __future__ import annotations

import hashlib

import pytest

from src.observatory import capsule_runtime_modules as runtime_modules


def _install_synthetic_modules(tmp_path, monkeypatch):
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(b"exe")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    expected = {}
    paths = {}
    for role, data in {
        "capsule_observer": b"capsule",
        "continue_helper": b"continue",
        "rng_seed_helper": b"seed",
    }.items():
        filename = f"{role}.dll"
        path = scripts / filename
        path.write_bytes(data)
        paths[role] = path
        expected[role] = {
            "filename": filename,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    monkeypatch.setattr(runtime_modules, "EXPECTED_RUNTIME_MODULES", expected)
    return executable, paths


def test_runtime_module_preflight_binds_all_exact_installed_files(
    tmp_path,
    monkeypatch,
):
    executable, paths = _install_synthetic_modules(tmp_path, monkeypatch)

    identities = runtime_modules.validate_capsule_runtime_modules(
        executable,
        paths["capsule_observer"],
    )

    assert set(identities) == {
        "capsule_observer",
        "continue_helper",
        "rng_seed_helper",
    }
    assert identities["continue_helper"]["path"] == str(
        paths["continue_helper"].resolve()
    )


def test_runtime_module_preflight_rejects_missing_or_misplaced_support(
    tmp_path,
    monkeypatch,
):
    executable, paths = _install_synthetic_modules(tmp_path, monkeypatch)
    paths["continue_helper"].unlink()

    with pytest.raises(runtime_modules.CapsuleRuntimeModuleError, match="continue"):
        runtime_modules.validate_capsule_runtime_modules(
            executable,
            paths["capsule_observer"],
        )

    paths["continue_helper"].write_bytes(b"continue")
    misplaced = tmp_path / paths["capsule_observer"].name
    misplaced.write_bytes(b"capsule")
    with pytest.raises(runtime_modules.CapsuleRuntimeModuleError, match="installed"):
        runtime_modules.validate_capsule_runtime_modules(executable, misplaced)
