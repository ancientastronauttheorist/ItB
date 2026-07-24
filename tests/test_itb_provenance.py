"""Tests for build-keyed mechanics provenance validation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.itb_provenance import main as provenance_main
from src.observatory.provenance import (
    ProvenanceError,
    audit_provenance_sources,
    load_json_object,
    validate_provenance,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64


def _inventory() -> dict:
    return {
        "platform": "windows",
        "executable": {"architecture": "x86", "sha256": HASH_A},
        "steam": {
            "build_id": "1",
            "installed_depots": [{"manifest": "2"}],
        },
        "content": {
            "scripts": {
                "revision_sha256": HASH_B,
                "files": [
                    {"path": "scripts/global.lua", "sha256": HASH_D}
                ],
            },
            "maps": {"revision_sha256": HASH_C},
        },
    }


def _provenance() -> dict:
    return {
        "schema_version": 1,
        "build_identity": {
            "platform": "windows",
            "architecture": "x86",
            "executable_sha256": HASH_A,
            "build_id": "1",
            "depot_manifest": "2",
            "scripts_revision_sha256": HASH_B,
            "maps_revision_sha256": HASH_C,
        },
        "inventory": "data/observatory/inventories/test.json",
        "records": [
            {
                "id": "enemy-scoring",
                "coverage": "partial",
                "sources": [
                    {
                        "path": "scripts/global.lua",
                        "sha256": HASH_D,
                        "symbols": ["ScorePositioning"],
                    }
                ],
                "implementations": [
                    {
                        "path": "rust_solver/src/turn_projection.rs",
                        "symbols": ["requeue_enemies_heuristic"],
                    }
                ],
                "tests": [
                    {
                        "path": "rust_solver/src/turn_projection.rs",
                        "symbols": ["test_projection"],
                    }
                ],
                "evidence": [
                    {
                        "classification": "fact",
                        "statement": "The Lua symbol is present.",
                    }
                ],
                "known_gaps": ["Native candidate enumeration is unresolved."],
            }
        ],
    }


def test_valid_provenance_is_counted(tmp_path: Path):
    (tmp_path / "rust_solver/src").mkdir(parents=True)
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text("// test")
    inventory_path = tmp_path / "data/observatory/inventories/test.json"
    inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")
    counts = validate_provenance(
        _provenance(), _inventory(), repo_root=tmp_path
    )
    assert counts == {
        "gap": 0,
        "native_dependency": 0,
        "partial": 1,
        "verified": 0,
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["build_identity"].update(build_id="2"), "build_identity.build_id"),
        (
            lambda data: data["records"][0]["sources"][0].update(sha256="stale"),
            "stale source hash",
        ),
        (
            lambda data: data["records"][0].update(coverage="partial", known_gaps=[]),
            "requires known_gaps",
        ),
        (
            lambda data: data["records"].append(deepcopy(data["records"][0])),
            "duplicate provenance id",
        ),
        (
            lambda data: data["records"][0].update(
                coverage="verified",
                implementations=[],
                tests=[],
                known_gaps=[],
            ),
            "verified coverage requires implementations and tests",
        ),
        (
            lambda data: data["records"][0].update(
                coverage="verified",
                known_gaps=[],
                evidence=[
                    {
                        "classification": "hypothesis",
                        "statement": "Maybe correct.",
                    }
                ],
            ),
            "verified coverage requires fact-classified evidence",
        ),
        (
            lambda data: data.update(schema_version=True),
            "unsupported provenance schema",
        ),
        (
            lambda data: data["records"][0].update(coverage=[]),
            "invalid coverage",
        ),
        (
            lambda data: data["records"][0]["evidence"][0].update(
                classification=[]
            ),
            "invalid evidence classification",
        ),
    ],
)
def test_invalid_provenance_fails_closed(mutation, message: str):
    provenance = _provenance()
    mutation(provenance)
    with pytest.raises(ProvenanceError, match=message):
        validate_provenance(provenance, _inventory())


def test_paths_cannot_escape_repository():
    provenance = _provenance()
    provenance["records"][0]["implementations"][0][
        "path"
    ] = "../../outside.rs"
    with pytest.raises(ProvenanceError, match="stay within"):
        validate_provenance(provenance, _inventory())


@pytest.mark.parametrize(
    "mutation",
    [
        lambda inventory: inventory.update(steam=[]),
        lambda inventory: inventory["steam"].update(installed_depots=[]),
        lambda inventory: inventory.update(content=[]),
        lambda inventory: inventory["content"].update(scripts=[]),
    ],
)
def test_malformed_inventory_shapes_fail_closed(mutation):
    inventory = _inventory()
    mutation(inventory)
    with pytest.raises(ProvenanceError):
        validate_provenance(_provenance(), inventory)


def test_referenced_inventory_must_match_supplied_inventory(tmp_path: Path):
    (tmp_path / "rust_solver/src").mkdir(parents=True)
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text("// test")
    inventory_path = tmp_path / "data/observatory/inventories/test.json"
    inventory_path.parent.mkdir(parents=True)
    other = _inventory()
    other["steam"]["build_id"] = "999"
    inventory_path.write_text(json.dumps(other), encoding="utf-8")
    with pytest.raises(ProvenanceError, match="content differs"):
        validate_provenance(
            _provenance(), _inventory(), repo_root=tmp_path
        )


def test_referenced_inventory_equality_is_json_type_strict(tmp_path: Path):
    (tmp_path / "rust_solver/src").mkdir(parents=True)
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text("// test")
    inventory_path = tmp_path / "data/observatory/inventories/test.json"
    inventory_path.parent.mkdir(parents=True)
    supplied = _inventory()
    supplied["extra_evidence"] = True
    referenced = deepcopy(supplied)
    referenced["extra_evidence"] = 1
    inventory_path.write_text(json.dumps(referenced), encoding="utf-8")
    with pytest.raises(ProvenanceError, match="content differs"):
        validate_provenance(
            _provenance(), supplied, repo_root=tmp_path
        )


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1, "a": 2}',
        '{"value": NaN}',
        "[]",
    ],
)
def test_json_loader_rejects_ambiguous_or_non_object_input(
    tmp_path: Path, text: str
):
    path = tmp_path / "input.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ProvenanceError):
        load_json_object(path)


def test_source_audit_distinguishes_indexing_from_behavioral_coverage():
    inventory = _inventory()
    inventory["content"]["scripts"]["files"].extend(
        [
            {
                "path": "scripts/advanced/ae_global.lua",
                "sha256": "e" * 64,
            },
            {
                "path": "scripts/spawner.lua",
                "sha256": "3" * 64,
            },
            {
                "path": "scripts/weapons_prime.lua",
                "sha256": "f" * 64,
            },
            {
                "path": "scripts/missions/final/env_final.lua",
                "sha256": "1" * 64,
            },
            {
                "path": "scripts/missions/acid/mission_belt.lua",
                "sha256": "4" * 64,
            },
            {
                "path": "scripts/missions/grass/mission_airstrike.lua",
                "sha256": "5" * 64,
            },
            {
                "path": "scripts/unrelated.lua",
                "sha256": "2" * 64,
            },
        ]
    )
    audit = audit_provenance_sources(_provenance(), inventory)
    categories = {
        item["category"]: item for item in audit["categories"]
    }
    scoring = categories["enemy-scoring"]
    assert scoring["candidate_files"] == 2
    assert scoring["indexed_files"] == 1
    assert scoring["unindexed_files"] == 1
    scoring_files = {item["path"]: item for item in scoring["files"]}
    assert scoring_files["scripts/global.lua"]["indexed_by"] == [
        "enemy-scoring"
    ]
    assert (
        scoring_files["scripts/advanced/ae_global.lua"]["status"]
        == "unindexed"
    )
    assert categories["player-weapons"]["unindexed_files"] == 1
    assert categories["spawn-selection"]["unindexed_files"] == 1
    assert categories["missions"]["unindexed_files"] == 3
    environment_files = {
        item["path"] for item in categories["environments"]["files"]
    }
    assert {
        "scripts/missions/acid/mission_belt.lua",
        "scripts/missions/grass/mission_airstrike.lua",
        "scripts/missions/final/env_final.lua",
    } <= environment_files
    assert categories["environments"]["unindexed_files"] == 3
    assert audit["method"]["indexed_does_not_mean"].startswith(
        "the Lua behavior"
    )
    assert audit["method"]["summary_counts"].startswith("unique file paths")
    assert sum(
        category["candidate_files"] for category in audit["categories"]
    ) > audit["summary"]["candidate_files"]
    assert audit["summary"] == {
        "candidate_files": 7,
        "indexed_files": 1,
        "unindexed_files": 6,
    }


def test_source_audit_is_deterministic():
    first = audit_provenance_sources(_provenance(), _inventory())
    reordered_inventory = _inventory()
    reordered_inventory["content"]["scripts"]["files"].reverse()
    reordered_provenance = _provenance()
    reordered_provenance["records"].reverse()
    reordered_provenance["records"][0]["sources"].reverse()
    second = audit_provenance_sources(
        reordered_provenance, reordered_inventory
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(
        second, sort_keys=True
    )


def test_source_audit_cli_emits_machine_readable_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    (tmp_path / "rust_solver/src").mkdir(parents=True)
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text(
        "// test", encoding="utf-8"
    )
    inventory_path = tmp_path / "data/observatory/inventories/test.json"
    inventory_path.parent.mkdir(parents=True)
    provenance_path = tmp_path / "provenance.json"
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")
    provenance_path.write_text(json.dumps(_provenance()), encoding="utf-8")

    assert (
        provenance_main(
            [
                str(provenance_path),
                str(inventory_path),
                "--repo-root",
                str(tmp_path),
                "--audit-sources",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["analysis_kind"] == "provenance_source_index_audit"
    assert result["summary"] == {
        "candidate_files": 1,
        "indexed_files": 1,
        "unindexed_files": 0,
    }


def test_real_titan_fist_record_is_family_scoped():
    repo_root = Path(__file__).resolve().parents[1]
    provenance = load_json_object(
        repo_root / "data/observatory/mechanics_provenance.json"
    )
    inventory = load_json_object(
        repo_root
        / "data/observatory/inventories"
        / "windows_build_13725832_31fe35265598_local_modified.json"
    )
    validate_provenance(provenance, inventory, repo_root=repo_root)

    record = next(
        item
        for item in provenance["records"]
        if item["id"] == "player-weapon-titan-fist"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/weapons_prime.lua",
            "sha256": (
                "ad82af253572fe7e86293592d0b670e5"
                "851e90842666062b919421e134173ac6"
            ),
            "symbols": [
                "Prime_Punchmech",
                "Prime_Punchmech:GetSkillEffect",
                "Prime_Punchmech_A",
                "Prime_Punchmech_B",
                "Prime_Punchmech_AB",
            ],
        }
    ]
    implementation_symbols = {
        symbol
        for reference in record["implementations"]
        for symbol in reference["symbols"]
    }
    assert {
        "WId::PrimePunchmech",
        "WId::PrimePunchmechA",
        "WId::PrimePunchmechB",
        "WId::PrimePunchmechAB",
        "sim_melee",
        "sim_charge",
        "charge_first_hit",
    } <= implementation_symbols
    test_symbols = {
        symbol
        for reference in record["tests"]
        for symbol in reference["symbols"]
    }
    assert {
        "test_titan_fist",
        "test_titan_fist_upgraded_defs",
        "test_titan_fist_kill_and_push",
        "test_titan_fist_ab_dash_punch_uses_damage_upgrade",
        "test_titan_fist_perp_via_bridge_replay",
        "titan_fist_dash_enumerates_direction_selector_for_long_target",
    } <= test_symbols
    assert record["known_gaps"]


def test_real_rocket_artillery_record_includes_inherited_targeting():
    repo_root = Path(__file__).resolve().parents[1]
    provenance = load_json_object(
        repo_root / "data/observatory/mechanics_provenance.json"
    )
    inventory = load_json_object(
        repo_root
        / "data/observatory/inventories"
        / "windows_build_13725832_31fe35265598_local_modified.json"
    )
    validate_provenance(provenance, inventory, repo_root=repo_root)

    record = next(
        item
        for item in provenance["records"]
        if item["id"] == "player-weapon-rocket-artillery"
    )
    assert record["coverage"] == "partial"
    sources = {source["path"]: source for source in record["sources"]}
    assert sources["scripts/weapons_base.lua"] == {
        "path": "scripts/weapons_base.lua",
        "sha256": (
            "bdb55457746d08b46e8b62ad7cfc27f"
            "0a08bde9fab7397a4780dfe945b5f8f38"
        ),
        "symbols": ["LineArtillery", "LineArtillery:GetTargetArea"],
    }
    assert sources["scripts/weapons_ranged.lua"]["symbols"] == [
        "Ranged_Rocket",
        "Ranged_Rocket:GetSkillEffect",
        "Ranged_Rocket_A",
        "Ranged_Rocket_B",
        "Ranged_Rocket_AB",
    ]
    implementation_symbols = {
        symbol
        for reference in record["implementations"]
        for symbol in reference["symbols"]
    }
    assert {
        "WId::RangedRocket",
        "WId::RangedRocketA",
        "WId::RangedRocketB",
        "WId::RangedRocketAB",
        "is_rocket_artillery",
        "simulate_action",
        "sim_artillery",
        "apply_rocket_center_push",
        "get_weapon_targets",
        "enumerate_actions",
        "replay_solution",
    } <= implementation_symbols
    test_symbols = {
        symbol
        for reference in record["tests"]
        for symbol in reference["symbols"]
    }
    assert {
        "test_rocket_artillery_damage_upgrades",
        "test_sim_artillery_rocket_smokes_behind_shooter",
        "test_upgraded_rocket_damage_plus_blocked_bump_kills_alpha_scorpion",
        "rocket_artillery_rejects_off_axis_targets",
        "replay_solution_noops_off_axis_rocket_target",
    } <= test_symbols
    assert record["known_gaps"]


def test_real_aerial_bombs_record_keeps_variant_test_gaps_explicit():
    repo_root = Path(__file__).resolve().parents[1]
    provenance = load_json_object(
        repo_root / "data/observatory/mechanics_provenance.json"
    )
    inventory = load_json_object(
        repo_root
        / "data/observatory/inventories"
        / "windows_build_13725832_31fe35265598_local_modified.json"
    )
    validate_provenance(provenance, inventory, repo_root=repo_root)

    record = next(
        item
        for item in provenance["records"]
        if item["id"] == "player-weapon-aerial-bombs"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/weapons_brute.lua",
            "sha256": (
                "e5989a06676ee04827401007a825c771"
                "9048268fb8ff2303bce921a32441b265"
            ),
            "symbols": [
                "Brute_Jetmech",
                "Brute_Jetmech:GetTargetArea",
                "Brute_Jetmech:GetSkillEffect",
                "Brute_Jetmech_A",
                "Brute_Jetmech_B",
                "Brute_Jetmech_AB",
            ],
        }
    ]
    implementation_symbols = {
        symbol
        for reference in record["implementations"]
        for symbol in reference["symbols"]
    }
    assert {
        "WId::BruteJetmech",
        "WId::BruteJetmechA",
        "WId::BruteJetmechB",
        "WId::BruteJetmechAB",
        "simulate_weapon_with",
        "sim_leap",
        "get_weapon_targets",
        "is_aerial_bombs",
        "aerial_bombs_transit_smoke_score",
    } <= implementation_symbols
    test_symbols = {
        symbol
        for reference in record["tests"]
        for symbol in reference["symbols"]
    }
    assert {
        "test_aerial_bombs_upgrades",
        "test_jetmech_smokes_transit_base_range",
        "test_aerial_bombs_damages_transit_tile_base_range",
        "test_aerial_bombs_damages_both_transit_tiles_range_upgraded",
        "test_aerial_bombs_enum_rejects_landing_on_water",
        "test_aerial_bombs_sim_noops_illegal_enemy_landing",
        "moved_aerial_bombs_targets_from_post_move_tile",
        "aerial_bombs_transit_smoke_building_threat_survives_pruning",
        "replay_solution_counts_aerial_bombs_pod_collection",
    } <= test_symbols
    replay_tests = next(
        reference
        for reference in record["tests"]
        if reference["path"] == "rust_solver/src/replay.rs"
    )
    assert replay_tests["symbols"] == [
        "replay_solution_counts_aerial_bombs_pod_collection"
    ]
    gaps = " ".join(record["known_gaps"])
    assert "no exact-ID end-to-end simulator case" in gaps
    assert "bypassing B/AB dispatch" in gaps


def test_real_mission_wind_record_keeps_rng_and_bridge_gaps_explicit():
    repo_root = Path(__file__).resolve().parents[1]
    provenance = load_json_object(
        repo_root / "data/observatory/mechanics_provenance.json"
    )
    inventory = load_json_object(
        repo_root
        / "data/observatory/inventories"
        / "windows_build_13725832_31fe35265598_local_modified.json"
    )
    validate_provenance(provenance, inventory, repo_root=repo_root)

    record = next(
        item
        for item in provenance["records"]
        if item["id"] == "environment-mission-wind"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/missions/sand/mission_wind.lua",
            "sha256": (
                "4e84bbb892fa90cf8e17f60c5b7d899d"
                "8258141e79445c130a1d2375f3750c67"
            ),
            "symbols": [
                "Mission_Wind",
                "Env_RandomWind",
                "Env_RandomWind:MarkBoard",
                "Env_RandomWind:Plan",
                "Env_RandomWind:ApplyEffect",
            ],
        }
    ]
    implementation_symbols = {
        symbol
        for reference in record["implementations"]
        for symbol in reference["symbols"]
    }
    assert {
        "engine_dir_to_solver_dir",
        "board_from_json",
        "simulate_mission_wind",
        "simulate_enemy_attacks",
    } <= implementation_symbols
    test_symbols = {
        symbol
        for reference in record["tests"]
        for symbol in reference["symbols"]
    }
    assert test_symbols == {
        "test_mission_wind_markers_do_not_damage_buildings",
        "test_mission_wind_dir_push_bumps_mech_into_building",
        "test_mission_wind_fire_kill_corpse_does_not_block_later_gust",
        "test_mission_wind_raw_dir_two_pushes_egg_sack_out_of_burnbug_lane",
    }
    gaps = " ".join(record["known_gaps"])
    assert "RNG" in gaps
    assert "bridge" in gaps.lower()
    assert "native" in gaps.lower()
