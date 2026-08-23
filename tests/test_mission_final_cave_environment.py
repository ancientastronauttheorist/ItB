"""Exact current-turn contracts for Mission_Final_Cave's Env_Final."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.bridge.reader import _normalize_mission_final_cave
from src.loop import commands
from src.loop.session import RunSession
from src.model.board import (
    Board,
    FINAL_CAVE_LAVA,
    FINAL_CAVE_ROCKS,
    validate_mission_final_cave_payload,
)
from src.strategy.mission_picker import NATIVE_FORECAST_GATED_MISSION_IDS

try:
    from lupa import lua51
except ImportError:  # pragma: no cover - optional local test dependency
    lua51 = None


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _phase_locations(phase: int) -> list[list[int]]:
    return {
        1: [[2, 2], [2, 5], [5, 2], [5, 5]],
        2: [[5, 1], [4, 2], [4, 4]],
        3: [[4, 2], [4, 1], [5, 1], [5, 2], [4, 3], [3, 3]],
        4: [[x, 2] for x in range(8)],
    }[phase]


def _cave_payload(
    *,
    phase: int = 1,
    locations: list[list[int]] | None = None,
    lava_path: list[list[int]] | None = None,
) -> dict:
    mode = FINAL_CAVE_ROCKS if phase in {1, 3} else FINAL_CAVE_LAVA
    locations = deepcopy(locations if locations is not None else _phase_locations(phase))
    lava_path = deepcopy(
        lava_path
        if lava_path is not None
        else [[2, y] for y in range(8)] + [[x, 4] for x in range(3, 8)]
    )
    return {
        "mission_id": "Mission_Final_Cave",
        "phase": "combat_player",
        "in_active_mission": True,
        "turn": phase,
        "env_type": "final_cave",
        "mission_final_cave": {
            "complete": True,
            "mode": mode,
            "phase": phase,
            "ordered": True,
            "instant": phase in {3, 4},
            "water_target": mode == FINAL_CAVE_ROCKS,
            "lava_path": lava_path,
            "locations": deepcopy(locations),
            "planned": deepcopy(locations),
        },
        "environment_danger": deepcopy(locations),
        "environment_danger_v2": [[x, y, 1, 1, 0] for x, y in locations],
        "tiles": [],
        "units": [],
        "spawning_tiles": [],
    }


def _gate(data: dict, mission_id: str = "Mission_Final_Cave") -> dict | None:
    return commands._mission_final_cave_payload_block(
        SimpleNamespace(mission_id=mission_id), data,
    )


def _gap_kinds(block: dict) -> set[str]:
    return {gap["kind"] for gap in block["forecast_gaps"]}


def _load_lua_helper():
    if lua51 is None:
        pytest.skip("exact Lua 5.1 Env_Final harness requires lupa.lua51")
    source = MODLOADER.read_text(encoding="utf-8")
    start = source.index("local function mission_final_volcano_points")
    end = source.index("\nlocal function mission_terraform_grass_tiles", start)
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    helper = runtime.execute(source[start:end] + "\nreturn mission_final_cave")
    return helper, runtime


def _lua_point_list(runtime, points):
    return runtime.table_from([
        runtime.table_from({"x": x, "y": y}) for x, y in points
    ])


def _lua_environment(runtime, payload: dict):
    cave = payload["mission_final_cave"]
    return runtime.table_from({
        "Mode": cave["mode"],
        "Phase": cave["phase"],
        "Ordered": cave["ordered"],
        "Instant": cave["instant"],
        "WaterTarget": cave["water_target"],
        "LavaPath": _lua_point_list(runtime, cave["lava_path"]),
        "Locations": _lua_point_list(runtime, cave["locations"]),
        "Planned": _lua_point_list(runtime, cave["planned"]),
    })


def _from_lua_points(points) -> list[list[int]]:
    return [[points[i][1], points[i][2]] for i in range(1, len(points) + 1)]


@pytest.mark.parametrize("phase", [1, 2, 3, 4])
def test_lua_helper_exports_each_source_phase_atomically(phase):
    helper, runtime = _load_lua_helper()
    payload = _cave_payload(phase=phase)
    result = helper("Mission_Final_Cave", _lua_environment(runtime, payload))
    expected = payload["mission_final_cave"]

    assert result["complete"] is True
    assert result["mode"] == expected["mode"]
    assert result["phase"] == expected["phase"]
    assert result["ordered"] is True
    assert result["instant"] is expected["instant"]
    assert result["water_target"] is expected["water_target"]
    assert _from_lua_points(result["lava_path"]) == expected["lava_path"]
    assert _from_lua_points(result["locations"]) == expected["locations"]
    assert _from_lua_points(result["planned"]) == expected["planned"]


def test_lua_helper_fails_closed_for_malformed_or_foreign_state():
    helper, runtime = _load_lua_helper()
    valid = _cave_payload()
    assert helper("Mission_Battle", _lua_environment(runtime, valid)) is None

    malformed = deepcopy(valid)
    malformed["mission_final_cave"]["planned"] = [[2, 2]]
    result = helper(
        "Mission_Final_Cave", _lua_environment(runtime, malformed)
    )
    assert result["complete"] is False
    assert len(result["locations"]) == 0


def test_reader_canonicalizes_valid_state_and_drops_partial_state():
    valid = _cave_payload(phase=3)
    _normalize_mission_final_cave(valid)
    assert valid["mission_final_cave"] == _cave_payload(phase=3)[
        "mission_final_cave"
    ]

    invalid = _cave_payload()
    invalid["mission_final_cave"]["ordered"] = False
    _normalize_mission_final_cave(invalid)
    assert "mission_final_cave" not in invalid


def test_python_board_copy_and_lava_probe_preserve_exact_cave_state():
    payload = _cave_payload(phase=2)
    payload["tiles"] = [
        {"x": 1, "y": 1, "terrain_id": 3, "terrain": "water", "lava": True},
        {"x": 1, "y": 2, "terrain_id": 3, "terrain": "lava"},
    ]
    payload["environment_danger_v2"][0][4] = 1
    board = Board.from_bridge_data(payload)
    copied = board.copy()

    assert board.environment_final_cave_known is True
    assert board.environment_final_cave_mode == FINAL_CAVE_LAVA
    assert board.environment_final_cave_phase == 2
    assert board.environment_final_cave_instant is False
    assert board.environment_final_cave_locations == [
        (5, 1), (4, 2), (4, 4)
    ]
    assert copied.environment_final_cave_locations == (
        board.environment_final_cave_locations
    )
    assert board.tile(1, 1).terrain == "lava"
    assert board.tile(1, 2).terrain == "water"
    assert board.environment_danger_v2[(5, 1)] == (1, True)
    assert board.environment_danger_flying_immune == set()


@pytest.mark.parametrize("phase", [1, 2, 3, 4])
def test_complete_current_cave_payload_passes_strict_gate(phase):
    payload = _cave_payload(phase=phase)
    assert validate_mission_final_cave_payload(payload) is not None
    assert _gate(payload) is None


def test_repeating_turn_cycle_accepts_turn_five_as_phase_one():
    payload = _cave_payload(phase=1)
    payload["turn"] = 5
    assert _gate(payload) is None


def test_phase_three_requires_the_native_center_first_not_scan_order():
    payload = _cave_payload(phase=3)
    scan_order = [[4, 1], [5, 1], [3, 2], [4, 2], [3, 3], [4, 3]]
    payload["mission_final_cave"]["locations"] = deepcopy(scan_order)
    payload["mission_final_cave"]["planned"] = deepcopy(scan_order)
    payload["environment_danger"] = deepcopy(scan_order)
    payload["environment_danger_v2"] = [
        [x, y, 1, 1, 0] for x, y in scan_order
    ]

    assert validate_mission_final_cave_payload(payload) is None
    assert "mission_final_cave_state_invalid" in _gap_kinds(_gate(payload))


@pytest.mark.parametrize("phase", ["combat_enemy", "deployment", "unknown", None])
def test_cave_payload_gate_is_scoped_to_combat_player(phase):
    data = _cave_payload()
    data["phase"] = phase
    data["mission_final_cave"]["complete"] = False
    assert _gate(data) is None


def test_foreign_mission_is_not_gated_by_cave_payload_shape():
    data = _cave_payload()
    data["mission_id"] = "Mission_Battle"
    assert _gate(data, mission_id="Mission_Battle") is None


@pytest.mark.parametrize(
    "mutate,expected_gap",
    [
        pytest.param(
            lambda data: data.update(env_type="unknown"),
            "mission_final_cave_environment_identity_invalid",
            id="environment-identity",
        ),
        pytest.param(
            lambda data: data["mission_final_cave"].update(mode=FINAL_CAVE_LAVA),
            "mission_final_cave_state_invalid",
            id="mode-phase-parity",
        ),
        pytest.param(
            lambda data: data["mission_final_cave"].update(instant=True),
            "mission_final_cave_state_invalid",
            id="instant-contract",
        ),
        pytest.param(
            lambda data: data["mission_final_cave"].update(water_target=False),
            "mission_final_cave_state_invalid",
            id="water-target-contract",
        ),
        pytest.param(
            lambda data: data["mission_final_cave"].update(lava_path=[]),
            "mission_final_cave_state_invalid",
            id="lava-path-evidence",
        ),
        pytest.param(
            lambda data: data["mission_final_cave"].update(planned=[[2, 2]]),
            "mission_final_cave_state_invalid",
            id="planned-mismatch",
        ),
        pytest.param(
            lambda data: data.update(turn=2),
            "mission_final_cave_turn_phase_mismatch",
            id="turn-phase-mismatch",
        ),
        pytest.param(
            lambda data: data["environment_danger"].pop(),
            "mission_final_cave_warning_mask_invalid",
            id="warning-mask-mismatch",
        ),
        pytest.param(
            lambda data: data["environment_danger_v2"][0].__setitem__(4, 1),
            "mission_final_cave_warning_mask_invalid",
            id="flying-immunity-wire-encoding",
        ),
    ],
)
def test_partial_stale_or_source_unreachable_payloads_fail_closed(
    mutate, expected_gap,
):
    data = _cave_payload()
    mutate(data)
    block = _gate(data)

    assert block["error"] == "RESEARCH_REQUIRED"
    assert block["requires_research"] is True
    assert block["blocking"] is True
    assert block["non_overridable"] is True
    assert block["reason"] == "mission_final_cave_payload_incomplete"
    assert expected_gap in _gap_kinds(block)


def _patch_solve_inputs(monkeypatch, data: dict):
    session = RunSession(run_id="cave-solve", squad="Random", difficulty=0)
    board = SimpleNamespace(mission_id="Mission_Final_Cave", mechs=lambda: [])
    monkeypatch.setattr(commands, "_check_wheel_sim_version", lambda: None)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_post_enemy_block_result", lambda _session: None)
    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (board, data))
    monkeypatch.setattr(
        commands, "_enrich_bridge_mech_weapons_from_save", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        commands,
        "_enrich_bridge_limited_mission_weapons_from_save",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        commands, "_final_post_enemy_audit_gate", lambda *_args, **_kwargs: None
    )


def test_cmd_solve_blocks_incomplete_payload_but_accepts_modeled_cave(monkeypatch):
    invalid = _cave_payload()
    invalid["environment_danger"] = []
    _patch_solve_inputs(monkeypatch, invalid)
    result = commands.cmd_solve()
    assert result["reason"] == "mission_final_cave_payload_incomplete"

    valid = _cave_payload()
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (
            SimpleNamespace(mission_id="Mission_Final_Cave", mechs=lambda: []),
            valid,
        ),
    )
    result = commands.cmd_solve()
    assert result["error"].startswith("No active mechs")
    assert "Mission_Final_Cave" not in NATIVE_FORECAST_GATED_MISSION_IDS
    assert commands._mission_native_forecast_block(
        SimpleNamespace(mission_id="Mission_Final_Cave"), valid,
    ) is None


def _patch_end_turn_inputs(monkeypatch, data: dict):
    board = SimpleNamespace(mission_id="Mission_Final_Cave")
    session = RunSession(run_id="cave-held", squad="Random", difficulty=0)
    session.current_mission = "Mission_Final_Cave"
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_post_enemy_block_result", lambda _session: None)
    monkeypatch.setattr(commands, "_refresh_end_turn_bridge_state", lambda: True)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (board, data))
    monkeypatch.setattr(
        commands, "_enrich_bridge_mech_weapons_from_save", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        commands,
        "_enrich_bridge_limited_mission_weapons_from_save",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        commands,
        "plan_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("must not plan End Turn")),
    )
    monkeypatch.setattr(
        commands,
        "execute_bridge_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("must not dispatch End Turn")),
    )


@pytest.mark.parametrize(
    "command_name,kwargs,block_path",
    [
        ("cmd_click_end_turn", {}, ()),
        ("cmd_end_turn", {}, ()),
        ("cmd_dispatch_end_turn", {"execute": False}, ("block",)),
        ("cmd_dispatch_end_turn", {"execute": True}, ("plan",)),
    ],
)
def test_public_end_turn_paths_block_incomplete_cave_before_dispatch(
    monkeypatch, command_name, kwargs, block_path,
):
    data = _cave_payload()
    data["environment_danger_v2"].pop()
    _patch_end_turn_inputs(monkeypatch, data)

    block = getattr(commands, command_name)(**kwargs)
    for key in block_path:
        block = block[key]
    assert block["status"] == "END_TURN_BLOCKED"
    assert block["reason"] == "held_end_turn_mission_final_cave_payload_incomplete"
    assert block["mission_final_cave_payload"]["reason"] == (
        "mission_final_cave_payload_incomplete"
    )


def test_gate_does_not_mutate_live_bridge_payload():
    data = _cave_payload()
    original = deepcopy(data)
    assert _gate(data) is None
    assert data == original


def test_checkpoint_schema_accepts_exact_current_and_consumed_future_state():
    checkpoint = _cave_payload(phase=4)
    checkpoint.update({
        "grid_power": 7,
        "grid_power_max": 7,
        "total_turns": 6,
        "remaining_spawns": 0,
        "mission_kill_target": 0,
        "mission_kill_limit": 0,
        "mission_kills_done": 0,
        "mission_mountain_target": 0,
        "mission_mountains_destroyed": 0,
        "repair_platform_target": 0,
        "repair_platforms_used": 0,
        "freeze_building_target": 0,
        "attack_order": [],
        "environment_freeze": [],
        "freeze_building_tiles": [],
        "mission_mountain_tiles": [],
        "teleporter_pairs": [],
        "bonus_objective_unit_types": [],
        "destroy_objective_unit_types": [],
        "protect_objective_unit_types": [],
        "tiles": [
            {"x": x, "y": y, "terrain": "ground"}
            for x in range(8)
            for y in range(8)
        ],
    })
    assert commands._held_end_turn_bridge_checkpoint_schema_error(
        checkpoint
    ) is None

    consumed = deepcopy(checkpoint)
    consumed["turn"] = 5
    consumed.pop("mission_final_cave")
    consumed["environment_danger"] = []
    consumed["environment_danger_v2"] = []
    assert commands._held_end_turn_bridge_checkpoint_schema_error(
        consumed
    ) is None

    malformed = deepcopy(checkpoint)
    malformed["mission_final_cave"]["complete"] = False
    assert commands._held_end_turn_bridge_checkpoint_schema_error(
        malformed
    ) == "checkpoint_mission_final_cave_invalid"
