from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.enemy_score_effect_ancestry import (
    ANALYSIS_KIND,
    EnemyScoreEffectAncestryError,
    build_enemy_score_effect_ancestry,
    encode_enemy_score_effect_ancestry,
    validate_enemy_score_effect_ancestry,
    validate_enemy_score_effect_ancestry_binding,
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
CALLBACK_INDEX = (
    ROOT
    / "data"
    / "observatory"
    / "callbacks"
    / "windows_build_13725832_31fe35265598_callback_index.json"
)
ANCESTRY_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "callbacks"
    / "windows_build_13725832_31fe35265598_enemy_score_effect_ancestry.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _callbacks() -> dict[str, dict]:
    return {record["symbol"]: record for record in _load(ANCESTRY_MAP)["target_score_callbacks"]}


def test_committed_map_binds_complete_score_side_ancestry_without_phase_overclaim():
    value = _load(ANCESTRY_MAP)
    result = validate_enemy_score_effect_ancestry_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "720f721d71869bcba25479410e124e666626d2b570c0dd3e5fb00acc50a86887"
        ),
        "score_side_effect_ancestry_complete": True,
        "transitive_native_helper_rng_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "dependency_count": 4,
        "class_anchor_count": 4,
        "target_score_definition_count": 20,
        "target_score_source_file_count": 15,
        "route_counts": {
            "direct_actual_effect": 4,
            "nested_actual_effect": 1,
            "synthetic_local_effect": 4,
            "no_effect_payload": 11,
        },
        "skill_effect_definition_count": 186,
        "skill_effect_source_file_count": 45,
        "explicit_lua_rng_call_count": 0,
        "finding_count": 8,
        "unresolved_count": 3,
        "score_side_effect_ancestry_complete": True,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def test_complete_occurrence_census_excludes_only_commented_garden_definition():
    scope = _load(ANCESTRY_MAP)["source_scope"]

    assert scope == {
        "inventory_script_file_count": 305,
        "accepted_lua_file_count": 153,
        "analysis_lua_file_count": 152,
        "excluded_project_bridge_overlay": "scripts/modloader.lua",
        "callback_index_definition_count": 757,
        "raw_get_target_score_identifier_count": 22,
        "active_get_target_score_identifier_count": 21,
        "active_get_target_score_definition_count": 20,
        "active_nondefinition_get_target_score_call_count": 1,
        "excluded_commented_definition": {
            "source_path": "scripts/weapons_enemy.lua",
            "line": 895,
            "symbol": "Garden_Atk:GetTargetScore",
        },
    }


def test_exact_direct_actual_effect_routes_are_only_four_definitions():
    callbacks = _callbacks()
    direct = {
        symbol
        for symbol, record in callbacks.items()
        if record["payload_route"] == "direct_actual_effect"
    }

    assert direct == {
        "Skill:GetTargetScore",
        "CentipedeAtk1:GetTargetScore",
        "CentipedeAtkB:GetTargetScore",
        "MosquitoAtkB:GetTargetScore",
    }
    assert callbacks["Skill:GetTargetScore"]["self_effect_calls"] == 1
    assert callbacks["Skill:GetTargetScore"]["score_list_calls"] == 2
    assert "scores both instant and queued" in callbacks["Skill:GetTargetScore"][
        "actual_effect_cardinality"
    ]


def test_shaman_is_the_only_nested_route_and_resolves_to_totem_base_score():
    value = _load(ANCESTRY_MAP)
    callbacks = _callbacks()
    nested = {
        symbol
        for symbol, record in callbacks.items()
        if record["payload_route"] == "nested_actual_effect"
    }
    anchors = {record["id"]: record for record in value["class_anchors"]}

    assert nested == {"ShamanAtk1:GetTargetScore"}
    assert callbacks["ShamanAtk1:GetTargetScore"][
        "nested_target_score_receivers"
    ] == ["TotemAtk1"]
    assert anchors["totem_atk1_constructor"]["declared_parent"] == "Skill"
    assert "inherits Skill:GetTargetScore" in anchors["totem_atk1_constructor"][
        "meaning"
    ]
    assert anchors["totem_atk1_effect"]["line"] == 201
    assert anchors["create_class"]["body_sha256"] == (
        "214fce796c535562d79f4cdeef89be1e098b7652b2444c6957702b6a6aed29f9"
    )


def test_synthetic_score_effects_are_exact_and_do_not_call_actual_effects():
    callbacks = _callbacks()
    synthetic = {
        symbol
        for symbol, record in callbacks.items()
        if record["payload_route"] == "synthetic_local_effect"
    }

    assert synthetic == {
        "DungAtk1:GetTargetScore",
        "ScarabAtkB:GetTargetScore",
        "StarfishAtkB1:GetTargetScore",
        "BlobberAtk1:GetTargetScore",
    }
    for symbol in synthetic:
        record = callbacks[symbol]
        assert record["self_effect_calls"] == 0
        assert record["skill_effect_constructors"] == 1
        assert record["score_list_calls"] == 1


def test_remaining_eleven_scores_do_not_score_an_effect_payload():
    callbacks = _callbacks()
    payload_free = {
        symbol
        for symbol, record in callbacks.items()
        if record["payload_route"] == "no_effect_payload"
    }

    assert len(payload_free) == 11
    assert {
        "BlobAtkB:GetTargetScore",
        "Armored_Train_Move:GetTargetScore",
        "Laser_U_Atk:GetTargetScore",
        "Piston_U_Atk:GetTargetScore",
        "SpiderlingHatch1:GetTargetScore",
        "Train_Move:GetTargetScore",
        "Filler_Attack:GetTargetScore",
        "SelfTarget:GetTargetScore",
        "BlobAtk1:GetTargetScore",
        "SpiderAtk1:GetTargetScore",
        "WebeggHatch1:GetTargetScore",
    } == payload_free
    assert all(callbacks[symbol]["self_effect_calls"] == 0 for symbol in payload_free)
    assert all(callbacks[symbol]["score_list_calls"] == 0 for symbol in payload_free)


def test_no_score_callback_uses_final_effect_or_explicit_lua_rng():
    value = _load(ANCESTRY_MAP)

    assert all(
        record["get_final_effect_calls"] == 0
        and record["explicit_rng_calls"] == 0
        for record in value["target_score_callbacks"]
    )
    assert value["skill_effect_census"] == {
        "active_definition_count": 186,
        "source_file_count": 45,
        "body_manifest_sha256": (
            "da84da86aaab86046b530547644307dd7159b2589f7a06be20fc0bd122899290"
        ),
        "searched_explicit_rng_helpers": [
            "random_int",
            "random_bool",
            "random_element",
            "random_removal",
        ],
        "explicit_rng_call_count": 0,
        "native_bound_helper_rng_complete": False,
    }


def test_score_and_cache_materialization_routes_remain_explicitly_separate():
    contracts = _load(ANCESTRY_MAP)["contracts"]

    assert contracts["native_to_lua"].endswith(
        "dynamically resolved Lua GetTargetScore"
    )
    assert contracts["base_lua_route"] == (
        "Skill:GetTargetScore -> self:GetSkillEffect -> ScoreList"
    )
    assert contracts["score_route_uses_native_cache_materializer"] is False
    assert contracts["score_route_uses_final_effect"] is False
    assert contracts["settled_queue_remains_authoritative"] is True


def test_binding_rejects_body_route_rng_and_scope_drift():
    value = _load(ANCESTRY_MAP)

    altered = copy.deepcopy(value)
    altered["target_score_callbacks"][0]["body_sha256"] = "0" * 64
    with pytest.raises(EnemyScoreEffectAncestryError, match="fields differ"):
        validate_enemy_score_effect_ancestry_binding(altered)

    altered = copy.deepcopy(value)
    altered["target_score_callbacks"][0]["payload_route"] = "no_effect_payload"
    with pytest.raises(EnemyScoreEffectAncestryError, match="fields differ"):
        validate_enemy_score_effect_ancestry_binding(altered)

    altered = copy.deepcopy(value)
    altered["skill_effect_census"]["explicit_rng_call_count"] = 1
    with pytest.raises(EnemyScoreEffectAncestryError, match="fields differ"):
        validate_enemy_score_effect_ancestry_binding(altered)

    altered = copy.deepcopy(value)
    altered["closure"]["transitive_native_helper_rng_complete"] = True
    with pytest.raises(EnemyScoreEffectAncestryError, match="fields differ"):
        validate_enemy_score_effect_ancestry_binding(altered)


def test_dependency_documents_fail_closed_when_their_fields_drift():
    inventory = _load(INVENTORY)
    callback_index = _load(CALLBACK_INDEX)

    altered = copy.deepcopy(inventory)
    altered["steam"]["build_id"] = "different"
    with pytest.raises(EnemyScoreEffectAncestryError, match="inventory fields differ"):
        build_enemy_score_effect_ancestry(CONTENT_ROOT, altered, callback_index)

    altered = copy.deepcopy(callback_index)
    altered["summary"]["callback_definitions"] += 1
    with pytest.raises(EnemyScoreEffectAncestryError, match="callback index fields differ"):
        build_enemy_score_effect_ancestry(CONTENT_ROOT, inventory, altered)


def test_encoding_is_deterministic_and_round_trips():
    value = _load(ANCESTRY_MAP)
    encoded = encode_enemy_score_effect_ancestry(value)

    assert encoded.endswith("\n")
    assert json.loads(encoded) == value
    assert encoded == encode_enemy_score_effect_ancestry(value)


def test_exact_installed_sources_rebuild_committed_map_when_available():
    if not (CONTENT_ROOT / "scripts" / "global.lua").is_file():
        pytest.skip("exact local ITB content root is not available")

    result = validate_enemy_score_effect_ancestry(
        CONTENT_ROOT,
        _load(INVENTORY),
        _load(CALLBACK_INDEX),
        _load(ANCESTRY_MAP),
    )
    assert result["status"] == "verified"
    assert result["score_side_effect_ancestry_complete"] is True
    assert result["transitive_native_helper_rng_complete"] is False
    assert result["simulator_change_required"] is False
