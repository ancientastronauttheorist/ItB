from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.observatory.piston_scheduler_boundary import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    PistonSchedulerBoundaryError,
    validate_piston_scheduler_boundary_map,
    validate_piston_scheduler_boundary_map_binding,
)
from src.observatory.death_event_credit_boundary import (
    POST_PUBLICATION_PROJECT_BRIDGE_OVERLAYS as DEATH_EVENT_BRIDGE_OVERLAYS,
)
from src.observatory.final_cave_block_spawn_lifetime import (
    POST_PUBLICATION_PROJECT_BRIDGE_OVERLAYS as FINAL_CAVE_BRIDGE_OVERLAYS,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_piston_scheduler_boundary.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_stock_piston_order_and_cancellation_gate():
    value = _load()
    result = validate_piston_scheduler_boundary_map_binding(value)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["board_vector_order_proven"] is True
    assert result["vek_piston_interleaving_proven"] is True
    assert result["dead_piston_action_cancellation_proven"] is True
    assert result["mission_environment_is_null"] is True
    assert result["mission_piston_scheduler_gate_closed"] is True
    assert result["simulator_change_required"] is True
    assert result["simulator_version"] == 408
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "board_vector_order_proven": True,
        "control_window_count": 15,
        "data_pointer_count": 3,
        "dead_piston_action_cancellation_proven": True,
        "dependency_count": 2,
        "direct_edge_count": 13,
        "finding_count": 8,
        "mission_environment_is_null": True,
        "mission_piston_scheduler_gate_closed": True,
        "neutral_piston_planning_proven": True,
        "region_count": 21,
        "simulator_change_required": True,
        "simulator_version": 408,
        "source_count": 3,
        "string_anchor_count": 1,
        "unresolved_count": 4,
        "vek_piston_interleaving_proven": True,
    }

    order = value["contracts"]["board_vector_order"]
    assert order["board_vector_begin_offset"] == "+0x3c"
    assert order["board_vector_end_offset"] == "+0x40"
    assert order["planning_neutral_offset"] == "+0x97c"
    assert order["planning_includes_team_or_neutral"] is True
    assert order["planning_filter_stable"] is True
    assert order["execution_returns_first_queued_pawn"] is True
    assert order["uid_sort_present"] is False
    assert order["pistons_and_vek_share_order_source"] is True

    cancellation = value["contracts"]["death_cancellation"]
    assert cancellation["explicit_kill_clears_queued_fields"] is True
    assert cancellation["shared_pawn_update_clears_queued_fields_before_return"] is True
    assert cancellation["earlier_queued_effect_blocks_next_selection_until_board_idle"] is True
    assert cancellation["corpse_remains_occupancy"] is True
    assert cancellation["corpse_retains_queued_action"] is False
    assert cancellation["stock_piston_death_before_selection_cancels_action"] is True

    chronology = value["contracts"]["exact_action_order"]
    assert chronology["order"] == (
        "first-to-last Board pawn vector among still-queued pawns"
    )
    assert chronology["vek_and_piston_actions_interleave"] is True
    assert chronology["dead_piston_slot_is_skipped"] is True
    assert chronology["corpse_wreck_is_not_removed_by_action_cancellation"] is True
    assert chronology["environment_precedence_changes_order"] is False

    source = value["contracts"]["mission_source"]
    assert source["environment_override_present"] is False
    assert source["inherited_environment"] == "Env_Null"
    assert source["environment_is_effect"] is False
    assert source["environment_apply_effect"] is False
    assert source["piston_corpse"] is True

    assert value["refines"] == [
        {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_"
                "corpse_classification_boundary.json"
            ),
            "narrowed_unresolved_ids": ["lifecycle_state_transition_timing"],
            "qualification": (
                "The general lifecycle-state question remains, but exact stock "
                "Piston planning, execution, death cancellation, and corpse occupancy "
                "are sufficient to close the Mission_Piston scheduler gate."
            ),
            "resolved_unresolved_ids": ["mission_piston_action_order"],
        }
    ]
    assert {item["id"] for item in value["unresolved"]} == {
        "mission_piston_setup_rng",
        "general_corpse_lifecycle_states",
        "modded_scheduler_variants",
        "non_windows_equivalence",
    }


def test_binding_rejects_order_cancellation_environment_or_version_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["board_vector_order"]["uid_sort_present"] = True
    with pytest.raises(PistonSchedulerBoundaryError, match="fields differ"):
        validate_piston_scheduler_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["death_cancellation"]["corpse_retains_queued_action"] = True
    with pytest.raises(PistonSchedulerBoundaryError, match="fields differ"):
        validate_piston_scheduler_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["mission_source"]["inherited_environment"] = "Env_Airstrike"
    with pytest.raises(PistonSchedulerBoundaryError, match="fields differ"):
        validate_piston_scheduler_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["solver_impact"]["implemented_simulator_version"] = 407
    with pytest.raises(PistonSchedulerBoundaryError, match="fields differ"):
        validate_piston_scheduler_boundary_map_binding(altered)


def test_bridge_rust_gate_version_and_archive_conform_to_native_map():
    bridge = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
        encoding="utf-8"
    )
    helper_start = bridge.index("local function mission_pistons")
    helper_end = bridge.index("\nlocal function mission_bridge_id", helper_start)
    helper = bridge[helper_start:helper_end]
    model = (ROOT / "src" / "model" / "board.py").read_text(encoding="utf-8")
    rust = (ROOT / "rust_solver" / "src" / "enemy.rs").read_text(
        encoding="utf-8"
    )
    commands = (ROOT / "src" / "loop" / "commands.py").read_text(
        encoding="utf-8"
    )
    rust_lib = (ROOT / "rust_solver" / "src" / "lib.rs").read_text(
        encoding="utf-8"
    )
    verify = (ROOT / "src" / "solver" / "verify.py").read_text(
        encoding="utf-8"
    )

    assert "for _, unit in ipairs(units) do" in helper
    assert "actions[#actions + 1]" in helper
    assert "table.sort(actions" not in helper
    assert "expected_order.append(uid)" in model
    assert "[uid for uid, _, _ in actions] != expected_order" in model
    assert "enum QueuedPawnAction" in rust
    assert "QueuedPawnAction::Piston(action)" in rust
    assert "simulate_mission_piston_action" in rust
    assert "for idx in 0..board.unit_count as usize" in rust
    assert 'board.mission_id == "Mission_Piston" && board.mission_pistons_known' in rust
    assert 'if getattr(board, "mission_pistons_known", False):' in commands
    assert "mission_piston_corpse_lifecycle_unknown" not in commands
    assert "pub const SIMULATOR_VERSION: u32 = 408;" in rust_lib
    assert "SIMULATOR_VERSION = 408" in verify

    archive = ROOT / "recordings" / "failure_db_snapshot_sim_v407.jsonl"
    assert archive.stat().st_size == 5_950_022
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == (
        "c3ec8cb98534ddb8a394dd860851bf123d6cd502d676651a11692c3d9576dfc8"
    )


def test_v408_bridge_is_hash_pinned_without_rewriting_predecessor_artifacts():
    bridge = ROOT / "src" / "bridge" / "modloader.lua"
    v408 = {
        "id": "mission_piston_v408_project_bridge",
        "size": 315_686,
        "sha256": (
            "5af8e809e6ed036084c84caed97f6a51a84785db2c2c0ee0c150da99adabf22d"
        ),
    }
    current = {
        "id": "enemy_tournament_hw_project_bridge",
        "size": bridge.stat().st_size,
        "sha256": hashlib.sha256(bridge.read_bytes()).hexdigest(),
    }
    assert current == {
        "id": "enemy_tournament_hw_project_bridge",
        "size": 357_175,
        "sha256": (
            "1abb8001eb6402c26d59fb09c05c78159a9199267130eecf9c73ccfd7879a5ac"
        ),
    }
    assert v408 in DEATH_EVENT_BRIDGE_OVERLAYS
    assert v408 in FINAL_CAVE_BRIDGE_OVERLAYS
    assert current in DEATH_EVENT_BRIDGE_OVERLAYS
    assert current in FINAL_CAVE_BRIDGE_OVERLAYS


def test_exact_local_executable_sources_and_dependencies_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_piston_scheduler_boundary_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["board_vector_order_proven"] is True
    assert result["vek_piston_interleaving_proven"] is True
    assert result["dead_piston_action_cancellation_proven"] is True
    assert result["mission_piston_scheduler_gate_closed"] is True
    assert result["simulator_version"] == 408
