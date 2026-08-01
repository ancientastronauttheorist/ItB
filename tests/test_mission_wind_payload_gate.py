"""Fail-closed checks for Mission_Wind's live warning payload."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from src.loop import commands
from src.loop.session import RunSession


def _wind_payload(*, columns: tuple[int, int] = (1, 5)) -> dict:
    positions = [[x, y] for x in columns for y in range(8)]
    return {
        "mission_id": "Mission_Wind",
        "phase": "combat_player",
        "in_active_mission": True,
        "turn": 2,
        "env_type": "wind",
        "environment_wind_dir": 2,
        "environment_danger": positions,
        "environment_danger_v2": [
            [x, y, 1, 0, 0] for x, y in positions
        ],
        "tiles": [],
        "units": [],
    }


def _gate(data: dict, *, mission_id: str = "Mission_Wind") -> dict | None:
    return commands._mission_wind_payload_block(
        SimpleNamespace(mission_id=mission_id), data,
    )


def _gap_kinds(block: dict) -> set[str]:
    return {gap["kind"] for gap in block["forecast_gaps"]}


def _patch_solve_inputs(monkeypatch, data: dict):
    session = RunSession(run_id="wind-payload-solve", squad="Random", difficulty=0)
    board = SimpleNamespace(mission_id=data["mission_id"], mechs=lambda: [])
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


def _patch_end_turn_inputs(monkeypatch, data: dict):
    mission_id = data["mission_id"]
    board = SimpleNamespace(mission_id=mission_id)
    session = RunSession(run_id="wind-payload-held", squad="Random", difficulty=0)
    session.current_mission = mission_id
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
    return session


@pytest.mark.parametrize("wind_dir", [0, 2])
def test_representative_complete_current_wind_payload_passes(wind_dir):
    data = _wind_payload()
    data["environment_wind_dir"] = wind_dir

    assert _gate(data) is None


def test_non_wind_mission_is_not_gated_by_wind_payload_shape():
    data = {
        "mission_id": "Mission_Battle",
        "env_type": "wind",
        "environment_wind_dir": None,
        "environment_danger": [],
        "environment_danger_v2": [],
    }

    assert _gate(data, mission_id="Mission_Battle") is None


@pytest.mark.parametrize("phase", ["combat_enemy", "deployment", "unknown", None])
def test_wind_payload_validation_is_scoped_to_combat_player(phase):
    data = _wind_payload()
    data["phase"] = phase
    data["environment_danger"] = []

    assert _gate(data) is None


@pytest.mark.parametrize("wind_dir", [1, 3])
def test_horizontal_raw_wind_directions_are_source_unreachable(wind_dir):
    data = _wind_payload()
    data["environment_wind_dir"] = wind_dir

    block = _gate(data)

    assert "mission_wind_direction_invalid" in _gap_kinds(block)
    gap = next(
        gap for gap in block["forecast_gaps"]
        if gap["kind"] == "mission_wind_direction_invalid"
    )
    assert gap["required_raw_directions"] == [0, 2]


@pytest.mark.parametrize("wind_dir", [None, -1, 4, True, "2"])
def test_direction_must_be_a_source_reachable_raw_engine_integer(wind_dir):
    data = _wind_payload()
    data["environment_wind_dir"] = wind_dir

    block = _gate(data)

    assert block["reason"] == "mission_wind_environment_payload_incomplete"
    assert "mission_wind_direction_invalid" in _gap_kinds(block)


@pytest.mark.parametrize("env_type", [None, "unknown", "Wind", "sandstorm"])
def test_environment_identity_must_be_authoritative_wind(env_type):
    data = _wind_payload()
    data["env_type"] = env_type

    block = _gate(data)

    assert "mission_wind_environment_identity_invalid" in _gap_kinds(block)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda data: data.update(environment_danger=[]),
            id="empty",
        ),
        pytest.param(
            lambda data: data["environment_danger"].pop(),
            id="partial-column",
        ),
        pytest.param(
            lambda data: data["environment_danger"].append([3, 3]),
            id="extra-tile",
        ),
        pytest.param(
            lambda data: data.update(
                environment_danger=[[x, y] for y in (2, 6) for x in range(8)]
            ),
            id="two-rows-not-columns",
        ),
        pytest.param(
            lambda data: data["environment_danger"].append(
                list(data["environment_danger"][0])
            ),
            id="duplicate",
        ),
        pytest.param(
            lambda data: data["environment_danger"].__setitem__(0, [8, 0]),
            id="out-of-bounds",
        ),
        pytest.param(
            lambda data: data.update(environment_danger_v2=None),
            id="missing-v2",
        ),
    ],
)
def test_malformed_partial_empty_extra_or_row_shaped_masks_block(mutate):
    data = _wind_payload()
    mutate(data)

    block = _gate(data)

    assert block["error"] == "RESEARCH_REQUIRED"
    assert block["requires_research"] is True
    assert block["blocking"] is True
    assert block["non_overridable"] is True
    assert block["forecast_complete"] is False
    assert _gap_kinds(block) & {
        "mission_wind_warning_mask_missing",
        "mission_wind_warning_mask_invalid",
        "mission_wind_warning_masks_disagree",
    }


def test_matching_shape_in_both_fields_is_required():
    data = _wind_payload()
    replacement = _wind_payload(columns=(2, 4))
    data["environment_danger_v2"] = replacement["environment_danger_v2"]

    block = _gate(data)

    assert "mission_wind_warning_masks_disagree" in _gap_kinds(block)


@pytest.mark.parametrize("columns", [(0, 1), (1, 6), (2, 7), (0, 7)])
def test_complete_outer_lane_columns_are_source_unreachable(columns):
    data = _wind_payload(columns=columns)

    block = _gate(data)

    assert "mission_wind_lane_columns_invalid" in _gap_kinds(block)
    lane_gaps = [
        gap for gap in block["forecast_gaps"]
        if gap["kind"] == "mission_wind_lane_columns_invalid"
    ]
    assert {gap["field"] for gap in lane_gaps} == {
        "environment_danger",
        "environment_danger_v2",
    }
    assert all(gap["required_column_subset"] == [1, 2, 3, 4, 5]
               for gap in lane_gaps)


@pytest.mark.parametrize(
    "replacement",
    [
        pytest.param([1, 0, 1, 0], id="truncated"),
        pytest.param([1, 0, "1", 0, 0], id="non-int-damage"),
        pytest.param([1, 0, 1, "0", 0], id="non-int-kill"),
        pytest.param([1, 0, 1, 0, "0"], id="non-int-flying-immune"),
        pytest.param([1, 0, 0, 0, 0], id="zero-damage"),
        pytest.param([1, 0, 2, 0, 0], id="wrong-damage"),
        pytest.param([1, 0, 1, 1, 0], id="lethal"),
        pytest.param([1, 0, 1, 0, 1], id="flying-immune"),
        pytest.param([1, 0, 1, 0, 0, 99], id="extra-field"),
    ],
)
def test_v2_requires_exact_current_nonlethal_wind_encoding(replacement):
    data = _wind_payload()
    data["environment_danger_v2"][0] = replacement

    block = _gate(data)

    assert "mission_wind_warning_encoding_invalid" in _gap_kinds(block)
    encoding_gap = next(
        gap for gap in block["forecast_gaps"]
        if gap["kind"] == "mission_wind_warning_encoding_invalid"
    )
    assert encoding_gap["field"] == "environment_danger_v2"
    assert encoding_gap["invalid_entry_indexes"] == [0]
    assert encoding_gap["required_v2_encoding"] == "[x, y, 1, 0, 0]"


def test_cmd_solve_returns_non_overridable_research_metadata(monkeypatch):
    data = _wind_payload()
    data["environment_danger"] = []
    _patch_solve_inputs(monkeypatch, data)

    result = commands.cmd_solve()

    assert result["error"] == "RESEARCH_REQUIRED"
    assert result["requires_research"] is True
    assert result["blocking"] is True
    assert result["non_overridable"] is True
    assert result["reason"] == "mission_wind_environment_payload_incomplete"
    assert result["mission_id"] == "Mission_Wind"
    assert result["forecast_complete"] is False
    assert "0=UP or 2=DOWN" in result["next"]
    assert "columns selected from 1..5" in result["next"]
    assert "[x,y,1,0,0]" in result["next"]


def test_auto_turn_preserves_wind_payload_gate_metadata(monkeypatch):
    data = _wind_payload()
    data["environment_danger_v2"] = []
    gate = _gate(data)
    session = RunSession(run_id="wind-payload-auto", squad="Random", difficulty=0)
    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_post_enemy_block_result", lambda _session: None)
    monkeypatch.setattr(commands, "_read_save_file_difficulty", lambda _profile: None)
    monkeypatch.setattr(
        commands,
        "cmd_read",
        lambda **_kwargs: {
            "status": "OK",
            "phase": "combat_player",
            "active_mechs": 1,
            "turn": 2,
        },
    )
    monkeypatch.setattr(commands, "cmd_solve", lambda **_kwargs: gate)

    result = commands.cmd_auto_turn(wait_for_turn=False)

    assert result["error"] == "Solve: RESEARCH_REQUIRED"
    assert result["requires_research"] is True
    assert result["blocking"] is True
    assert result["non_overridable"] is True
    assert result["reason"] == "mission_wind_environment_payload_incomplete"


@pytest.mark.parametrize(
    "command_name,kwargs,block_path",
    [
        ("cmd_click_end_turn", {}, ()),
        ("cmd_end_turn", {}, ()),
        ("cmd_dispatch_end_turn", {"execute": False}, ("block",)),
        ("cmd_dispatch_end_turn", {"execute": True}, ("plan",)),
    ],
)
def test_public_end_turn_paths_block_incomplete_wind_before_plan_or_dispatch(
    monkeypatch, command_name, kwargs, block_path,
):
    data = _wind_payload()
    data["environment_danger"] = data["environment_danger"][:-1]
    _patch_end_turn_inputs(monkeypatch, data)

    result = getattr(commands, command_name)(**kwargs)
    block = result
    for key in block_path:
        block = block[key]

    assert block["status"] == "END_TURN_BLOCKED"
    assert block["error"] == "RESEARCH_REQUIRED"
    assert block["requires_research"] is True
    assert block["blocking"] is True
    assert block["non_overridable"] is True
    assert block["reason"] == "held_end_turn_mission_wind_payload_incomplete"
    assert block["mission_id"] == "Mission_Wind"
    assert block["forecast_complete"] is False
    assert block["mission_wind_payload"]["reason"] == (
        "mission_wind_environment_payload_incomplete"
    )


def test_validator_does_not_mutate_live_bridge_payload():
    data = _wind_payload()
    original = deepcopy(data)

    assert _gate(data) is None
    assert data == original
