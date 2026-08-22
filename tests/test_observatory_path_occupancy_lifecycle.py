from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.path_occupancy_lifecycle import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    PathOccupancyLifecycleError,
    validate_path_occupancy_lifecycle_map,
    validate_path_occupancy_lifecycle_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
PATH_OCCUPANCY_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_path_occupancy_lifecycle.json"
)


def _load() -> dict:
    return json.loads(PATH_OCCUPANCY_MAP.read_text(encoding="utf-8"))


def test_committed_map_pins_live_corpse_and_transient_dead_path_behavior():
    value = _load()
    result = validate_path_occupancy_lifecycle_map_binding(value)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["mode_1_predicate"] == "live_or_persistent_corpse"
    assert result["ordinary_persistent_corpse_blocks"] is True
    assert result["ordinary_transient_dead_non_corpse_blocks"] is False
    assert result["roadrunner_persistent_corpse_transit"] is True
    assert result["roadrunner_persistent_corpse_stop"] is False
    assert result["simulator_version"] == 403
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "binding_count": 2,
        "control_window_count": 10,
        "mode_1_predicate": "live_or_persistent_corpse",
        "ordinary_persistent_corpse_blocks": True,
        "ordinary_transient_dead_non_corpse_blocks": False,
        "region_count": 8,
        "remaining_runtime_proof": [
            "matched IsCorpse values across disabled mechs and source Corpse=true pawns",
            "transient dead-pawn removal timing between separate player actions",
            "AddMove step effects, interruption, and scheduler timing",
            "non-Windows build equivalence",
        ],
        "roadrunner_persistent_corpse_stop": False,
        "roadrunner_persistent_corpse_transit": True,
        "simulator_version": 403,
    }


def test_binding_rejects_lifecycle_or_roadrunner_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["occupancy_mode"]["mode_1"]["counts_dead_corpse_pawn"] = False
    with pytest.raises(PathOccupancyLifecycleError, match="fields differ"):
        validate_path_occupancy_lifecycle_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["path_behavior"]["roadrunner_persistent_corpse_blocks_transit"] = True
    with pytest.raises(PathOccupancyLifecycleError, match="fields differ"):
        validate_path_occupancy_lifecycle_map_binding(altered)


def test_exact_local_executable_reproduces_map_when_available():
    executable = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_path_occupancy_lifecycle_map(executable, _load())
    assert result["status"] == "verified"
