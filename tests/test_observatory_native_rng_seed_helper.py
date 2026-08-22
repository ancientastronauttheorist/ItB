from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_itb_observatory_rng_seed_helper as helper_build
from src.observatory.rng_trial_capsule import (
    RngTrialCapsuleError,
    msvc_random_int_first,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "observatory_rng_seed.c"


def test_native_seed_helper_has_one_narrow_export_and_no_injection_surface():
    source = SOURCE.read_text(encoding="utf-8")
    assert source.count("__declspec(dllexport)") == 1
    assert "luaopen_itb_observatory_rng_seed" in source
    assert "OBS_RNG_CORE_RVA 0x00387f16u" in source
    assert "OBS_RNG_SEED_RVA 0x00387f37u" in source
    assert helper_build.EXPECTED_EXECUTABLE_SHA256 in source
    for forbidden in (
        "VirtualProtect",
        "WriteProcessMemory",
        "CreateRemoteThread",
        "OpenProcess",
        "CreateFile",
        "WinHttp",
        "socket(",
    ):
        assert forbidden not in source


def test_pinned_msvc_first_result_vectors():
    assert msvc_random_int_first(0, 7) == 3
    assert msvc_random_int_first(1234, 7) == 1
    assert msvc_random_int_first(0x13579BDF, 65521) == 24356
    with pytest.raises(RngTrialCapsuleError, match="signed 32-bit"):
        msvc_random_int_first(0x80000000, 7)


def test_helper_builder_rejects_an_unpinned_executable(tmp_path):
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(b"not the pinned executable")
    boundaries = tmp_path / "boundaries.json"
    boundaries.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(helper_build.HelperBuildError, match="pinned helper build"):
        helper_build._validate_inputs(executable, boundaries)


def test_helper_build_receipt_normalizes_random_temporary_directory():
    first = helper_build._normalize_compiler_stdout(
        "Creating library C:\\Temp\\build_one\\helper.lib",
        Path("C:/Temp/build_one"),
    )
    second = helper_build._normalize_compiler_stdout(
        "Creating library C:\\Temp\\build_two\\helper.lib",
        Path("C:/Temp/build_two"),
    )
    assert first == second == "Creating library <temporary-build>\\helper.lib"
