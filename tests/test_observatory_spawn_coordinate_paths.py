from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.spawn_coordinate_paths import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    SpawnCoordinatePathError,
    validate_spawn_coordinate_path_map,
    validate_spawn_coordinate_path_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "data" / "observatory" / "native"
PATH_MAP = NATIVE / (
    "windows_build_13725832_31fe35265598_spawn_coordinate_paths.json"
)
RETURN_MAP = NATIVE / (
    "windows_build_13725832_31fe35265598_rng_return_ids.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_path_map_closes_offline_scheduler_and_fallback_semantics():
    value = _load(PATH_MAP)
    result = validate_spawn_coordinate_path_map_binding(value, _load(RETURN_MAP))

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["rng_caller_ids"] == [59, 60, 66]
    assert result["fallback_is_emergency_only"] is True
    assert result["scheduler_selects_final_coordinate"] is False
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "control_window_count": 6,
        "direct_edge_count": 4,
        "fallback_is_emergency_only": True,
        "final_selector_rng_caller_ids": [59, 60],
        "region_count": 2,
        "rng_caller_ids": [59, 60, 66],
        "scheduler_direct_callsite_count": 3,
        "scheduler_rng_caller_ids": [66],
        "scheduler_selects_final_coordinate": False,
        "selector_direct_callsite_count": 4,
        "string_anchor_count": 3,
    }


def test_path_map_binding_rejects_control_flow_or_caller_drift():
    value = _load(PATH_MAP)
    return_map = _load(RETURN_MAP)

    altered = copy.deepcopy(value)
    altered["control_windows"][0]["instruction_hex"] = "90"
    with pytest.raises(SpawnCoordinatePathError, match="fields differ"):
        validate_spawn_coordinate_path_map_binding(altered, return_map)

    altered = copy.deepcopy(value)
    altered["rng_callers"][2]["caller_id"] = 65
    with pytest.raises(SpawnCoordinatePathError, match="fields differ"):
        validate_spawn_coordinate_path_map_binding(altered, return_map)


def test_exact_local_executable_reproduces_path_map_when_available():
    executable = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_spawn_coordinate_path_map(
        executable,
        _load(PATH_MAP),
        _load(RETURN_MAP),
    )
    assert result["status"] == "verified"
