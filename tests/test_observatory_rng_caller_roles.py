from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.rng_caller_roles import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    RNGCallerRoleError,
    validate_rng_caller_role_map,
    validate_rng_caller_role_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "data" / "observatory" / "native"
OVERLAY_PATH = NATIVE / (
    "windows_build_13725832_31fe35265598_rng_caller_roles.json"
)
RETURN_MAP_PATH = NATIVE / (
    "windows_build_13725832_31fe35265598_rng_return_ids.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_overlay_binds_all_variable_static_callers():
    overlay = _load(OVERLAY_PATH)
    result = validate_rng_caller_role_map_binding(
        overlay,
        _load(RETURN_MAP_PATH),
    )

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["caller_role_count"] == 13
    assert result["presentation_caller_ids"] == [
        4,
        5,
        6,
        7,
        9,
        10,
        11,
        12,
        13,
        101,
        114,
        115,
    ]
    assert result["gameplay_caller_ids"] == [72]
    assert overlay["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert {item["text"] for item in overlay["string_anchors"]} >= {
        "max_particles",
        "Pilot_Blink",
        "UnitAcid",
        "env_xp",
    }


def test_overlay_binding_rejects_caller_or_identity_drift():
    overlay = _load(OVERLAY_PATH)
    return_map = _load(RETURN_MAP_PATH)

    altered = copy.deepcopy(overlay)
    altered["caller_roles"][0]["caller_id"] = 3
    with pytest.raises(RNGCallerRoleError, match="caller_roles differs"):
        validate_rng_caller_role_map_binding(altered, return_map)

    altered = copy.deepcopy(overlay)
    altered["identity"]["build_id"] = "different"
    with pytest.raises(RNGCallerRoleError, match="identity differs"):
        validate_rng_caller_role_map_binding(altered, return_map)

    altered = copy.deepcopy(overlay)
    altered["regions"][0]["sha256"] = "0" * 64
    with pytest.raises(RNGCallerRoleError, match="regions differs"):
        validate_rng_caller_role_map_binding(altered, return_map)


def test_exact_local_executable_reproduces_overlay_when_available():
    executable = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_rng_caller_role_map(
        executable,
        _load(OVERLAY_PATH),
        _load(RETURN_MAP_PATH),
    )
    assert result["status"] == "verified"
