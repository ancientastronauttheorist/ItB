#!/usr/bin/env python3
"""Build and attest the one-purpose, build-keyed x86 RNG seed helper."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "observatory_rng_seed.c"
HELPER_VERSION = "observatory-rng-seed-helper/1"
EXPORT_NAME = "luaopen_itb_observatory_rng_seed"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_ARCHITECTURE = "x86"
EXPECTED_RNG_SEED_RVA = "0x00387f37"
EXPECTED_RNG_SEED_SHA256 = (
    "67b19fe39627674ef04d07bd86e989a39ce744be2e93f9265c16e2aeb928cf9d"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class HelperBuildError(RuntimeError):
    """Raised when helper compilation or attestation cannot be trusted."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--native-boundaries", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _stable_bytes(path: Path, label: str) -> bytes:
    path = Path(os.path.abspath(path.expanduser()))
    if path.is_symlink() or not path.is_file():
        raise HelperBuildError(f"{label} is not a regular file: {path}")
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != before.st_size
    ):
        raise HelperBuildError(f"{label} changed while being read")
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    data = _stable_bytes(path, label)
    try:
        value = json.loads(data.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HelperBuildError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise HelperBuildError(f"{label} must be an object")
    return value, data


def _validate_inputs(executable: Path, boundaries_path: Path) -> dict[str, str]:
    executable_data = _stable_bytes(executable, "Breach.exe")
    executable_sha = _sha256(executable_data)
    if (
        executable_sha != EXPECTED_EXECUTABLE_SHA256
        or len(executable_data) != EXPECTED_EXECUTABLE_SIZE
    ):
        raise HelperBuildError("Breach.exe does not match the pinned helper build")

    boundaries, boundary_data = _load_json(boundaries_path, "native boundaries")
    identity = boundaries.get("identity")
    if (
        boundaries.get("schema_version") != 1
        or boundaries.get("analysis_kind") != "pe_reviewed_boundary_map"
        or not isinstance(identity, dict)
        or identity.get("executable_sha256") != executable_sha
        or identity.get("build_id") != EXPECTED_BUILD_ID
        or identity.get("architecture") != EXPECTED_ARCHITECTURE
    ):
        raise HelperBuildError("native boundaries do not match the pinned helper")
    seed_regions = [
        item
        for item in boundaries.get("regions", [])
        if isinstance(item, dict) and item.get("id") == "rng_seed"
    ]
    if len(seed_regions) != 1 or any(
        seed_regions[0].get(key) != value
        for key, value in {
            "start_rva": EXPECTED_RNG_SEED_RVA,
            "sha256": EXPECTED_RNG_SEED_SHA256,
            "size": 18,
        }.items()
    ):
        raise HelperBuildError("native rng_seed boundary is not the pinned region")
    return {
        "executable_sha256": executable_sha,
        "native_boundaries_sha256": _sha256(boundary_data),
    }


def _vswhere() -> Path:
    candidate = Path(os.environ.get("ProgramFiles(x86)", "")) / (
        "Microsoft Visual Studio/Installer/vswhere.exe"
    )
    if not candidate.is_file():
        raise HelperBuildError("Visual Studio vswhere.exe is unavailable")
    return candidate


def _msvc_environment() -> tuple[dict[str, str], str]:
    result = subprocess.run(
        [
            str(_vswhere()),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    installation = Path(result.stdout.strip())
    vcvars = installation / "VC" / "Auxiliary" / "Build" / "vcvars32.bat"
    if not vcvars.is_file():
        raise HelperBuildError("Visual C++ x86 environment is unavailable")
    # A tiny temporary batch file avoids cmd.exe's special first-quoted-token
    # parsing while retaining the exact environment produced by vcvars32.
    with tempfile.TemporaryDirectory(prefix="itb_observatory_msvc_env_") as raw:
        environment_script = Path(raw) / "environment.cmd"
        environment_script.write_text(
            f'@call "{vcvars}" >nul\n@set\n',
            encoding="utf-8",
        )
        env_result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(environment_script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    if env_result.returncode != 0:
        detail = (env_result.stderr or env_result.stdout).strip()
        raise HelperBuildError(
            "vcvars32.bat failed to configure MSVC"
            + (f": {detail}" if detail else "")
        )
    environment = {key.upper(): value for key, value in os.environ.items()}
    for line in env_result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            environment[key.upper()] = value
    cl = shutil.which("cl.exe", path=environment.get("PATH"))
    if cl is None:
        raise HelperBuildError("cl.exe was not configured by vcvars32.bat")
    version = subprocess.run(
        [cl],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    banner = (version.stderr or version.stdout).splitlines()
    return environment, (banner[0].strip() if banner else "unknown MSVC")


def _machine(data: bytes) -> int:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise HelperBuildError("compiled helper is not a PE image")
    (pe_offset,) = struct.unpack_from("<I", data, 0x3C)
    if pe_offset + 6 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise HelperBuildError("compiled helper has an invalid PE header")
    return struct.unpack_from("<H", data, pe_offset + 4)[0]


def _write_create_only(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise HelperBuildError(f"immutable output already exists: {path.name}") from exc


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _normalize_compiler_stdout(value: str, temporary_root: Path) -> str:
    """Remove the randomized build directory from otherwise stable MSVC output."""
    result = value.strip()
    for spelling in {str(temporary_root), temporary_root.as_posix()}:
        result = result.replace(spelling, "<temporary-build>")
    return result


def build_helper(args: argparse.Namespace) -> int:
    identities = _validate_inputs(args.executable, args.native_boundaries)
    source_data = _stable_bytes(SOURCE, "helper source")
    environment, compiler = _msvc_environment()
    with tempfile.TemporaryDirectory(prefix="itb_observatory_rng_seed_") as raw:
        temp = Path(raw)
        dll = temp / "itb_observatory_rng_seed.dll"
        obj = temp / "observatory_rng_seed.obj"
        cl = shutil.which("cl.exe", path=environment.get("PATH"))
        assert cl is not None
        command = [
            cl,
            "/nologo",
            "/LD",
            "/O2",
            "/MT",
            "/W4",
            "/WX",
            "/GS-",
            f"/Fo{obj}",
            f"/Fe{dll}",
            str(SOURCE),
            "/link",
            "/NOLOGO",
            "/INCREMENTAL:NO",
            "/Brepro",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        compiler_stdout = _normalize_compiler_stdout(completed.stdout, temp)
        helper_data = _stable_bytes(dll, "compiled helper")
        if _machine(helper_data) != 0x014C:
            raise HelperBuildError("compiled helper is not x86")
        helper_sha = _sha256(helper_data)
        if _SHA256_RE.fullmatch(helper_sha) is None:
            raise HelperBuildError("compiled helper digest is invalid")

    output_root = Path(os.path.abspath(args.output_root.expanduser()))
    filename = f"itb_observatory_rng_seed_{helper_sha}.dll"
    helper_path = output_root / filename
    receipt_path = output_root / f"{filename}.receipt.json"
    _write_create_only(helper_path, helper_data)
    receipt = {
        "schema_version": 1,
        "kind": "observatory_rng_seed_helper_build",
        "helper_version": HELPER_VERSION,
        "module_filename": filename,
        "module_sha256": helper_sha,
        "module_size": len(helper_data),
        "architecture": EXPECTED_ARCHITECTURE,
        "export_name": EXPORT_NAME,
        "source_path": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": _sha256(source_data),
        "compiler": compiler,
        "compiler_stdout": compiler_stdout,
        "executable_sha256": identities["executable_sha256"],
        "build_id": EXPECTED_BUILD_ID,
        "native_boundaries_sha256": identities["native_boundaries_sha256"],
        "rng_seed_rva": EXPECTED_RNG_SEED_RVA,
        "rng_seed_region_sha256": EXPECTED_RNG_SEED_SHA256,
    }
    _write_create_only(receipt_path, _canonical_json(receipt))
    if _stable_bytes(helper_path, "published helper") != helper_data:
        raise HelperBuildError("published helper failed byte verification")
    print(
        f"helper={helper_path} sha256={helper_sha} size={len(helper_data)} "
        f"receipt={receipt_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return build_helper(args)
    except (HelperBuildError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
