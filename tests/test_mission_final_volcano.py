"""Exact bridge and solver-boundary contracts for surface-final Env_Volcano."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.bridge.reader import _normalize_mission_final_volcano
from src.loop import commands
from src.loop.session import RunSession
from src.model.board import (
    Board,
    VOLCANO_LAVA,
    VOLCANO_ROCKS,
    validate_mission_final_volcano_payload,
)
from src.strategy.mission_picker import NATIVE_FORECAST_GATED_MISSION_IDS

try:
    from lupa import lua51
except ImportError:  # pragma: no cover - optional local test dependency
    lua51 = None


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _volcano_payload(
    *,
    mode=VOLCANO_LAVA,
    phase=1,
    lava_start=None,
    locations=None,
) -> dict:
    if lava_start is None:
        lava_start = [[1, 2]] if phase in {1, 2} else []
    if locations is None:
        locations = (
            [[2, 1], [3, 1], [3, 2]]
            if mode == VOLCANO_LAVA
            else [[2, 2], [2, 5], [5, 2], [5, 5]]
        )
    encoding = [0, 0, 0] if mode == VOLCANO_LAVA else [1, 1, 0]
    return {
        "mission_id": "Mission_Final",
        "phase": "combat_player",
        "in_active_mission": True,
        "turn": phase,
        "env_type": "volcano",
        "mission_final_volcano": {
            "complete": True,
            "mode": mode,
            "phase": phase,
            "lava_start": deepcopy(lava_start),
            "locations": deepcopy(locations),
            "planned": deepcopy(locations),
        },
        "environment_danger": deepcopy(locations),
        "environment_danger_v2": [
            [x, y, *encoding] for x, y in locations
        ],
        "tiles": [],
        "units": [],
        "spawning_tiles": [],
    }


def _gate(data: dict, mission_id="Mission_Final") -> dict | None:
    return commands._mission_final_volcano_payload_block(
        SimpleNamespace(mission_id=mission_id), data,
    )


def _gap_kinds(block: dict) -> set[str]:
    return {gap["kind"] for gap in block["forecast_gaps"]}


def _load_lua_helper():
    if lua51 is None:
        pytest.skip("exact Lua 5.1 Env_Volcano harness requires lupa.lua51")
    source = MODLOADER.read_text(encoding="utf-8")
    start = source.index("local function mission_final_volcano_points")
    end = source.index("\nlocal function mission_terraform_grass_tiles", start)
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    helper = runtime.execute(
        source[start:end] + "\nreturn mission_final_volcano"
    )
    return helper, runtime


def _lua_point_list(runtime, points):
    return runtime.table_from([
        runtime.table_from({"x": x, "y": y}) for x, y in points
    ])


def _lua_environment(runtime, payload: dict):
    volcano = payload["mission_final_volcano"]
    return runtime.table_from({
        "Mode": volcano["mode"],
        "Phase": volcano["phase"],
        "LavaStart": _lua_point_list(runtime, volcano["lava_start"]),
        "Locations": _lua_point_list(runtime, volcano["locations"]),
        "Planned": _lua_point_list(runtime, volcano["planned"]),
    })


def _from_lua_points(points) -> list[list[int]]:
    return [[points[i][1], points[i][2]] for i in range(1, len(points) + 1)]


@pytest.mark.parametrize(
    "payload",
    [
        _volcano_payload(mode=VOLCANO_LAVA, phase=1),
        _volcano_payload(mode=VOLCANO_ROCKS, phase=2),
        _volcano_payload(
            mode=VOLCANO_LAVA,
            phase=3,
            lava_start=[],
            locations=[[1, 2], [2, 2], [2, 3]],
        ),
        _volcano_payload(
            mode=VOLCANO_ROCKS,
            phase=4,
            lava_start=[],
        ),
    ],
)
def test_lua_helper_exports_each_source_reachable_phase_atomically(payload):
    helper, runtime = _load_lua_helper()
    result = helper("Mission_Final", _lua_environment(runtime, payload))
    expected = payload["mission_final_volcano"]

    assert result["complete"] is True
    assert result["mode"] == expected["mode"]
    assert result["phase"] == expected["phase"]
    assert _from_lua_points(result["lava_start"]) == expected["lava_start"]
    assert _from_lua_points(result["locations"]) == expected["locations"]
    assert _from_lua_points(result["planned"]) == expected["planned"]


def test_lua_helper_fails_closed_for_malformed_or_nonfinal_state():
    helper, runtime = _load_lua_helper()
    valid = _volcano_payload()
    assert helper("Mission_Battle", _lua_environment(runtime, valid)) is None

    malformed = deepcopy(valid)
    malformed["mission_final_volcano"]["planned"] = [[2, 1]]
    result = helper("Mission_Final", _lua_environment(runtime, malformed))
    assert result["complete"] is False
    assert len(result["locations"]) == 0


def test_reader_canonicalizes_valid_state_and_drops_partial_state():
    valid = _volcano_payload()
    _normalize_mission_final_volcano(valid)
    assert valid["mission_final_volcano"] == {
        "complete": True,
        "mode": VOLCANO_LAVA,
        "phase": 1,
        "lava_start": [[1, 2]],
        "locations": [[2, 1], [3, 1], [3, 2]],
        "planned": [[2, 1], [3, 1], [3, 2]],
    }

    invalid = _volcano_payload()
    invalid["mission_final_volcano"]["planned"] = [[2, 1]]
    _normalize_mission_final_volcano(invalid)
    assert "mission_final_volcano" not in invalid


def test_python_board_and_copy_preserve_exact_ordered_volcano_state():
    lava = Board.from_bridge_data(_volcano_payload())
    copied = lava.copy()

    assert lava.environment_volcano_known is True
    assert lava.environment_volcano_mode == VOLCANO_LAVA
    assert lava.environment_volcano_phase == 1
    assert lava.environment_volcano_lava_start == [(1, 2)]
    assert lava.environment_volcano_locations == [(2, 1), (3, 1), (3, 2)]
    assert copied.environment_volcano_known is True
    assert copied.environment_volcano_locations == lava.environment_volcano_locations
    assert lava.environment_danger_v2[(2, 1)] == (0, False)

    rocks = Board.from_bridge_data(_volcano_payload(
        mode=VOLCANO_ROCKS,
        phase=2,
    ))
    assert rocks.environment_volcano_mode == VOLCANO_ROCKS
    assert rocks.environment_danger_v2[(2, 2)] == (1, True)


@pytest.mark.parametrize(
    "payload",
    [
        _volcano_payload(),
        _volcano_payload(mode=VOLCANO_ROCKS, phase=2),
        _volcano_payload(
            mode=VOLCANO_LAVA,
            phase=3,
            lava_start=[],
            locations=[[1, 2], [2, 2], [2, 3]],
        ),
        _volcano_payload(mode=VOLCANO_ROCKS, phase=4, lava_start=[]),
    ],
)
def test_complete_current_volcano_payload_passes_strict_gate(payload):
    assert validate_mission_final_volcano_payload(payload) is not None
    assert _gate(payload) is None


@pytest.mark.parametrize("phase", ["combat_enemy", "deployment", "unknown", None])
def test_volcano_payload_gate_is_scoped_to_combat_player(phase):
    data = _volcano_payload()
    data["phase"] = phase
    data["mission_final_volcano"]["complete"] = False
    assert _gate(data) is None


def test_nonfinal_mission_is_not_gated_by_volcano_payload_shape():
    data = _volcano_payload()
    data["mission_id"] = "Mission_Battle"
    assert _gate(data, mission_id="Mission_Battle") is None


@pytest.mark.parametrize(
    "mutate,expected_gap",
    [
        pytest.param(
            lambda data: data.update(env_type="unknown"),
            "mission_final_volcano_environment_identity_invalid",
            id="environment-identity",
        ),
        pytest.param(
            lambda data: data["mission_final_volcano"].update(mode=VOLCANO_ROCKS),
            "mission_final_volcano_state_invalid",
            id="mode-phase-parity",
        ),
        pytest.param(
            lambda data: data["mission_final_volcano"].update(lava_start=[]),
            "mission_final_volcano_state_invalid",
            id="lava-start-remainder",
        ),
        pytest.param(
            lambda data: data["mission_final_volcano"]["locations"].__setitem__(
                2, [4, 2]
            ),
            "mission_final_volcano_state_invalid",
            id="diagonal-lava-path",
        ),
        pytest.param(
            lambda data: data["mission_final_volcano"].update(planned=[[2, 1]]),
            "mission_final_volcano_state_invalid",
            id="planned-mismatch",
        ),
        pytest.param(
            lambda data: data.update(turn=2),
            "mission_final_volcano_turn_phase_mismatch",
            id="turn-phase-mismatch",
        ),
        pytest.param(
            lambda data: data["environment_danger"].pop(),
            "mission_final_volcano_warning_mask_invalid",
            id="warning-mask-mismatch",
        ),
        pytest.param(
            lambda data: data["environment_danger_v2"][0].__setitem__(2, 1),
            "mission_final_volcano_warning_mask_invalid",
            id="lava-wire-encoding",
        ),
    ],
)
def test_partial_stale_or_source_unreachable_payloads_fail_closed(
    mutate, expected_gap,
):
    data = _volcano_payload()
    mutate(data)
    block = _gate(data)

    assert block["error"] == "RESEARCH_REQUIRED"
    assert block["requires_research"] is True
    assert block["blocking"] is True
    assert block["non_overridable"] is True
    assert block["reason"] == "mission_final_volcano_payload_incomplete"
    assert expected_gap in _gap_kinds(block)


def _patch_solve_inputs(monkeypatch, data: dict):
    session = RunSession(run_id="volcano-solve", squad="Random", difficulty=0)
    board = SimpleNamespace(mission_id="Mission_Final", mechs=lambda: [])
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


def test_cmd_solve_blocks_incomplete_payload_but_not_modeled_final(monkeypatch):
    invalid = _volcano_payload()
    invalid["environment_danger"] = []
    _patch_solve_inputs(monkeypatch, invalid)
    result = commands.cmd_solve()
    assert result["reason"] == "mission_final_volcano_payload_incomplete"

    valid = _volcano_payload()
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (SimpleNamespace(mission_id="Mission_Final", mechs=lambda: []), valid),
    )
    result = commands.cmd_solve()
    assert result["error"].startswith("No active mechs")
    assert "Mission_Final" not in NATIVE_FORECAST_GATED_MISSION_IDS
    assert commands._mission_native_forecast_block(
        SimpleNamespace(mission_id="Mission_Final"), valid,
    ) is None


def _patch_end_turn_inputs(monkeypatch, data: dict):
    board = SimpleNamespace(mission_id="Mission_Final")
    session = RunSession(run_id="volcano-held", squad="Random", difficulty=0)
    session.current_mission = "Mission_Final"
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
def test_public_end_turn_paths_block_incomplete_volcano_before_dispatch(
    monkeypatch, command_name, kwargs, block_path,
):
    data = _volcano_payload()
    data["environment_danger_v2"].pop()
    _patch_end_turn_inputs(monkeypatch, data)

    block = getattr(commands, command_name)(**kwargs)
    for key in block_path:
        block = block[key]
    assert block["status"] == "END_TURN_BLOCKED"
    assert block["reason"] == (
        "held_end_turn_mission_final_volcano_payload_incomplete"
    )
    assert block["mission_final_volcano_payload"]["reason"] == (
        "mission_final_volcano_payload_incomplete"
    )


def test_gate_does_not_mutate_live_bridge_payload():
    data = _volcano_payload()
    original = deepcopy(data)
    assert _gate(data) is None
    assert data == original
