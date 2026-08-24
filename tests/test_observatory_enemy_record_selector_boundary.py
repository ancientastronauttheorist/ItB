from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory.enemy_record_selector_boundary import (
    ANALYSIS_KIND,
    EnemyRecordSelectorBoundaryError,
    compare_enemy_records,
    replay_enemy_record_selector,
    replay_enemy_target_tie,
    validate_enemy_record_selector_boundary_map,
    validate_enemy_record_selector_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_enemy_record_selector_boundary.json"
)
SCRIPT = ROOT / "scripts" / "itb_observatory_enemy_record_selector.py"
EXECUTABLE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def _record(
    destination_x: int,
    destination_y: int,
    target_score: int,
    positioning_score: int,
    *,
    target_x: int = 4,
    target_y: int = 4,
) -> dict[str, int]:
    return {
        "destination_x": destination_x,
        "destination_y": destination_y,
        "target_x": target_x,
        "target_y": target_y,
        "target_score": target_score,
        "positioning_score": positioning_score,
    }


def test_committed_map_closes_parameterized_record_selector_boundary():
    value = _load()
    result = validate_enemy_record_selector_boundary_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "1a7ef818d1e889849e68301cb3e94d2291bc908f98b7501c5033d390ba110bfc"
        ),
        "record_size_bytes": 24,
        "parameterized_target_tie_complete": True,
        "parameterized_record_selector_complete": True,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "complete_enemy_phase_forecast": False,
        "control_window_count": 9,
        "data_anchor_count": 2,
        "dependency_count": 4,
        "direct_edge_count": 17,
        "finding_count": 6,
        "parameterized_record_selector_complete": True,
        "parameterized_target_tie_complete": True,
        "record_size_bytes": 24,
        "region_count": 10,
        "replay_vector_count": 13,
        "rng_role_count": 5,
        "simulator_change_required": False,
        "simulator_version": 408,
        "unresolved_count": 4,
    }
    assert value["solver_impact"]["simulator_change_required"] is False
    assert value["solver_impact"]["current_simulator_version"] == 408


def test_record_layout_destination_order_and_rng_roles_are_pinned():
    value = _load()
    layout = value["contracts"]["record_layout"]
    assert layout["size_bytes"] == 24
    assert [(item["offset"], item["name"]) for item in layout["fields"]] == [
        (0, "destination_x"),
        (4, "destination_y"),
        (8, "target_x"),
        (12, "target_y"),
        (16, "target_score"),
        (20, "positioning_score"),
    ]
    assert layout["empty_selection_default"] == [-1, -1, -1, -1, 0, 0]
    assert value["contracts"]["destination_order"] == {
        "ai_filter_preserves_order": True,
        "current_pawn_tile_appended_after_filtered_reachable": True,
        "later_edge_destinations_skipped_after_interior_favorable": True,
        "reachable_input_order": ["x", "y"],
        "record_seed_consumes_sequentially": True,
    }
    assert [(item["caller_id"], item["call_rva"]) for item in value["rng_call_roles"]] == [
        (29, "0x000f7b62"),
        (30, "0x000f7f6a"),
        (31, "0x000f7f94"),
        (32, "0x000f8012"),
        (33, "0x000f88a3"),
    ]


def test_target_tie_discards_negative_retains_zero_and_draws_for_positive_singleton():
    no_positive = replay_enemy_target_tie(
        3,
        3,
        2,
        [
            {"x": 1, "y": 1, "score": -4},
            {"x": 2, "y": 2, "score": 0},
        ],
        0,
    )
    assert no_positive["equal_best_target_indices"] == [1]
    assert no_positive["selected_target_index"] is None
    assert no_positive["record"] == _record(3, 3, 0, 2, target_x=-1, target_y=-1)
    assert no_positive["draw_count"] == 0
    assert no_positive["canonical_observable_final_state"] == "0x00000000"

    singleton = replay_enemy_target_tie(
        3,
        3,
        2,
        [{"x": 6, "y": 5, "score": 4}],
        0,
    )
    assert singleton["selected_target_index"] == 0
    assert singleton["record"] == _record(3, 3, 4, 2, target_x=6, target_y=5)
    assert singleton["draw_count"] == 1
    assert singleton["rng_transcript"][0]["caller_id"] == 29
    assert singleton["rng_transcript"][0]["bound"] == 1


def test_target_tie_preserves_returned_order_for_raw_modulo_choice():
    result = replay_enemy_target_tie(
        3,
        3,
        0,
        [
            {"x": 1, "y": 1, "score": 5},
            {"x": 2, "y": 2, "score": 4},
            {"x": 6, "y": 6, "score": 5},
        ],
        1,
    )
    assert result["equal_best_target_indices"] == [0, 2]
    assert result["rng_transcript"][0]["raw_result"] == 41
    assert result["rng_transcript"][0]["modulo_result"] == 1
    assert result["selected_target_index"] == 2


def test_native_comparator_special_case_and_ordinary_lexicographic_order():
    assert compare_enemy_records(_record(2, 2, 1, 1), _record(3, 3, 100, -1)) == 1
    assert compare_enemy_records(_record(2, 2, 100, -1), _record(3, 3, 1, 1)) == -1
    assert compare_enemy_records(_record(2, 2, 9, 0), _record(3, 3, 8, 5)) == 1
    assert compare_enemy_records(_record(2, 2, 9, -2), _record(3, 3, 9, -3)) == 1
    assert compare_enemy_records(_record(2, 2, 9, 0), _record(3, 3, 9, 0)) == 0


def test_empty_and_singleton_selector_have_exact_draw_grammar():
    empty = replay_enemy_record_selector([], 0)
    assert empty["selected_source"] == "default"
    assert empty["selected_input_index"] is None
    assert empty["selected_record"] == _record(-1, -1, 0, 0, target_x=-1, target_y=-1)
    assert empty["draw_count"] == 0

    singleton = replay_enemy_record_selector([_record(3, 3, 5, 0)], 0)
    assert singleton["selected_input_index"] == 0
    assert singleton["draw_count"] == 1
    assert singleton["rng_transcript"][0]["caller_id"] == 30
    assert singleton["rng_transcript"][0]["bound"] == 1


def test_displaced_primary_is_not_recomputed_global_second_best():
    result = replay_enemy_record_selector(
        [
            _record(2, 2, 1, 0),
            _record(3, 3, 3, 0),
            _record(4, 4, 2, 0),
        ],
        2,
    )
    assert result["primary_input_indices"] == [1]
    assert result["displaced_primary_input_indices"] == [0]
    assert result["fallback_gate_remainder"] == 0
    assert result["selected_source"] == "displaced_primary_fallback"
    assert result["selected_input_index"] == 0
    assert 2 not in result["primary_input_indices"]
    assert 2 not in result["displaced_primary_input_indices"]


def test_gate_miss_and_hit_consume_primary_before_fallback():
    records = [_record(2, 2, 2, 0), _record(3, 3, 3, 0)]
    miss = replay_enemy_record_selector(records, 0)
    assert miss["fallback_gate_remainder"] == 3
    assert miss["selected_source"] == "primary"
    assert [item["caller_id"] for item in miss["rng_transcript"]] == [30, 31]

    hit = replay_enemy_record_selector(records, 2)
    assert hit["fallback_gate_remainder"] == 0
    assert hit["selected_source"] == "displaced_primary_fallback"
    assert hit["selected_input_index"] == 0
    assert [item["caller_id"] for item in hit["rng_transcript"]] == [30, 31, 33]
    assert [item["bound"] for item in hit["rng_transcript"]] == [1, 4, 1]


def test_invalid_displaced_group_is_sampled_without_replacement_then_exhausted():
    result = replay_enemy_record_selector(
        [
            _record(2, 2, 0, 0),
            _record(3, 3, 0, 0),
            _record(4, 4, 1, 0),
        ],
        2,
    )
    assert result["displaced_primary_input_indices"] == [0, 1]
    assert result["fallback_attempts"] == [
        {"attempt_index": 1, "input_index": 0, "accepted": False},
        {"attempt_index": 2, "input_index": 1, "accepted": False},
    ]
    assert [item["caller_id"] for item in result["rng_transcript"]] == [
        30,
        31,
        33,
        32,
    ]
    assert [item["bound"] for item in result["rng_transcript"]] == [1, 4, 2, 1]
    assert result["selected_source"] == "primary"
    assert result["selected_input_index"] == 2


def test_interior_flag_and_minus_ten_cutoff_filter_before_ranking():
    interior = replay_enemy_record_selector(
        [_record(0, 2, 99, 3), _record(3, 3, 1, 0)],
        0,
    )
    assert interior["interior_favorable"] is True
    assert interior["eligible_input_indices"] == [1]
    assert interior["rejected_records"] == [
        {"input_index": 0, "reason": "edge_after_interior_favorable"}
    ]

    cutoff = replay_enemy_record_selector(
        [_record(2, 2, 99, -11), _record(3, 3, 1, -10)],
        0,
    )
    assert cutoff["interior_favorable"] is False
    assert cutoff["eligible_input_indices"] == [1]
    assert cutoff["selected_input_index"] == 1


def test_fallback_keeps_hardcoded_seven_even_with_other_runtime_dimensions():
    result = replay_enemy_record_selector(
        [_record(7, 2, 2, 0), _record(8, 2, 3, 0)],
        2,
        board_width=10,
        board_height=10,
    )
    assert result["interior_favorable"] is True
    assert result["eligible_input_indices"] == [0, 1]
    assert result["displaced_primary_input_indices"] == [0]
    assert result["fallback_gate_remainder"] == 0
    assert result["fallback_attempts"] == [
        {"attempt_index": 1, "input_index": 0, "accepted": False}
    ]
    assert result["selected_source"] == "primary"
    assert result["selected_input_index"] == 1


def test_replay_rejects_noncanonical_inputs_and_hidden_state_bit_is_equivalent():
    records = [_record(3, 3, 5, 0)]
    low = replay_enemy_record_selector(records, 1)
    high = replay_enemy_record_selector(records, 0x80000001)
    assert low["input_state"] == "0x00000001"
    assert high["input_state"] == "0x80000001"
    assert {key: value for key, value in low.items() if key != "input_state"} == {
        key: value for key, value in high.items() if key != "input_state"
    }

    with pytest.raises(EnemyRecordSelectorBoundaryError, match="fields must be exactly"):
        replay_enemy_record_selector([{"destination_x": 1}], 0)
    for state in (True, -1, 0x1_0000_0000, "0"):
        with pytest.raises(EnemyRecordSelectorBoundaryError, match="32-bit unsigned"):
            replay_enemy_record_selector([], state)  # type: ignore[arg-type]
    with pytest.raises(EnemyRecordSelectorBoundaryError, match="positive signed"):
        replay_enemy_record_selector([], 0, board_width=0)


def test_binding_rejects_comparator_rng_and_solver_scope_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["record_selector"]["minimum_positioning_score_inclusive"] = -11
    with pytest.raises(EnemyRecordSelectorBoundaryError, match="fields differ"):
        validate_enemy_record_selector_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["rng_call_roles"][4]["caller_id"] = 32
    with pytest.raises(EnemyRecordSelectorBoundaryError, match="fields differ"):
        validate_enemy_record_selector_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["solver_impact"]["simulator_change_required"] = True
    with pytest.raises(EnemyRecordSelectorBoundaryError, match="fields differ"):
        validate_enemy_record_selector_boundary_map_binding(altered)


def test_artifact_file_is_immutable_and_hash_pinned():
    assert BOUNDARY_MAP.stat().st_size == 43_927
    assert hashlib.sha256(BOUNDARY_MAP.read_bytes()).hexdigest() == (
        "73ccd7972fd25f2f455173673fed19b2310f6039e58b8cf5118236ff4f8b2022"
    )


@pytest.mark.skipif(not EXECUTABLE.is_file(), reason="exact ITB executable unavailable")
def test_exact_installed_executable_rebuilds_committed_map():
    result = validate_enemy_record_selector_boundary_map(EXECUTABLE, _load())
    assert result["status"] == "verified"
    assert result["artifact_sha256"] == (
        "1a7ef818d1e889849e68301cb3e94d2291bc908f98b7501c5033d390ba110bfc"
    )


def test_cli_replays_selector_only_after_binding_artifact(tmp_path: Path):
    records = tmp_path / "records.json"
    records.write_text(
        json.dumps({"records": [_record(2, 2, 2, 0), _record(3, 3, 3, 0)]}),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "replay-selector",
            "--boundary-map",
            str(BOUNDARY_MAP),
            "--records",
            str(records),
            "--rng-state",
            "2",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["selected_source"] == "displaced_primary_fallback"
    assert result["selected_input_index"] == 0
    assert result["draw_count"] == 3


@pytest.mark.skipif(not EXECUTABLE.is_file(), reason="exact ITB executable unavailable")
def test_cli_verify_rebuilds_exact_artifact():
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "verify",
            "--executable",
            str(EXECUTABLE),
            "--boundary-map",
            str(BOUNDARY_MAP),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["status"] == "verified"
    assert result["record_size_bytes"] == 24
