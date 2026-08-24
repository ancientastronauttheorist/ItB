from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.enemy_skill_effect_boundary import (
    ANALYSIS_KIND,
    MAX_EFFECT_RECORDS,
    REPLAY_KIND,
    EnemySkillEffectBoundaryError,
    encode_enemy_skill_effect_boundary_map,
    replay_enemy_skill_effect_boundary,
    validate_enemy_skill_effect_boundary_map,
    validate_enemy_skill_effect_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_"
    "enemy_skill_effect_boundary.json"
)
EXECUTABLE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def _record(
    loc: tuple[int, int] = (2, 3),
    damage: int = 1,
    *,
    animation: str = "",
    origin: tuple[int, int] = (-1, -1),
    source_tag: int = 2,
    boost_marker: bool = False,
) -> dict:
    return {
        "loc": list(loc),
        "iDamage": damage,
        "sAnimation": animation,
        "piOrigin": list(origin),
        "native_source_tag": source_tag,
        "native_boost_marker": boost_marker,
    }


def _effect(
    effect: list[dict] | None = None,
    q_effect: list[dict] | None = None,
    *,
    owner: int = -1,
    skill_key: str = "old",
) -> dict:
    return {
        "effect": [_record()] if effect is None else effect,
        "q_effect": [] if q_effect is None else q_effect,
        "iOwner": owner,
        "native_skill_key": skill_key,
    }


def _replay(**overrides: object) -> dict:
    payload = {
        "cached_target_points": [[2, 3], [4, 4]],
        "selected_target": [2, 3],
        "origin": [4, 5],
        "two_click": False,
        "second_target": [-1, -1],
        "cached_effect": _effect([_record((0, 0), 9)], owner=99),
        "get_skill_effect": _effect(),
        "get_final_effect": None,
        "explosion": "ExploAir2",
        "skill_source_tag": 7,
        "owner_id": 17,
        "skill_id": "FireflyAtk1",
        "skill_key": "FireflyAtk1_A",
        "friendly_fire_passives": {
            "base": False,
            "a": False,
            "b": False,
            "ab": False,
        },
        "friendly_fire_owner_matches_team6": False,
        "friendly_fire_target_points": [],
        "owner_boosted": False,
    }
    payload.update(overrides)
    return replay_enemy_skill_effect_boundary(**payload)


def test_committed_map_binds_complete_native_projection_without_lua_overclaim():
    value = _load()
    result = validate_enemy_skill_effect_boundary_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "d3502ffc37ce5fb0a685e6df3587173f2076f0701e944dbd4888ee0f46711bdd"
        ),
        "parameterized_native_materializer_complete": True,
        "concrete_lua_skill_effect_payloads_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "dependency_count": 2,
        "region_count": 16,
        "control_window_count": 14,
        "direct_edge_count": 13,
        "call_inventory_count": 2,
        "data_anchor_count": 16,
        "instruction_anchor_count": 2,
        "replay_vector_count": 6,
        "finding_count": 8,
        "unresolved_count": 5,
        "parameterized_native_materializer_complete": True,
        "target_membership_and_clear_complete": True,
        "callback_selection_and_argument_order_complete": True,
        "annotation_and_damage_postprocess_complete": True,
        "concrete_lua_skill_effect_payloads_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def test_layout_offsets_and_complete_direct_call_inventories_are_exact():
    value = _load()
    contracts = value["contracts"]
    inventories = {item["id"]: item for item in value["call_inventories"]}

    assert contracts["skill_layout"]["cached_target_points"] == "+0x118..+0x120"
    assert contracts["skill_effect_layout"]["iOwner"] == "+0x5c"
    assert contracts["space_damage_projection"] == {
        "stride": "0x134",
        "loc": "+0x00/+0x04",
        "iDamage": "+0x08",
        "sAnimation": "+0x38",
        "sAnimation_length": "+0x48",
        "private_boost_marker": "+0x31",
        "private_origin": "+0x9c/+0xa0",
        "private_source_tag": "+0xc0",
    }
    assert [site["rva"] for site in inventories["skill_effect_materialize_callers"]["sites"]] == [
        0x0016B0DB,
        0x0016B6FC,
        0x0016E7CF,
        0x00228044,
        0x00228F44,
        0x002689B9,
        0x0026A223,
        0x0026A7FE,
    ]
    assert [site["rva"] for site in inventories["skill_effect_annotation_callers"]["sites"]] == [
        0x0022E9DD,
        0x0022ED2A,
        0x002682A8,
    ]


def test_target_cache_miss_clears_cache_and_invokes_no_callback():
    result = _replay(
        selected_target=[7, 7],
        get_skill_effect=None,
        cached_effect=_effect(
            [_record((1, 1), 3)],
            [_record((2, 2), 4)],
            owner=44,
            skill_key="stale",
        ),
    )

    assert result["kind"] == REPLAY_KIND
    assert result["target_was_cached"] is False
    assert result["selected_target"] == [-1, -1]
    assert result["callback"] is None
    assert result["callback_arguments"] is None
    assert result["cache_action"] == "clear"
    assert result["cached_effect"] == {
        "effect": [],
        "q_effect": [],
        "iOwner": -1,
        "native_skill_key": "",
    }
    assert result["postprocess"] is None


def test_regular_callback_replaces_prior_cache_and_writes_owner_and_key():
    replacement = _effect([_record((3, 3), 4)], owner=999, skill_key="ignored")
    result = _replay(get_skill_effect=replacement)

    assert result["callback"] == "GetSkillEffect"
    assert result["callback_arguments"] == {"origin": [4, 5], "target": [2, 3]}
    assert result["cache_action"] == "replace"
    assert result["cached_effect"]["iOwner"] == 17
    assert result["cached_effect"]["native_skill_key"] == "FireflyAtk1_A"
    assert result["cached_effect"]["effect"][0]["iDamage"] == 4


def test_two_click_final_effect_uses_exact_three_point_order():
    final_effect = _effect(
        [_record((2, 3), 2)],
        [_record((1, 1), -1)],
    )
    result = _replay(
        two_click=True,
        second_target=[6, 5],
        get_skill_effect=None,
        get_final_effect=final_effect,
    )

    assert result["callback"] == "GetFinalEffect_Helper"
    assert result["callback_arguments"] == {
        "ordered_points": [[4, 5], [6, 5], [2, 3]]
    }
    assert result["postprocess"]["vector_order"] == ["effect", "q_effect"]


@pytest.mark.parametrize("second_target", [[-1, 5], [6, -1]])
def test_either_literal_minus_one_second_coordinate_uses_regular_callback(second_target):
    result = _replay(two_click=True, second_target=second_target)

    assert result["callback"] == "GetSkillEffect"


def test_annotations_cover_both_vectors_and_default_only_exact_empty_sentinels():
    projected = _effect(
        [
            _record((2, 3), 1, source_tag=99),
            _record(
                (2, 4),
                2,
                animation="keep",
                origin=(-1, 4),
                source_tag=-8,
            ),
        ],
        [_record((1, 1), 3, source_tag=0)],
    )
    result = _replay(get_skill_effect=projected)
    effect = result["cached_effect"]

    assert [record["sAnimation"] for record in effect["effect"]] == [
        "ExploAir2",
        "keep",
    ]
    assert [record["piOrigin"] for record in effect["effect"]] == [
        [4, 5],
        [-1, 4],
    ]
    assert effect["q_effect"][0]["piOrigin"] == [4, 5]
    assert [record["native_source_tag"] for record in effect["effect"]] == [7, 7]
    assert effect["q_effect"][0]["native_source_tag"] == 7
    assert result["postprocess"]["explosion_defaulted"] == [
        {"list": "effect", "index": 0},
        {"list": "q_effect", "index": 0},
    ]


@pytest.mark.parametrize(
    ("passives", "expected_bonus"),
    [
        ({"base": True, "a": False, "b": False, "ab": False}, 1),
        ({"base": True, "a": True, "b": False, "ab": False}, 2),
        ({"base": True, "a": False, "b": True, "ab": False}, 2),
        ({"base": True, "a": True, "b": True, "ab": True}, 3),
    ],
)
def test_vek_hormones_bonus_levels_and_damage_exclusions(passives, expected_bonus):
    projected = _effect(
        [
            _record((2, 3), 1),
            _record((2, 3), 500),
            _record((2, 3), 1000),
            _record((2, 3), 0),
            _record((9, 9), 4),
        ],
        [_record((2, 3), 2)],
    )
    result = _replay(
        get_skill_effect=projected,
        friendly_fire_passives=passives,
        friendly_fire_owner_matches_team6=True,
        friendly_fire_target_points=[[2, 3]],
    )

    damage = [record["iDamage"] for record in result["cached_effect"]["effect"]]
    assert damage == [1 + expected_bonus, 500, 1000, 0, 4]
    assert result["cached_effect"]["q_effect"][0]["iDamage"] == 2 + expected_bonus
    assert result["postprocess"]["friendly_fire"]["bonus"] == expected_bonus


def test_vek_hormones_requires_base_owner_and_target_gates():
    inactive_cases = [
        {
            "friendly_fire_passives": {
                "base": False,
                "a": True,
                "b": True,
                "ab": True,
            },
            "friendly_fire_owner_matches_team6": True,
            "friendly_fire_target_points": [[2, 3]],
        },
        {
            "friendly_fire_passives": {
                "base": True,
                "a": False,
                "b": False,
                "ab": False,
            },
            "friendly_fire_owner_matches_team6": False,
            "friendly_fire_target_points": [[2, 3]],
        },
        {
            "friendly_fire_passives": {
                "base": True,
                "a": False,
                "b": False,
                "ab": False,
            },
            "friendly_fire_owner_matches_team6": True,
            "friendly_fire_target_points": [[1, 1]],
        },
    ]
    for case in inactive_cases:
        result = _replay(**case)
        assert result["cached_effect"]["effect"][0]["iDamage"] == 1
        assert not result["postprocess"]["friendly_fire"]["adjustments"]


def test_boost_adjusts_exact_damage_classes_and_marks_every_record():
    values = [1, 499, 500, 999, 1000, 0, -1, -9, -10]
    projected = _effect([_record((2, 3), value) for value in values])
    result = _replay(get_skill_effect=projected, owner_boosted=True)
    records = result["cached_effect"]["effect"]

    assert [record["iDamage"] for record in records] == [
        2,
        500,
        500,
        1000,
        1000,
        0,
        -2,
        -10,
        -10,
    ]
    assert all(record["native_boost_marker"] is True for record in records)
    assert len(result["postprocess"]["boost"]["marked"]) == len(values)


@pytest.mark.parametrize("skill_id", ["Move", "Move_Power"])
def test_exact_move_ids_exclude_boost(skill_id):
    result = _replay(owner_boosted=True, skill_id=skill_id)

    assert result["postprocess"]["boost"]["active"] is False
    assert result["cached_effect"]["effect"][0]["iDamage"] == 1
    assert result["cached_effect"]["effect"][0]["native_boost_marker"] is False


def test_vek_hormones_precedes_boost_at_special_threshold():
    projected = _effect([_record((2, 3), 497), _record((2, 3), 499)])
    result = _replay(
        get_skill_effect=projected,
        friendly_fire_passives={"base": True, "a": False, "b": False, "ab": True},
        friendly_fire_owner_matches_team6=True,
        friendly_fire_target_points=[[2, 3]],
        owner_boosted=True,
    )

    assert [record["iDamage"] for record in result["cached_effect"]["effect"]] == [
        500,
        503,
    ]


def test_native_damage_additions_wrap_as_signed_i32():
    result = _replay(
        get_skill_effect=_effect([_record((2, 3), (1 << 31) - 1)]),
        owner_boosted=True,
    )

    assert result["cached_effect"]["effect"][0]["iDamage"] == -(1 << 31)


def test_callback_and_projection_schemas_fail_closed():
    with pytest.raises(EnemySkillEffectBoundaryError, match="must not supply"):
        _replay(selected_target=[7, 7])
    with pytest.raises(EnemySkillEffectBoundaryError, match="GetSkillEffect"):
        _replay(get_skill_effect=None)
    with pytest.raises(EnemySkillEffectBoundaryError, match="GetFinalEffect_Helper"):
        _replay(
            two_click=True,
            second_target=[3, 4],
            get_final_effect=_effect(),
        )
    invalid = _effect()
    invalid["effect"][0].pop("native_source_tag")
    with pytest.raises(EnemySkillEffectBoundaryError, match="fields differ"):
        _replay(get_skill_effect=invalid)
    with pytest.raises(EnemySkillEffectBoundaryError, match="record cap"):
        _replay(get_skill_effect=_effect([_record()] * (MAX_EFFECT_RECORDS + 1)))
    with pytest.raises(EnemySkillEffectBoundaryError, match="Boolean"):
        _replay(owner_boosted=1)


def test_every_committed_replay_vector_recomputes_exactly():
    for vector in _load()["replay_vectors"]:
        assert replay_enemy_skill_effect_boundary(**vector["input"]) == vector["expected"]


def test_binding_rejects_native_contract_and_replay_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["control_windows"][0]["meaning"] = "skip membership"
    with pytest.raises(EnemySkillEffectBoundaryError, match="fields differ"):
        validate_enemy_skill_effect_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["boost"]["positive_adjust"] = "+2"
    with pytest.raises(EnemySkillEffectBoundaryError, match="fields differ"):
        validate_enemy_skill_effect_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["replay_vectors"][0]["expected"]["cache_action"] = "clear"
    with pytest.raises(EnemySkillEffectBoundaryError, match="fields differ"):
        validate_enemy_skill_effect_boundary_map_binding(altered)


def test_encoding_is_deterministic_and_round_trips():
    value = _load()
    encoded = encode_enemy_skill_effect_boundary_map(value)

    assert encoded.endswith("\n")
    assert json.loads(encoded) == value
    assert encoded == encode_enemy_skill_effect_boundary_map(value)


def test_exact_installed_executable_rebuilds_committed_map_when_available():
    if not EXECUTABLE.is_file():
        pytest.skip("exact local ITB executable is not available")

    result = validate_enemy_skill_effect_boundary_map(EXECUTABLE, _load())
    assert result["status"] == "verified"
    assert result["parameterized_native_materializer_complete"] is True
    assert result["concrete_lua_skill_effect_payloads_complete"] is False
    assert result["simulator_change_required"] is False
