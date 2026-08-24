from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.enemy_score_list_semantics import (
    ANALYSIS_KIND,
    MAX_EXACT_LUA_NUMBER,
    SIGNED_MAX,
    EnemyScoreListSemanticsError,
    build_enemy_score_list_semantics,
    encode_enemy_score_list_semantics,
    replay_enemy_base_target_score,
    replay_enemy_score_list,
    validate_enemy_score_list_semantics,
    validate_enemy_score_list_semantics_binding,
)


ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")
INVENTORY = (
    ROOT
    / "data"
    / "observatory"
    / "inventories"
    / "windows_build_13725832_31fe35265598_local_modified.json"
)
SEMANTICS_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "callbacks"
    / "windows_build_13725832_31fe35265598_enemy_score_list_semantics.json"
)


def _load(path: Path = SEMANTICS_MAP) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _record(**overrides) -> dict:
    record = {
        "loc": [2, 3],
        "iDamage": 1,
        "sPawn": "",
        "is_movement": False,
        "move_start": None,
        "move_end": None,
        "board_is_valid": True,
        "board_is_pawn_space": False,
        "target_is_non_grid_structure": False,
        "target_team": 0,
        "target_is_frozen": False,
        "target_is_targeted": False,
        "target_is_dead": False,
        "target_is_temp_unit": False,
        "board_is_building": False,
        "board_is_powered": False,
        "board_is_pod": False,
        "positioning_score": None,
    }
    record.update(overrides)
    return record


def _score(records, **overrides):
    values = {
        "records": records,
        "queued": False,
        "pawn_space": [4, 5],
        "pawn_team": 6,
        "team_none": 0,
        "score_enemy": 5,
        "score_friendly_damage": -2,
        "score_building": 4,
        "score_nothing": 1,
    }
    values.update(overrides)
    return replay_enemy_score_list(**values)


def _base(effect_records, q_effect_records, **overrides):
    values = {
        "effect_records": effect_records,
        "q_effect_records": q_effect_records,
        "pawn_space": [4, 5],
        "pawn_team": 6,
        "team_none": 0,
        "score_enemy": 5,
        "score_friendly_damage": -2,
        "score_building": 4,
        "score_nothing": 1,
    }
    values.update(overrides)
    return replay_enemy_base_target_score(**values)


def test_committed_map_binds_complete_base_projection_without_overclaim():
    value = _load()
    result = validate_enemy_score_list_semantics_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "4871a8f128211e258f6737b2c221e5f7"
            "3789a021a95ecd995e5d5a3a86566d60"
        ),
        "score_list_projection_complete": True,
        "base_get_target_score_projection_complete": True,
        "score_positioning_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "dependency_count": 3,
        "source_region_count": 3,
        "replay_vector_count": 7,
        "finding_count": 6,
        "unresolved_count": 3,
        "score_list_projection_complete": True,
        "base_get_target_score_projection_complete": True,
        "score_positioning_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def test_source_regions_pin_exact_shipped_function_bodies():
    regions = {item["id"]: item for item in _load()["source_regions"]}

    assert regions["base_get_target_score"] == {
        "id": "base_get_target_score",
        "source_path": "scripts/global.lua",
        "symbol": "Skill:GetTargetScore",
        "line": 378,
        "body_size": 422,
        "body_sha256": (
            "85b370b2d3d9d4284ce94f03844a5047"
            "da731a6f4c06a4198a0604561df6d5f4"
        ),
    }
    assert regions["is_enemy_helper"]["line"] == 395
    assert regions["is_enemy_helper"]["body_size"] == 126
    assert regions["score_list"]["line"] == 400
    assert regions["score_list"]["body_size"] == 1541


def test_empty_list_returns_zero_and_invalid_record_is_skipped():
    empty = _score([])
    assert empty["record_count"] == 0
    assert empty["result"] == 0

    skipped = _score([_record(board_is_valid=False)])
    assert skipped["trace"][0]["branch"] == "invalid_skip"
    assert skipped["result"] == 0


@pytest.mark.parametrize(
    ("positioning", "expected", "override"),
    [(-5, 0, False), (-6, -6, True)],
)
def test_movement_position_threshold_is_strictly_below_minus_five(
    positioning,
    expected,
    override,
):
    movement = _record(
        board_is_valid=False,
        is_movement=True,
        move_start=[4, 5],
        move_end=[3, 5],
        positioning_score=positioning,
    )
    result = _score([movement], score_nothing=0)

    assert result["trace"][0]["moving_from_pawn"] is True
    assert result["trace"][0]["branch"] == "movement_position"
    assert result["position_override"] is override
    assert result["result"] == expected


def test_fractional_lua_position_scores_survive_and_can_cross_threshold():
    result = _score(
        [
            _record(
                is_movement=True,
                move_start=[4, 5],
                move_end=[3, 5],
                positioning_score=-10,
            ),
            _record(
                loc=[5, 5],
                is_movement=True,
                move_start=[4, 5],
                move_end=[5, 5],
                positioning_score=4.5,
            ),
        ],
        score_nothing=0,
    )

    assert result["position_score"] == -5.5
    assert result["position_override"] is True
    assert result["result"] == -5.5


def test_invalid_movement_not_from_pawn_is_skipped_without_position_call():
    movement = _record(
        board_is_valid=False,
        is_movement=True,
        move_start=[1, 1],
        move_end=[2, 1],
        positioning_score=None,
    )
    result = _score([movement])

    assert result["trace"][0]["branch"] == "invalid_skip"
    assert result["position_score"] == 0


def test_positioning_input_presence_must_match_the_exact_source_call():
    missing = _record(
        is_movement=True,
        move_start=[4, 5],
        move_end=[3, 5],
    )
    with pytest.raises(EnemyScoreListSemanticsError, match="presence differs"):
        _score([missing])

    unexpected = _record(positioning_score=-10)
    with pytest.raises(EnemyScoreListSemanticsError, match="presence differs"):
        _score([unexpected])


def test_non_grid_structure_precedes_friendly_enemy_building_and_pod_tests():
    record = _record(
        board_is_pawn_space=True,
        target_is_non_grid_structure=True,
        target_team=6,
        target_is_frozen=True,
        board_is_building=True,
        board_is_powered=True,
        board_is_pod=True,
    )
    result = _score([record])

    assert result["trace"][0]["branch"] == "non_grid_structure"
    assert result["result"] == 4


def test_frozen_untargeted_friend_uses_enemy_weight_but_targeted_friend_does_not():
    untargeted = _score([_record(target_team=6, target_is_frozen=True)])
    targeted = _score(
        [
            _record(
                target_team=6,
                target_is_frozen=True,
                target_is_targeted=True,
            )
        ]
    )

    assert untargeted["trace"][0]["branch"] == "friendly_frozen_untargeted"
    assert untargeted["result"] == 5
    assert targeted["trace"][0]["branch"] == "friendly_damage"
    assert targeted["result"] == -2


def test_friendly_zero_damage_falls_through_to_nothing():
    result = _score([_record(target_team=6, iDamage=0)])
    assert result["trace"][0]["branch"] == "nothing"
    assert result["result"] == 1


@pytest.mark.parametrize("terminal_field", ["target_is_dead", "target_is_temp_unit"])
def test_dead_or_temp_enemy_assigns_score_nothing_and_erases_prior_score(
    terminal_field,
):
    terminal = _record(loc=[3, 3], target_team=1, **{terminal_field: True})
    result = _score([_record(target_team=1), terminal])

    assert result["trace"][0]["branch"] == "enemy_live"
    assert result["trace"][1]["branch"] == "enemy_dead_or_temp_reset"
    assert result["trace"][1]["score_before"] == 5
    assert result["result"] == 1


def test_team_none_never_counts_as_enemy_for_either_side():
    no_target_team = _score([_record(target_team=0)])
    no_pawn_team = _score([_record(target_team=1)], pawn_team=0)

    assert no_target_team["trace"][0]["branch"] == "nothing"
    assert no_pawn_team["trace"][0]["branch"] == "nothing"


@pytest.mark.parametrize(
    ("building", "powered", "damage", "branch", "score"),
    [
        (True, True, 1, "powered_building_damage", 4),
        (True, False, 1, "nothing", 1),
        (True, True, 0, "nothing", 1),
    ],
)
def test_building_score_requires_power_and_positive_damage(
    building,
    powered,
    damage,
    branch,
    score,
):
    result = _score(
        [
            _record(
                board_is_building=building,
                board_is_powered=powered,
                iDamage=damage,
            )
        ]
    )
    assert result["trace"][0]["branch"] == branch
    assert result["result"] == score


@pytest.mark.parametrize(
    ("queued", "damage", "pawn", "expected_branch", "expected"),
    [
        (False, 1, "", "instant_pod_veto", -100),
        (False, 0, "Blob1", "instant_pod_veto", -100),
        (False, 0, "", "nothing", 1),
        (True, 1, "", "nothing", 1),
    ],
)
def test_pod_veto_requires_instant_damage_or_spawn(
    queued,
    damage,
    pawn,
    expected_branch,
    expected,
):
    result = _score(
        [_record(board_is_pod=True, iDamage=damage, sPawn=pawn)],
        queued=queued,
    )
    assert result["trace"][0]["branch"] == expected_branch
    assert result["result"] == expected


def test_base_target_score_runs_queue_first_but_instant_catastrophe_wins():
    result = _base(
        [_record(target_team=6)],
        [_record(target_team=1)],
        score_friendly_damage=-21,
    )

    assert result["evaluation_order"] == ["q_effect", "effect"]
    assert result["q_effect"]["result"] == 5
    assert result["effect"]["result"] == -21
    assert result["selected_branch"] == "instant_below_minus_twenty"
    assert result["result"] == -100


def test_base_target_score_minus_twenty_is_not_catastrophic():
    result = _base(
        [_record(target_team=6)],
        [],
        score_friendly_damage=-20,
    )
    assert result["selected_branch"] == "empty_q_effect_uses_instant"
    assert result["result"] == -20


def test_base_target_score_chooses_instant_only_for_empty_queue():
    empty_queue = _base([_record(target_team=1)], [])
    nonempty_queue = _base(
        [_record(target_team=1)],
        [_record(target_team=0)],
    )

    assert empty_queue["selected_branch"] == "empty_q_effect_uses_instant"
    assert empty_queue["result"] == 5
    assert nonempty_queue["selected_branch"] == "nonempty_q_effect_uses_queued"
    assert nonempty_queue["result"] == 1


def test_replay_rejects_schema_type_movement_and_accumulation_drift():
    missing = _record()
    del missing["board_is_pod"]
    with pytest.raises(EnemyScoreListSemanticsError, match="fields differ"):
        _score([missing])

    with pytest.raises(EnemyScoreListSemanticsError, match="queued"):
        _score([], queued=1)

    bad_movement = _record(is_movement=True)
    with pytest.raises(EnemyScoreListSemanticsError, match="requires start and end"):
        _score([bad_movement])

    with pytest.raises(EnemyScoreListSemanticsError, match="signed 32-bit"):
        _score([], score_enemy=SIGNED_MAX + 1)

    with pytest.raises(EnemyScoreListSemanticsError, match="exact Lua-number"):
        _score(
            [
                _record(
                    is_movement=True,
                    move_start=[4, 5],
                    move_end=[3, 5],
                    positioning_score=MAX_EXACT_LUA_NUMBER,
                ),
                _record(
                    loc=[5, 5],
                    is_movement=True,
                    move_start=[4, 5],
                    move_end=[5, 5],
                    positioning_score=MAX_EXACT_LUA_NUMBER,
                ),
            ],
        )


def test_committed_replay_vectors_recompute_from_public_helpers():
    for vector in _load()["replay_vectors"]:
        replay = (
            replay_enemy_score_list
            if vector["replay"] == "score_list"
            else replay_enemy_base_target_score
        )
        assert replay(**vector["input"]) == vector["expected"]


def test_binding_rejects_branch_closure_and_replay_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["branch_order"][0] = "enemy"
    with pytest.raises(EnemyScoreListSemanticsError, match="fields differ"):
        validate_enemy_score_list_semantics_binding(altered)

    altered = copy.deepcopy(value)
    altered["closure"]["score_positioning_complete"] = True
    with pytest.raises(EnemyScoreListSemanticsError, match="fields differ"):
        validate_enemy_score_list_semantics_binding(altered)

    altered = copy.deepcopy(value)
    altered["replay_vectors"][0]["expected"]["result"] = 7
    with pytest.raises(EnemyScoreListSemanticsError, match="fields differ"):
        validate_enemy_score_list_semantics_binding(altered)


def test_inventory_binding_and_encoding_fail_closed():
    inventory = _load(INVENTORY)
    altered = copy.deepcopy(inventory)
    altered["steam"]["build_id"] = "different"
    with pytest.raises(EnemyScoreListSemanticsError, match="inventory fields differ"):
        build_enemy_score_list_semantics(CONTENT_ROOT, altered)

    value = _load()
    encoded = encode_enemy_score_list_semantics(value)
    assert encoded.endswith("\n")
    assert json.loads(encoded) == value
    assert encoded == encode_enemy_score_list_semantics(value)


def test_exact_installed_source_rebuilds_committed_map_when_available():
    if not (CONTENT_ROOT / "scripts" / "global.lua").is_file():
        pytest.skip("exact local ITB content root is not available")

    result = validate_enemy_score_list_semantics(
        CONTENT_ROOT,
        _load(INVENTORY),
        _load(),
    )
    assert result["status"] == "verified"
    assert result["score_list_projection_complete"] is True
    assert result["base_get_target_score_projection_complete"] is True
    assert result["score_positioning_complete"] is False
    assert result["simulator_change_required"] is False
