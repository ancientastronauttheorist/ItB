from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.path_boundaries import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    PathBoundaryError,
    validate_path_boundary_map,
    validate_path_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
PATH_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_path_boundaries.json"
)


def _load() -> dict:
    return json.loads(PATH_MAP.read_text(encoding="utf-8"))


def test_committed_path_map_proves_roadrunner_transit_stop_distinction():
    value = _load()
    result = validate_path_boundary_map_binding(value)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["roadrunner_profile"] == 4
    assert result["roadrunner_can_transit_occupied"] is True
    assert result["roadrunner_can_stop_occupied"] is False
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "api_binding_count": 5,
        "control_window_count": 10,
        "direct_edge_count": 4,
        "get_path_same_point_empty": True,
        "path_constant_count": 7,
        "region_count": 12,
        "remaining_runtime_proof": [
            "weighted path-cost and tie-breaking details",
            "team-specific ordinary occupancy edge cases",
            "matched native path/reachable result ordering",
        ],
        "roadrunner_can_stop_occupied": False,
        "roadrunner_can_transit_occupied": True,
        "roadrunner_profile": 4,
    }


def test_path_map_binding_rejects_profile_or_vtable_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["path_constants"][-1]["value"] = 5
    with pytest.raises(PathBoundaryError, match="fields differ"):
        validate_path_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["board_gridsearch_vtable"]["slots"][3]["target_rva"] = (
        "0x0015ff41"
    )
    with pytest.raises(PathBoundaryError, match="fields differ"):
        validate_path_boundary_map_binding(altered)


def test_exact_local_executable_reproduces_path_map_when_available():
    executable = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_path_boundary_map(executable, _load())
    assert result["status"] == "verified"
