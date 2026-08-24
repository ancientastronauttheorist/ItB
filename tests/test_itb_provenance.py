"""Tests for build-keyed mechanics provenance validation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.itb_provenance import main as provenance_main
from src.observatory.provenance import (
    ProvenanceError,
    audit_provenance_gaps,
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
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text(
        "// requeue_enemies_heuristic test_projection",
        encoding="utf-8",
    )
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


@pytest.mark.parametrize("reference_kind", ["implementations", "tests"])
def test_literal_repo_symbol_must_exist_in_its_claimed_file(
    tmp_path: Path,
    reference_kind: str,
):
    (tmp_path / "rust_solver/src").mkdir(parents=True)
    present_symbol = (
        "test_projection"
        if reference_kind == "implementations"
        else "requeue_enemies_heuristic"
    )
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text(
        f"// {present_symbol}",
        encoding="utf-8",
    )
    inventory_path = tmp_path / "data/observatory/inventories/test.json"
    inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")
    provenance = _provenance()
    provenance["records"][0][reference_kind][0]["symbols"] = [
        "missing_anchor"
    ]

    with pytest.raises(ProvenanceError, match="anchor is absent.*missing_anchor"):
        validate_provenance(
            provenance,
            _inventory(),
            repo_root=tmp_path,
        )


@pytest.mark.parametrize("symbol", [" ", "missing_symbol "])
def test_repo_symbols_reject_whitespace_escape(symbol: str):
    provenance = _provenance()
    provenance["records"][0]["implementations"][0]["symbols"] = [symbol]

    with pytest.raises(ProvenanceError, match="leading or trailing whitespace"):
        validate_provenance(provenance, _inventory())


def test_descriptive_and_wildcard_repo_symbols_are_not_literal_anchors(
    tmp_path: Path,
):
    (tmp_path / "rust_solver/src").mkdir(parents=True)
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text(
        "// test_projection",
        encoding="utf-8",
    )
    inventory_path = tmp_path / "data/observatory/inventories/test.json"
    inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(json.dumps(_inventory()), encoding="utf-8")
    provenance = _provenance()
    provenance["records"][0]["implementations"][0]["symbols"] = [
        "mission-specific handler",
        "*:MarkBoard",
    ]

    counts = validate_provenance(
        provenance,
        _inventory(),
        repo_root=tmp_path,
    )
    assert counts["partial"] == 1


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
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text(
        "// requeue_enemies_heuristic test_projection",
        encoding="utf-8",
    )
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
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text(
        "// requeue_enemies_heuristic test_projection",
        encoding="utf-8",
    )
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
    assert scoring["candidate_files"] == 1
    assert scoring["indexed_files"] == 1
    assert scoring["unindexed_files"] == 0
    scoring_files = {item["path"]: item for item in scoring["files"]}
    assert scoring_files["scripts/global.lua"]["indexed_by"] == [
        "enemy-scoring"
    ]
    assert "scripts/advanced/ae_global.lua" not in scoring_files
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
        "candidate_files": 6,
        "indexed_files": 1,
        "unindexed_files": 5,
    }


def test_gap_audit_exposes_build_keyed_open_work():
    audit = audit_provenance_gaps(_provenance(), _inventory())

    assert audit["analysis_kind"] == "provenance_gap_audit"
    assert audit["build_identity"] == _provenance()["build_identity"]
    assert audit["summary"] == {
        "records_total": 1,
        "open_records": 1,
        "known_gap_items": 1,
        "records_with_open_evidence": 0,
        "open_evidence_items": 0,
        "coverage": {
            "gap": 0,
            "native_dependency": 0,
            "partial": 1,
            "verified": 0,
        },
    }
    assert audit["records"] == [
        {
            "id": "enemy-scoring",
            "coverage": "partial",
            "sources": ["scripts/global.lua"],
            "known_gaps": [
                "Native candidate enumeration is unresolved."
            ],
            "open_evidence": [],
        }
    ]


def test_gap_audit_includes_unresolved_evidence_and_sorts_records():
    provenance = _provenance()
    second = deepcopy(provenance["records"][0])
    second["id"] = "alpha-gap"
    second["evidence"].append(
        {
            "classification": "unresolved",
            "statement": "Native tie order is unknown.",
        }
    )
    provenance["records"].append(second)

    audit = audit_provenance_gaps(provenance, _inventory())

    assert [record["id"] for record in audit["records"]] == [
        "alpha-gap",
        "enemy-scoring",
    ]
    assert audit["records"][0]["open_evidence"] == [
        {
            "classification": "unresolved",
            "statement": "Native tie order is unknown.",
        }
    ]
    assert audit["summary"]["records_with_open_evidence"] == 1
    assert audit["summary"]["open_evidence_items"] == 1


def test_gap_audit_preserves_hypothesis_classification():
    provenance = _provenance()
    provenance["records"][0]["evidence"].append(
        {
            "classification": "hypothesis",
            "statement": "Candidate order may be stable.",
        }
    )

    record = audit_provenance_gaps(
        provenance,
        _inventory(),
    )["records"][0]

    assert record["open_evidence"] == [
        {
            "classification": "hypothesis",
            "statement": "Candidate order may be stable.",
        }
    ]


def test_gap_audit_verified_record_requires_open_evidence_for_inclusion():
    provenance = _provenance()
    record = provenance["records"][0]
    record["coverage"] = "verified"
    record["known_gaps"] = []

    clean_audit = audit_provenance_gaps(provenance, _inventory())
    assert clean_audit["records"] == []
    assert clean_audit["summary"]["open_records"] == 0

    record["evidence"].append(
        {
            "classification": "unresolved",
            "statement": "Native tie order remains untraced.",
        }
    )
    open_audit = audit_provenance_gaps(provenance, _inventory())
    assert open_audit["records"][0]["coverage"] == "verified"
    assert open_audit["records"][0]["known_gaps"] == []
    assert open_audit["records"][0]["open_evidence"] == [
        {
            "classification": "unresolved",
            "statement": "Native tie order remains untraced.",
        }
    ]


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
        "// requeue_enemies_heuristic test_projection",
        encoding="utf-8",
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


def test_gap_audit_cli_emits_machine_readable_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    (tmp_path / "rust_solver/src").mkdir(parents=True)
    (tmp_path / "rust_solver/src/turn_projection.rs").write_text(
        "// requeue_enemies_heuristic test_projection",
        encoding="utf-8",
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
                "--audit-gaps",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["analysis_kind"] == "provenance_gap_audit"
    assert result["summary"]["records_total"] == 1
    assert result["records"][0]["id"] == "enemy-scoring"


def test_real_spawn_selection_record_includes_sector_parameter_matrix():
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
        if item["id"] == "spawn-selection"
    )
    assert record["coverage"] == "native_dependency"
    sources = {source["path"]: source for source in record["sources"]}
    assert sources["scripts/spawner.lua"] == {
        "path": "scripts/spawner.lua",
        "sha256": (
            "03c4004ce21e450a21d1018627380302"
            "aea80f8718edf05877834ee9c6a84a2e"
        ),
        "symbols": [
            "SectorSpawners",
            "DIFF_EASY",
            "DIFF_NORMAL",
            "DIFF_HARD",
            "DIFF_UNFAIR",
        ],
    }
    assert sources["scripts/spawner_backend.lua"]["symbols"] == [
        "Spawner:NextPawn",
        "Spawner:SelectPawn",
        "Spawner:ModifyCount",
    ]
    assert sources["scripts/advanced/ae_spawner_backend.lua"]["symbols"] == [
        "WeakPawns",
        "Spawner.max_pawns",
        "Spawner.max_level",
        "getFinalEnemyLists",
    ]
    assert sources["scripts/missions/missions.lua"]["symbols"] == [
        "Mission:CreateSpawner"
    ]
    evidence = " ".join(item["statement"] for item in record["evidence"])
    assert "optional mission-specific data overrides" in evidence
    assert "caller 60 as the standard selector" in evidence
    assert "caller 59 as the emergency selector" in evidence
    assert "caller 66 as without-replacement predicate ordering" in evidence
    assert "candidates[raw_rng % 5]" in evidence
    assert "all 689 accepted installation entries" in evidence
    implementations = {
        item["path"]: set(item["symbols"])
        for item in record["implementations"]
    }
    assert implementations["src/observatory/spawn_coordinate_paths.py"] == {
        "build_spawn_coordinate_path_map",
        "validate_spawn_coordinate_path_map_binding",
        "validate_spawn_coordinate_path_map",
    }
    assert implementations["src/observatory/spawn_coordinate_rng.py"] == {
        "match_spawn_coordinate_rng_records",
        "attribute_spawn_coordinate_rng",
        "compare_spawn_coordinate_rng_attributions",
        "explain_spawn_coordinate_rng_variation",
    }
    tests = {item["path"]: set(item["symbols"]) for item in record["tests"]}
    assert tests[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_spawn_coordinate_paths.json"
    ] == {
        "fallback_is_emergency_placement",
        "both_final_selectors_use_modulo",
        "scheduler_is_predicate_order_not_final_selection",
        "scheduler_draws_are_upstream_state",
    }
    assert tests[
        "data/observatory/captures/"
        "windows_build_13725832_owner_local_modified_20260822_"
        "spawn_coordinate_rng_receipt.json"
    ] == {
        '"classification":"spawn_coordinate_direct_rng_resolved_'
        'shared_presentation_stream_blocks_stable_prediction"',
        '"selector_caller_ids":[60,60,60]',
        '"selector_rng_ordinals":[1495,1475,1450]',
        '"ordinal_deltas_fully_accounted":true',
    }
    gaps = " ".join(record["known_gaps"])
    assert "does not parse or apply SectorSpawners" in gaps
    assert "GAME:GetSpawnList" in gaps
    assert "Standard spawn-coordinate candidate order" in gaps
    assert "scheduler/fallback paths' opaque predicate inputs" in gaps
    assert "spawn-coordinate selection, and the coordinate RNG call order" not in gaps


def test_real_enemy_target_scoring_reconciles_static_and_runtime_boundaries():
    repo_root = Path(__file__).resolve().parents[1]
    provenance = load_json_object(
        repo_root / "data/observatory/mechanics_provenance.json"
    )
    record = next(
        item
        for item in provenance["records"]
        if item["id"] == "enemy-target-scoring"
    )

    evidence = " ".join(item["statement"] for item in record["evidence"])
    assert "consumes the returned target-area vector sequentially" in evidence
    assert "direct shared-RNG call modulo the equal-best count" in evidence
    assert "accepted all 100, 47, and 181 attempts" in evidence
    assert "every pair restored all 65 installed callback slots" in evidence
    assert "selected 24-byte record immediately" in evidence
    assert "aiDest matched queue origin" in evidence
    assert "live bridge queue remains the authoritative current action" in evidence
    assert "immediately displaced primary group" in evidence
    assert "caller-31 remainder of zero out of four" in evidence
    assert "selector-entry shared state" in evidence
    assert "Pawn +0x8d6 is bInjured" in evidence
    assert "ordinary planning passes mode 0" in evidence
    assert "targetHistory contributes -5" in evidence
    assert "priorityTarget contributes +10" in evidence
    assert "literal 50" in evidence
    assert "14 adversarial replay vectors" in evidence
    assert "iBonusShift +0xa64 <= 0" in evidence
    assert "TERRAIN_WATER is registered as 3" in evidence
    assert "separately owned SkillManager +0x68 Skill_Repair" in evidence
    assert "206 visually matching one-line SkillList forms" in evidence
    assert "eight block-commented matches" in evidence
    assert "198 active assignments" in evidence
    assert "17 adversarial replay vectors" in evidence
    assert "Skill +0x110" in evidence
    assert "Board +0x0c secondary/path-manager interface" in evidence
    assert "move-assigns a fresh empty PointList" in evidence
    assert "selects GetSecondTargetArea" in evidence
    assert "nonnegative out-of-board coordinates survive" in evidence
    assert "nine exact functions" in evidence
    assert "12 adversarial replay vectors" in evidence
    assert "22 raw GetTargetScore identifier occurrences" in evidence
    assert "20 active definitions across 15 files" in evidence
    assert "Shaman's TotemAtk1:GetTargetScore call" in evidence
    assert "bypasses the separate native Skill cache materializer" in evidence
    assert "all 186 active GetSkillEffect definitions" in evidence
    assert "zero direct calls to random_int" in evidence
    assert "movement, non-grid structure, positive same-team damage" in evidence
    assert "assigns score=ScoreNothing" in evidence
    assert "strictly below -5 replaces the ordinary score" in evidence
    assert "scores q_effect before effect" in evidence
    assert "strictly below -20 returns -100" in evidence
    assert "seven adversarial replay vectors" in evidence
    assert "fractional Lua movement-position values remain unrounded" in evidence
    assert "including a half-point accumulation case" in evidence
    assert "19 custom score callbacks" in evidence
    assert "global ScorePositioning body short-circuits Pod" in evidence
    assert "The ACID penalty is commented out" in evidence
    assert "TEAM_PLAYER selects TEAM_ENEMY" in evidence
    assert "DIR_START=0 through DIR_END=3" in evidence
    assert "Odd differences therefore remain half-points" in evidence
    assert "lua5.1.dll lua_tointeger body" in evidence
    assert "uses x87 FISTP" in evidence
    assert "active callback-thread rounding mode remains runtime state" in evidence
    assert "Three fresh-process, counterbalanced control/dormant/armed triplets" in evidence
    assert "x87 control word 0x027F (639), selecting nearest-even" in evidence
    assert "all six whole-game control comparisons matched semantically" in evidence
    assert "one exact 2,075-byte source body" in evidence
    assert "14 adversarial replay vectors" in evidence
    assert "unique native GetDangerScore registration" in evidence
    assert "exact 57-byte body" in evidence
    assert "unique GetCustomPositionScore registration" in evidence
    assert "exact 147-byte body" in evidence
    assert "all 152 inventoried shipped Lua files" in evidence
    assert "base ScoreDanger=-10 and PositionScore=0" in evidence
    assert "exact under every x87 rounding mode" in evidence
    assert "seven hash-pinned dependencies" in evidence
    assert "all 17 named Board/Pawn bindings" in evidence
    assert "Board:IsDangerous is a native tile byte plus two Point vectors" in evidence
    assert "non-DIR_NONE push" in evidence
    assert "query 6 matches actual team 6 or greater" in evidence
    assert "Profile-six Board:GetDistanceToPawn" in evidence
    assert "cache that is rebuilt by scanning every terrain-1 tile" in evidence
    assert "17 qualified current-state mappings" in evidence
    assert "Native observation meanings and the current carrier matrix are complete" in evidence
    tournament = next(
        item
        for item in record["evidence"]
        if "consumes the returned target-area vector sequentially"
        in item["statement"]
    )
    assert tournament["classification"] == "inference"

    implementations = {
        item["path"]: set(item["symbols"])
        for item in record["implementations"]
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_pe_boundaries.json"
    ] == {
        "enemy_candidate_tournament",
        "selected_ai_record",
        "dynamic_lua_callbacks",
    }
    assert implementations["src/observatory/selected_queue_hw.py"] == {
        "validate_selected_queue_snapshot",
        "correlate_selected_queue_snapshot",
    }
    assert implementations[
        "src/observatory/enemy_record_selector_boundary.py"
    ] == {
        "replay_enemy_target_tie",
        "compare_enemy_records",
        "replay_enemy_record_selector",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "enemy_record_selector_boundary.json"
    ] == {
        "candidate_record_and_target_tie",
        "record_comparator_and_displaced_group",
        "selector_rng_grammar",
    }
    assert implementations[
        "src/observatory/enemy_candidate_score_boundary.py"
    ] == {
        "normalize_enemy_selected_weapon",
        "replay_enemy_positioning_clamp",
        "replay_enemy_target_score_wrapper",
        "replay_enemy_candidate_target_score",
    }
    assert implementations[
        "scripts/itb_observatory_enemy_candidate_score.py"
    ] == {
        "build",
        "verify",
        "replay-positioning",
        "replay-target-score",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "enemy_candidate_score_boundary.json"
    ] == {
        "positioning_clamp",
        "selected_weapon_normalization",
        "target_score_wrapper",
    }
    assert implementations[
        "src/observatory/enemy_target_area_boundary.py"
    ] == {
        "replay_usable_skill_scan",
        "resolve_enemy_skill_index",
        "replay_enemy_target_area_gate",
    }
    assert implementations[
        "scripts/itb_observatory_enemy_target_area.py"
    ] == {
        "build",
        "verify",
        "replay-usable",
        "replay-gate",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "enemy_target_area_boundary.json"
    ] == {
        "ordinary_target_area_gate",
        "usable_skill_scan",
        "literal_50_is_repair",
        "active_literal_skill_list_assignment_count",
    }
    assert implementations[
        "src/observatory/enemy_target_area_callback_boundary.py"
    ] == {
        "replay_enemy_target_area_callback",
        "validate_enemy_target_area_callback_boundary_map",
    }
    assert implementations[
        "scripts/itb_observatory_enemy_target_area_callback.py"
    ] == {
        "build",
        "verify",
        "replay",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "enemy_target_area_callback_boundary.json"
    ] == {
        "skill_context_is_board_secondary_interface",
        "invalid_origin_clears_cache",
        "two_click_callback_selection",
        "native_post_callback_filter",
    }
    assert implementations[
        "src/observatory/enemy_skill_effect_boundary.py"
    ] == {
        "replay_enemy_skill_effect_boundary",
        "validate_enemy_skill_effect_boundary_map",
    }
    assert implementations[
        "scripts/itb_observatory_enemy_skill_effect.py"
    ] == {
        "build",
        "verify",
        "replay",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "enemy_skill_effect_boundary.json"
    ] == {
        "selected_target_membership_is_hard_gate",
        "two_click_final_argument_order",
        "both_record_vectors_receive_annotations",
        "vek_hormones_adjustment_is_exact",
        "boost_adjustment_is_exact",
    }
    assert implementations[
        "src/observatory/enemy_score_effect_ancestry.py"
    ] == {
        "build_enemy_score_effect_ancestry",
        "validate_enemy_score_effect_ancestry",
    }
    assert implementations[
        "scripts/itb_observatory_enemy_score_effect_ancestry.py"
    ] == {
        "build",
        "verify",
    }
    assert implementations[
        "data/observatory/callbacks/"
        "windows_build_13725832_31fe35265598_"
        "enemy_score_effect_ancestry.json"
    ] == {
        "base_score_directly_materializes_actual_effect",
        "score_side_effect_bypasses_native_cache_materializer",
        "shaman_nested_totem_effect_route",
        "four_synthetic_score_effects",
        "skill_effect_bodies_have_no_explicit_lua_rng_calls",
    }
    assert implementations[
        "src/observatory/enemy_score_list_semantics.py"
    ] == {
        "replay_enemy_score_list",
        "replay_enemy_base_target_score",
        "build_enemy_score_list_semantics",
        "validate_enemy_score_list_semantics",
    }
    assert implementations[
        "scripts/itb_observatory_enemy_score_list_semantics.py"
    ] == {"build", "verify"}
    assert implementations[
        "data/observatory/callbacks/"
        "windows_build_13725832_31fe35265598_"
        "enemy_score_list_semantics.json"
    ] == {
        "score_list_branch_order_is_exact",
        "dead_or_temp_enemy_resets_score",
        "frozen_friend_can_score_as_enemy",
        "instant_pod_veto_is_ordered_and_queued_exempt",
        "movement_position_below_minus_five_overrides_score",
        "base_target_score_evaluates_queue_then_instant",
    }
    assert implementations[
        "src/observatory/enemy_score_positioning_semantics.py"
    ] == {
        "replay_enemy_score_positioning",
        "replay_score_positioning_native_integer",
        "build_enemy_score_positioning_semantics",
        "validate_enemy_score_positioning_semantics",
    }
    assert implementations[
        "scripts/itb_observatory_enemy_score_positioning.py"
    ] == {"build", "verify"}
    assert implementations[
        "data/observatory/callbacks/"
        "windows_build_13725832_31fe35265598_"
        "enemy_score_positioning_semantics.json"
    ] == {
        "hazard_short_circuit_order_is_exact",
        "acid_penalty_is_inactive",
        "custom_score_precedes_stock_edges",
        "enemy_team_selection_is_binary",
        "melee_adjacency_order_is_exact",
        "melee_distance_preserves_half_points",
        "stock_pawn_score_helpers_resolve_to_inherited_defaults",
        "native_integer_rounding_depends_on_x87_control",
        "native_observation_boundaries_and_current_carriers_are_exact",
    }
    assert implementations["src/observatory/score_positioning_x87.py"] == {
        "validate_score_positioning_x87_snapshot",
        "analyze_score_positioning_x87_snapshot",
    }
    assert implementations[
        "src/observatory/score_positioning_x87_campaign.py"
    ] == {
        "build_score_positioning_x87_campaign_receipt",
        "publish_score_positioning_x87_campaign_receipt",
    }
    assert implementations[
        "src/native/observatory_score_positioning_x87_observer.c"
    ] == {
        "observer_score_positioning_x87_veh",
        "arm_observer",
        "finish_observer",
    }
    assert implementations[
        "scripts/itb_observatory_score_positioning_x87_trial.py"
    ] == {"run"}
    assert implementations[
        "src/observatory/enemy_position_score_helpers_boundary.py"
    ] == {
        "replay_stock_enemy_position_score_helpers",
        "build_enemy_position_score_helpers_boundary",
        "validate_enemy_position_score_helpers_boundary",
    }
    assert implementations[
        "scripts/itb_observatory_enemy_position_score_helpers.py"
    ] == {"build", "verify"}
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "enemy_position_score_helpers_boundary.json"
    ] == {
        "native_registrations_are_exact",
        "danger_score_uses_generated_getter",
        "custom_position_uses_get_position_score",
        "create_class_synthesizes_both_getters",
        "shipped_defaults_have_no_explicit_override",
        "stock_results_are_rounding_invariant",
    }
    assert implementations[
        "src/observatory/enemy_position_observations_boundary.py"
    ] == {
        "replay_board_is_dangerous",
        "replay_board_is_dangerous_item",
        "replay_board_is_spawning",
        "replay_board_is_pawn_team",
        "replay_distance_to_pawn",
        "replay_distance_to_building",
        "build_enemy_position_observations_boundary",
        "validate_enemy_position_observations_boundary",
    }
    assert implementations[
        "scripts/itb_observatory_enemy_position_observations.py"
    ] == {"build", "verify"}
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "enemy_position_observations_boundary.json"
    ] == {
        "all_named_observation_bindings_are_exact",
        "dangerous_is_not_environment_danger",
        "dangerous_item_has_eight_effect_tests",
        "spawning_has_two_native_sources",
        "targeted_is_direct_object_membership",
        "score_team_queries_are_simple",
        "pawn_distance_is_manhattan",
        "building_distance_uses_terrain_one_cache",
        "pawn_definition_flags_are_exact_but_not_all_live_carriers",
        "no_solver_contradiction",
    }

    tests = {item["path"]: set(item["symbols"]) for item in record["tests"]}
    assert tests["tests/test_observatory_enemy_score_list_semantics.py"] == {
        "test_non_grid_structure_precedes_friendly_enemy_building_and_pod_tests",
        "test_frozen_untargeted_friend_uses_enemy_weight_but_targeted_friend_does_not",
        "test_dead_or_temp_enemy_assigns_score_nothing_and_erases_prior_score",
        "test_pod_veto_requires_instant_damage_or_spawn",
        "test_base_target_score_runs_queue_first_but_instant_catastrophe_wins",
        "test_exact_installed_source_rebuilds_committed_map_when_available",
    }
    assert tests[
        "tests/test_observatory_enemy_score_positioning_semantics.py"
    ] == {
        "test_hazard_precedence_starts_with_pod_hole_and_targeted_danger",
        "test_custom_score_precedes_hardcoded_stock_corner_and_edge",
        "test_melee_checks_each_direction_pawn_before_building_and_short_circuits",
        "test_melee_distance_formula_preserves_exact_half_points",
        "test_x87_integer_conversion_replay_distinguishes_all_rounding_modes",
        "test_exact_install_rebuilds_source_executable_and_lua_dll_join_when_available",
    }
    assert tests[
        "tests/test_observatory_enemy_position_score_helpers_boundary.py"
    ] == {
        "test_complete_active_source_census_has_defaults_and_no_explicit_getters",
        "test_registration_windows_bind_unique_member_pointers_and_names",
        "test_native_call_edges_reach_both_integer_converters",
        "test_stock_replay_resolves_inherited_values_without_rounding_input",
        "test_exact_install_rebuilds_executable_dll_and_shipped_source_join_when_available",
    }
    assert tests[
        "tests/test_observatory_enemy_position_observations_boundary.py"
    ] == {
        "test_all_score_positioning_native_method_names_are_bound",
        "test_dangerous_replay_uses_tile_flag_and_two_independent_point_vectors",
        "test_each_dangerous_item_effect_is_independently_sufficient",
        "test_score_team_queries_match_native_one_and_six_semantics",
        "test_distance_to_pawn_is_team_filtered_manhattan_and_empty_int_max",
        "test_carrier_matrix_keeps_native_danger_separate_from_environment_danger",
        "test_exact_install_rebuilds_native_source_and_carrier_join_when_available",
    }
    assert tests[
        "data/observatory/captures/"
        "windows_build_13725832_owner_local_modified_20260824_"
        "score_positioning_x87_receipt.json"
    ] == {
        '"classification": "score_positioning_x87_rounding_mode_resolved"',
        '"stable_control_word": 639',
        '"stable_rounding_mode": "nearest_even"',
        '"all_semantic_outcomes_match": true',
    }
    assert tests[
        "data/observatory/captures/"
        "windows_build_13725832_owner_local_modified_20260824_"
        "score_positioning_x87_cleanup_receipt.json"
    ] == {
        "observatory_score_positioning_x87_cleanup_receipt",
        '"remaining_experimental_file_count": 0',
        '"file_set_and_bytes_match_pre_experiment": true',
    }
    assert tests[
        "tests/test_observatory_score_positioning_x87_campaign.py"
    ] == {
        "test_committed_x87_campaign_rebuilds_exactly_and_is_neutral",
        "test_committed_x87_campaign_selects_nearest_even_replay",
        "test_x87_cleanup_closes_pending_restore_and_binds_artifacts",
    }

    gaps = " ".join(record["known_gaps"])
    assert "now-proven record-level native tournament" in gaps
    assert "no live capture serializes one complete tournament" in gaps
    assert "selector-entry state" in gaps
    assert "one Firefly1 single-weapon shape" in gaps
    assert "now-proven native target-area eligibility gate" in gaps
    assert "callback/cache/filter wrapper" in gaps
    assert "SkillEffect cache materializer/postprocessor" in gaps
    assert "native target-area wrapper" in gaps
    assert "native target-area wrapper and SkillEffect cache wrapper" in gaps
    assert "concrete ordered Lua-produced PointLists" in gaps
    assert "concrete ordered Lua-produced PointLists and SkillEffects" in gaps
    assert "raw callback values" in gaps
    assert "source-exact score/effect ancestry" in gaps
    assert "inherited base ScoreList projection" in gaps
    assert "global ScorePositioning projection" in gaps
    assert "native Pawn positioning helpers" in gaps
    assert "runtime-mutated Pawn score fields" in gaps
    assert "candidate-time Board snapshots" in gaps
    assert "direct dangerous predicate carriers" in gaps
    assert "ScorePositioning observation semantics/current carrier matrix" in gaps
    assert "exact-build nearest-even integer conversion" in gaps
    assert "callback-time x87 control" not in gaps
    assert "base ScoreList projection" in gaps
    assert "global ScorePositioning projections" in gaps
    assert "native Pawn positioning helper defaults" in gaps
    assert "runtime-mutated Pawn score values" in gaps
    assert "transitive native-helper RNG" in gaps
    assert "score-side callback ancestry" not in gaps
    assert "Candidate evaluation order and native tie-breaking are not captured" not in gaps
    assert "24-byte record comparator" in gaps
    assert "future Board observations" not in gaps


def test_real_broad_records_keep_symbols_on_their_exact_source_files():
    repo_root = Path(__file__).resolve().parents[1]
    provenance = load_json_object(
        repo_root / "data/observatory/mechanics_provenance.json"
    )
    records = {record["id"]: record for record in provenance["records"]}

    assert records["enemy-target-scoring"]["sources"] == [
        {
            "path": "scripts/global.lua",
            "sha256": (
                "96d82d83a1620061e6fd013aa8462883"
                "e1f3764d03752757ad77fbbbd04bc9b2"
            ),
            "symbols": [
                "Skill:GetTargetArea",
                "Skill:GetTargetScore",
                "Skill:ScoreList",
                "ScorePositioning",
                "CreateClass",
                "Pawn.ScoreDanger",
                "Pawn.PositionScore",
                "Pawn.Ranged",
                "Pawn.Flying",
                "Pawn.AvoidingMines",
            ],
        },
        {
            "path": "scripts/pawns.lua",
            "sha256": (
                "e999b8d98526c1e36f4746dd65b9d9e7"
                "ee3ca0b22029ed391d5b71fda49dc239"
            ),
            "symbols": [
                "Snowmine1.AvoidingMines",
                "Snowmine2.AvoidingMines",
            ],
        },
        {
            "path": "scripts/weapons_base.lua",
            "sha256": (
                "bdb55457746d08b46e8b62ad7cfc27f"
                "0a08bde9fab7397a4780dfe945b5f8f38"
            ),
            "symbols": [
                "Skill_Repair",
                "Skill_Repair:GetSkillEffect",
            ],
        },
        {
            "path": "scripts/advanced/ae_weapons_base.lua",
            "sha256": (
                "4444af60a0b4d38894690425a83a4f61"
                "0cbdc88f20b3fb322db410f257a89742"
            ),
            "symbols": ["Skill_Repair:GetSkillEffect"],
        },
    ]
    mission_sources = {
        source["path"]: source["symbols"]
        for source in records["missions"]["sources"]
    }
    assert mission_sources == {
        "scripts/missions/missions.lua": [
            "Mission",
            "Mission_Infinite",
        ],
        "scripts/missions/mission_critical.lua": [
            "Mission_Critical",
        ],
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
        "test_titan_fist_b_dispatches_exact_damage_only_melee",
        "test_titan_fist_ab_dash_punch_uses_damage_upgrade",
        "test_titan_fist_perp_via_bridge_replay",
        "titan_fist_dash_enumerates_direction_selector_for_long_target",
    } <= test_symbols
    assert record["known_gaps"]
    gaps = " ".join(record["known_gaps"])
    assert "damage-only B variant" not in gaps
    assert "Native GetProjectileEnd" in gaps


def test_real_needle_shot_record_is_family_scoped():
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
        if item["id"] == "player-weapon-needle-shot"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/weapons_technovek.lua",
            "sha256": (
                "6e770aa6ea4c8a9cbcb295574c608f76e"
                "1afdc3f3ffd944848f7329b6dcaeb0e"
            ),
            "symbols": [
                "Vek_Hornet",
                "Vek_Hornet:GetSkillEffect",
                "Vek_Hornet_A",
                "Vek_Hornet_B",
                "Vek_Hornet_AB",
            ],
        },
        {
            "path": "scripts/weapons_prime.lua",
            "sha256": (
                "ad82af253572fe7e86293592d0b670e5"
                "851e90842666062b919421e134173ac6"
            ),
            "symbols": [
                "Prime_Spear",
                "Prime_Spear:GetTargetArea",
            ],
        },
    ]
    implementation_symbols = {
        symbol
        for reference in record["implementations"]
        for symbol in reference["symbols"]
    }
    assert {
        "WId::VekHornet",
        "WId::VekHornetA",
        "WId::VekHornetB",
        "WId::VekHornetAB",
        "get_weapon_targets",
        "sim_melee",
        "is_needle_shot_weapon",
        "replay_solution",
    } <= implementation_symbols
    test_symbols = {
        symbol
        for reference in record["tests"]
        for symbol in reference["symbols"]
    }
    assert {
        "test_techno_hornet_needle_shot_defs_and_mappings",
        "test_needle_shot_upgrade_target_ranges",
        "test_needle_shot_variants_dispatch_exact_damage_and_push",
        "test_needle_shot_ab_damages_full_line_and_pushes_only_farthest",
        "test_needle_shot_killed_target_corpse_bumps_live_blocker",
        "replay_solution_burrower_retreat_prevents_phantom_boss_kill",
    } <= test_symbols
    gaps = " ".join(record["known_gaps"])
    assert "Native Board:IsValid" in gaps
    assert "otherwise-empty intact building target" in gaps
    assert "no dedicated exact-ID" not in gaps


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
        "test_rocket_artillery_variants_dispatch_exact_damage_push_and_smoke",
        "test_upgraded_rocket_damage_plus_blocked_bump_kills_alpha_scorpion",
        "rocket_artillery_rejects_off_axis_targets",
        "replay_solution_noops_off_axis_rocket_target",
    } <= test_symbols
    gaps = " ".join(record["known_gaps"])
    assert "B and AB variants" not in gaps
    assert "OnlyEmpty=false" in gaps


def test_real_aerial_bombs_record_proves_exact_variant_dispatch():
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
        "test_aerial_bombs_variants_dispatch_exact_damage_and_range",
        "moved_aerial_bombs_targets_from_post_move_tile",
        "aerial_bombs_transit_smoke_building_threat_survives_pruning",
        "aerial_bombs_range_upgrade_ids_enumerate_distance_three",
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
    assert "no exact-ID end-to-end simulator case" not in gaps
    assert "bypassing B/AB dispatch" not in gaps
    assert "Native Board:IsBlocked" in gaps
    assert "Exact conformance across every landing terrain" in gaps


def test_real_reverse_thrusters_record_proves_exact_upgrade_dispatch():
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
        if item["id"] == "player-weapon-reverse-thrusters"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/ae_weapons.lua",
            "sha256": (
                "5566b679c696ab489e40a0189d0a63b6"
                "99d01e9657f79a20e6f119239af1680f"
            ),
            "symbols": [
                "Brute_KickBack",
                "Brute_KickBack:GetTargetArea",
                "Brute_KickBack:GetSkillEffect",
                "Brute_KickBack_A",
                "Brute_KickBack_B",
                "Brute_KickBack_AB",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::BruteKickBack",
        "WId::BruteKickBackA",
        "WId::BruteKickBackB",
        "WId::BruteKickBackAB",
        "is_reverse_thrusters",
        "reverse_thrusters_hit_tile",
    } <= implementations["rust_solver/src/weapons.rs"]
    assert {
        "reverse_thrusters_landing_illegal_reason",
        "reverse_thrusters_effective_unit_damage",
        "sim_reverse_thrusters",
    } <= implementations["rust_solver/src/simulate.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/replay.rs"] == {
        "replay_solution_reverse_thrusters_backblast_smoke_does_not_same_action_heal"
    }
    assert "test_reverse_thrusters_upgrades" in tests["rust_solver/src/weapons.rs"]
    assert {
        "test_reverse_thrusters_smokes_backblast_tile_self_damages_and_dashes",
        "test_boosted_reverse_thrusters_adds_dash_and_recoil_damage",
        "test_reverse_thrusters_acid_two_tile_dash_fires_backburner_event",
        "test_reverse_thrusters_upgrade_ids_dispatch_exact_extended_ranges",
    } <= tests["rust_solver/src/simulate.rs"]
    gaps = " ".join(record["known_gaps"])
    assert "no exact-ID end-to-end case" not in gaps
    assert "Boost and Nanofilter timing are live-derived" in gaps


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
                "Env_RandomWind:Start",
                "Env_RandomWind:MarkBoard",
                "Env_RandomWind:Plan",
                "Env_RandomWind:IsEffect",
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
        "_mission_wind_payload_block",
        "cmd_solve",
        "_held_end_turn_safety_block_result",
        "MISSION_ID_TAGS",
    } <= implementation_symbols
    test_symbols = {
        symbol
        for reference in record["tests"]
        for symbol in reference["symbols"]
    }
    assert {
        "test_mission_wind_markers_do_not_damage_buildings",
        "test_mission_wind_dir_push_bumps_mech_into_building",
        "test_mission_wind_fire_kill_corpse_does_not_block_later_gust",
        "test_mission_wind_raw_dir_two_pushes_egg_sack_out_of_burnbug_lane",
        "test_representative_complete_current_wind_payload_passes",
        "test_non_wind_mission_is_not_gated_by_wind_payload_shape",
        "test_wind_payload_validation_is_scoped_to_combat_player",
        "test_horizontal_raw_wind_directions_are_source_unreachable",
        "test_direction_must_be_a_source_reachable_raw_engine_integer",
        "test_environment_identity_must_be_authoritative_wind",
        "test_malformed_partial_empty_extra_or_row_shaped_masks_block",
        "test_matching_shape_in_both_fields_is_required",
        "test_complete_outer_lane_columns_are_source_unreachable",
        "test_v2_requires_exact_current_nonlethal_wind_encoding",
        "test_cmd_solve_returns_non_overridable_research_metadata",
        "test_auto_turn_preserves_wind_payload_gate_metadata",
        "test_public_end_turn_paths_block_incomplete_wind_before_plan_or_dispatch",
        "test_validator_does_not_mutate_live_bridge_payload",
        "test_advanced_wind_mission_is_not_tagged_as_legacy_critical_buildings",
    } <= test_symbols
    gaps = " ".join(record["known_gaps"])
    assert "RNG" in gaps
    assert "bridge" in gaps.lower()
    assert "native" in gaps.lower()
    assert "integrity stop" in gaps
    assert "{0,2}" in gaps
    assert "columns 1 through 5" in gaps
    assert "[x, y, 1, 0, 0]" in gaps


def test_real_mission_tides_record_keeps_remaining_native_and_spawn_gaps_explicit():
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
        if item["id"] == "environment-mission-tides"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/grass/mission_tides.lua",
            "sha256": (
                "d27dab9f44e804e90385a6557057fc9a"
                "1281fab4bc83d6fff50151fc7702277a"
            ),
            "symbols": [
                "Mission_Tides",
                "Env_Tides",
                "Env_Tides:Start",
                "Env_Tides:MarkBoard",
                "Env_Tides:Plan",
                "Env_Tides:ApplyEffect",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {"mission_tides_index", "mission_tides_planned", "dump_state"} <= implementations[
        "src/bridge/modloader.lua"
    ]
    assert {
        "tides_permanent_spawn_block_mask",
        "is_tides_spawn_permanently_blocked",
    } <= implementations["rust_solver/src/board.rs"]
    assert {
        "apply_env_danger",
        "apply_env_danger_board",
        "simulate_enemy_attacks",
    } <= implementations["rust_solver/src/enemy.rs"]
    assert {
        "legacy_tides_index_from_markers",
        "advance_mission_tides_warning",
        "project_plan_with_spawns",
    } <= implementations["rust_solver/src/turn_projection.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert {
        "test_mission_tides_flying_mech_takes_one_damage",
        "test_mission_tides_converts_marked_ground_and_mountain_to_water",
        "test_mission_tides_vek_attack_before_wave",
    } <= tests["rust_solver/src/simulate.rs"]
    assert {
        "test_mission_tides_projection_advances_warning_lane",
        "test_mission_tides_projection_reconstructs_building_shadow_and_convert_mask",
        "test_mission_tides_index_advances_markerless_lane_and_spawn_boundary",
        "test_mission_tides_index_beats_stale_visible_marker_row",
        "test_mission_tides_conservative_projection_keeps_current_marker",
        "test_mission_tides_legacy_single_row_recovers_index_and_advances",
        "test_mission_tides_legacy_recovered_index_survives_hidden_next_lane",
        "test_mission_tides_legacy_ambiguous_rows_keep_fail_closed_fallback",
        "test_mission_tides_legacy_empty_and_row_zero_masks_do_not_recover_index",
        "test_board_to_json_roundtrip",
    } == tests["rust_solver/src/turn_projection.rs"]
    assert tests["rust_solver/src/replay.rs"] == {
        "replay_solution_mission_tides_advances_final_warning_lane",
        "replay_solution_mission_tides_index_recovers_markerless_warning",
        "replay_solution_mission_tides_wave_destroys_pod",
    }
    gaps = " ".join(record["known_gaps"])
    assert "no native blocked-cell getter has been identified or traced" in gaps
    assert "not been installed or live-captured" in gaps
    assert "live-derived runtime observations" in gaps


def test_real_mission_terratide_record_tracks_inherited_smoke_semantics():
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
        if item["id"] == "environment-mission-terratide"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/missions/sand/mission_terratide.lua",
            "sha256": (
                "43356b9cb53d0ec369cf1a2bc5519acf"
                "7baa8cd54d096b4afbe8ff4fabd2c7dd"
            ),
            "symbols": [
                "Mission_Terratide",
                "Mission_Terratide:StartMission",
                "Env_Terratide",
            ],
        },
        {
            "path": "scripts/missions/grass/mission_tides.lua",
            "sha256": (
                "d27dab9f44e804e90385a6557057fc9a"
                "1281fab4bc83d6fff50151fc7702277a"
            ),
            "symbols": [
                "Env_Tides",
                "Env_Tides:Start",
                "Env_Tides:MarkBoard",
                "Env_Tides:Plan",
                "Env_Tides:ApplyEffect",
            ],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "dump_state",
        "mission_tides_index",
        "mission_tides_planned",
        "Mission_Terratide",
    } <= implementations[
        "src/bridge/modloader.lua"
    ]
    assert implementations["src/model/board.py"] == {"from_bridge_data"}
    assert implementations["src/solver/threat_audit.py"] == {
        "_will_be_smoked_by_environment_before_attack"
    }
    assert {"apply_env_smoke_board", "simulate_enemy_attacks"} <= (
        implementations["rust_solver/src/enemy.rs"]
    )
    assert {
        "legacy_terratide_index_from_markers",
        "advance_mission_tides_warning",
        "project_plan_with_spawns",
    } <= implementations["rust_solver/src/turn_projection.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["tests/test_modloader_tides_metadata.py"] == {
        "test_tides_metadata_exports_exact_integer_index_for_inherited_missions",
        "test_tides_metadata_omits_unrelated_missions",
        "test_tides_metadata_rejects_missing_fractional_and_out_of_range_indices",
        "test_tides_metadata_exports_exact_planned_state_for_inherited_missions",
        "test_modloader_serializes_only_the_mission_scoped_inherited_tides_index",
    }
    assert tests["tests/test_terratide_smoke.py"] == {
        "test_terratide_warning_routes_to_pending_smoke_not_damage",
        "test_terratide_index_reconstructs_markerless_smoke_and_survives_copy",
        "test_environment_tides_index_is_rejected_for_unrelated_or_invalid_payloads",
        "test_terratide_index_without_explicit_planned_true_does_not_invent_smoke",
        "test_threat_audit_credits_attacker_on_pending_terratide_smoke",
    }
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_mission_terratide_projection_smokes_full_row_and_advances_warning_backwards",
        "test_mission_terratide_prior_building_does_not_shadow_next_warning",
        "test_mission_terratide_index_survives_markerless_lane_across_depth",
        "test_mission_terratide_unplanned_index_does_not_advance",
        "test_mission_terratide_legacy_index_recovery_is_single_row_and_bounded",
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_terratide_wave_smokes_without_damage_and_cancels_queued_attack",
        "test_terratide_index_reconstructs_markerless_current_smoke_lane",
        "test_terratide_unplanned_index_does_not_reapply_smoke",
    }
    assert tests["rust_solver/src/serde_bridge.rs"] == {
        "test_terratide_danger_routes_to_smoke_not_damage",
        "test_tides_index_is_accepted_only_for_tides_and_terratide",
    }
    assert tests["rust_solver/src/replay.rs"] == {
        "replay_solution_terratide_smokes_full_row_and_advances_final_warning_lane",
        "replay_solution_terratide_index_recovers_markerless_smoke_and_warning",
    }
    gaps = " ".join(record["known_gaps"])
    assert "not been installed or live-captured" in gaps
    assert "conditional" in gaps
    assert "does not independently seed" in gaps
    assert "live-derived" in gaps


def test_real_final_cave_record_pins_exact_current_payload_and_bounded_model():
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
        if item["id"] == "environment-final-cave-danger"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/final/env_final.lua",
            "sha256": (
                "8d9220a9f7c0b6f3887ec8b9ffdd351b"
                "25cd4c53696d2f401c81dbeb932a6f33"
            ),
            "symbols": [
                "Env_Final",
                "Env_Final:Start",
                "Env_Final:MarkSpace",
                "Env_Final:SelectSpaces",
                "Env_Final:ApplyStart",
                "Env_Final:ApplyEnd",
                "Env_Final:GetAttackEffect",
                "IsBomb",
            ],
        },
        {
            "path": "scripts/environments.lua",
            "sha256": (
                "5f8a7d74f537abb33bc88c1f9669f3f"
                "6fabdd5c8c51aad3486d2e965e4fb80ec"
            ),
            "symbols": [
                "Env_Attack", "Env_Attack:Start", "Env_Attack:IsEffect",
                "Env_Attack:BlockSpawn", "Env_Attack:Plan",
                "Env_Attack:ApplyEffect", "Env_Attack:MarkBoard",
            ],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/bridge/modloader.lua"] == {
        "mission_final_cave_points", "mission_final_cave", "env_type",
        "environment_danger", "environment_danger_v2",
    }
    assert implementations["src/model/board.py"] == {
        "validate_mission_final_cave_payload", "environment_final_cave_known",
        "environment_final_cave_locations", "from_bridge_data",
    }
    assert implementations["rust_solver/src/serde_bridge.rs"] == {
        "JsonMissionFinalCave", "exact_mission_final_cave", "board_from_json",
    }
    assert implementations["rust_solver/src/enemy.rs"] == {
        "apply_mission_final_cave", "apply_env_danger",
        "apply_env_danger_board", "simulate_enemy_attacks",
    }
    assert implementations["src/loop/commands.py"] == {
        "_mission_final_cave_payload_block", "cmd_solve",
        "cmd_click_end_turn", "cmd_dispatch_end_turn", "cmd_end_turn",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "Rocks, tentacles-to-Lava, Rocks, tentacles-to-Lava" in facts
    assert "Ordered application emits DAMAGE_DEATH" in facts
    assert "otherwise-unused LavaPath" in facts
    assert "before queued Vek attacks" in facts
    assert "flying, Massive, Shielded, and Frozen" in facts
    assert "Two git-preserved live runs" in facts
    gaps = " ".join(record["known_gaps"])
    assert "does not reproduce GetQuarters, GetCrossingPath" in gaps
    assert "cannot forecast a second future turn" in gaps
    assert "source-derived plus historically corroborated" in gaps
    assert "Bomb replacement RNG" in gaps
    assert "lack build identity" in gaps
    assert "does not replace the separate Env_Volcano" in gaps

    historical = json.loads((
        repo_root
        / "data/observatory/captures/historical_git_mission_final_cave_runs.json"
    ).read_text(encoding="utf-8"))
    assert historical["kind"] == (
        "historical_git_mission_final_cave_corroboration"
    )
    assert [record["mode"] for record in historical["runs"][0]["records"]] == [
        "rocks", "tentacles_to_lava", "rocks", "tentacles_to_lava",
    ]
    assert historical["runs"][0]["records"][1][
        "turn_entry_mech_positions"
    ] == [[4, 2], [4, 4], [5, 1]]
    assert historical["runs"][0]["records"][3]["shape"] == (
        "complete cardinal crossing row"
    )
    assert historical["runs"][1]["records"][2]["next_sample"][
        "still_terrain_id_3"
    ] == [[5, 3], [6, 3]]


def test_real_control_shot_record_pins_v390_source_predicate_and_bridge_validation():
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
        if item["id"] == "player-weapon-control-shot"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/ae_weapons.lua",
            "sha256": (
                "5566b679c696ab489e40a0189d0a63b6"
                "99d01e9657f79a20e6f119239af1680f"
            ),
            "symbols": [
                "Science_TC_Control",
                "Science_TC_Control:GetTargetArea",
                "Science_TC_Control:IsControllable",
                "Science_TC_Control:GetSkillEffect",
                "Science_TC_Control:GetSecondTargetArea",
                "Science_TC_Control:GetFinalEffect",
                "Science_TC_Control_A",
                "Science_TC_Control_B",
                "Science_TC_Control_AB",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::ScienceTcControl",
        "WId::ScienceTcControlA",
        "WId::ScienceTcControlB",
        "WId::ScienceTcControlAB",
        "is_control_shot",
    } <= implementations["rust_solver/src/weapons.rs"]
    assert {
        "UnitFlags::UNPOWERED",
        "UnitFlags::GUARDING",
        "UnitFlags::BURROWER",
        "UnitFlags::GRAPPLED",
        "UnitFlags::JUMPER",
        "pub fn powered",
        "pub fn guarding",
        "pub fn burrower",
        "pub fn grappled",
        "pub fn jumper",
    } <= implementations["rust_solver/src/board.rs"]
    assert {
        "control_shot_eligible_unit",
        "controlled_reachable_tiles_with_cost",
        "controlled_reachable_tiles",
    } == implementations["rust_solver/src/movement.rs"]
    assert {
        "control_shot_target_range",
        "control_shot_move_budget",
        "enumerate_control_shot_targets",
    } == implementations["rust_solver/src/solver.rs"]
    assert {
        "control_shot_target_range",
        "control_shot_move_budget",
        "sim_control_shot",
    } == implementations["rust_solver/src/simulate.rs"]
    assert {
        "JsonUnit",
        "board_from_json",
        "known_burrower_type",
        "known_jumper_type",
    } == implementations["rust_solver/src/serde_bridge.rs"]
    assert implementations["rust_solver/src/turn_projection.rs"] == {"board_to_json"}
    assert {
        "p:GetBaseMove()",
        "p:IsPowered()",
        "p:IsBurrower()",
        "p:IsJumper()",
        "IsGrappled",
        "point_list_contains",
        "skill:GetTargetArea",
        "skill:GetSecondTargetArea",
        "skill:GetFinalEffect",
    } == implementations["src/bridge/modloader.lua"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert len(set().union(*tests.values())) == 22
    assert {
        "control_shot_variants_enumerate_exact_move_budgets",
        "control_shot_target_enumeration_matches_source_predicate",
        "test_control_shot_can_move_grappled_zero_current_move_unit",
        "test_control_shot_moves_eligible_ally_without_lets_walk_progress",
        "test_control_shot_moves_named_zero_move_exceptions",
        "test_control_shot_rejects_ineligible_source_predicate_cases",
        "test_control_shot_guarding_burrower_remains_eligible",
        "test_control_shot_fixed_budget_moves_grappled_and_named_exceptions",
        "test_control_shot_named_exceptions_still_obey_prior_status_gates",
        "test_control_shot_native_predicates_and_base_move_survive_bridge_parse",
        "test_control_shot_state_export_uses_live_predicates_separately",
        "test_control_shot_execution_validates_native_target_areas_before_effect",
    } <= set().union(*tests.values())
    assert "test_control_shot_moves_eligible_ally_without_lets_walk_progress" in tests[
        "rust_solver/src/simulate.rs"
    ]
    gaps = " ".join(record["known_gaps"])
    assert "extra-tile" in gaps
    assert "origin as the second click" in gaps
    assert "legacy payload defaults" in gaps
    assert "direct coordinate mutation" in gaps
    assert "visible-UI/achievement" in gaps


def test_real_mission_belt_record_pins_checkpoint_direction_fix():
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
        if item["id"] == "environment-mission-belt-conveyors"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/acid/mission_belt.lua",
            "sha256": (
                "0cde35aae24938eb38a0e4dcb03d5ee7"
                "a6ea4f6fc6ae8201c9d568f8ef590f5a"
            ),
            "symbols": [
                "Mission_Belt",
                "Mission_BeltRandom",
                "Env_Belt",
                "Env_Belt:IsValidTarget",
                "Env_Belt:IsBelt",
                "Env_Belt:GetDir",
                "Env_Belt:CheckBelts",
                "Env_Belt:AddBelt",
                "Env_Belt:MarkBoard",
                "Env_Belt:IsEffect",
                "Env_Belt:ApplyBelts",
                "Env_Belt:ApplyEffect",
                "Env_BeltLine",
                "Env_BeltLine:Start",
                "Env_BeltRandom",
                "Env_BeltRandom:IsValidTarget",
                "Env_BeltRandom:Start",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "engine_dir_to_solver_dir",
        "solver_dir_to_engine_dir",
        "board_from_json",
    } <= implementations["rust_solver/src/serde_bridge.rs"]
    assert {
        "active_conveyor_mission",
        "simulate_conveyor_belts",
        "simulate_enemy_attacks",
    } == implementations["rust_solver/src/enemy.rs"]
    assert implementations["rust_solver/src/turn_projection.rs"] == {
        "board_to_json"
    }
    assert implementations["rust_solver/src/replay.rs"] == {
        "replay_solution"
    }
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/serde_bridge.rs"] == {
        "test_conveyor_engine_dirs_normalized_to_solver_dirs"
    }
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_board_to_json_roundtrip_preserves_all_conveyor_directions"
    }
    assert {
        "test_conveyor_moves_enemy_before_projectile_attack",
        "test_beltrandom_queued_attack_resolves_before_random_belt_tick",
        "test_conveyor_collision_with_same_tick_mover_does_not_bump_damage",
    } <= tests["rust_solver/src/enemy.rs"]
    gaps = " ".join(record["known_gaps"])
    assert "does not reproduce native GetCrossingPath" in gaps
    assert "native environment scheduler" in gaps
    assert "runtime-stub test" in gaps


def test_real_starfish_record_pins_exact_family_dispatch():
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
        if item["id"] == "enemy-weapon-starfish"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/ae_pawns.lua",
            "sha256": (
                "e87efe90c0342f26969c14159e6b6c93"
                "766aeedcbc3319fb0f418048d129e9f4"
            ),
            "symbols": ["Starfish1", "Starfish2"],
        },
        {
            "path": "scripts/advanced/ae_weapons_enemy.lua",
            "sha256": (
                "db757b1afa790fe3f7576930abd0c7e4"
                "cf5d8b9dc7308aa15ce9a9736f224d13"
            ),
            "symbols": [
                "StarfishAtk1",
                "StarfishAtk1:GetTargetArea",
                "StarfishAtk1:GetSkillEffect",
                "StarfishAtk2",
            ],
        },
        {
            "path": "scripts/advanced/bosses/starfish.lua",
            "sha256": (
                "6d7d122e7be43abf535bf4295afde222"
                "aeb6d61482a97d7787d1f962b585fe94"
            ),
            "symbols": [
                "StarfishBoss",
                "StarfishAtkB1",
                "StarfishAtkB1:GetTargetArea",
                "StarfishAtkB1:GetTargetScore",
                "StarfishAtkB1:GetSkillEffect",
            ],
        },
        {
            "path": "scripts/global.lua",
            "sha256": (
                "96d82d83a1620061e6fd013aa8462883e"
                "1f3764d03752757ad77fbbbd04bc9b2"
            ),
            "symbols": ["Skill:GetTargetScore", "Skill:ScoreList"],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::StarfishAtk1",
        "WId::StarfishAtk2",
        "WId::StarfishAtkB1",
        "WEAPONS",
        "weapon_def",
        "wid_from_str",
        "wid_to_str",
        "enemy_weapon_for_type",
        "weapon_name",
    } == implementations["rust_solver/src/weapons.rs"]
    assert implementations["rust_solver/src/enemy.rs"] == {
        "apply_starfish_appendages",
        "simulate_enemy_attacks",
    }
    assert {
        "projected_enemy_uses_special_targeting",
        "projected_enemy_attack_reach",
        "projected_enemy_reach",
        "projected_starfish_target_score",
        "requeue_enemies_heuristic",
    } == implementations["rust_solver/src/turn_projection.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/weapons.rs"] == {
        "test_starfish_weapon_defs_and_mappings"
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_starfish_hits_diagonal_tiles_only",
        "test_starfish_leader_diagonal_damage_and_cardinal_push",
        "test_starfish_variants_dispatch_exact_diagonal_damage",
    }
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_webbed_starfish_requeues_self_for_positive_diagonal_score",
        "test_starfish_zero_score_projection_stays_queueless",
        "test_requeued_starfish_damages_on_second_projection",
    }
    gaps = " ".join(record["known_gaps"])
    assert "next-turn projection reproduces the sole self-target" in gaps
    assert "not native movement, candidate selection, tie-breaking" in gaps
    assert "Vek Hormones" in gaps


def test_real_bouncer_record_pins_exact_family_dispatch():
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
        if item["id"] == "enemy-weapon-bouncer"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/ae_pawns.lua",
            "sha256": (
                "e87efe90c0342f26969c14159e6b6c93"
                "766aeedcbc3319fb0f418048d129e9f4"
            ),
            "symbols": ["Bouncer1", "Bouncer2"],
        },
        {
            "path": "scripts/advanced/ae_weapons_enemy.lua",
            "sha256": (
                "db757b1afa790fe3f7576930abd0c7e4"
                "cf5d8b9dc7308aa15ce9a9736f224d13"
            ),
            "symbols": [
                "BouncerAtk1",
                "BouncerAtk1:GetSkillEffect",
                "BouncerAtk2",
            ],
        },
        {
            "path": "scripts/advanced/bosses/bouncer.lua",
            "sha256": (
                "39b41d020af444251d3565b3cf606ac7"
                "e6a56547f26ca88efdd7d24182a38704"
            ),
            "symbols": [
                "BouncerBoss",
                "BouncerAtkB",
                "BouncerAtkB:GetSkillEffect",
            ],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::BouncerAtk1",
        "WId::BouncerAtk2",
        "WId::BouncerAtkB",
        "WEAPONS",
        "weapon_def",
        "wid_from_str",
        "wid_to_str",
        "enemy_weapon_for_type",
        "weapon_name",
    } == implementations["rust_solver/src/weapons.rs"]
    assert implementations["rust_solver/src/simulate.rs"] == {
        "apply_push",
        "apply_push_no_edge_bump",
    }
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert {
        "test_bouncer_weapon_defs_and_mappings",
        "test_bouncer_boss_sweeping_horns_def",
    } == tests["rust_solver/src/weapons.rs"]
    assert {
        "test_bouncer_melee_self_bounce_and_target_push",
        "test_bouncer_variants_dispatch_exact_damage_and_recoil",
        "test_bouncer_boss_enemy_attack_hits_t_pattern_and_bounces",
    } <= tests["rust_solver/src/enemy.rs"]
    gaps = " ".join(record["known_gaps"])
    assert "does not reproduce native target acquisition" in gaps
    assert "leader branch uses generic apply_push" in gaps
    assert "no focused live leader-at-edge evidence" in gaps


def test_real_moth_record_pins_exact_range_fix():
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
        if item["id"] == "enemy-weapon-moth"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/ae_pawns.lua",
            "sha256": (
                "e87efe90c0342f26969c14159e6b6c93"
                "766aeedcbc3319fb0f418048d129e9f4"
            ),
            "symbols": ["Moth1", "Moth2"],
        },
        {
            "path": "scripts/advanced/ae_weapons_enemy.lua",
            "sha256": (
                "db757b1afa790fe3f7576930abd0c7e4"
                "cf5d8b9dc7308aa15ce9a9736f224d13"
            ),
            "symbols": ["MothAtk1", "MothAtk1:GetSkillEffect", "MothAtk2"],
        },
        {
            "path": "scripts/weapons_base.lua",
            "sha256": (
                "bdb55457746d08b46e8b62ad7cfc27f"
                "0a08bde9fab7397a4780dfe945b5f8f38"
            ),
            "symbols": ["LineArtillery", "LineArtillery:GetTargetArea"],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::MothAtk1",
        "WId::MothAtk2",
        "WEAPONS",
        "weapon_def",
        "wid_from_str",
        "wid_to_str",
        "enemy_weapon_for_type",
        "weapon_name",
    } == implementations["rust_solver/src/weapons.rs"]
    assert implementations["rust_solver/src/turn_projection.rs"] == {
        "projected_enemy_attack_reach",
        "projected_enemy_reach",
        "requeue_enemies_heuristic",
    }
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/weapons.rs"] == {
        "test_moth_weapon_defs_and_mappings"
    }
    assert {
        "test_moth_variants_enforce_exact_lua_range_and_damage",
        "test_moth_artillery_self_bounce_bumps_blocking_mech",
        "test_moth_artillery_killed_target_corpse_bumps_live_mech",
    } <= tests["rust_solver/src/enemy.rs"]
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_webbed_moth_reach_stops_at_lua_maximum"
    }
    assert tests["tests/test_weapon_defs.py"] == {
        "test_moth_weapon_defs_match_inherited_lua_artillery_range"
    }
    gaps = " ".join(record["known_gaps"])
    assert "does not reproduce native movement, target acquisition" in gaps
    assert "movement-plus-attack heuristic" in gaps
    assert "2..=5 target interval" in gaps


def test_real_tumblebug_record_pins_live_ids_and_projected_bombrocks():
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
        if item["id"] == "enemy-weapon-tumblebug"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/ae_pawns.lua",
            "sha256": (
                "e87efe90c0342f26969c14159e6b6c93"
                "766aeedcbc3319fb0f418048d129e9f4"
            ),
            "symbols": ["Dung1", "Dung2"],
        },
        {
            "path": "scripts/advanced/ae_weapons_enemy.lua",
            "sha256": (
                "db757b1afa790fe3f7576930abd0c7e4"
                "cf5d8b9dc7308aa15ce9a9736f224d13"
            ),
            "symbols": [
                "DungAtk1",
                "BombRock",
                "DungAtk1:GetTargetArea",
                "DungAtk1:GetTargetScore",
                "DungAtk1:CanSpawnRock",
                "DungAtk1:GetSkillEffect",
                "DungAtk2",
            ],
        },
        {
            "path": "scripts/advanced/bosses/dung.lua",
            "sha256": (
                "2aa80c73688694d9f904c6264ef63e7f"
                "e1562028cc5007705a561c8696cbf906"
            ),
            "symbols": ["DungBoss", "DungAtkB"],
        },
        {
            "path": "scripts/global.lua",
            "sha256": (
                "96d82d83a1620061e6fd013aa8462883"
                "e1f3764d03752757ad77fbbbd04bc9b2"
            ),
            "symbols": ["Skill:ScoreList"],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::TumblebugAtk1",
        "WId::TumblebugAtk2",
        "WId::TumblebugAtkB",
        "WEAPONS",
        "weapon_def",
        "wid_from_str",
        "wid_to_str",
        "enemy_weapon_for_type",
        "weapon_name",
    } == implementations["rust_solver/src/weapons.rs"]
    assert {
        "projected_enemy_uses_special_targeting",
        "projected_enemy_attack_reach",
        "projected_enemy_reach",
        "projected_tumblebug_target_score",
        "projected_tumblebug_can_spawn_rock",
        "spawn_projected_bombrock",
        "requeue_tumblebug_heuristic",
        "eligible_for_requeue",
        "requeue_enemies_heuristic",
    } == implementations["rust_solver/src/turn_projection.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/weapons.rs"] == {
        "test_tumblebug_live_lua_dung_aliases"
    }
    assert {
        "test_tumblebug_projection_spawns_bombrock_and_queues_its_hit",
        "test_tumblebug_leader_projection_spawns_two_rocks_in_attack_line",
        "test_tumblebug_leader_projection_skips_blocked_second_rock_only",
        "test_tumblebug_projection_does_not_spawn_when_first_target_is_blocked",
        "test_tumblebug_projection_rejects_harmless_empty_rock_targets",
        "test_tumblebug_projected_bombrock_legality_matrix",
    } <= tests["rust_solver/src/turn_projection.rs"]
    assert tests["tests/test_weapon_defs.py"] == {
        "test_dung_attack_aliases_match_tumblebug_weapon_defs"
    }
    gaps = " ".join(record["known_gaps"])
    assert "Board:GetDeployLocScore" in gaps
    assert "mobile projection" in gaps
    assert "bridge-materialized BombRocks" in gaps


def test_real_centipede_record_pins_acid_t_shape_and_leader_trail():
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
        if item["id"] == "enemy-weapon-centipede"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/pawns.lua",
            "sha256": (
                "e999b8d98526c1e36f4746dd65b9d9e"
                "7ee3ca0b22029ed391d5b71fda49dc239"
            ),
            "symbols": ["Centipede1", "Centipede2"],
        },
        {
            "path": "scripts/weapons_enemy.lua",
            "sha256": (
                "5231dd7a2de730f04fa4116c0d99f07e"
                "cbb3b25059db3593d54d689c37bd4b7b"
            ),
            "symbols": [
                "CentipedeAtk1",
                "CentipedeAtk1:GetTargetScore",
                "CentipedeAtk1:GetSkillEffect",
                "CentipedeAtk2",
                "CentipedeAtk_Acid",
            ],
        },
        {
            "path": "scripts/advanced/bosses/centipede.lua",
            "sha256": (
                "eaa9a21947be4b7aa8e016558aadc79c"
                "b528f1bfa3cf20c2fd747ff947711ef0"
            ),
            "symbols": [
                "CentipedeBoss",
                "CentipedeAtkB",
                "CentipedeAtkB:GetTargetScore",
                "CentipedeAtkB:GetSkillEffect",
            ],
        },
        {
            "path": "scripts/global.lua",
            "sha256": (
                "96d82d83a1620061e6fd013aa8462883"
                "e1f3764d03752757ad77fbbbd04bc9b2"
            ),
            "symbols": ["Skill:ScoreList"],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::CentipedeAtk1",
        "WId::CentipedeAtk2",
        "WId::CentipedeAtkB",
        "WEAPONS",
        "weapon_def",
        "wid_from_str",
        "wid_to_str",
        "enemy_weapon_for_type",
        "weapon_name",
    } == implementations["rust_solver/src/weapons.rs"]
    assert implementations["rust_solver/src/enemy.rs"] == {
        "simulate_enemy_attacks"
    }
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/weapons.rs"] == {
        "test_centipede_weapon_defs_and_mappings"
    }
    assert {
        "test_normal_centipede_applies_one_damage_and_acid_t_splash",
        "test_alpha_centipede_applies_acid_to_target",
        "test_alpha_centipede_aoe_perpendicular_splashes",
        "test_centipede_leader_acidifies_projectile_path",
        "test_centipede_attack_lands_on_board_edge",
    } <= tests["rust_solver/src/enemy.rs"]
    assert tests["tests/test_weapon_defs.py"] == {
        "test_centipede_weapon_defs_match_lua_acid_t_shape"
    }
    gaps = " ".join(record["known_gaps"])
    assert "GetProjectileEnd" in gaps
    assert "ScoreList" in gaps
    assert "bridge-selected queued target" in gaps


def test_real_supply_train_record_pins_inherited_lifecycle_and_immunities():
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
        if item["id"] == "mission-supply-train"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/mission_train.lua",
            "sha256": (
                "a9ec7ce1ea386e3b82ecd992b6cacd8c"
                "a17990cb37f7109e8060140cbb3a5e0b"
            ),
            "symbols": [
                "Mission_Train",
                "Mission_Train:StartMission",
                "Mission_Train:IsTrainAlive",
                "Mission_Train:UpdateObjectives",
                "Mission_Train:GetCompletedObjectives",
                "Mission_Train:StopTrain",
                "Mission_Train:UpdateMission",
                "Train_Pawn",
                "Train_Damaged",
                "Train_Move",
                "Train_Move:GetTargetArea",
                "Train_Move:GetSkillEffect",
                "Train_Move:GetTargetScore",
            ],
        },
        {
            "path": (
                "scripts/advanced/missions/grass/"
                "mission_armored_train.lua"
            ),
            "sha256": (
                "4c1438bd02ffdcc0d4f975f432168d1d4"
                "5017126f819995c86873978b67a288a"
            ),
            "symbols": [
                "Mission_Armored_Train",
                "Train_Armored_Damaged",
                "Train_Armored",
                "Armored_Train_Move",
                "Armored_Train_Move:GetTargetArea",
                "Armored_Train_Move:GetSkillEffect",
                "Armored_Train_Move:GetTargetScore",
            ],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/board.rs"] == {
        "can_catch_fire"
    }
    assert {
        "simulate_enemy_attacks",
        "simulate_train_advance",
        "transition_destroyed_supply_train",
    } == implementations["rust_solver/src/enemy.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert {
        "test_smoked_train_still_activates",
        "test_supply_train_types_clear_stale_fire_without_tick_damage",
    } <= tests["rust_solver/src/enemy.rs"]
    assert {
        "test_chain_whip_forest_does_not_ignite_fireproof_supply_trains",
        "test_supply_train_types_ignore_flamethrower_fire",
    } <= tests["rust_solver/src/simulate.rs"]
    assert tests["tests/test_train_objective_scoring.py"] == {
        "test_python_breakdown_scores_train_once_and_penalizes_degradation",
        "test_supply_train_static_stats_match_lua",
    }
    gaps = " ".join(record["known_gaps"])
    assert "VEC_UP" in gaps
    assert "AddQueuedCharge" in gaps
    assert "protected live achievement session" in gaps


def test_real_reactivation_record_pins_roster_thaw_approximation():
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
        if item["id"] == "mission-reactivation"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/snow/mission_reactivation.lua",
            "sha256": (
                "8dd29071133d7af56d872792e97323541"
                "226e93315f76d729ccdd8ea9145e9d5"
            ),
            "symbols": [
                "Mission_Reactivation",
                "Mission_Reactivation:StartMission",
                "Mission_Reactivation:NextTurn",
            ],
        }
    ]
    assert record["implementations"] == [
        {
            "path": "rust_solver/src/enemy.rs",
            "symbols": [
                "simulate_enemy_attacks",
                "simulate_reactivation_thaw",
            ],
        }
    ]
    assert record["tests"] == [
        {
            "path": "rust_solver/src/enemy.rs",
            "symbols": [
                "test_reactivation_thaws_two_per_enemy_turn",
                "test_reactivation_thaw_skipped_on_other_missions",
                "test_reactivation_thaw_caps_at_two_even_with_more_frozen",
            ],
        }
    ]
    gaps = " ".join(record["known_gaps"])
    assert "Mission_Reactivation.Enemies" in gaps
    assert "lowest-UID" in " ".join(
        item["statement"] for item in record["evidence"]
    )
    assert "random_removal" in gaps


def test_real_dam_record_pins_dual_tile_objective_and_flood():
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
        if item["id"] == "mission-dam-flood"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/grass/mission_dam.lua",
            "sha256": (
                "bc677d4ea6f0dfc80b43b6711d1f20e"
                "3ea2d75fb87c869d59956c745830c7f08"
            ),
            "symbols": [
                "Mission_Dam",
                "Mission_Dam:StartMission",
                "Mission_Dam:IsEndBlocked",
                "Mission_Dam:UpdateObjectives",
                "Mission_Dam:GetCompletedObjectives",
                "Mission_Dam:NextTurn",
                "Mission_Dam:UpdateMission",
                "Dam_Pawn",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "apply_damage_inner",
        "dam_dead",
        "trigger_dam_flood",
        "flood_tile",
    }
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert {
        "test_dam_flood_destroys_time_pod_without_collecting",
        "test_dam_flood_drowning_triggers_blast_psion_explosion",
        "test_dam_flood_extinguishes_forest_ignited_by_same_attack",
    } <= tests["rust_solver/src/simulate.rs"]
    assert tests["tests/test_mission_unit_objectives.py"] == {
        "test_mission_dam_destroys_dam_pawn"
    }
    gaps = " ".join(record["known_gaps"])
    assert "named dam location" in gaps
    assert "IsEndBlocked" in gaps
    assert "IgnoreSmoke" in gaps


def test_real_teleporter_record_pins_live_pair_capture_and_scoping():
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
        if item["id"] == "mission-teleporter-pads"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/acid/mission_teleport.lua",
            "sha256": (
                "b6aa9286de8cfd6f871ed479b8d78f84"
                "02860db15e5c5dc7b29f33972680ea8f"
            ),
            "symbols": [
                "Mission_Teleporter",
                "Mission_Teleporter:StartMission",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "apply_teleport_on_land"
    }
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/serde_bridge.rs"] == {
        "test_non_teleporter_mission_ignores_stale_pad_pairs",
        "test_teleporter_mission_keeps_pad_pairs",
    }
    assert {
        "test_teleport_partner_lookup_both_directions",
        "test_mine_kill_on_pad_does_not_teleport",
        "test_mech_move_onto_pad_teleports",
        "test_empty_teleporter_pairs_is_noop",
    } == tests["rust_solver/src/simulate.rs"]
    gaps = " ".join(record["known_gaps"])
    assert "Environment:GetQuarters" in gaps
    assert "Board:AddTeleport" in gaps
    assert "protected live achievement session" in gaps


def test_real_airstrike_record_pins_lethal_cross_and_spawn_boundary():
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
        if item["id"] == "environment-mission-airstrike"
    )
    assert record["coverage"] == "partial"
    sources = {
        reference["path"]: reference
        for reference in record["sources"]
    }
    assert sources["scripts/missions/grass/mission_airstrike.lua"] == {
        "path": "scripts/missions/grass/mission_airstrike.lua",
        "sha256": (
            "5adcffbf370ba0e33a029fc22cb71c892"
            "62b00d64b83e30dabe6a4842effe94a"
        ),
        "symbols": [
            "Mission_Airstrike",
            "Env_Airstrike",
            "Env_Airstrike:GetAttackArea",
            "Env_Airstrike:MarkSpace",
            "Env_Airstrike:GetAttackEffect",
            "Env_Airstrike:BlockSpawn",
            "Env_Airstrike:IsValidTarget",
            "Env_Airstrike:SelectSpaces",
        ],
    }
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/enemy.rs"] == {
        "apply_env_danger",
        "apply_env_danger_board",
        "simulate_enemy_attacks",
    }
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_airstrike_lethal_danger_collapses_empty_cracked_ground",
        "test_airstrike_lethal_danger_does_not_collapse_occupied_cracked_ground",
        "test_airstrike_nonlethal_danger_leaves_empty_cracked_ground",
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_airstrike_env_ignores_stale_flying_immune_field"
    }
    gaps = " ".join(record["known_gaps"])
    assert "native scheduler" in gaps
    assert "SpaceDamage(DAMAGE_DEATH)" in gaps
    assert "protected live achievement session" in gaps


def test_real_support_wind_record_pins_zones_scan_order_and_use_limit():
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
        if item["id"] == "player-weapon-support-wind"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/weapons_support.lua",
            "sha256": (
                "f5fc6be6bde2aae2676f29c39b45fe03"
                "9d2a81537608e1f43e17ebc3ecda1855"
            ),
            "symbols": [
                "Support_Wind",
                "Support_Wind:GetTargetZone",
                "Support_Wind:GetTargetArea",
                "Support_Wind:GetSkillEffect",
                "Support_Wind_A",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::SupportWind",
        "SUPPORT_WIND_TARGETS",
        "support_wind_dir_from_target",
    } <= implementations["rust_solver/src/weapons.rs"]
    assert "sim_global_push" in implementations["rust_solver/src/simulate.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_support_wind_pushes_every_unit_left",
        "test_support_wind_right_scan_order_moves_leading_unit_first",
        "test_support_wind_bump_into_building_costs_grid",
    }
    assert tests["tests/test_action_classification.py"] == {
        "test_support_wind_target_zone_is_attack"
    }
    gaps = " ".join(record["known_gaps"])
    assert "one representative target per 2x2 zone" in gaps
    assert "cross-turn single-use state" in gaps
    assert "protected live achievement session" in gaps


def test_real_sandstorm_record_pins_non_damage_boundary_and_open_row_gap():
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
        if item["id"] == "environment-mission-sandstorm"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/sand/mission_sandstorm.lua",
            "sha256": (
                "e657b1a8fdc21cd011d28b16051336b3"
                "820248a4cab1c111e36a437a209650c1"
            ),
            "symbols": [
                "Mission_Sandstorm",
                "Env_Sandstorm",
                "Env_Sandstorm:Start",
                "Env_Sandstorm:IsEffect",
                "Env_Sandstorm:ApplyEffect",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert "env_sandstorm_non_damage" in implementations[
        "rust_solver/src/serde_bridge.rs"
    ]
    assert "sandstorm_non_damage" in implementations["src/model/board.py"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_sandstorm_markers_do_not_damage_mech_or_building"
    }
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_board_to_json_preserves_sandstorm_environment_identity"
    }
    assert tests["tests/test_sandstorm_environment.py"] == {
        "test_sandstorm_warning_omits_phantom_damage",
        "test_sandstorm_warning_is_not_reported_as_damage",
        "test_sandstorm_raw_markers_do_not_break_held_checkpoint_parity",
    }
    gaps = " ".join(record["known_gaps"])
    assert "Env_Sandstorm.Row" in gaps
    assert "RandomizeTerrain" in gaps
    assert "protected live achievement session" in gaps


def test_real_ice_storm_record_pins_freeze_status_and_open_rng_gap():
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
        if item["id"] == "environment-mission-ice-storm"
    )
    assert record["coverage"] == "partial"
    sources = {
        reference["path"]: reference
        for reference in record["sources"]
    }
    assert sources["scripts/missions/snow/mission_snowstorm.lua"] == {
        "path": "scripts/missions/snow/mission_snowstorm.lua",
        "sha256": (
            "b798e1faca26239af59057eaa83155fe"
            "3fac9db4e6fdb8010907bad258d9c4d6"
        ),
        "symbols": [
            "Mission_SnowStorm",
            "Mission_SnowStorm:StartMission",
            "Env_SnowStorm",
            "Env_SnowStorm:MarkSpace",
            "Env_SnowStorm:ApplyEffect",
            "Env_SnowStorm:SelectSpaces",
        ],
    }
    assert {
        "Env_Attack:Start",
        "Env_Attack:IsEffect",
        "Env_Attack:BlockSpawn",
        "Env_Attack:Plan",
        "Env_Attack:MarkBoard",
    } <= set(sources["scripts/environments.lua"]["symbols"])
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert "_freeze_covers_single_building_threat" in implementations[
        "src/solver/threat_audit.py"
    ]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_ice_storm_freezes_building_then_damage_only_thaws_it",
        "test_ice_storm_shield_blocks_status_and_is_consumed",
        "test_ice_storm_extinguishes_and_freezes_burning_unit_and_mountain",
    }
    assert "test_ice_storm_freezes_flying_enemy_and_cancels_attack" in tests[
        "tests/test_ice_storm_pytest.py"
    ]
    gaps = " ".join(record["known_gaps"])
    assert "random selection" in gaps
    assert "indexed separately" in gaps
    assert "protected live achievement session" in gaps


def test_real_nanostorm_record_pins_damage_acid_and_building_exclusion():
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
        if item["id"] == "environment-mission-nanostorm"
    )
    assert record["coverage"] == "partial"
    sources = {
        reference["path"]: reference
        for reference in record["sources"]
    }
    assert sources["scripts/advanced/missions/acid/mission_nanostorm.lua"] == {
        "path": "scripts/advanced/missions/acid/mission_nanostorm.lua",
        "sha256": (
            "6c6145ab3f4dc747c89850548d0f1f1d"
            "ed45584ecd30d5b955a4daf2f85e76f2"
        ),
        "symbols": [
            "Mission_NanoStorm",
            "Mission_NanoStorm:StartMission",
            "Env_NanoStorm",
        ],
    }
    assert {
        "Env_SnowStorm:ApplyEffect",
        "Env_SnowStorm:SelectSpaces",
    } <= set(sources["scripts/missions/snow/mission_snowstorm.lua"]["symbols"])
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert "env_danger_acid" in implementations["rust_solver/src/board.rs"]
    assert "nanostorm_env" in implementations["rust_solver/src/serde_bridge.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_nanostorm_applies_damage_and_acid_but_excludes_buildings"
    }
    assert tests["rust_solver/src/serde_bridge.rs"] == {
        "test_explicit_lethal_mission_outranks_stale_nanostorm_env_type"
    }
    assert {
        "test_nano_storm_damages_and_acidifies_without_freeze",
        "test_nano_storm_hits_and_acidifies_flying_units",
        "test_nano_storm_rejects_stale_building_marker",
    } <= tests["tests/test_ice_storm_pytest.py"]
    gaps = " ".join(record["known_gaps"])
    assert "native RNG state" in gaps
    assert "Shield" in gaps
    assert "protected live achievement session" in gaps


def test_real_repulse_record_pins_variant_shield_matrix_and_open_native_order():
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
        if item["id"] == "player-weapon-repulse"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/weapons_science.lua",
        "sha256": (
            "b77845b449f4e477805fe1b5087113451"
            "19230a7b70cfb0b049d79ccd735376e"
        ),
        "symbols": [
            "Science_Repulse",
            "Science_Repulse:GetTargetArea",
            "Science_Repulse:GetSkillEffect",
            "Science_Repulse_A",
            "Science_Repulse_B",
            "Science_Repulse_AB",
        ],
    }]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::ScienceRepulse",
        "WId::ScienceRepulseA",
        "WId::ScienceRepulseB",
        "WId::ScienceRepulseAB",
        "WeaponFlags::SHIELD_SELF",
        "WeaponFlags::SHIELD_ALLIES",
    } <= implementations["rust_solver/src/weapons.rs"]
    assert "sim_self_aoe" in implementations["rust_solver/src/simulate.rs"]
    assert "Science_Repulse_B" in implementations["src/model/weapons.py"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/weapons.rs"] == {
        "test_repulse_variant_defs_and_mappings"
    }
    assert {
        "test_repulse_b_shields_adjacent_friendlies_and_buildings_only",
        "test_repulse_ab_combines_friendly_building_and_self_shields",
        "test_repulse_center_and_cardinal_targets_are_effect_equivalent",
        "test_repulse_offboard_cardinal_target_noops_conservatively",
    } <= tests["rust_solver/src/simulate.rs"]
    gaps = " ".join(record["known_gaps"])
    assert "SpaceDamage ordering" in gaps
    assert "canonicalizes" in gaps
    assert "protected live achievement session" in gaps


def test_real_deploy_tank_record_pins_cannon_effects_and_open_native_helpers():
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
        if item["id"] == "player-weapon-deploy-tank"
    )
    assert record["coverage"] == "partial"
    sources = {
        reference["path"]: reference
        for reference in record["sources"]
    }
    assert sources["scripts/weapons_deploy.lua"] == {
        "path": "scripts/weapons_deploy.lua",
        "sha256": (
            "9c5301c1ca91864d92a441ba032d4c02"
            "4a0e184978d77242f79e0b012522ca73"
        ),
        "symbols": [
            "Deploy_Tank",
            "Deploy_TankA",
            "Deploy_TankB",
            "Deploy_TankAB",
            "Deploy_TankShot",
            "Deploy_TankShot2",
        ],
    }
    assert {
        "TankDefault",
        "TankDefault:GetTargetArea",
        "TankDefault:GetSkillEffect",
    } == set(sources["scripts/weapons_base.lua"]["symbols"])
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::DeployTankShot",
        "WId::DeployTankShot2",
    } <= implementations["rust_solver/src/weapons.rs"]
    assert "sim_projectile" in implementations["rust_solver/src/simulate.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_deploy_tank_canonical_direction_dispatches_both_cannons"
    }
    assert {
        "test_deploy_tank_stock_cannon_pushes_without_damage",
        "test_deploy_tank_upgraded_cannon_damages_and_pushes_distant_blocker",
    } == tests["tests/test_sim_v50_deploy_tank.py"]
    gaps = " ".join(record["known_gaps"])
    assert "Board:GetSimpleReachable" in gaps
    assert "adjacent effect-equivalent target" in gaps
    assert "protected live achievement session" in gaps


def test_real_mission_hacking_record_pins_conversion_and_open_update_timing():
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
        if item["id"] == "mission-hacking-conversion"
    )
    assert record["coverage"] == "partial"
    sources = {
        reference["path"]: reference
        for reference in record["sources"]
    }
    assert sources["scripts/advanced/missions/snow/mission_hacking.lua"] == {
        "path": "scripts/advanced/missions/snow/mission_hacking.lua",
        "sha256": (
            "1d26d25e090ef69854001d48a676657b"
            "f049e37b432acf87aebf66936feb0e55"
        ),
        "symbols": [
            "Mission_Hacking",
            "Mission_Hacking:UpdateObjectives",
            "Mission_Hacking:GetCompletedStatus",
            "Mission_Hacking:NextTurn",
            "Mission_Hacking:GetCompletedObjectives",
            "Mission_Hacking:StartMission",
            "Mission_Hacking:UpdateMission",
            "Hacked_Building",
            "Snowtank1_Player",
            "SnowtankAtk1_Player",
        ],
    }
    assert sources["scripts/missions/missions.lua"]["symbols"] == [
        "Mission:BaseUpdate"
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "transition_hacked_cannon_bot",
        "simulate_enemy_attacks",
    } <= implementations["rust_solver/src/enemy.rs"]
    assert {
        "count_unit_deaths_between",
        "is_mission_hacking_bot_replacement",
    } <= implementations["rust_solver/src/board.rs"]
    assert {
        "mission_hacking_ids",
        "mission_hacking_bot_id",
        "mission_hacking_hack_id",
    } <= implementations["src/bridge/modloader.lua"]
    assert implementations["src/bridge/reader.py"] == {
        "_normalize_mission_hacking_ids"
    }
    assert {
        "mission_hacking_bot_id",
        "mission_hacking_hack_id",
        "from_bridge_data",
        "copy",
    } <= implementations["src/model/board.py"]
    assert {
        "mission_hacking_bot_id",
        "mission_hacking_hack_id",
        "board_from_json",
    } <= implementations["rust_solver/src/serde_bridge.rs"]
    assert implementations["rust_solver/src/turn_projection.rs"] == {
        "board_to_json"
    }
    assert "_UNSTABLE_SPAWN_IDENTITY_TYPES" in implementations[
        "src/solver/verify.py"
    ]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert {
        "test_hacking_conversion_replaces_bot_and_preserves_only_location_and_shield",
        "test_hacking_conversion_guards_missing_wrong_or_dead_identity",
        "test_hacking_conversion_uses_stored_bot_id_not_unrelated_snowtank",
        "test_enemy_phase_tail_carries_hacking_conversion_into_next_turn",
    } == tests["rust_solver/src/enemy.rs"]
    assert tests["rust_solver/src/board.rs"] == {
        "test_hacking_bot_uid_replacement_is_not_a_unit_death"
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_player_action_converts_hacking_bot_before_next_actor"
    }
    assert tests["rust_solver/src/serde_bridge.rs"] == {
        "test_hacking_identity_requires_a_complete_valid_mission_scoped_pair"
    }
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_board_to_json_roundtrip_preserves_hacking_identity"
    }
    assert tests["rust_solver/src/replay.rs"] == {
        "replay_solution_preserves_fresh_hacking_bot_identity"
    }
    assert tests["tests/test_mission_hacking_identity.py"] == {
        "test_lua_hacking_identity_exports_only_a_complete_exact_pair",
        "test_modloader_serializes_the_hacking_identity_pair_together",
        "test_reader_drops_partial_or_malformed_hacking_identity",
        "test_reader_keeps_a_valid_hacking_identity_pair",
        "test_python_board_import_and_copy_preserve_only_valid_hacking_identity",
    }
    gaps = " ".join(record["known_gaps"])
    assert "paired HackID and BotID" in gaps
    assert "fail closed" in gaps
    assert "same-enemy-phase cancellation" in gaps
    assert "RemovePawn plus AddPawn reset behavior" in gaps
    assert "protected live achievement session" in gaps


def test_real_mission_satellite_record_pins_launch_and_open_native_timing():
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
        if item["id"] == "mission-satellite-launch"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/grass/mission_satellites.lua",
            "sha256": (
                "ad88320a25a411db2fb7de188b658e27"
                "05b2e6552a737f387d2ab9c982285301"
            ),
            "symbols": [
                "Mission_Satellite",
                "Mission_Satellite:GetSavedCount",
                "Mission_Satellite:GetCompletedObjectives",
                "Mission_Satellite:StartMission",
                "Mission_Satellite:NextTurn",
                "Mission_Satellite:UpdateMission",
                "Mission_Satellite:IsDestroyed",
                "Mission_Satellite:IsGone",
                "Mission_Satellite:UpdateObjectives",
                "SatelliteRocket",
                "Rocket_Launch",
                "Rocket_Launch:GetSkillEffect",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "queued_launch",
        "environment_danger_v2",
    } == implementations["src/bridge/modloader.lua"]
    assert implementations["src/bridge/reader.py"] == {
        "_satellite_launch_danger_tiles",
        "_mark_satellite_launch_danger_flying_immune",
    }
    assert {
        "UnitFlags::SATELLITE_LAUNCH_QUEUED",
        "count_unit_deaths_between",
        "is_mission_satellite_flyaway",
    } == implementations["rust_solver/src/board.rs"]
    assert {
        "apply_env_danger_board",
        "resolve_mission_satellite_flyaways",
        "simulate_enemy_attacks",
    } == implementations["rust_solver/src/enemy.rs"]
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_mission_satellite_vek_attack_before_launch",
        "test_mission_satellite_launch_exhaust_then_flyaway",
        "test_destroyed_queued_satellite_is_not_flyaway",
        "test_satellite_launch_danger_does_not_prevent_queued_enemy_attack",
    }
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_board_to_json_roundtrip_scopes_satellite_launch_identity"
    }
    gaps = " ".join(record["known_gaps"])
    assert "random_removal" in gaps
    assert "DAMAGE_DEATH does not itself prove flying immunity" in gaps
    assert "source-defined Gone success" in gaps
    assert "protected live achievement session" in gaps


def test_real_passive_board_effect_record_pins_exact_variants_and_native_gaps():
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
        if item["id"] == "player-weapon-passive-board-effects"
    )
    assert record["coverage"] == "partial"
    sources = {
        reference["path"]: reference
        for reference in record["sources"]
    }
    passive = sources["scripts/weapons_passive.lua"]
    assert passive["sha256"] == (
        "ba3555413140f1eb33c9cc94e0645d"
        "980950411524d96b96716f82dbb2512a47"
    )
    assert {
        "Passive_Electric:GetSkillEffect",
        "Passive_Leech:GetSkillEffect",
        "Passive_MassRepair:GetSkillEffect",
        "Passive_AutoShields:GetSkillEffect",
        "Passive_Boosters:GetSkillEffect",
        "Passive_Medical:GetSkillEffect",
        "Passive_FriendlyFire:GetSkillEffect",
        "Passive_FastDecay:GetSkillEffect",
        "Passive_ForceAmp:GetSkillEffect",
        "Passive_CritDefense:GetSkillEffect",
    } <= set(passive["symbols"])
    assert sources["scripts/advanced/ae_weapons_base.lua"] == {
        "path": "scripts/advanced/ae_weapons_base.lua",
        "sha256": (
            "4444af60a0b4d38894690425a83a4f61"
            "0cbdc88f20b3fb322db410f257a89742"
        ),
        "symbols": ["Skill_Repair:GetSkillEffect"],
    }
    assert sources["scripts/text_weapons.lua"]["sha256"] == (
        "a432a3dab32f1748657508da314ba8c"
        "11211496502493eebd93acc30b5aa61e1"
    )
    ae_passives = sources["scripts/advanced/ae_weapons.lua"]
    assert ae_passives["sha256"] == (
        "5566b679c696ab489e40a0189d0a63b6"
        "99d01e9657f79a20e6f119239af1680f"
    )
    assert {
        "Passive_HealingSmoke:GetSkillEffect",
        "Passive_FireBoost:GetSkillEffect",
        "Passive_PlayerTurnShield:GetSkillEffect",
        "Passive_VoidShock:GetSkillEffect",
    } <= set(ae_passives["symbols"])
    assert sources["scripts/global.lua"]["sha256"] == (
        "96d82d83a1620061e6fd013aa8462883"
        "e1f3764d03752757ad77fbbbd04bc9b2"
    )
    assert sources["scripts/localization/Weapons.csv"]["sha256"] == (
        "13bfd89f12e5fa0de2e00d6a6b4801d"
        "2db604c0285467dbb311b63ce2b440fd7"
    )

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "storm_generator_damage",
        "vek_hormones_damage",
        "mass_repair",
        "auto_shields",
        "stabilizers",
        "networked_shielding",
        "void_shocker_damage",
        "VOID_SHOCK_IMMUNE",
    } == implementations["rust_solver/src/board.rs"]
    assert {
        "enemy_hit_damage",
        "apply_spawn_blocking",
        "simulate_enemy_attacks",
        "AttackDamageSnapshot",
        "apply_void_shocker_after_attack",
    } == implementations["rust_solver/src/enemy.rs"]
    assert {
        "apply_auto_shield_after_building_damage",
        "simulate_attack_with_target2",
        "networked_shield_blocks",
    } == implementations["rust_solver/src/simulate.rs"]
    assert "SOURCE_KNOWN_WEAPONS" in implementations[
        "scripts/regenerate_known_types.py"
    ]
    assert implementations["src/bridge/modloader.lua"] == {
        "direct_repair_pawn",
        "Mass_Repair",
        "void_shock_immune",
    }
    assert implementations["src/capture/save_parser.py"] == {
        "_MODELED_UPGRADED_WEAPONS",
        "_modeled_upgrade_from_save_mods",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/serde_bridge.rs"] == {
        "test_passive_board_effects_preserve_effective_variants"
    }
    assert {
        "test_mass_repair_applies_actor_repair_to_every_living_player_mech",
        "test_auto_shields_protects_surviving_building_from_next_hit",
        "test_vek_hormones_upgrades_use_exact_damage_magnitudes",
        "test_storm_generator_upgrade_deals_two_damage_in_smoke",
        "test_stabilizers_prevents_only_player_mech_spawn_damage",
    } == tests["rust_solver/src/simulate.rs"]
    assert tests["tests/test_save_parser_weapon_upgrades.py"] == {
        "test_passive_upgrades_overlay_from_powered_save_mods",
        "test_advanced_edition_passives_have_no_modeled_upgrade_variants",
    }
    assert {
        "test_networked_shielding_blocks_player_phase_damage_but_not_enemy_attack",
        "test_networked_shielding_blocks_player_turn_old_earth_mine_damage",
        "test_void_shocker_retaliates_after_empty_attack",
        "test_void_shocker_retaliates_when_attack_only_damages_mountain",
        "test_void_shocker_does_not_retaliate_after_unit_or_building_damage",
        "test_void_shocker_counts_shield_and_frozen_absorption_as_no_damage",
        "test_void_shocker_honors_source_immunity_and_multi_hit_damage",
    } == tests["rust_solver/src/enemy.rs"]
    assert tests["tests/test_modloader_void_shock.py"] == {
        "test_modloader_exports_source_defined_void_shock_immunity"
    }
    assert tests["tests/test_modloader_mass_repair.py"] == {
        "test_direct_repair_helper_clears_every_modeled_repair_status",
        "test_bridge_repair_field_reuses_direct_repair_for_other_mechs",
    }
    gaps = " ".join(record["known_gaps"])
    assert "Psionic Receiver" in gaps
    assert "Ammo Generator" in gaps
    assert "Networked Shielding" in gaps
    assert "Void Shocker" in gaps
    assert "Critical Shields" in gaps
    assert "Networked Armor" in gaps
    assert "Kickoff Boosters" in gaps
    assert "protected live achievement session" in gaps


def test_real_firestorm_generator_record_pins_adjacent_targeting_correction():
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
        if item["id"] == "player-weapon-firestorm-generator"
    )
    assert record["coverage"] == "partial"
    sources = {
        reference["path"]: reference
        for reference in record["sources"]
    }
    firestorm = sources["scripts/advanced/ae_weapons.lua"]
    assert firestorm["sha256"] == (
        "5566b679c696ab489e40a0189d0a63b6"
        "99d01e9657f79a20e6f119239af1680f"
    )
    assert {
        "Science_RainingFire",
        "Science_RainingFire:GetTargetArea",
        "Science_RainingFire:GetSkillEffect",
        "Science_RainingFire_A",
        "Science_RainingFire_B",
        "Science_RainingFire_AB",
    } == set(firestorm["symbols"])
    assert sources["scripts/weapons_base.lua"]["sha256"] == (
        "bdb55457746d08b46e8b62ad7cfc27"
        "f0a08bde9fab7397a4780dfe945b5f8f38"
    )

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::ScienceRainingFire",
        "WId::ScienceRainingFireA",
        "WId::ScienceRainingFireB",
        "WId::ScienceRainingFireAB",
        "is_firestorm_generator",
    } == implementations["rust_solver/src/weapons.rs"]
    assert implementations["rust_solver/src/solver.rs"] == {
        "get_weapon_targets",
        "weapon_action_has_effect",
    }
    assert "sim_firestorm_generator" in implementations[
        "rust_solver/src/simulate.rs"
    ]

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/solver.rs"] == {
        "firestorm_generator_adjacent_new_fire_target_is_actionable"
    }
    assert {
        "test_firestorm_generator_target_enumeration_includes_adjacent_and_respects_maximum",
        "test_firestorm_generator_adjacent_target_ignites_and_pushes_without_transit",
    } <= tests["rust_solver/src/simulate.rs"]
    assert tests["tests/test_weapon_defs.py"] == {
        "test_firestorm_generator_static_defs_use_source_exact_adjacent_minimum"
    }
    gaps = " ".join(record["known_gaps"])
    assert "effect-queue ordering" in gaps
    assert "protected live achievement session" in gaps


def test_real_sand_terrain_hazard_record_pins_conversion_and_native_gaps():
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
        if item["id"] == "environment-sand-terrain-hazards"
    )
    assert record["coverage"] == "partial"
    sources = {
        reference["path"]: reference
        for reference in record["sources"]
    }
    assert sources["scripts/missions/sand/mission_cataclysm.lua"] == {
        "path": "scripts/missions/sand/mission_cataclysm.lua",
        "sha256": (
            "49173aecf489be6ae363a7caeb25c203e"
            "aee3151a15413ee1c699a400f0e5797"
        ),
        "symbols": [
            "Mission_Cataclysm",
            "Env_Cataclysm",
            "Env_Cataclysm:MarkBoard",
            "Env_Cataclysm:Start",
            "Env_Cataclysm:IsEffect",
            "Env_Cataclysm:Plan",
            "Env_Cataclysm:ApplyEffect",
        ],
    }
    assert sources["scripts/missions/sand/mission_lightning.lua"] == {
        "path": "scripts/missions/sand/mission_lightning.lua",
        "sha256": (
            "2849a6fa5fb27a6c30b992642191fb7d"
            "1889eb1570f9336318d58b493587649b"
        ),
        "symbols": [
            "Mission_Lightning",
            "Mission_Lightning:StartMission",
            "Env_Lightning",
            "Env_Lightning:MarkSpace",
            "Env_Lightning:GetAttackEffect",
            "Env_Lightning:SelectSpaces",
        ],
    }
    assert sources["scripts/missions/sand/mission_crack.lua"] == {
        "path": "scripts/missions/sand/mission_crack.lua",
        "sha256": (
            "9823c2a2ea447ede11339fe4274040218"
            "480823a3ab7f3231c3940e4dd21f00f"
        ),
        "symbols": [
            "Mission_Crack",
            "Env_Seismic",
            "Env_Seismic:MarkSpace",
            "Env_Seismic:Start",
            "Env_Seismic:GetAttackEffect",
            "Env_Seismic:SelectSpaces",
        ],
    }
    base = sources["scripts/environments.lua"]
    assert base["sha256"] == (
        "5f8a7d74f537abb33bc88c1f9669f3f"
        "6fabdd5c8c51aad3486d2e965e4fb80ec"
    )
    assert {
        "Environment:IsValidTarget",
        "Environment:GetQuarters",
        "Environment:FindEndpoints",
        "Environment:GetCrossPath",
        "Env_Attack:Start",
        "Env_Attack:IsEffect",
        "Env_Attack:BlockSpawn",
        "Env_Attack:Plan",
        "Env_Attack:ApplyEffect",
        "Env_Attack:MarkBoard",
    } <= set(base["symbols"])

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/enemy.rs"] == {
        "apply_env_danger",
        "apply_env_danger_board",
        "simulate_enemy_attacks",
    }
    assert implementations["rust_solver/src/turn_projection.rs"] == {
        "advance_environment_warning",
        "advance_mission_tides_warning",
        "project_plan_with_spawns",
    }
    assert implementations["rust_solver/src/replay.rs"] == {
        "advance_environment_warning",
        "replay_solution",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert {
        "test_massive_cataclysm_lethal_env_dies",
        "test_massive_seismic_lethal_env_dies",
        "test_cataclysm_lethal_spares_flying",
        "test_lightning_lethal_kills_flying_without_terrain_conversion",
    } <= tests["rust_solver/src/simulate.rs"]
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_cataclysm_projection_converts_to_chasm_and_consumes_current_warning",
        "test_lightning_projection_consumes_warning_without_inventing_next_selection",
    }
    assert tests["rust_solver/src/replay.rs"] == {
        "replay_solution_cataclysm_converts_chasm_and_consumes_final_warning"
    }
    gaps = " ".join(record["known_gaps"])
    assert "Cataclysm Index" in gaps
    assert "Seismic Path" in gaps
    assert "native random_int/random_element/random_removal" in gaps
    assert "cannot construct the next native" in gaps
    assert "spawn-block" in gaps
    assert "protected live achievement session" in gaps


def test_real_acid_tank_record_pins_move_four_fallback_and_native_gaps():
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
        if item["id"] == "mission-acid-tank"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/acid/mission_acidtank.lua",
            "sha256": (
                "10089d2b6592acbf49af3e459712a52cd"
                "b6009e7946f87bbb6c5e8feecc64599"
            ),
            "symbols": [
                "Mission_AcidTank",
                "Mission_AcidTank:StartMission",
                "Mission_AcidTank:GetCompletedObjectives",
                "Mission_AcidTank:GetCompletedStatus",
                "Mission_AcidTank:UpdateObjectives",
                "Mission_AcidTank:UpdateMission",
                "Acid_Tank",
                "Acid_Tank_Attack",
                "Acid_Tank_Attack:GetSkillEffect",
            ],
        }
    ]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/model/pawn_stats.py"] == {
        "PawnStats",
        "Acid_Tank",
    }
    assert implementations["rust_solver/src/serde_bridge.rs"] == {
        "board_from_json",
        "source_default_move",
        "Acid_Tank",
    }
    assert implementations["rust_solver/src/board.rs"] == {
        "unit_counts_for_mission_kill",
        "Mission_AcidTank",
    }
    assert implementations["rust_solver/src/weapons.rs"] == {
        "WId::AcidTankAtk",
        "Acid_Tank_Attack",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/serde_bridge.rs"] == {
        "test_acid_tank_missing_move_uses_source_default_and_live_move_wins"
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_acid_tank_clean_kill_does_not_advance_mission_kill_counter",
        "test_acid_tank_acid_kill_advances_mission_kill_counter",
        "test_acid_tank_cannon_acids_unit_without_ground_pool",
    }
    assert tests["tests/test_weapon_defs.py"] == {
        "test_acid_tank_source_stats_and_cannon_definition"
    }
    assert tests["tests/test_mission_kill_bonus.py"] == {
        "test_acid_tank_defaults_to_fixed_kill_target_for_older_bridge",
        "test_acid_tank_missing_move_uses_source_static_default",
    }
    gaps = " ".join(record["known_gaps"])
    assert "Board:AddPawn placement" in gaps
    assert "EVENT_ACID_DESTROYED production" in gaps
    assert "GetProjectileEnd(PATH_PROJECTILE)" in gaps
    assert "without a weapon list" in gaps
    assert "protected live achievement session" in gaps


def test_real_digger_record_pins_persistent_wall_semantics_and_native_gaps():
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
        if item["id"] == "enemy-weapon-digger"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/weapons_enemy.lua",
            "sha256": (
                "5231dd7a2de730f04fa4116c0d99f07e"
                "cbb3b25059db3593d54d689c37bd4b7b"
            ),
            "symbols": [
                "DiggerAtk1",
                "DiggerAtk1:GetTargetArea",
                "DiggerAtk1:GetSkillEffect",
                "DiggerAtk2",
            ],
        },
        {
            "path": "scripts/pawns.lua",
            "sha256": (
                "e999b8d98526c1e36f4746dd65b9d9e"
                "7ee3ca0b22029ed391d5b71fda49dc239"
            ),
            "symbols": ["Digger1", "Digger2", "Wall"],
        },
    ]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/enemy.rs"] == {
        "digger_wall_tile_eligible",
        "DIGGER_WALL_SOURCE_DIRS",
        "spawn_digger_wall",
        "simulate_enemy_attacks",
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "clear_destroyed_digger_walls"
    }
    assert implementations["rust_solver/src/weapons.rs"] == {
        "WId::DiggerAtk1",
        "WId::DiggerAtk2",
        "enemy_weapon_for_type",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_digger_spawns_four_persistent_neutral_walls_after_own_damage",
        "test_alpha_digger_damages_occupied_tiles_and_walls_only_empty_cards",
        "test_digger_wall_source_predicate_rejects_each_blocker_class",
        "test_digger_wall_blocks_later_enemy_projectile",
        "test_digger_wall_spawn_skips_safely_at_board_capacity",
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_dead_digger_wall_clears_before_later_needle_shot"
    }
    assert tests["tests/test_replay_parity.py"] == {
        "test_replay_solution_digger_enemy_phase_serializes_persistent_walls"
    }

    retained = load_json_object(
        repo_root / "recordings/20260627_104252_085/m18_turn_02_board.json"
    )
    live_walls = [
        unit
        for unit in retained["data"]["bridge_state"]["units"]
        if unit["type"] == "Wall"
    ]
    assert {(unit["x"], unit["y"]) for unit in live_walls} == {
        (6, 4),
        (6, 6),
        (5, 5),
    }
    assert {
        (unit["x"], unit["y"]): unit["uid"] for unit in live_walls
    } == {
        (6, 4): 741,
        (6, 6): 742,
        (5, 5): 743,
    }
    assert all(
        unit["team"] == 2
        and unit["hp"] == 1
        and unit["max_hp"] == 1
        and unit["move"] == 0
        and unit["base_move"] == 0
        and unit["pushable"]
        for unit in live_walls
    )

    gaps = " ".join(record["known_gaps"])
    assert "scheduler's internal insertion order" in gaps
    assert "Board:IsBlocked(PATH_PROJECTILE)" in gaps
    assert "Chasm, Lava, Fire, Ice" in gaps
    assert "native pawn-capacity edge" in gaps
    assert "protected achievement session" in gaps


def test_real_shaman_totem_record_pins_spawn_chain_and_native_gaps():
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
        if item["id"] == "enemy-weapon-shaman-totem"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/ae_weapons_enemy.lua",
            "sha256": (
                "db757b1afa790fe3f7576930abd0c7e4c"
                "f5d8b9dc7308aa15ce9a9736f224d13"
            ),
            "symbols": [
                "ShamanAtk1",
                "ShamanAtk1:GetTargetScore",
                "ShamanAtk1:GetSkillEffect",
                "ShamanAtk2",
                "TotemAtk1",
                "TotemAtk1:GetSkillEffect",
                "TotemAtk2",
            ],
        },
        {
            "path": "scripts/advanced/ae_pawns.lua",
            "sha256": (
                "e87efe90c0342f26969c14159e6b6c93"
                "766aeedcbc3319fb0f418048d129e9f4"
            ),
            "symbols": ["Shaman1", "Shaman2", "Totem1", "Totem2"],
        },
    ]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/enemy.rs"] == {
        "spawn_shaman_totem",
        "simulate_enemy_attacks",
    }
    assert implementations["rust_solver/src/weapons.rs"] == {
        "WId::ShamanAtk1",
        "WId::ShamanAtk2",
        "WId::TotemAtk1",
        "WId::TotemAtk2",
        "enemy_weapon_for_type",
    }
    assert implementations["rust_solver/src/serde_bridge.rs"] == {
        "known_void_shock_immune_type",
        "board_from_json",
    }
    assert implementations["rust_solver/src/turn_projection.rs"] == {
        "projected_enemy_uses_special_targeting"
    }
    assert implementations["src/model/pawn_stats.py"] == {
        "PawnStats",
        "Shaman1",
        "Shaman2",
        "Totem1",
        "Totem2",
    }
    assert implementations["src/model/weapons.py"] == {
        "ShamanAtk1",
        "ShamanAtk2",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/weapons.rs"] == {
        "test_shaman_spawn_weapon_defs_and_mappings"
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_shaman_spawns_exact_totem_without_same_phase_attack",
        "test_shaman_totem_spawn_fails_closed_on_occupied_or_blocked_target",
        "test_spawned_shaman_totem_can_fire_and_self_destruct_next_phase",
        "test_totem_projectile_retraces_into_new_blocker_and_bumps_building",
        "test_totem_projectile_retraces_past_vacated_target_to_building",
    }
    assert tests["rust_solver/src/serde_bridge.rs"] == {
        "test_shaman_void_shock_immunity_inferred_but_explicit_live_value_wins"
    }
    assert tests["tests/test_weapon_defs.py"] == {
        "test_shaman_and_totem_source_stats_and_weapon_definitions"
    }
    assert tests["tests/test_replay_parity.py"] == {
        "test_replay_solution_shaman_enemy_phase_serializes_new_totem"
    }

    gaps = " ".join(record["known_gaps"])
    assert "Board:GetDeployLocScore" in gaps
    assert "board-edge filtering" in gaps
    assert "SkillEffect scheduler boundary" in gaps
    assert "Board:GetProjectileEnd" in gaps
    assert "ShamanBoss/ShamanAtkB" in gaps
    assert "protected achievement session" in gaps


def test_real_mission_piston_record_pins_native_order_and_remaining_gaps():
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
        if item["id"] == "mission-piston-trash-compactors"
    )
    assert record["coverage"] == "partial"
    source_by_path = {source["path"]: source for source in record["sources"]}
    assert len(source_by_path) == 5
    assert source_by_path["scripts/missions/acid/mission_piston.lua"] == {
        "path": "scripts/missions/acid/mission_piston.lua",
        "sha256": (
            "1f426bad3b4149f0088831680264f716a"
            "3f9cc6acebf828306946c55990d51ad"
        ),
        "symbols": [
            "Mission_Piston",
            "Mission_Piston:StartMission",
            "Pawn_Piston_U",
            "Pawn_Piston_R",
            "Pawn_Piston_D",
            "Pawn_Piston_L",
            "Piston_U_Atk",
            "Piston_U_Atk:GetTargetScore",
            "Piston_U_Atk:GetSkillEffect",
            "Piston_R_Atk",
            "Piston_D_Atk",
            "Piston_L_Atk",
        ],
    }
    assert source_by_path["scripts/missions/missions.lua"]["symbols"] == [
        "Mission",
        "Mission_Auto",
        "Mission:GetMapTag",
        "Mission:BaseStart",
        "Mission:BaseUpdate",
    ]
    assert source_by_path["scripts/global.lua"]["symbols"] == [
        "random_element",
        "random_removal",
    ]
    assert source_by_path["scripts/events.lua"]["symbols"] == [
        "extract_table",
    ]
    assert source_by_path["scripts/environments.lua"]["symbols"] == [
        "Environment:Start",
        "Environment:IsEffect",
        "Environment:ApplyEffect",
        "Env_Null",
    ]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/bridge/modloader.lua"] == {"mission_pistons"}
    assert implementations["src/bridge/reader.py"] == {
        "_normalize_mission_pistons"
    }
    assert implementations["src/loop/commands.py"] == {
        "_mission_piston_forecast_block",
        "_lookahead_forecast_gaps",
        "cmd_solve",
    }
    assert implementations["rust_solver/src/serde_bridge.rs"] == {
        "JsonMissionPistons",
        "JsonPistonAction",
        "mission_piston_front",
        "board_from_json",
    }
    assert implementations["src/observatory/piston_scheduler_boundary.py"] == {
        "build_piston_scheduler_boundary_map",
        "validate_piston_scheduler_boundary_map",
        "validate_piston_scheduler_boundary_map_binding",
    }
    assert implementations["src/observatory/piston_setup_boundary.py"] == {
        "build_piston_setup_boundary_map",
        "validate_piston_setup_boundary_map",
        "validate_piston_setup_boundary_map_binding",
        "replay_piston_start_mission",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_piston_setup_boundary.json"
    ] == {
        "piston_map_pool_and_zone_order",
        "rejected_attempt_draw_count",
        "hidden_constructor_draw",
        "invalid_fallback_excluded",
        "parameterized_replay_complete",
        "solver_boundary_unchanged",
    }
    assert implementations["scripts/itb_observatory_piston_scheduler.py"] == {
        "main"
    }
    assert implementations["scripts/itb_observatory_piston_setup.py"] == {
        "main"
    }
    assert implementations["src/observatory/death_event_credit_boundary.py"] == {
        "POST_PUBLICATION_PROJECT_BRIDGE_OVERLAYS"
    }
    assert implementations[
        "src/observatory/final_cave_block_spawn_lifetime.py"
    ] == {"POST_PUBLICATION_PROJECT_BRIDGE_OVERLAYS"}
    assert implementations["rust_solver/src/enemy.rs"] == {
        "QueuedPawnAction",
        "simulate_mission_piston_action",
        "simulate_enemy_attacks",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/serde_bridge.rs"] == {
        "test_mission_pistons_require_complete_exact_neutral_corroboration"
    }
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_board_to_json_roundtrip_preserves_known_piston_state"
    }
    assert {
        "test_lua_helper_preserves_native_unit_order_and_complete_empty_state",
        "test_reader_drops_partial_stale_or_uncorroborated_payloads",
        "test_python_board_preserves_state_and_forces_exact_neutral_static_traits",
        "test_hard_forecast_gate_requires_exact_payload_then_accepts_living_and_corpses",
        "test_lookahead_only_surfaces_missing_ordered_piston_state",
    } == tests["tests/test_mission_piston_payload.py"]
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_mission_piston_pushes_front_occupant",
        "test_mission_piston_interleaves_after_earlier_vek_in_board_order",
        "test_dead_mission_piston_keeps_corpse_but_cancels_queued_push",
    }
    assert tests["tests/test_observatory_piston_scheduler_boundary.py"] == {
        "test_committed_map_closes_stock_piston_order_and_cancellation_gate",
        "test_binding_rejects_order_cancellation_environment_or_version_drift",
        "test_bridge_rust_gate_version_and_archive_conform_to_native_map",
        "test_v408_bridge_is_hash_pinned_without_rewriting_predecessor_artifacts",
        "test_exact_local_executable_sources_and_dependencies_reproduce_map_when_available",
    }
    assert tests["tests/test_observatory_piston_setup_boundary.py"] == {
        "test_committed_map_closes_parameterized_piston_setup_rng_boundary",
        "test_exact_map_pool_zone_order_and_initial_rejections_are_pinned",
        "test_replay_pins_hidden_constructor_draw_and_dynamic_zone_removal",
        "test_replay_rejected_candidates_consume_only_one_draw_each",
        "test_replay_canonicalizes_only_the_permanently_hidden_state_bit",
        "test_binding_rejects_draw_zone_guard_or_solver_scope_drift",
        "test_artifact_file_is_immutable_and_hash_pinned",
        "test_exact_local_executable_sources_maps_and_dependencies_reproduce_when_available",
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "valid, non-edge, unoccupied" in facts
    assert "zero damage" in facts
    assert "native Board pawn-vector order rather than UID order" in facts
    assert "team-6 or Neutral pawns" in facts
    assert "inherits no-op Env_Null" in facts
    assert "cannot dispatch its old push" in facts
    assert "Simulator v408" in facts
    assert "blocks only incomplete or malformed ordered payloads" in facts
    assert "hash-pinned post-publication bridge-only overlay" in facts
    assert "304 analysis-relevant non-overlay scripts entries" in facts
    assert "acid0, acid1, acid10, acid11, acid15, acid3, and acid4" in facts
    assert "exactly three draws" in facts
    assert "common Pawn constructor" in facts
    assert "build-keyed offline replay" in facts
    gaps = " ".join(record["known_gaps"])
    assert "incoming observable CRT state" in gaps
    assert "used-map registry" in gaps
    assert "settled live bridge board remains authoritative" in gaps
    assert "macOS, other depots, and mods" in gaps
    assert "Presentation-only hide/animation timing" in gaps

    boundary = json.loads((
        repo_root
        / "data"
        / "observatory"
        / "native"
        / "windows_build_13725832_31fe35265598_"
        "piston_scheduler_boundary.json"
    ).read_text(encoding="utf-8"))
    assert boundary["summary"]["mission_piston_scheduler_gate_closed"] is True
    assert boundary["summary"]["simulator_version"] == 408

    setup_boundary = json.loads((
        repo_root
        / "data"
        / "observatory"
        / "native"
        / "windows_build_13725832_31fe35265598_"
        "piston_setup_boundary.json"
    ).read_text(encoding="utf-8"))
    assert setup_boundary["summary"]["parameterized_replay_complete"] is True
    assert setup_boundary["summary"]["constructor_draw_proven"] is True
    assert setup_boundary["summary"]["concrete_forecast_proven"] is False
    assert setup_boundary["summary"]["simulator_version"] == 408


def test_real_mission_freeze_buildings_record_pins_exact_predicate_and_rubble_gap():
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
        if item["id"] == "mission-freeze-buildings"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/snow/mission_freezebldg.lua",
        "sha256": (
            "fe56574f05b58bdbfae1b9f977c0efd9"
            "116570d994d5af9a60b98574a6d547a4"
        ),
        "symbols": [
            "Mission_FreezeBldg",
            "Mission_FreezeBldg:StartMission",
            "Mission_FreezeBldg:GetCompletedObjectives",
            "Mission_FreezeBldg:CountThawed",
            "Mission_FreezeBldg:UpdateObjectives",
        ],
    }]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/bridge/reader.py"] == {
        "_read_freeze_building_objective_tiles_from_save",
        "freeze_building_target",
        "freeze_building_tiles",
    }
    assert implementations["rust_solver/src/evaluate.rs"] == {
        "evaluate", "Mission_FreezeBldg", "freeze_building_target",
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "thaw_frozen_building", "apply_damage_inner", "Mission_FreezeBldg",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/evaluate.rs"] == {
        "test_mission_freeze_building_scores_thawed_objective_buildings"
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_weapon_damage_thaws_frozen_building_without_grid_loss",
        "test_aerial_bombs_frozen_objective_building_damage_defers_grid",
    }
    assert tests["tests/test_plan_safety.py"] == {
        "test_freeze_building_objective_blocks_final_under_target",
        "test_freeze_building_objective_blocks_destroyed_target_before_final",
        "test_freeze_building_objective_allows_incomplete_nonfinal_progress",
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "extract_table(Board:GetBuildings())" in facts
    assert "Board:IsFrozen(v) is false" in facts
    assert "does not inspect terrain, building HP, or building survival" in facts
    assert "surviving building" in facts
    gaps = " ".join(record["known_gaps"])
    assert "destroyed or replaced by rubble" in gaps
    assert "alive-and-thawed predicate is deliberately conservative" in gaps
    assert "visible objective counter and postgame result" in gaps
    assert "protected achievement session" in gaps


def test_real_crab_scarab_artillery_record_pins_exact_range_and_footprint():
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
        if item["id"] == "enemy-weapon-crab-scarab-artillery"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/weapons_enemy.lua",
            "sha256": (
                "5231dd7a2de730f04fa4116c0d99f07e"
                "cbb3b25059db3593d54d689c37bd4b7b"
            ),
            "symbols": [
                "CrabAtk1",
                "CrabAtk1:GetSkillEffect",
                "CrabAtk2",
                "ScarabAtk1",
                "ScarabAtk2",
            ],
        },
        {
            "path": "scripts/weapons_base.lua",
            "sha256": (
                "bdb55457746d08b46e8b62ad7cfc27f0"
                "a08bde9fab7397a4780dfe945b5f8f38"
            ),
            "symbols": ["LineArtillery", "LineArtillery:GetTargetArea"],
        },
        {
            "path": "scripts/pawns.lua",
            "sha256": (
                "e999b8d98526c1e36f4746dd65b9d9e7"
                "ee3ca0b22029ed391d5b71fda49dc239"
            ),
            "symbols": ["Scarab1", "Scarab2", "Crab1", "Crab2"],
        },
    ]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/model/weapons.py"] == {
        "ScarabAtk1", "ScarabAtk2", "CrabAtk1", "CrabAtk2",
    }
    assert implementations["rust_solver/src/enemy.rs"] == {
        "simulate_enemy_attacks"
    }
    assert implementations["rust_solver/src/solver.rs"] == {"get_weapon_targets"}
    assert implementations["rust_solver/src/turn_projection.rs"] == {
        "projected_enemy_attack_reach",
        "projected_enemy_reach",
        "projected_requeue_click",
        "requeue_enemies_heuristic",
        "building_retarget_candidates",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/weapons.rs"] == {
        "test_crab_scarab_line_artillery_defs_have_exact_two_to_five_range"
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_crab_scarab_queued_artillery_respects_exact_range",
        "test_crab_range_five_click_hits_forward_sixth_tile",
    }
    assert tests["rust_solver/src/solver.rs"] == {
        "crab_scarab_line_artillery_targeting_stops_at_exact_range_five"
    }
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_webbed_scarab_reach_stops_at_lua_maximum",
        "test_webbed_crab_range_six_threat_queues_range_five_click",
        "test_mobile_crab_scarab_projection_never_queues_illegal_click",
        "test_crab_range_six_building_retarget_uses_legal_click",
        "test_requeued_webbed_crab_damages_sixth_tile_on_second_projection",
    }
    assert tests["tests/test_weapon_defs.py"] == {
        "test_crab_and_scarab_weapon_defs_match_inherited_lua_artillery_range"
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "distances two through ArtillerySize five" in facts
    assert "one tile forward from the selected tile" in facts
    assert "range-five target can damage tile six" in facts
    gaps = " ".join(record["known_gaps"])
    assert "target scoring" in gaps
    assert "RNG state" in gaps
    assert "queued-effect scheduler boundaries" in gaps
    assert "pressure may remain scalar without a concrete queue" in gaps
    assert "terrain, status, objective, corpse" in gaps


def test_real_mission_acid_vats_record_pins_objective_and_death_terrain():
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
        item for item in provenance["records"] if item["id"] == "mission-acid-vats"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/acid/mission_barrels.lua",
        "sha256": (
            "3101ea805315e49e6a098c240f242bea"
            "28e39466dd9c41deb253468d93f7fc48"
        ),
        "symbols": [
            "Mission_Barrels",
            "Mission_Barrels:IsEndBlocked",
            "Mission_Barrels:CountBarrels",
            "Mission_Barrels:StartMission",
            "Mission_Barrels:GetCompletedStatus",
            "Mission_Barrels:GetCompletedObjectives",
            "Mission_Barrels:UpdateObjectives",
            "Mission_Barrels:UpdateMission",
            "AcidVat",
            "AcidVat:GetDeathEffect",
            "Acid_Death_Tooltip",
            "Acid_Death_Tooltip:GetSkillEffect",
        ],
    }]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/mission_unit_objectives.json"] == {
        "Mission_Barrels", "AcidVat",
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "apply_acid_vat_death_terrain",
        "apply_damage_inner",
        "sim_pierce_projectile",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_mission_barrels_acid_vat_death_creates_acid_water",
        "test_brute_pierce_shot_barrels_acid_vat_death_terrain_after_first_push",
    }
    assert tests["tests/test_board_summary_safety.py"] == {
        "test_summary_tracks_acid_vats_destroy_objective_from_metadata"
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "two neutral, two-HP AcidVat" in facts
    assert "one-of-two partial objective at one" in facts
    assert "Water and applies ACID" in facts
    assert "AP Cannon regression ordering" in facts
    gaps = " ".join(record["known_gaps"])
    assert "random_removal" in gaps
    assert "Board:ClearSpace" in gaps
    assert "Board:AddPawn" in gaps
    assert "objective UI" in gaps
    assert "SkillEffect/death scheduler ordering" in gaps
    assert "protected achievement session" in gaps


def test_real_hornet_record_pins_line_attacks_and_open_native_gaps():
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
        item for item in provenance["records"] if item["id"] == "enemy-weapon-hornet"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/weapons_enemy.lua",
            "sha256": (
                "5231dd7a2de730f04fa4116c0d99f07e"
                "cbb3b25059db3593d54d689c37bd4b7b"
            ),
            "symbols": [
                "HornetAtk1",
                "HornetAtk1:GetSkillEffect",
                "HornetAtk2",
            ],
        },
        {
            "path": "scripts/pawns.lua",
            "sha256": (
                "e999b8d98526c1e36f4746dd65b9d9e7"
                "ee3ca0b22029ed391d5b71fda49dc239"
            ),
            "symbols": ["Hornet1", "Hornet2"],
        },
        {
            "path": "scripts/missions/bosses/hornet.lua",
            "sha256": (
                "e41ca873c3e600e4b422291eca2a8c733"
                "f3193267d351d58c9fd25ffc213185f"
            ),
            "symbols": [
                "HornetBoss",
                "HornetAtkB",
                "HornetAtkB:GetSkillEffect",
            ],
        },
        {
            "path": "scripts/global.lua",
            "sha256": (
                "96d82d83a1620061e6fd013aa8462883e"
                "1f3764d03752757ad77fbbbd04bc9b2"
            ),
            "symbols": ["Skill:GetTargetArea"],
        },
    ]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::HornetAtk1",
        "WId::HornetAtk2",
        "WId::HornetAtkB",
        "enemy_weapon_for_type",
    } <= implementations["rust_solver/src/weapons.rs"]
    assert implementations["rust_solver/src/enemy.rs"] == {
        "simulate_enemy_attacks"
    }
    assert implementations["src/model/weapons.py"] == {
        "HornetAtk1", "HornetAtk2", "HornetAtkB"
    }
    assert implementations["src/model/pawn_stats.py"] == {"HornetBoss"}
    assert implementations["src/model/board.py"] == {
        "Unit", "Board", "from_bridge_data"
    }
    assert implementations["rust_solver/src/turn_projection.rs"] == {
        "projected_enemy_attack_reach", "projected_requeue_click"
    }
    assert implementations["src/solver/threat_audit.py"] == {
        "_original_queued_offset",
        "_queued_hornet_line_targets",
        "_queued_hornet_line_building_targets",
        "capture_building_threats",
        "_coverage_reason",
        "_will_die_to_prior_melee_before_attack",
        "_will_die_to_prior_artillery_before_attack",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/weapons.rs"] == {
        "test_alpha_hornet_has_aoe_behind"
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_alpha_hornet_weapon_id_hits_both_tiles_without_bridge_flag",
        "test_pushed_alpha_hornet_reanchors_line_from_current_position",
        "test_pushed_hornet_boss_reanchors_full_offset_line",
    }
    assert tests["tests/test_final_cave_enemy_stats.py"] == {
        "test_hornet_boss_has_canonical_stats"
    }
    assert tests["rust_solver/src/turn_projection.rs"] == {
        "test_alpha_hornet_projected_requeue_uses_adjacent_cardinal_click",
        "test_hornet_boss_projected_requeue_reaches_distant_cardinal_building",
    }
    assert tests["tests/test_threat_audit.py"] == {
        "test_capture_alpha_hornet_line_threat_uses_weapon_definition_not_bridge_flag",
        "test_capture_hornet_leader_three_tile_line_threat",
        "test_capture_pushed_alpha_hornet_uses_original_raw_queue_direction",
        "test_capture_pushed_hornet_leader_preserves_original_target_offset",
        "test_bridge_retains_raw_and_normalized_queued_hornet_target_fields",
        "test_threat_audit_alpha_hornet_line_kills_later_attacker_without_bridge_flag",
        "test_threat_audit_hornet_leader_line_kills_later_attacker_before_attack",
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "one damage on the adjacent selected tile" in facts
    assert "one tile farther in the same direction" in facts
    assert "three consecutive tiles" in facts
    assert "PathSize INT_MAX" in facts
    assert "Raw piQueuedShot/piOrigin" in facts
    assert "rechecks every resulting line tile" in facts
    gaps = " ".join(record["known_gaps"])
    assert "Hornet_Acid and HornetAtk_Acid" in gaps
    assert "target scoring" in gaps
    assert "obstacles" in gaps
    assert "queued-effect scheduler boundaries" in gaps
    assert "protected achievement session" in gaps


def test_real_cluster_artillery_record_pins_variants_and_inherited_helpers():
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
        if item["id"] == "player-weapon-cluster-artillery"
    )
    assert record["coverage"] == "partial"
    sources = {reference["path"]: reference for reference in record["sources"]}
    assert sources["scripts/weapons_ranged.lua"] == {
        "path": "scripts/weapons_ranged.lua",
        "sha256": (
            "41417c5d5690bc2f51938480eb2c538f"
            "7b260e8233c4ad9209b35080ece90747"
        ),
        "symbols": [
            "Ranged_Defensestrike",
            "Ranged_Defensestrike_A",
            "Ranged_Defensestrike_B",
            "Ranged_Defensestrike_AB",
        ],
    }
    assert sources["scripts/weapons_base.lua"] == {
        "path": "scripts/weapons_base.lua",
        "sha256": (
            "bdb55457746d08b46e8b62ad7cfc27f0"
            "a08bde9fab7397a4780dfe945b5f8f38"
        ),
        "symbols": [
            "LineArtillery",
            "LineArtillery:GetTargetArea",
            "ArtilleryDefault",
            "ArtilleryDefault:GetSkillEffect",
        ],
    }
    assert sources["scripts/pawns.lua"] == {
        "path": "scripts/pawns.lua",
        "sha256": (
            "e999b8d98526c1e36f4746dd65b9d9e7"
            "ee3ca0b22029ed391d5b71fda49dc239"
        ),
        "symbols": ["DStrikeMech"],
    }

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert {
        "WId::RangedDefensestrike",
        "WId::RangedDefensestrikeA",
        "WId::RangedDefensestrikeB",
        "WId::RangedDefensestrikeAB",
        "is_cluster_artillery",
    } <= implementations["rust_solver/src/weapons.rs"]
    assert implementations["rust_solver/src/solver.rs"] == {"get_weapon_targets"}
    assert implementations["src/model/weapons.py"] == {
        "Ranged_Defensestrike",
        "Ranged_Defensestrike_A",
        "Ranged_Defensestrike_B",
        "Ranged_Defensestrike_AB",
    }
    assert implementations["src/capture/save_parser.py"] == {
        "_MODELED_UPGRADED_WEAPONS"
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/weapons.rs"] == {
        "test_cluster_artillery_upgrade_defs_and_mappings"
    }
    assert tests["rust_solver/src/solver.rs"] == {
        "cluster_artillery_variants_target_intact_building_centers"
    }
    assert {
        "test_cluster_artillery_variants_dispatch_outer_damage_and_building_immunity",
        "test_cluster_artillery_building_immunity_does_not_block_collision_damage",
    } <= tests["rust_solver/src/simulate.rs"]
    assert tests["tests/test_save_parser_weapon_upgrades.py"] == {
        "test_cluster_artillery_upgrades_overlay_from_save_mods"
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "four cardinal tiles" in facts
    assert "selected center remains harmless" in facts
    assert "intact Building as the selected protected center" in facts
    assert "physical collision damage" in facts
    gaps = " ".join(record["known_gaps"])
    assert "LineArtillery candidate enumeration" in gaps
    assert "ArtilleryDefault" in gaps
    assert "Grid Defense" in gaps
    assert "protected achievement session" in gaps


def test_real_mission_acid_storm_record_pins_generator_lifecycle():
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
        if item["id"] == "mission-acid-storm-lifecycle"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/missions/acid/mission_acidstorm.lua",
            "sha256": (
                "71d3d80d27ddeee0f05b6f237eaba35e"
                "98b5e585d98e67331b0b56a62731f6b8"
            ),
            "symbols": [
                "Mission_AcidStorm",
                "Env_AcidStorm",
                "Mission_AcidStorm:GetCompletedObjectives",
                "Mission_AcidStorm:NextTurn",
                "Mission_AcidStorm:UpdateObjectives",
                "Mission_AcidStorm:StartMission",
                "Mission_AcidStorm:UpdateMission",
                "Storm_Generator",
                "Storm_Generator_Tooltip",
                "Storm_Generator_Tooltip:GetSkillEffect",
            ],
        }
    ]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/mission_unit_objectives.json"] == {
        "Mission_AcidStorm",
        "Storm_Generator",
    }
    assert implementations["rust_solver/src/serde_bridge.rs"] == {
        "known_minor_type",
        "Storm_Generator",
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "acid_storm_active",
        "apply_active_acid_storm",
        "drain_pending_spider_eggs",
        "simulate_action_with_target2",
    }
    assert implementations["rust_solver/src/enemy.rs"] == {
        "spawn_enemy",
        "simulate_enemy_attacks",
    }
    assert implementations["rust_solver/src/replay.rs"] == {
        "apply_active_acid_storm",
        "replay_solution",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_acid_storm_completed_player_action_acidifies_fresh_walking_bomb"
    }
    assert tests["rust_solver/src/enemy.rs"] == {
        "test_acid_storm_enemy_phase_refreshes_fresh_enemy_spawns_and_keeps_prior_acid_after_death"
    }
    assert tests["rust_solver/src/replay.rs"] == {
        "replay_solution_acid_storm_refreshes_fresh_player_spawn_before_snapshot"
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "every remaining building" in facts
    assert "every living pawn" in facts
    assert "does not remove existing ACID" in facts
    assert "completed player-action and enemy-phase boundaries" in facts
    gaps = " ".join(record["known_gaps"])
    assert "GetReplaceableBuildings" in gaps
    assert "native Mission:BaseUpdate scheduling" in gaps
    assert "SetWeather" in gaps
    assert "protected achievement session" in gaps


def test_real_mission_disposal_launcher_record_pins_cross_and_end_block_gap():
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
        if item["id"] == "mission-disposal-launcher"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/acid/mission_disposal.lua",
            "sha256": (
                "2929df660b2289048aaebc96923cafb61"
                "58834d01a08116399e514642c5eb908"
            ),
            "symbols": [
                "Mission_Disposal",
                "Mission_Disposal:CountMountains",
                "Mission_Disposal:IsEndBlocked",
                "Mission_Disposal:GetCompletedObjectives",
                "Mission_Disposal:UpdateObjectives",
                "Mission_Disposal:GetCompletedStatus",
                "Mission_Disposal:StartMission",
                "Disposal_Unit",
                "Disposal_Attack",
                "Disposal_Attack:GetSkillEffect",
            ],
        },
        {
            "path": "scripts/weapons_base.lua",
            "sha256": (
                "bdb55457746d08b46e8b62ad7cfc27f"
                "0a08bde9fab7397a4780dfe945b5f8f38"
            ),
            "symbols": ["Grenade_Base", "Grenade_Base:GetTargetArea"],
        },
    ]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/mission_unit_objectives.json"] == {
        "Mission_Disposal",
        "Disposal_Unit",
    }
    assert implementations["rust_solver/src/weapons.rs"] == {
        "DisposalAttack",
        "disposal_cross_tiles",
        "wid_from_str",
        "wid_to_str",
        "weapon_name",
    }
    assert implementations["rust_solver/src/solver.rs"] == {
        "get_weapon_targets",
        "weapon_action_has_effect",
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "apply_disposal_tile",
        "sim_disposal",
        "simulate_weapon",
    }
    assert implementations["rust_solver/src/evaluate.rs"] == {
        "friendly_npc_killed",
        "mission_protect_unit_dead_penalty",
    }

    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["rust_solver/src/solver.rs"] == {
        "disposal_target_area_includes_every_board_tile_and_launcher_self"
    }
    assert tests["rust_solver/src/simulate.rs"] == {
        "test_disposal_attack_kills_acid_cross_and_clears_mountains",
        "test_disposal_attack_can_self_target_without_counting_launcher_as_mech",
    }
    assert tests["rust_solver/src/evaluate.rs"] == {
        "test_disposal_launcher_death_scores_protected_npc_loss"
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "every board coordinate including the firing tile" in facts
    assert "DAMAGE_DEATH and ACID" in facts
    assert "dead protected friendly NPC" in facts
    gaps = " ".join(record["known_gaps"])
    assert "IsEndBlocked" in gaps
    assert "at least one Mountain remains" in gaps
    assert "separate mission-end, safety, and UI semantics tranche" in gaps
    assert "no fresh controlled UI capture" in gaps


def test_real_mission_terraformer_record_pins_zone_and_mountain_clear():
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
        if item["id"] == "mission-terraformer-sweep"
    )
    assert record["coverage"] == "partial"
    sources = {source["path"]: source for source in record["sources"]}
    assert sources["scripts/missions/sand/mission_terraform.lua"] == {
        "path": "scripts/missions/sand/mission_terraform.lua",
        "sha256": (
            "52d3ea23e01938a47c06fad04be6fa23"
            "d5baa3516738c39abc9224dc2a7d49a2"
        ),
        "symbols": [
            "Mission_Terraform",
            "Mission_Terraform:IsEndBlocked",
            "Mission_Terraform:NextTurn",
            "Mission_Terraform:GetCompletedObjectives",
            "Mission_Terraform:UpdateObjectives",
            "Mission_Terraform:GetCompletedStatus",
            "Mission_Terraform:StartMission",
            "Mission_Terraform:UpdateMission",
            "Terraformer",
            "Terraformer_Attack",
            "Terraformer_Attack:GetSkillEffect",
        ],
    }
    assert sources["scripts/global.lua"]["sha256"] == (
        "96d82d83a1620061e6fd013aa8462883"
        "e1f3764d03752757ad77fbbbd04bc9b2"
    )
    assert sources["scripts/global.lua"]["symbols"] == [
        "Skill",
        "Skill:GetTargetArea",
    ]
    inventory_maps = {
        item["path"]: item["sha256"]
        for item in inventory["content"]["maps"]["files"]
    }
    assert {
        path: inventory_maps[path]
        for path in (
            "maps/terraformer1.map",
            "maps/terraformer2.map",
            "maps/terraformer3.map",
        )
    } == {
        "maps/terraformer1.map": (
            "6e265a2e0a16a17fff622104f3dcb081"
            "8265bb70441a0dcb9ca6e5e4a8798b80"
        ),
        "maps/terraformer2.map": (
            "44e3abd2a6f5afe07420aba65ef60dafa"
            "ee8efdd886019e5ddcdd9cda4c0ffa8"
        ),
        "maps/terraformer3.map": (
            "87dff7034fc24c9efcc86e0ce927ea1c"
            "31546d18680905ae0a013538a270eb3b"
        ),
    }
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/bridge/modloader.lua"] == {
        "dump_state",
        "mission_terraform_grass_tiles",
    }
    assert implementations["src/bridge/reader.py"] == {
        "_normalize_live_terraform_grass",
        "_read_terraform_grass_tiles_from_save",
        "read_bridge_state",
    }
    assert implementations["rust_solver/src/weapons.rs"] == {
        "TerraformerAttack",
        "terraformer_sweep_tiles",
        "weapon_name",
        "wid_from_str",
        "wid_to_str",
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "apply_terraformer_tile",
        "sim_terraformer",
        "simulate_weapon",
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert 'only Board:GetZone("grass")' in facts
    assert "unconditional Board:SetCustomTile" in facts
    assert "has 17 custom and 16 zone points" in facts
    assert "has 17 custom and 13 zone points" in facts
    assert "6e265a2e0a16a17fff622104f3dcb0818265bb70441a0dcb9ca6e5e4a8798b80" in facts
    assert "44e3abd2a6f5afe07420aba65ef60dafaee8efdd886019e5ddcdd9cda4c0ffa8" in facts
    assert "87dff7034fc24c9efcc86e0ce927ea1c31546d18680905ae0a013538a270eb3b" in facts
    assert "including Mountains while retaining Mountain terrain" in facts
    gaps = " ".join(record["known_gaps"])
    assert "not been installed or live-captured" in gaps
    assert "overcounts the documented decorative points" in gaps
    assert "IsEndBlocked" in gaps
    assert "Frozen" in gaps
    assert "v198" in gaps


def test_real_mission_repair_record_pins_platform_objective_and_native_events():
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
        if item["id"] == "mission-repair-platform-objective"
    )
    assert record["coverage"] == "partial"
    sources = {source["path"]: source for source in record["sources"]}
    assert sources["scripts/advanced/missions/grass/mission_repair.lua"] == {
        "path": "scripts/advanced/missions/grass/mission_repair.lua",
        "sha256": (
            "37a3d07aba486bad553a6bf568ad8596e"
            "d7d08914625720a41899b6e228d0889"
        ),
        "symbols": [
            "Mission_Repair",
            "Env_RepairMission",
            "Mission_Repair:NextTurn",
            "Mission_Repair:StartDeployment",
            "Mission_Repair:UpdateMission",
            "Mission_Repair:GetCompletedObjectives",
            "Mission_Repair:UpdateObjectives",
        ],
    }
    assert sources["scripts/missions/mission_minebase.lua"] == {
        "path": "scripts/missions/mission_minebase.lua",
        "sha256": (
            "1ac2efa710e4a7469b116ed65a66a4fc"
            "53b70f6b5e643c62f2a4c21b6705fb4e"
        ),
        "symbols": ["Mission_MineBase", "Mission_MineBase:StartMission"],
    }
    assert sources["scripts/items.lua"] == {
        "path": "scripts/items.lua",
        "sha256": (
            "9d23a6749ba2222a5bcf7e4ff1c4a300"
            "eafcb7895bd19429e0877ab930370aea"
        ),
        "symbols": ["Item_Repair_Mine"],
    }

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "apply_landing_effects",
        "apply_repair_platform",
        "simulate_move",
    }
    assert implementations["src/loop/commands.py"] == {
        "_is_transient_delayed_repair_platform_diff",
        "recommend_deploy_tiles",
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "sets every TEAM_MECH pawn to one HP" in facts
    assert "subtracting EVENT_REPAIR_UNDO" in facts
    assert "up to eight random inner-board" in facts
    assert "SpaceDamage(-10)" in facts
    assert "player mechs" in facts
    gaps = " ".join(record["known_gaps"])
    assert "native engine events" in gaps
    assert "interactive move-undo path" in gaps
    assert "not reclassified as source-proven" in gaps
    assert "placement randomness" in gaps


def test_real_mission_missiles_record_pins_barrages_and_partial_objective():
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
        if item["id"] == "mission-missiles-barrages"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/missions/acid/mission_missiles.lua",
            "sha256": (
                "f334ce1a26473322d50528d6349d8b942"
                "fb9202d2e1b0faa07c1d59f1d299131"
            ),
            "symbols": [
                "Mission_Missiles",
                "Mission_Missiles:GetCompletedObjectives",
                "Mission_Missiles:UpdateObjectives",
                "Mission_Missiles:StartMission",
                "Missile_Unit",
                "Missiles_Unit_Weapon",
                "Missiles_Shield",
                "Missiles_OneDmg",
            ],
        },
        {
            "path": "scripts/weapons_support.lua",
            "sha256": (
                "f5fc6be6bde2aae2676f29c39b45fe039"
                "d2a81537608e1f43e17ebc3ecda1855"
            ),
            "symbols": [
                "Support_Missiles",
                "Support_Missiles:GetTargetArea",
                "Support_Missiles:GetSkillEffect",
            ],
        },
        {
            "path": "scripts/global.lua",
            "sha256": (
                "96d82d83a1620061e6fd013aa8462883"
                "e1f3764d03752757ad77fbbbd04bc9b2"
            ),
            "symbols": ["Skill:GetTargetZone"],
        },
    ]

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/solver.rs"] == {
        "get_weapon_targets",
        "mission_missiles_action_bonus",
        "weapon_action_has_effect",
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "sim_global_unit_effect",
        "simulate_weapon",
    }
    assert implementations["src/loop/commands.py"] == {
        "_enrich_bridge_limited_mission_weapons_from_save",
        "_is_transient_delayed_multihit_damage_diff",
    }

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "zero reputation at zero or one shot" in facts
    assert "one reputation at two or three shots" in facts
    assert "two reputation at four shots" in facts
    assert "proposed failure when the Missile_Unit dies is commented out" in facts
    assert "scans x then y" in facts
    assert "every pawn-space except the source" in facts
    gaps = " ".join(record["known_gaps"])
    assert "does not export Mission_Missiles.ShotsUsed" in gaps
    assert "Board:IsPawnSpace" in gaps
    assert "generic friendly-NPC penalty" in gaps
    assert "decorative" in gaps


def test_real_mission_bomb_record_pins_objective_and_fire_immunity():
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
        if item["id"] == "mission-bomb-protobombs"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/sand/mission_bomb.lua",
            "sha256": (
                "6fba941f738972f39a69432da105c4b06"
                "a77e8b4042ac191a3415c320b9051f2"
            ),
            "symbols": [
                "Mission_Bomb",
                "Mission_Bomb:StartMission",
                "Mission_Bomb:GetCompletedObjectives",
                "Mission_Bomb:CountBombs",
                "Mission_Bomb:UpdateObjectives",
                "ProtoBomb",
            ],
        },
        {
            "path": "scripts/missions/missions.lua",
            "sha256": (
                "505c02a8668ba2e39d868f95051ede81"
                "c6cc1611f1e409219b6caa4fbe1d0257"
            ),
            "symbols": ["Mission:AddDefended", "Mission_Infinite"],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/board.rs"] == {"can_catch_fire"}
    assert implementations["src/solver/threat_audit.py"] == {
        "_unit_takes_fire_tick"
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "one reputation when exactly one survives" in facts
    assert "Corpse=false, IgnoreFire=true, and Explodes=true" in facts
    assert "two nonadjacent satellite-zone points" in facts
    gaps = " ".join(record["known_gaps"])
    assert "explosion footprint" in gaps
    assert "Mission:AddDefended selection randomness" in gaps
    assert "safety policy" in gaps


def test_real_mission_civilians_record_pins_vip_move_semantics():
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
        if item["id"] == "mission-civilians-vip-trucks"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/advanced/missions/acid/mission_civilians.lua",
            "sha256": (
                "ebee1b69eb19f0449777894056b5b695f"
                "8d41dd4f20d2da0a17a72e87fc9caf8"
            ),
            "symbols": [
                "Mission_Civilians",
                "Mission_Civilians:StartMission",
                "Mission_Civilians:NextTurn",
                "Mission_Civilians:GetCompletedObjectives",
                "Mission_Civilians:CountTanks",
                "Mission_Civilians:UpdateObjectives",
                "VIP_Truck",
                "VIP_Truck_Move",
                "VIP_Truck_Move:GetTargetArea",
                "VIP_Truck_Move:GetSkillEffect",
            ],
        },
        {
            "path": "scripts/missions/missions.lua",
            "sha256": (
                "505c02a8668ba2e39d868f95051ede81"
                "c6cc1611f1e409219b6caa4fbe1d0257"
            ),
            "symbols": ["Mission:AddDefended", "Mission_Infinite"],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/loop/commands.py"] == {
        "_enrich_bridge_limited_mission_weapons_from_save"
    }
    assert implementations["rust_solver/src/solver.rs"] == {
        "enumerate_actions",
        "get_weapon_targets",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "one reputation when exactly one survives" in facts
    assert "IgnoreSmoke=true" in facts
    assert "Limited=2" in facts
    assert "mission-, UID-, type-, slot-, and weapon-matched" in facts
    gaps = " ".join(record["known_gaps"])
    assert "Native Board:GetReachable" in gaps
    assert "stale" in gaps
    assert "Mission:AddDefended satellite-zone randomness" in gaps


def _mission_provenance_record(record_id: str) -> dict:
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
    return next(item for item in provenance["records"] if item["id"] == record_id)


def test_real_mission_force_record_pins_counter_and_gaps():
    record = _mission_provenance_record("mission-force-mountain-counter")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/sand/mission_force.lua",
        "sha256": "fa42203134fae821bb488eb41f49d62bba4dd5e79e53afbf729b0a63e31bf725",
        "symbols": [
            "Mission_Force", "Mission_Force:PrepBonus",
            "Mission_Force:GetCompletedStatus", "Mission_Force:NextTurn",
            "Mission_Force:StartMission", "Mission_Force:IsEndBlocked",
            "Mission_Force:UpdateMission", "Mission_Force:GetCompletedObjectives",
            "Mission_Force:UpdateObjectives",
        ],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "EVENT_MOUNTAIN_DESTROYED" in facts
    assert "BONUS_KILL_FIVE" in facts
    gaps = " ".join(record["known_gaps"])
    assert "random_removal" in gaps
    assert "GetCompletedStatus" in gaps


def test_real_mission_holes_record_pins_spawn_and_inherited_mites():
    record = _mission_provenance_record("mission-holes-sinkhole-hive")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/sand/mission_holes.lua",
        "sha256": "ba6df180c061ceb4fe400bcc3083e2e392b505952c5a460ace40c98c25dc3718",
        "symbols": [
            "Mission_Holes", "Mission_Holes:UpdateSpawning",
            "Mission_Holes:IsEndBlocked",
        ],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "BONUS_BLOCK" in facts
    assert "GetSpawnCount Hornets" in facts
    gaps = " ".join(record["known_gaps"])
    assert "BONUS_SELFDAMAGE inheritance" in gaps
    assert "Mission_Holes:IsEndBlocked" in gaps


def test_real_mission_trapped_record_pins_base_and_ae_callbacks():
    record = _mission_provenance_record("mission-trapped-decoy-buildings")
    assert record["coverage"] == "partial"
    sources = {source["path"]: source for source in record["sources"]}
    assert sources["scripts/missions/sand/mission_trapped.lua"]["sha256"] == (
        "f46bb4cce26c02dd1904a88217fc5d154bba61a21cbf85f72d1c101460d37a02"
    )
    assert sources["scripts/advanced/missions/sand/mission_trapped.lua"]["sha256"] == (
        "6916b02be75795f7bb133767ece7367c1d3ecb346013157892fdaabbc07c46da"
    )
    assert sources["scripts/advanced/missions/sand/mission_trapped.lua"]["symbols"][-2:] == [
        "Trapped_Explode:GetTargetArea", "Trapped_Explode:GetSkillEffect"
    ]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "DAMAGE_DEATH" in facts
    gaps = " ".join(record["known_gaps"])
    assert "legacy setup callback" in gaps
    assert "SkillEffect queue order" in gaps


def test_real_mission_forest_fire_record_pins_counter_and_policy_gap():
    record = _mission_provenance_record("mission-forest-fire-counter")
    assert record["coverage"] == "partial"
    source = record["sources"][0]
    assert source["path"] == "scripts/advanced/missions/grass/mission_fires.lua"
    assert source["sha256"] == (
        "a146d1ff25ffb5d8d4459990214bd831c3a0c4cd243fd4ee7f8dc7d98044d739"
    )
    assert source["symbols"] == [
        "Mission_ForestFire", "Mission_ForestFire:StartMission",
        "Mission_ForestFire:GetFireCount", "Mission_ForestFire:GetCompletedObjectives",
        "Mission_ForestFire:GetReward", "Mission_ForestFire:UpdateObjectives",
    ]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "two reputation at eight or more fires" in facts
    gaps = " ".join(record["known_gaps"])
    assert "authoritative solver scalar" in gaps
    assert "conservative strategy policy" in gaps


def test_real_mission_shields_record_preserves_source_live_gap():
    record = _mission_provenance_record("mission-shields-generator")
    assert record["coverage"] == "partial"
    source = record["sources"][0]
    assert source["path"] == "scripts/advanced/missions/snow/mission_shields.lua"
    assert source["sha256"] == (
        "43a620c78ab42e4fe94e78ba311086bcc5a28433c0a841ca90cc542447a430d6"
    )
    assert "Mission_Shields:UpdateMission" in source["symbols"]
    assert "Shield_Generator_Tooltip:GetSkillEffect" in source["symbols"]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "not controlled proof" in facts
    assert "Ricochet path was later diagnosed as a native no-op" in facts
    gaps = " ".join(record["known_gaps"])
    assert "exact one-time source semantics" in gaps
    assert "controlled direct-hit, push, and death traces" in gaps


def test_real_mission_acid_record_pins_native_spawn_gap():
    record = _mission_provenance_record("mission-acid-water-spawns")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/acid/mission_acid.lua",
        "sha256": "082947a38cd3ad831ecca58cb046a5817d6c0669cbae11160604c3c25f73a461",
        "symbols": [
            "Mission_Acid", "Mission_Acid:StartMission",
            "Mission_Acid:UpdateSpawning", "Mission_Acid:SpawnAcidMonsters",
        ],
    }]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/bridge/modloader.lua"] == {"dump_state"}
    assert implementations["src/model/board.py"] == {"from_bridge_data"}
    assert implementations["rust_solver/src/serde_bridge.rs"] == {"board_from_json"}
    assert implementations["src/solver/plan_safety.py"] == {"audit_plan_safety"}
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "ACID-water tiles" in facts
    assert "SpawnPawns(GetSpawnCount()) first" in facts
    assert "except on the final turn" in facts
    gaps = " ".join(record["known_gaps"])
    assert "GetBoardList ACID-water snapshot" in gaps
    assert "Mission_Infinite and Mission_Auto inheritance" in gaps
    assert "no source-specific forecast" in gaps


def test_real_mission_fence_record_pins_native_wall_gate():
    record = _mission_provenance_record("mission-fence-edge-walls")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/acid/mission_fence.lua",
        "sha256": "3833931bfd66db1690ba76ebca3890d4cea5a6f2904d3beecf17ae69d75789a0",
        "symbols": [
            "Mission_Fence", "Mission_Fence:IsObstructed",
            "Mission_Fence:TrimFence", "Mission_Fence:StartMission",
        ],
    }]
    implementations = next(
        reference
        for reference in record["implementations"]
        if reference["path"] == "src/loop/commands.py"
    )
    assert implementations["path"] == "src/loop/commands.py"
    assert set(implementations["symbols"]) == {
        "_MISSION_NATIVE_FORECAST_GAPS", "_mission_native_forecast_block",
        "cmd_solve", "cmd_click_end_turn", "cmd_dispatch_end_turn", "cmd_end_turn",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "at most five directional Board:SetWall segments" in facts
    assert "exact-ID" in facts
    gaps = " ".join(record["known_gaps"])
    assert "edge geometry" in gaps
    assert "fail-closed and non-overridable" in gaps


def test_real_mission_laser_record_pins_native_beam_gate():
    record = _mission_provenance_record("mission-laser-queued-beam")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/acid/mission_laser.lua",
        "sha256": "e9195a160fd8a7b971555d767033eb7baea116668462cc0f50d22de01d2b13db",
        "symbols": [
            "Mission_Laser", "Mission_Laser:GetLaserDirection",
            "Mission_Laser:StartMission", "Laser_U_Atk:GetTargetArea",
            "Laser_U_Atk:GetTargetScore", "Laser_U_Atk:GetSkillEffect",
        ],
    }, {
        "path": "scripts/weapons_base.lua",
        "sha256": "bdb55457746d08b46e8b62ad7cfc27f0a08bde9fab7397a4780dfe945b5f8f38",
        "symbols": ["Laser_Base:AddQueuedLaser", "Laser_Base:AddLaser"],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "neutral, immobile, nonpushable Corpse" in facts
    assert "damage 5 decaying to minimum 1" in facts
    assert "passes pawns and stops at a Building, Mountain, or board edge" in facts
    gaps = " ".join(record["known_gaps"])
    assert "queued Laser_Base traversal" in gaps
    assert "fail-closed and non-overridable" in gaps


def test_real_mission_respawn_record_pins_native_resurrection_gate():
    record = _mission_provenance_record("mission-respawn-major-vek")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/acid/mission_respawn.lua",
        "sha256": "15abbd0799343a36c0b849f184b1afcb21b9cc6d8358e9f0f0260c4bc26874a1",
        "symbols": [
            "Mission_Respawn", "Mission_Respawn:StartMission",
            "Mission_Respawn:UpdateMission", "Mission_Respawn:NextTurn",
        ],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "latest space" in facts
    assert "enemy-turn entry" in facts
    assert "new native pawn identity" in facts
    gaps = " ".join(record["known_gaps"])
    assert "Board:IsBusy timing" in gaps
    assert "enemy-zone random selection" in gaps
    assert "fail-closed and non-overridable" in gaps


def test_real_mission_artillery_record_pins_support_and_fallback_gap():
    record = _mission_provenance_record("mission-artillery-support-objective")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/grass/mission_artillery.lua",
        "sha256": "fe78f546038a8a83a3db277ddd47a32c9be117db14f04ff51145dd880f8418f9",
        "symbols": [
            "Mission_Artillery", "Mission_Artillery:StartMission",
            "Mission_Artillery:UpdateObjectives",
            "Mission_Artillery:GetCompletedObjectives",
            "Mission_Artillery:NextTurn", "ArchiveArtillery",
            "Archive_ArtShot", "Archive_ArtShot:GetSkillEffect",
        ],
    }]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/mission_unit_objectives.json"] == {
        "Mission_Artillery", "ArchiveArtillery",
    }
    assert implementations["rust_solver/src/weapons.rs"] == {
        "WId::ArchiveArtShot", "wid_from_str", "wid_to_str",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "one-reputation objective" in facts
    assert "immediately-behind tile" in facts
    assert "plan safety protect" in facts
    gaps = " ".join(record["known_gaps"])
    assert "LineArtillery target legality" in gaps
    assert "synchronized Python fallback movement" in gaps
    assert "shipped no-op body" in gaps


def test_real_mission_mines_record_pins_zero_callback_inherited_gap():
    record = _mission_provenance_record("mission-mines-inherited-old-earth-placement")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/grass/mission_mines.lua",
        "sha256": "4857fb2b0c29c758f66f78b5a07451fc8159cfa9c6cedb898d1fb859f5f3b3d0",
        "symbols": ["Mission_Mines"],
    }]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/bridge/reader.py"] == {
        "_read_old_earth_mines_from_save", "read_bridge_state",
    }
    assert implementations["rust_solver/src/simulate.rs"] == {
        "simulate_move", "apply_landing_effects",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "zero-callback Mission_MineBase constructor" in facts
    assert "GlobalSpawnMod=1 and SpawnStartMod=0" in facts
    gaps = " ".join(record["known_gaps"])
    assert "not defined by this zero-callback file" in gaps
    assert "does not claim source-specific placement simulation" in gaps


def test_real_mission_tanks_record_pins_activation_and_static_gap():
    record = _mission_provenance_record("mission-tanks-delayed-activation")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/grass/mission_tanks.lua",
        "sha256": "126c017dce32b8026773621a9fb4c60f187d01c7dc4066627e0c49664e916a77",
        "symbols": [
            "Mission_Tanks", "Mission_Tanks:StartMission",
            "Mission_Tanks:NextTurn", "Mission_Tanks:GetCompletedObjectives",
            "Mission_Tanks:CountTanks", "Mission_Tanks:UpdateObjectives",
            "Archive_Tank",
        ],
    }]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/mission_unit_objectives.json"] == {
        "Mission_Tanks", "Archive_Tank",
    }
    assert implementations["rust_solver/src/weapons.rs"] == {
        "WId::DeployTankShot", "wid_from_str",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "player turn three" in facts
    assert "two reputation for two survivors, one for one survivor" in facts
    assert "MoveSpeed=4" in facts
    gaps = " ".join(record["known_gaps"])
    assert "SetPowered/SetNeutral timing" in gaps
    assert "synchronized Python fallback movement" in gaps
    assert "separately indexed Deploy_TankShot cannon" in gaps


def test_real_mission_filler_record_pins_native_wave_gap():
    record = _mission_provenance_record("mission-filler-earth-mover-objective")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/sand/mission_filler.lua",
        "sha256": "38e00c007476a42c05bbe4968f9b081de4bbdfb3761667b0e3e72c28c39079f9",
        "symbols": [
            "Mission_Filler", "Mission_Filler:StartMission",
            "Mission_Filler:UpdateObjectives",
            "Mission_Filler:GetCompletedObjectives", "Filler_Pawn",
            "Filler_Attack", "Filler_Attack:GetTargetScore",
            "Filler_Attack:GetSkillEffect",
        ],
    }]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/mission_unit_objectives.json"] == {
        "Mission_Filler", "Filler_Pawn",
    }
    assert implementations["src/solver/plan_safety.py"] == {"audit_plan_safety"}
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "Road" in facts
    assert "Cracked" in facts
    assert "stops after finding a Hole" in facts
    gaps = " ".join(record["known_gaps"])
    assert "Board:AddPawn identity/allocation" in gaps
    assert "No Rust WId/action simulation" in gaps
    assert "live-derived discrepancy policy" in gaps


def test_real_mission_wind_legacy_stub_records_no_semantics():
    record = _mission_provenance_record("mission-wind-legacy-empty-stub")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/sand/mission_wind.lua",
        "sha256": "7eb70257593da06f682a3ddda54a9d260d4fc514f645237f5ca74b08f8da61a6",
        "symbols": ["legacy CRLF-only stub (no Lua symbols)"],
    }]
    assert record["implementations"] == [{
        "path": "data/mission_metadata.json",
        "symbols": ["Mission_Wind"],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "two CRLF bytes" in facts
    assert "contains no Lua declarations" in facts
    assert "Advanced Edition mission_wind.lua source" in facts
    gaps = " ".join(record["known_gaps"])
    assert "provides no mission class" in gaps
    assert "must not be used to support or contradict" in gaps


def test_real_mission_battle_stub_records_no_semantics():
    record = _mission_provenance_record("mission-battle-empty-stub")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/mission_battle.lua",
        "sha256": "dba5166ad9db9ba648c1032ebbd34dcd0d085b50023b839ef5c68ca1db93a563",
        "symbols": ["legacy two-CRLF-line stub (no Lua symbols)"],
    }]
    assert record["implementations"] == [{
        "path": "src/strategy/mission_picker.py",
        "symbols": ["Mission_Battle"],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "two CRLF lines" in facts
    assert "no source behavior" in facts
    gaps = " ".join(record["known_gaps"])
    assert "no mission class" in gaps
    assert "strategy anchor is policy" in gaps


def test_real_mission_survive_stub_records_no_semantics():
    record = _mission_provenance_record("mission-survive-empty-stub")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/mission_survive.lua",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "symbols": ["empty file (no Lua symbols)"],
    }]
    assert record["implementations"] == [{
        "path": "src/strategy/mission_picker.py",
        "symbols": ["Mission_Survive"],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "zero bytes" in facts
    assert "no source behavior" in facts
    gaps = " ".join(record["known_gaps"])
    assert "no mission class" in gaps
    assert "Mission_Infinite lifecycle" in gaps
    assert "strategy anchor is policy" in gaps


def test_real_mission_volatile_record_pins_callbacks_and_retreat_gap():
    record = _mission_provenance_record("mission-volatile-glowing-scorpion-objective")
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/mission_volatile.lua",
            "sha256": "cb60e9c4b3730604c1a958ec7ae44cf22ff901e7d5fd543b5ae8f9403d9af5c4",
            "symbols": [
                "Mission_Volatile",
                "Mission_Volatile:GetCompletedObjectives",
                "Mission_Volatile:NextTurn",
                "Mission_Volatile:UpdateObjectives",
                "Mission_Volatile:StartMission",
                "Mission_Volatile:UpdateMission",
                "GlowingScorpion",
            ],
        },
        {
            "path": "scripts/missions/missions.lua",
            "sha256": "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257",
            "symbols": ["Mission_Infinite", "Mission_Auto"],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/mission_bonus_objectives.json"] == {
        "Mission_Volatile", "GlowingScorpion",
    }
    assert implementations["src/loop/commands.py"] == {
        "_protected_objective_patterns",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "four-HP" in facts
    assert "TargetLeft=true" in facts
    assert "retreat branch is unreachable" in facts
    assert "commented-out custom GetDeathEffect" in facts
    gaps = " ".join(record["known_gaps"])
    assert "non-stock override of InfiniteSpawn" in gaps
    assert "no runtime behavior or simulator gap" in gaps
    assert "inactive commented GetDeathEffect" in gaps


def test_real_mission_boss_core_record_pins_callbacks_and_native_gaps():
    record = _mission_provenance_record(
        "mission-boss-core-beetle-firefly-scorpion"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/bosses/boss.lua",
            "sha256": (
                "9a957789e714c6d22d2f90bcd79dbb68"
                "c897aaa530e23d5be50cf7cf650853f1"
            ),
            "symbols": [
                "Mission_Boss",
                "Mission_Boss:GetRewardCount",
                "Mission_Boss:GetObjectives",
                "Mission_Boss:GetBossPawn",
                "Mission_Boss:IsBossDead",
                "Mission_Boss:GetCompletedStatus",
                "Mission_Boss:Initialize",
                "Mission_Boss:StartBoss",
                "Mission_Boss:NextTurn",
                "Mission_Boss:StartMission",
                "Mission_Boss:UpdateObjectives",
                "Mission_Boss:GetCompletedObjectives",
            ],
        },
        {
            "path": "scripts/missions/bosses/beetle.lua",
            "sha256": (
                "7494baf7d88bb339fa6ddb558b71f4b94"
                "c56b8ad930256896e4a10c72dc37fea"
            ),
            "symbols": ["Mission_BeetleBoss", "BeetleBoss", "BeetleAtkB"],
        },
        {
            "path": "scripts/missions/bosses/firefly.lua",
            "sha256": (
                "f1c016ba9031553067a38f1de3d884d17"
                "6dd1af22cd74d3bf02de32649642250"
            ),
            "symbols": [
                "Mission_FireflyBoss",
                "FireflyBoss",
                "FireflyAtkB",
                "FireflyAtkB:GetSkillEffect",
            ],
        },
        {
            "path": "scripts/missions/bosses/scorpion.lua",
            "sha256": (
                "acf7325aba556595e45c24e6773bb5dc"
                "63feffe734217bba04bf9d1662b1bb63"
            ),
            "symbols": [
                "Mission_ScorpionBoss",
                "ScorpionBoss",
                "ScorpionAtkB",
                "ScorpionAtkB:GetTargetArea",
                "ScorpionAtkB:GetSkillEffect",
            ],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/mission_unit_objectives.json"] == {
        "Mission_BeetleBoss", "BeetleBoss", "Mission_FireflyBoss",
        "FireflyBoss", "Mission_ScorpionBoss", "ScorpionBoss",
    }
    assert implementations["rust_solver/src/weapons.rs"] == {
        "WId::BeetleAtkB", "WId::FireflyAtkB", "WId::ScorpionAtkB",
        "enemy_weapon_for_type",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "BONUS_ASSET Tower priority" in facts
    assert "Misison_FireflyBoss_Obj" in facts
    assert "two-damage cardinal melee" in facts
    assert "directly add each attack sound effect and hold grapple" in facts
    assert "implementation anchors" in facts
    gaps = " ".join(record["known_gaps"])
    assert "Board:AddPawn placement and ID allocation" in gaps
    assert "inherited BeetleAtk1 traversal" in gaps
    assert "Tower bonus precedence" in gaps


def test_real_mission_blob_boss_record_pins_queued_chain_and_native_gaps():
    record = _mission_provenance_record("mission-blob-boss-goo-chain")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/bosses/goo.lua",
        "sha256": (
            "f6761a7cad49883fa85e631b3a524a6d5"
            "6d0d593616aa3e1031b1c65b4bab03b"
        ),
        "symbols": [
            "Mission_BlobBoss", "Mission_BlobBoss:StartMission",
            "Mission_BlobBoss:CountDeadBlobs", "Mission_BlobBoss:UpdateMission",
            "Mission_BlobBoss:UpdateObjectives", "Mission_BlobBoss:IsBossDead",
            "BlobBoss", "BlobBoss:GetDeathEffect", "BlobBossMed", "BlobBossSmall",
            "BlobBossAtk", "BlobBossAtk:GetTargetArea",
            "BlobBossAtk:GetSkillEffect", "BlobBossAtkMed", "BlobBossAtkSmall",
        ],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "BlobDeaths=5" in facts
    assert "random_removal" in facts
    assert "queues four damage" in facts
    assert "not direct damage calls" in facts
    gaps = " ".join(record["known_gaps"])
    assert "PATH_GROUND eligibility" in gaps
    assert "queued-effect ordering" in gaps


def test_real_mission_jelly_boss_record_pins_source_alias_and_native_gaps():
    record = _mission_provenance_record("mission-jelly-boss-psion-abomination")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/bosses/psion.lua",
        "sha256": (
            "bd2f27f4f28fa3cfe87b871840ab2fb4"
            "36174599b5c0a4fde3b371db7fb27ad3"
        ),
        "symbols": [
            "Mission_JellyBoss", "Mission_JellyBoss:StartMission", "Jelly_Boss",
            "Jelly_Boss_Tooltip",
        ],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "GlobalSpawnMod=-1" in facts
    assert "Leader=LEADER_BOSS" in facts
    assert "does not define the inherited health/regen/explode aura callbacks" in facts
    gaps = " ".join(record["known_gaps"])
    assert "LEADER_BOSS lookup" in gaps
    assert "No direct or queued offensive SkillEffect" in gaps


def test_real_mission_slug_boss_record_pins_flying_spawn_helper_gap():
    record = _mission_provenance_record("mission-slug-boss-hive-spawns")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/bosses/slug.lua",
        "sha256": (
            "cf93aa66cf65079d55518a446da2bffd8"
            "5df4a3602c5afdf52bca6ab6c728d52"
        ),
        "symbols": [
            "Mission_SlugBoss", "Mission_SlugBoss:StartMission",
            "Mission_SlugBoss:UpdateSpawning", "Mission_SlugBoss:SpawnSluglings",
            "SlugBoss", "SlugEgg1",
        ],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "SpawnPawns(GetSpawnCount())" in facts
    assert "exactly two SlugEgg1" in facts
    assert "direct AddDamage/AddQueuedDamage" in facts
    gaps = " ".join(record["known_gaps"])
    assert "FlyingSpawns candidate selection" in gaps
    assert "Explodes=true" in gaps


def test_real_mission_spider_boss_record_pins_hatch_order_and_native_gaps():
    record = _mission_provenance_record("mission-spider-boss-eggs-and-hatch")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/bosses/spider.lua",
        "sha256": (
            "f7d81d714922e1b5b22d5b76a8edcb6f"
            "b96dd61ae5b20a3008c66b5068046455"
        ),
        "symbols": [
            "Mission_SpiderBoss", "Mission_SpiderBoss:StartMission",
            "Mission_SpiderBoss:UpdateSpawning", "Mission_SpiderBoss:SpawnSpiderlings",
            "SpiderBoss", "SpiderBoss_Tooltip", "SpiderBoss_Tooltip:GetSkillEffect",
            "SpiderlingEgg1", "SpiderlingHatch1",
            "SpiderlingHatch1:GetTargetScore", "SpiderlingHatch1:GetSkillEffect",
        ],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "EggCount=-1" in facts
    assert "alternates the stored count between 2 and 3" in facts
    assert "first adds a Board:RemovePawn script and then adds a non-queued" in facts
    gaps = " ".join(record["known_gaps"])
    assert "direct-versus-queued effects" in gaps
    assert "AddScript/Board:RemovePawn and AddDamage ordering" in gaps


def test_real_mission_tutorial_and_trailers_record_pins_callbacks_and_native_gaps():
    record = _mission_provenance_record("mission-tutorial-and-trailer-scripts")
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/scripts.lua",
            "sha256": (
                "53632a1abe38638eae14b7a0cc9cee80"
                "590a9a90da9d110200d81eb3281b3a60"
            ),
            "symbols": ["GetScripts"],
        },
        {
            "path": "scripts/missions/missions.lua",
            "sha256": (
                "505c02a8668ba2e39d868f95051ede81"
                "c6cc1611f1e409219b6caa4fbe1d0257"
            ),
            "symbols": ["CreateTutorial"],
        },
        {
            "path": "scripts/missions/mission_ae_trailer.lua",
            "sha256": (
                "b3bab4d6a928ea6d7c72afc2be044402"
                "f5b03d8f426c67f592c880c72ba8e39e"
            ),
            "symbols": [
                "Mission_Tutorial", "Mission_Tutorial:StartMission",
                "Mission_Tutorial:UpdateMission", "TrailerOpening",
                "TrailerOpening_Two",
            ],
        },
        {
            "path": "scripts/missions/mission_trailer.lua",
            "sha256": (
                "5bd9d7a4ac8810c4c9433357fc8e56c9"
                "b6bf533f4bbec922526ff3c2b079662f"
            ),
            "symbols": [
                "Mission_Tutorial", "Mission_Tutorial:StartMission",
                "Mission_Tutorial:UpdateMission", "TrailerOpening",
                "TrailerOpening_Two",
            ],
        },
        {
            "path": "scripts/missions/mission_tutorial.lua",
            "sha256": (
                "8629ce275906d97e3f53172ff7202ff3"
                "c59cd10322583c3c391a92621b8bbf39"
            ),
            "symbols": [
                "TUT_ATTACKS", "TUT_COMBATMECH", "Mission_Tutorial",
                "Mission_Tutorial:StartMission", "Mission_Tutorial:NextTurn",
                "Mission_Tutorial:AddUndoTip",
                "Mission_Tutorial:GetCompletedObjectives",
                "Mission_Tutorial:UpdateObjectives",
                "Mission_Tutorial:UpdateTurnOne",
                "Mission_Tutorial:UpdateTurnTwo",
                "Mission_Tutorial:UpdateTurnThree",
                "Mission_Tutorial:UpdateMission",
            ],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/mission_metadata.json"] == {"Mission_Tutorial"}
    assert implementations["src/bridge/modloader.lua"] == {
        "mission_bridge_id", "dump_state",
    }
    assert implementations["src/loop/commands.py"] == {
        "_MISSION_NATIVE_FORECAST_GAPS", "_mission_native_forecast_block",
        "cmd_solve", "cmd_click_end_turn", "cmd_dispatch_end_turn", "cmd_end_turn",
    }
    assert implementations["src/strategy/mission_picker.py"] == {
        "NATIVE_FORECAST_GATED_MISSION_IDS",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "dormant/unrouted" in facts
    assert "TurnLimit=7" in facts
    assert "Board:SpawnQueued" in facts
    assert "Game:BlockNextTurn" in facts
    gaps = " ".join(record["known_gaps"])
    assert "loader override precedence" in gaps
    assert "PAWN_FACTORY construction" in gaps
    assert "does not infer a normal campaign mission lifecycle" in gaps


def test_real_mission_boombots_record_pins_callbacks_and_explosion_gap():
    record = _mission_provenance_record("mission-boombots-explosive-decay")
    assert record["coverage"] == "partial"
    source = record["sources"][0]
    assert source["path"] == "scripts/advanced/missions/snow/mission_boombots.lua"
    assert source["sha256"] == (
        "1af2b8146aa399f01131f4ae08e7f04f3439ee00a7b908451d4684d0bc44ae2b"
    )
    assert source["symbols"][1:5] == [
        "Mission_BoomBots:StartMission", "Mission_BoomBots:GetDestroyedCount",
        "Mission_BoomBots:UpdateObjectives", "Mission_BoomBots:GetCompletedObjectives",
    ]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "two unfrozen and two frozen" in facts
    assert "Explodes=true" in facts
    gaps = " ".join(record["known_gaps"])
    assert "random_element roster choice" in gaps
    assert "0/1/2-reputation settlement" in gaps


def test_real_mission_factory_record_pins_critical_and_order_gaps():
    record = _mission_provenance_record("mission-factory-critical-launches")
    assert record["coverage"] == "partial"
    source = record["sources"][0]
    assert source["path"] == "scripts/missions/snow/mission_factory.lua"
    assert source["sha256"] == (
        "bcb9d31ba2efa17c2d48db36acb152760ed0ce7ab89fda4a486389b259af0997"
    )
    assert source["symbols"][1:] == [
        "Mission_Factory:UpdateSpawning", "Mission_Factory:UpdateMission",
        "Mission_Factory:NextTurn", "Mission_Factory:GetCompletedObjectives",
    ]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "turn parity" in facts
    assert "lower-UID Burnbug" in facts
    gaps = " ".join(record["known_gaps"])
    assert "FlyingSpawns" in gaps
    assert "SetPowered transition scheduling" in gaps


def test_real_mission_freezebots_record_pins_frozen_objective_coverage():
    record = _mission_provenance_record("mission-freezebots-frozen-robots")
    assert record["coverage"] == "partial"
    sources = {source["path"]: source for source in record["sources"]}
    source = sources["scripts/missions/snow/mission_freezebots.lua"]
    assert source["sha256"] == (
        "3fcff4c8edcdab7b787b255e916083e414035a04a32e0b9dec0e82e6e5246786"
    )
    assert source["symbols"][1:] == [
        "Mission_FreezeBots:StartMission", "Mission_FreezeBots:GetCompletedObjectives",
        "Mission_FreezeBots:GetCompletedStatus", "Mission_FreezeBots:CountDead",
        "Mission_FreezeBots:CountFrozen", "Mission_FreezeBots:UpdateObjectives",
    ]
    assert sources["scripts/missions/snow/snow_helper.lua"] == {
        "path": "scripts/missions/snow/snow_helper.lua",
        "sha256": "218e6fa6c8efc08a760347af26d185004c5dc141f7c27b8f9ed7a0e985e191d1",
        "symbols": ["Freeze_Tank", "Pinnacle_FreezeTank"],
    }
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["rust_solver/src/weapons.rs"] == {
        "WId::PinnacleFreezeTank", "wid_from_str", "wid_to_str",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "NextRobot twice" in facts
    assert "Freeze_Tank" in facts
    assert "Snowtank, Snowlaser, and Snowart families" in facts
    assert "Damage=0, Push=0, and Freeze=1" in facts
    gaps = " ".join(record["known_gaps"])
    assert "duplicate-family selection" in gaps
    assert "partial reward settlement" in gaps


def test_real_mission_snowbattle_record_pins_native_setup_gap():
    record = _mission_provenance_record("mission-snowbattle-native-robot-setup")
    assert record["coverage"] == "partial"
    assert record["sources"] == [{
        "path": "scripts/missions/snow/mission_snowbattle.lua",
        "sha256": "f3d7598924348c3283145d4478c0e4b7833bfd37261e61c17fefc3e4b7ed0f0c",
        "symbols": ["Mission_SnowBattle", "Mission_SnowBattle:StartMission"],
    }]
    assert record["implementations"] == [{
        "path": "data/mission_metadata.json",
        "symbols": ["Mission_SnowBattle"],
    }]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "RobotStart=2" in facts
    assert (
        "two normally added native-selected robots and one explicitly frozen "
        "native-selected robot"
    ) in facts
    assert "no dynamic forced_pawns assertion" in facts
    gaps = " ".join(record["known_gaps"])
    assert "NextRobot candidate roster and RNG" in gaps
    assert "safety gate after bridge state extraction" in gaps


def test_real_mission_final_surface_and_cave_record_pins_lifecycle_and_terminal_settlement():
    record = _mission_provenance_record(
        "mission-final-surface-and-cave-lifecycle"
    )
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/game.lua",
            "sha256": (
                "8fc587a6d341f43cf521ae2c95e91e57"
                "39355cb929581a18f9c374fba2c88db7"
            ),
            "symbols": [
                "GameObject:GetMissionId", "GameObject:GetMission",
                "GameObject:CreateNextPhase",
                "Values.pod_z", "Values.pod_velocity",
            ],
        },
        {
            "path": "scripts/global.lua",
            "sha256": (
                "96d82d83a1620061e6fd013aa8462883e"
                "1f3764d03752757ad77fbbbd04bc9b2"
            ),
            "symbols": ["random_element", "random_removal"],
        },
        {
            "path": "scripts/environments.lua",
            "sha256": (
                "5f8a7d74f537abb33bc88c1f9669f3f"
                "6fabdd5c8c51aad3486d2e965e4fb80ec"
            ),
            "symbols": [
                "Environment:IsValidTarget", "Environment:FindEndpoints",
                "Environment:GetCrossPath", "Env_Attack:Start",
            ],
        },
        {
            "path": "scripts/missions/missions.lua",
            "sha256": (
                "505c02a8668ba2e39d868f95051ede81"
                "c6cc1611f1e409219b6caa4fbe1d0257"
            ),
            "symbols": [
                "Mission.NextPhase", "Mission:IsEndBlocked",
                "Mission:IsNextPhase", "Mission:MissionEnd",
                "Mission:BaseUpdate",
                "CreateMission", "Mission:GetMapTag", "Mission:BaseStart",
                "Mission:GetStartingPawns", "Mission:SpawnPawns",
                "Mission:SetupDiffMod",
            ],
        },
        {
            "path": "scripts/missions/final/mission_final.lua",
            "sha256": (
                "f92875ba570871b7b3184adb168105c8"
                "f29150398b8b14e87a863f67d6c61e29"
            ),
            "symbols": [
                "Mission_Final", "Mission_Final:StartMission",
                "Mission_Final:NextTurn", "Mission_Final:MissionEnd",
                "Mission_Final:UpdateMission",
                "Mission_Final:UpdateObjectives",
                "Mission_Final:IsEndBlocked",
            ],
        },
        {
            "path": "scripts/missions/final/env_final.lua",
            "sha256": (
                "8d9220a9f7c0b6f3887ec8b9ffdd351"
                "b25cd4c53696d2f401c81dbeb932a6f33"
            ),
            "symbols": ["Env_Final", "Env_Final:Start"],
        },
        {
            "path": "scripts/missions/final/mission_final_two.lua",
            "sha256": (
                "c8a8e40f512939c1f4fd0e0df416e5c"
                "baec00c639e2985ad776e13c38735b17c"
            ),
            "symbols": [
                "Mission_Final_Cave", "SpawnMechs",
                "Mission_Final_Cave:MissionEnd",
                "Mission_Final_Cave:NextTurn",
                "Mission_Final_Cave:IsFinalTurn",
                "Mission_Final_Cave:StartMission",
                "Mission_Final_Cave:UpdateSpawning",
                "Mission_Final_Cave:UpdateMission",
                "Mission_Final_Cave:UpdateObjectives",
                "Mission_Final_Cave:AddBomb",
                "Mission_Final_Cave:IsEndBlocked", "BigBomb", "AddPawn",
            ],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/bridge/terrain_fingerprint.py"] == {
        "fingerprint_from_bridge_tiles", "is_stage_change",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_final_phase_scheduler.json"
    ] == {
        "normal_end_readiness_veto", "mission_end_callback_order",
        "native_phase_handoff_order", "create_next_phase_dispatch",
        "final_surface_target", "solver_boundary",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_final_end_settlement.json"
    ] == {
        "final_limit_bypasses_end_block",
        "both_final_stages_use_current_limit",
        "mission_end_queues_native_effect",
        "queued_effect_is_board_activity",
        "phase_handoff_waits_for_activity_clear",
        "final_mission_end_effects_precede_exit",
        "solver_boundary",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_final_cave_outcome.json"
    ] == {
        "outcome_storage_and_callers_are_exact",
        "final_cave_limit_writes_victory",
        "countdown_does_not_recheck_bomb_or_objectives",
        "missing_bomb_delays_instead_of_directly_losing",
        "forced_zero_mech_failure_is_separate",
        "campaign_result_join_is_exact",
        "solver_boundary",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_final_cave_replacement.json"
    ] == {
        "source_callback_and_selection_are_exact",
        "board_update_precedes_replacement_callback",
        "is_busy_blocks_queued_repeat",
        "add_dropper_copy_semantics_are_exact",
        "add_effect_queues_for_later_dispatch",
        "dropper_preserves_space_damage_to_impact",
        "bigbomb_drop_resolution_path_is_exact",
        "replacement_rng_boundary_is_narrow",
        "solver_boundary",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "final_cave_replacement_cadence.json"
    ] == {
        "dispatcher_result_enters_busy_vector",
        "pylon_is_busy_until_impact",
        "replacement_repeat_cadence_is_exact",
        "solver_boundary",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_final_campaign_settlement.json"
    ] == {
        "start_mech_travel_initializes_native_queue",
        "travel_queue_finishes_with_bomb_lock_and_fade",
        "campaign_terminal_predicate_is_exact",
        "final_campaign_bypasses_ordinary_cleanup",
        "campaign_manager_settles_in_order",
        "completed_run_saves_are_removed",
        "victory_profile_and_achievement_path",
        "profile_write_path_is_pinned",
        "final_victory_renderer_handoff",
        "solver_boundary",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_final_cave_startup.json"
    ] == {
        "native_startup_order", "final_cave_map_pool",
        "base_start_source_order", "startup_rng_skeleton",
        "center_assignment", "solver_boundary",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "final_cave_startup_spawn_order.json"
    ] == {
        "spawn_overloads_are_exact",
        "implicit_enemy_spawn_selects_and_commits_space",
        "spawn_blocks_precede_implicit_selection",
        "logical_spawns_precede_startup_effect_dispatch",
        "startup_rng_order_is_narrower",
        "solver_boundary",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "final_cave_startup_effect_order.json"
    ] == {
        "release_branch_is_exact",
        "builders_append_independent_records",
        "delays_partition_without_reordering",
        "mech_scripts_are_attempted_in_id_order",
        "duplicate_pylon_droppers_are_real_records",
        "startup_effect_order_is_closed",
        "solver_boundary_remains_settled_read",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "final_cave_block_spawn_lifetime.json"
    ] == {
        "blocked_constants_are_exact",
        "both_block_values_reject_spawns",
        "temporary_cleanup_is_exact",
        "player_turn_is_the_native_cleanup_boundary",
        "final_cave_startup_lifetime_is_exact",
        "permanent_is_board_scoped",
        "solver_boundary_remains_settled_read",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_"
        "final_cave_drop_resolution.json"
    ] == {
        "space_damage_layout_is_exact",
        "terrain_precedes_spawn_resolution",
        "carried_pawns_are_offboard_before_startmission",
        "ordinary_pylons_materialize_at_two_hp",
        "occupied_spawn_records_kill_before_recheck",
        "startup_optional_enemy_is_replaced_by_bigbomb",
        "replacement_enemy_collision_is_blocker_conditional",
        "solver_boundary_remains_settled_read",
    }
    assert implementations[
        "data/observatory/native/"
        "windows_build_13725832_31fe35265598_final_cave_map_choice.json"
    ] == {
        "random_map_is_shipped_lua", "installation_order",
        "all_nine_cave_maps_are_eligible",
        "ordinary_first_transition_has_one_attempt",
        "random_int_one_advances", "two_draw_map_boundary",
        "solver_boundary",
    }
    assert implementations["src/loop/commands.py"] == {
        "_detect_terrain_stage_change", "_capture_board_summary",
        "_lookahead_forecast_gaps",
        "_held_end_turn_bridge_checkpoint_schema_error",
    }
    assert implementations["src/model/board.py"] == {
        "from_bridge_data", "bigbomb_alive", "bigbomb_replacement_pending",
        "bigbomb_replacement_snapshot_candidates", "BigBomb",
    }
    assert implementations["src/observatory/final_phase_scheduler.py"] == {
        "build_final_phase_scheduler_map",
        "validate_final_phase_scheduler_map",
        "validate_final_phase_scheduler_map_binding",
    }
    assert implementations["src/observatory/final_end_settlement.py"] == {
        "build_final_end_settlement_map",
        "validate_final_end_settlement_map",
        "validate_final_end_settlement_map_binding",
    }
    assert implementations["src/observatory/final_cave_outcome.py"] == {
        "build_final_cave_outcome_map",
        "validate_final_cave_outcome_map",
        "validate_final_cave_outcome_map_binding",
    }
    assert implementations["src/observatory/final_cave_replacement.py"] == {
        "build_final_cave_replacement_map",
        "validate_final_cave_replacement_map",
        "validate_final_cave_replacement_map_binding",
    }
    assert implementations[
        "src/observatory/final_cave_replacement_cadence.py"
    ] == {
        "build_final_cave_replacement_cadence_map",
        "validate_final_cave_replacement_cadence_map",
        "validate_final_cave_replacement_cadence_map_binding",
    }
    assert implementations["src/observatory/final_campaign_settlement.py"] == {
        "build_final_campaign_settlement_map",
        "validate_final_campaign_settlement_map",
        "validate_final_campaign_settlement_map_binding",
    }
    assert implementations["src/observatory/final_cave_startup.py"] == {
        "build_final_cave_startup_map",
        "validate_final_cave_startup_map",
        "validate_final_cave_startup_map_binding",
    }
    assert implementations[
        "src/observatory/final_cave_startup_spawn_order.py"
    ] == {
        "build_final_cave_startup_spawn_order_map",
        "validate_final_cave_startup_spawn_order_map",
        "validate_final_cave_startup_spawn_order_map_binding",
    }
    assert implementations[
        "src/observatory/final_cave_startup_effect_order.py"
    ] == {
        "build_final_cave_startup_effect_order_map",
        "validate_final_cave_startup_effect_order_map",
        "validate_final_cave_startup_effect_order_map_binding",
    }
    assert implementations[
        "src/observatory/final_cave_block_spawn_lifetime.py"
    ] == {
        "build_final_cave_block_spawn_lifetime_map",
        "validate_final_cave_block_spawn_lifetime_map",
        "validate_final_cave_block_spawn_lifetime_map_binding",
    }
    assert implementations[
        "src/observatory/final_cave_drop_resolution.py"
    ] == {
        "build_final_cave_drop_resolution_map",
        "validate_final_cave_drop_resolution_map",
        "validate_final_cave_drop_resolution_map_binding",
    }
    assert implementations["src/observatory/final_cave_map_choice.py"] == {
        "build_final_cave_map_choice_map",
        "validate_final_cave_map_choice_map",
        "validate_final_cave_map_choice_map_binding",
    }
    assert implementations["src/solver/plan_safety.py"] == {
        "audit_plan_safety", "bigbomb_replacement_unresolved",
        "final_cave_emergency_pylon_loss_allowed",
        "final_cave_resist_gamble_allowed", "bigbomb_alive",
        "pylons_alive", "pylon_hp_total",
    }
    assert implementations["rust_solver/src/board.rs"] == {
        "Board", "bigbomb_replacement_pending",
        "bigbomb_replacement_snapshot_candidates",
    }
    assert implementations["rust_solver/src/turn_projection.rs"] == {
        "apply_final_cave_bomb_replacement_boundary",
        "final_cave_bomb_snapshot_candidates", "board_to_json",
    }
    assert implementations["rust_solver/src/beam.rs"] == {"solve_beam"}
    assert implementations[
        "scripts/itb_observatory_final_phase_scheduler.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_end_settlement.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_cave_outcome.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_cave_replacement.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_cave_replacement_cadence.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_campaign_settlement.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_cave_startup.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_cave_startup_spawn_order.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_cave_startup_effect_order.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_cave_block_spawn_lifetime.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_cave_drop_resolution.py"
    ] == {"_parser", "main"}
    assert implementations[
        "scripts/itb_observatory_final_cave_map_choice.py"
    ] == {"_parser", "main"}
    tests = {
        reference["path"]: set(reference["symbols"])
        for reference in record["tests"]
    }
    assert tests["tests/test_observatory_final_cave_outcome.py"] == {
        "test_committed_map_closes_final_cave_countdown_outcome_boundary",
        "test_binding_rejects_pointer_source_or_prose_drift",
        "test_exact_local_executable_and_source_reproduce_map_when_available",
    }
    assert tests["tests/test_observatory_final_cave_replacement.py"] == {
        "test_committed_map_closes_replacement_materialization_path_without_rng_overclaim",
        "test_binding_rejects_pointer_source_or_prose_drift",
        "test_exact_local_executable_and_sources_reproduce_map_when_available",
    }
    assert tests[
        "tests/test_observatory_final_cave_replacement_cadence.py"
    ] == {
        "test_committed_map_closes_semantic_repeat_cadence_without_rng_overclaim",
        "test_binding_rejects_vtable_source_or_prose_drift",
        "test_exact_local_executable_and_source_reproduce_map_when_available",
    }
    assert tests[
        "tests/test_observatory_final_cave_startup_spawn_order.py"
    ] == {
        "test_committed_map_closes_logical_startup_spawn_order_without_rng_overclaim",
        "test_binding_rejects_wrapper_order_or_prose_drift",
        "test_exact_local_executable_and_sources_reproduce_map_when_available",
    }
    assert tests[
        "tests/test_observatory_final_cave_startup_effect_order.py"
    ] == {
        "test_committed_map_closes_startup_effect_order_without_visual_overclaim",
        "test_binding_rejects_native_source_schedule_or_prose_drift",
        "test_exact_local_executable_and_source_reproduce_map_when_available",
    }
    assert tests[
        "tests/test_observatory_final_cave_block_spawn_lifetime.py"
    ] == {
        "test_committed_map_closes_ordinary_spawn_block_lifetime_without_overclaim",
        "test_binding_rejects_native_lifetime_contract_or_prose_drift",
        "test_exact_local_executable_and_source_reproduce_map_when_available",
    }
    assert tests[
        "tests/test_observatory_final_cave_drop_resolution.py"
    ] == {
        "test_committed_map_closes_ordinary_drop_resolution_without_rng_overclaim",
        "test_binding_rejects_layout_collision_or_prose_drift",
        "test_exact_local_executable_source_dependencies_and_captures_reproduce_map_when_available",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "only Hard or Unfair" in facts
    assert "does not explicitly reset iDamage" in facts
    assert "fixed four-space supervolcano" in facts
    assert "50% native RNG branch" in facts
    assert "IsFinalTurn returns false exactly" in facts
    assert "increments TurnLimit by 2" in facts
    assert "does not state that bomb loss is terminal" in facts
    assert "Simulator v406 models the source-guaranteed" in facts
    assert "fabricates no pawn or UID" in facts
    assert "relative native path" in facts
    assert "IsNextPhase before dispatching MissionEnd" in facts
    assert "current turn equals that limit" in facts
    assert "before constructing or invoking IsEndBlocked" in facts
    assert "Board activity reason 6" in facts
    assert "cannot reach the later IsNextPhase" in facts
    assert "current-limit readiness writes primary outcome code 1" in facts
    assert "without a bomb, objective, or IsEndBlocked query" in facts
    assert "TEAM_MECH value 4" in facts
    assert (
        "delays the queried boundary by two turns rather than directly losing"
        in facts
    )
    assert "Board effect update precedes BaseUpdate" in facts
    assert "independent full 0x134-byte SpaceDamage copies" in facts
    assert "landing applies the preserved sPawn=BigBomb record" in facts
    assert "fresh settled bridge-read gate remain exact" in facts
    assert "closes semantic repeated-cycle ordering" in facts
    assert "primary Board's +0x2d20 active-animation vector" in facts
    assert "no duplicate replacement can queue" in facts
    assert "resolves that post-StartMechTravel gap" in facts
    assert "4.5-second state value" in facts
    assert "common completed-battle state" in facts
    assert "DeleteFileA wrapper" in facts
    assert "Result 1 alone initializes" in facts
    assert "source-selected handoff target is exact" in facts
    assert "map selection, map loading/AddMap" in facts
    assert "exactly nine final_cave-tagged maps" in facts
    assert "24 source-reachable center assignments" in facts
    assert "binds explicit-point and no-point Board:SpawnPawn overloads" in facts
    assert "synchronously calls the exact standard coordinate selector" in facts
    assert "before any queued Mech SetSpace script" in facts
    assert "fresh settled bridge-read boundary remains correct" in facts
    assert "Registered IsRelease returns true" in facts
    assert "synchronously attempt luaL_loadbuffer then lua_pcall" in facts
    assert "valid-startup Mech script order 0, 1, 2" in facts
    assert "44 records with three mountains or 46 with four" in facts
    assert "not wall-clock duration, impact overlap" in facts
    assert (
        "binds BLOCKED_NONE, BLOCKED_TEMP, and BLOCKED_PERM to 0, 1, and 2"
        in facts
    )
    assert "ClearBlockSpawns changes only 1 to 0" in facts
    assert "player-turn mode 1 invokes it before player-turn UI" in facts
    assert "permanent is Board-scoped rather than immortal storage" in facts
    assert "all 304 analysis-relevant scripts entries" in facts
    assert "all 153 Lua files of either accepted tree" in facts
    assert "iDamage, sPawn, and iTerrain to SpaceDamage offsets" in facts
    assert "invokes SetSpace(-1,-1) while re-admitting every carried pawn" in facts
    assert "before dispatching BaseStart" in facts
    assert "BoardPlayer state five" in facts
    assert "skips the only native auto-deployment tail" in facts
    assert "deployment points disjoint from both pylon and mountain zones" in facts
    assert "first independent Building record creates current/max 1/1" in facts
    assert "three retained exact-map turn-zero boards" in facts
    assert "invokes registered Pawn:Kill(false) on every occupant" in facts
    assert "optional startup enemy at bomb_loc is deliberately replaced" in facts
    assert "AddBomb does not exclude the spawn-block map" in facts
    assert "destroyed pylon can retain BLOCKED_PERM and abort" in facts
    assert "pending replacement remains non-fabricated" in facts
    assert "contains no Advanced Edition filter" in facts
    assert "FindFirstFileA and FindNextFileA" in facts
    assert "exactly one RandomMap attempt" in facts
    assert "random_int(1) consumes one draw" in facts
    assert "no concrete cross-stage Rust forecast" in facts
    gaps = " ".join(record["known_gaps"])
    assert "Env_Final records cover exact current bridge selections" in gaps
    assert "exact-build native maps now close the ordinary turn-limit" in gaps
    assert "Incoming pre-map-draw CRT state" in gaps
    assert "startup explicit/implicit SpawnPawn binding" in gaps
    assert "startup visual impact overlap" in gaps
    assert "SpawnPawns/NextPawn behavior" not in gaps
    assert "enemy logical admission before queued startup-effect dispatch" in gaps
    assert "release startup record construction/delay partitioning" in gaps
    assert (
        "player-turn temporary cleanup and Board-scoped permanent lifetime"
        in gaps
    )
    assert "ordered 0x134-byte startup records" in gaps
    assert "both duplicated pylon droppers are exact" in gaps
    assert "Temporary and permanent spawn-block lifetime" not in gaps
    assert "Ordinary spawn-block lifetime is exact too" in gaps
    assert "Ordinary startup drop resolution is now exact" in gaps
    assert "every phase-carried pawn is set logically offboard before BaseStart" in gaps
    assert "state-five Surface handoff skips the native auto-deployment tail" in gaps
    assert "disjoint from both pylon and mountain zones" in gaps
    assert (
        "first and second unoccupied pylon records settle at 1/1 then 2/2 HP"
        in gaps
    )
    assert (
        "adversarial Water/Chasm/corpse/multi-space/unusual-blocker collisions"
        in gaps
    )
    assert "Arbitrary modified-script block-map contents" in gaps
    assert "Intra-effect AddScript execution" not in gaps
    assert "release-versus-debug delays" not in gaps
    assert "queued startup effects executing conformantly" not in gaps
    assert "concrete selected map" in gaps
    assert "post-StartMechTravel campaign settlement" not in gaps
    assert "live campaign-settlement timing and file contents" in gaps
    assert "whether reused SpaceDamage objects are copied immediately" not in gaps
    assert "each earlier AddDropper record is insulated" in gaps
    assert "repeated native replacement cycles remain untraced" not in gaps
    assert "Startup record-type order and requested delay values are now statically pinned" in gaps
    assert "actual end-of-countdown outcome" not in gaps
    assert "replacement materialization is unresolved" not in gaps
    assert (
        "as are startup BigBomb drop resolution, conditional later "
        "occupied-enemy kill/recheck order"
        in gaps
    )
    assert (
        "concrete replacement coordinate, UID, surviving block state, and "
        "settled wall-clock timing"
        in gaps
    )
    assert (
        "not because repeat mechanics, ordinary startup spawn-block lifetime/"
        "drop resolution, pylon health, accepted-point materialization, or bomb "
        "destruction as a direct terminal mission loss are unresolved"
        in gaps
    )


def test_real_environment_final_volcano_record_pins_exact_current_payload_and_bounded_model():
    record = _mission_provenance_record("environment-final-volcano-cycle")
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/final/env_volcano.lua",
            "sha256": (
                "e3499feaaf71d01a78bd649915165ec1"
                "c6713d20baa39bb2ac12db7bb787ea16"
            ),
            "symbols": [
                "Env_Volcano", "Env_Volcano:Start",
                "Env_Volcano:MarkSpace", "Env_Volcano:SelectSpaces",
                "Env_Volcano:GetAttackEffect",
            ],
        },
        {
            "path": "scripts/environments.lua",
            "sha256": (
                "5f8a7d74f537abb33bc88c1f9669f3f"
                "6fabdd5c8c51aad3486d2e965e4fb80ec"
            ),
            "symbols": [
                "Env_Attack", "Env_Attack:Start", "Env_Attack:IsEffect",
                "Env_Attack:BlockSpawn", "Env_Attack:Plan",
                "Env_Attack:ApplyEffect", "Env_Attack:MarkBoard",
            ],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/bridge/modloader.lua"] == {
        "mission_final_volcano_points", "mission_final_volcano", "env_type",
        "environment_danger", "environment_danger_v2",
    }
    assert implementations["src/model/board.py"] == {
        "validate_mission_final_volcano_payload", "environment_volcano_known",
        "environment_volcano_locations", "from_bridge_data",
    }
    assert implementations["rust_solver/src/enemy.rs"] == {
        "apply_mission_final_volcano", "apply_volcano_lava",
        "apply_volcano_rock", "simulate_enemy_attacks",
    }
    assert implementations["src/loop/commands.py"] == {
        "_mission_final_volcano_payload_block", "cmd_solve",
        "cmd_click_end_turn", "cmd_dispatch_end_turn", "cmd_end_turn",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "phase 1 Lava, phase 2 Rocks, phase 3 Lava, and phase 4 Rocks" in facts
    assert "up to three random right-or-down steps" in facts
    assert "at most one randomly removed point per returned quarter" in facts
    assert "DAMAGE_DEATH, iFire=1" in facts
    assert "temporarily spawn-blocks every selected point" in facts
    assert "Two git-preserved live Mission_Final runs" in facts
    assert "remaining LavaStart" in facts
    assert "Projection clears the resolved payload" in facts
    assert "removed from the broad native-forecast gate" in facts
    gaps = " ".join(record["known_gaps"])
    assert "does not reproduce GetQuarters, random_removal" in gaps
    assert "cannot forecast a second future turn" in gaps
    assert "do not record their executable/depot/scripts build identity" in gaps
    assert "no fifth selection" in gaps
    assert "full scheduler conformance remain native dependencies" in gaps

    repo_root = Path(__file__).resolve().parents[1]
    historical = json.loads((
        repo_root
        / "data/observatory/captures/historical_git_mission_final_volcano_runs.json"
    ).read_text(encoding="utf-8"))
    assert historical["kind"] == (
        "historical_git_mission_final_volcano_corroboration"
    )
    assert [run["master_seed"] for run in historical["runs"]] == [
        125574395, 979832553,
    ]
    assert [record["mode"] for record in historical["runs"][0]["records"]] == [
        "lava", "rocks", "lava", "rocks",
    ]
    second_rocks = historical["runs"][1]["records"][1]
    assert second_rocks["queued_enemy_killed_before_attack"] == {
        "uid": 751,
        "type": "Scarab2",
        "tile": [6, 5],
        "player_plan_left_alive": True,
        "next_turn_present": False,
    }
    assert second_rocks["solve_git_blob_oid"] == (
        "114c922d55218492f9295440a97d1e0ed6c99b2d"
    )


def test_native_damage_death_record_pins_hp_boundary_without_tail_overclaim():
    record = _mission_provenance_record("native-damage-death-pawn-boundary")
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/final/env_final.lua",
            "sha256": (
                "8d9220a9f7c0b6f3887ec8b9ffdd351b"
                "25cd4c53696d2f401c81dbeb932a6f33"
            ),
            "symbols": ["Env_Final:GetAttackEffect"],
        },
        {
            "path": "scripts/missions/final/env_volcano.lua",
            "sha256": (
                "e3499feaaf71d01a78bd649915165ec1"
                "c6713d20baa39bb2ac12db7bb787ea16"
            ),
            "symbols": ["Env_Volcano:GetAttackEffect"],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/observatory/damage_death_boundary.py"] == {
        "build_damage_death_boundary_map",
        "validate_damage_death_boundary_map",
        "validate_damage_death_boundary_map_binding",
    }
    assert implementations["rust_solver/src/enemy.rs"] == {
        "apply_env_danger",
        "apply_mission_final_volcano",
        "apply_mission_final_cave",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "publishes DAMAGE_DEATH as integer 1000" in facts
    assert "Shield and Frozen invoke their registered clear setters" in facts
    assert "Armor subtracts one" in facts
    assert "ACID doubles the remaining positive damage" in facts
    assert "caps at minus-current HP" in facts
    assert "no flying or Massive predicate" in facts
    assert "separately mapped Building-terrain occupant-removal branch" in facts
    assert "continues in native-zero-hp-cleanup-boundary" in facts
    gaps = " ".join(record["known_gaps"])
    assert "structural dead-noncorpse Board-vector erase" in gaps
    assert "exact damage-relative lifecycle timing" in gaps
    assert "no subclass-specific IsCorpse implementation" in gaps
    assert "Lua OnKill dispatch" in gaps
    assert "kill credit and owner/team attribution" in gaps
    assert "other specialized post-zero vtable" in gaps
    assert "macOS and other Windows depot equivalence" in gaps

    repo_root = Path(__file__).resolve().parents[1]
    boundary = json.loads((
        repo_root
        / "data"
        / "observatory"
        / "native"
        / "windows_build_13725832_31fe35265598_damage_death_pawn_boundary.json"
    ).read_text(encoding="utf-8"))
    assert boundary["contracts"]["sentinel"]["native_integer"] == 1000
    assert boundary["contracts"]["hp_handoff"][
        "direct_pawn_kill_call_in_receiver_to_hp_chain"
    ] is False
    assert boundary["contracts"]["scope_limit"] == {
        "corpse_or_removal_timing_proven": False,
        "kill_credit_or_owner_attribution_proven": False,
        "lua_on_kill_dispatch_proven": False,
        "specialized_subclass_overrides_exhausted": False,
    }


def test_native_zero_hp_cleanup_record_pins_structural_erase_without_tail_overclaim():
    record = _mission_provenance_record("native-zero-hp-cleanup-boundary")
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/final/env_final.lua",
            "sha256": (
                "8d9220a9f7c0b6f3887ec8b9ffdd351b"
                "25cd4c53696d2f401c81dbeb932a6f33"
            ),
            "symbols": ["Env_Final:GetAttackEffect"],
        },
        {
            "path": "scripts/missions/final/env_volcano.lua",
            "sha256": (
                "e3499feaaf71d01a78bd649915165ec1"
                "c6713d20baa39bb2ac12db7bb787ea16"
            ),
            "symbols": ["Env_Volcano:GetAttackEffect"],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/observatory/zero_hp_cleanup_boundary.py"] == {
        "build_zero_hp_cleanup_boundary_map",
        "validate_zero_hp_cleanup_boundary_map",
        "validate_zero_hp_cleanup_boundary_map_binding",
    }
    assert implementations["scripts/itb_observatory_zero_hp_cleanup.py"] == {
        "main",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "18 reviewed regions" in facts
    assert "Later in the same Pawn HP-delta routine" in facts
    assert "direct Pawn:IsCorpse result of false" in facts
    assert "two instruction-aligned direct callers" in facts
    assert "All four exact OnKill string references" in facts
    assert "requires no simulator semantic change or version bump" in facts
    gaps = " ".join(record["known_gaps"])
    assert "exact cleanup-sweep timing" in gaps
    assert "corpse-classification successor closes the common Pawn:IsCorpse" in gaps
    assert "lifecycle states 2/3/4" in gaps
    assert "Generic or indirect Lua OnKill dispatch" in gaps
    assert "iKills, iMissionDamage, iKillCount" in gaps
    assert "GetDeathEffect, IsDeathEffect" in gaps
    assert "macOS and other Windows depot equivalence" in gaps

    repo_root = Path(__file__).resolve().parents[1]
    cleanup = json.loads((
        repo_root
        / "data"
        / "observatory"
        / "native"
        / "windows_build_13725832_31fe35265598_zero_hp_cleanup_boundary.json"
    ).read_text(encoding="utf-8"))
    assert cleanup["summary"] == {
        "absolute_reference_anchor_count": 9,
        "absolute_reference_count": 20,
        "callback_or_credit_tail_proven": False,
        "conditional_dead_noncorpse_board_erase_proven": True,
        "control_window_count": 7,
        "dependency_count": 2,
        "direct_edge_count": 6,
        "exact_cleanup_timing_proven": False,
        "finding_count": 8,
        "region_count": 18,
        "simulator_change_required": False,
        "unresolved_count": 6,
    }
    assert cleanup["contracts"]["board_cleanup"][
        "exact_direct_caller_rvas"
    ] == ["0x0016ae58", "0x001e9fb5"]
    assert cleanup["contracts"]["corpse_join"] == {
        "corpse_true_skips_reviewed_erase": True,
        "is_corpse_is_nontrivial_predicate": True,
        "retained_corpse_counts_path_occupancy": True,
        "retained_dead_noncorpse_counts_path_occupancy": False,
        "subclass_results_exhausted": False,
    }
    assert cleanup["contracts"]["callback_and_credit"][
        "lua_onkill_dispatch_proven"
    ] is False


def test_native_death_event_credit_record_pins_environment_split_without_onkill_overclaim():
    record = _mission_provenance_record("native-death-event-credit-boundary")
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/environments.lua",
            "sha256": (
                "5f8a7d74f537abb33bc88c1f9669f3f6"
                "fabdd5c8c51aad3486d2e965e4fb80ec"
            ),
            "symbols": ["Env_Attack:ApplyEffect", "ENV_EFFECT", "Board:AddEffect"],
        },
        {
            "path": "scripts/global.lua",
            "sha256": (
                "96d82d83a1620061e6fd013aa8462883e"
                "1f3764d03752757ad77fbbbd04bc9b2"
            ),
            "symbols": ["Skill", "Skill.OnKill"],
        },
        {
            "path": "scripts/advanced/ae_weapons.lua",
            "sha256": (
                "5566b679c696ab489e40a0189d0a63b6"
                "99d01e9657f79a20e6f119239af1680f"
            ),
            "symbols": [
                "Prime_KO_Crack:GetSkillEffect",
                "Brute_KO_Combo:GetSkillEffect",
                "Ranged_Arachnoid:GetSkillEffect",
                "Ranged_KO_Combo:GetSkillEffect",
                "Science_KO_Crack:GetSkillEffect",
                "Support_KO_GridCharger:GetSkillEffect",
            ],
        },
        {
            "path": "scripts/missions/missions.lua",
            "sha256": (
                "505c02a8668ba2e39d868f95051ede81c"
                "6cc1611f1e409219b6caa4fbe1d0257"
            ),
            "symbols": [
                "Mission:BaseUpdate",
                "Mission.KilledVek",
                "EVENT_ENEMY_KILLED",
            ],
        },
        {
            "path": "scripts/localization/Global_ae.csv",
            "sha256": (
                "b07fc5c5e2ffc0a167d538ae5f52c69c"
                "26e3560d949cb7837038a2252db3b01d"
            ),
            "symbols": ["Skill_OnKill"],
        },
        {
            "path": "scripts/localization/Weapons_ae.csv",
            "sha256": (
                "1b61022ce01ba36400056d6f871c9c6e"
                "0bfebb68f7911d52141ba76cc0fd76e2"
            ),
            "symbols": [
                "Prime_KO_Crack_OnKill",
                "Brute_KO_Combo_OnKill",
                "Ranged_Arachnoid_OnKill",
                "Ranged_KO_Combo_OnKill",
                "Science_KO_Crack_OnKill",
                "Support_KO_GridCharger_OnKill",
            ],
        },
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/observatory/death_event_credit_boundary.py"] == {
        "build_death_event_credit_boundary_map",
        "validate_death_event_credit_boundary_map",
        "validate_death_event_credit_boundary_map_binding",
    }
    assert implementations["scripts/itb_observatory_death_event_credit.py"] == {
        "main",
    }
    assert implementations["rust_solver/src/board.rs"] == {
        "record_enemy_kill",
        "unit_counts_for_mission_kill",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "24 reviewed regions" in facts
    assert "All seven OnKill occurrences" in facts
    assert "SkillEffect.iOwner to record offset +0x5c" in facts
    assert "ENV_EFFECT as integer -10" in facts
    assert "records event 2" in facts
    assert "other owners add victim XP to env_xp" in facts
    assert "iMissionDamage +0x1170 is a separate health-delta accumulator" in facts
    assert "No simulator semantic change or version bump is required" in facts
    gaps = " ".join(record["known_gaps"])
    assert "native-only consumers" in gaps
    assert "same outer update versus the next" in gaps
    assert "Achievement-specific event" in gaps
    assert "all consumers of any_kill_-10" in gaps
    assert "every writer of +0x1175" in gaps
    assert "macOS and other Windows depot equivalence" in gaps

    repo_root = Path(__file__).resolve().parents[1]
    boundary = json.loads((
        repo_root
        / "data"
        / "observatory"
        / "native"
        / "windows_build_13725832_31fe35265598_death_event_credit_boundary.json"
    ).read_text(encoding="utf-8"))
    assert boundary["summary"] == {
        "absolute_reference_anchor_count": 13,
        "absolute_reference_count": 27,
        "control_window_count": 37,
        "data_anchor_count": 1,
        "dependency_count": 1,
        "direct_edge_count": 15,
        "environment_mech_credit_bypass_proven": True,
        "environment_owner_pipeline_proven": True,
        "exact_event_frame_visibility_proven": False,
        "finding_count": 11,
        "mission_enemy_killed_event_proven": True,
        "region_count": 24,
        "shipped_lua_onkill_callback_proven": False,
        "simulator_change_required": False,
        "source_count": 6,
        "unresolved_count": 6,
    }
    assert boundary["contracts"]["owner_pipeline"] == {
        "board_effect_vector_offset": "+0x2c50",
        "context_owner_field_offset": "+0x00",
        "current_owner_address": "0x008bd254",
        "dispatcher_by_value_iowner_stack_offset": "+0x64",
        "environment_owner_name": "ENV_EFFECT",
        "environment_owner_pipeline_proven": True,
        "environment_owner_value": -10,
        "queued_copy_preserves_iowner": True,
        "skill_effect_iowner_offset": "+0x5c",
        "skill_effect_size_bytes": 124,
    }
    assert boundary["contracts"]["mission_event"]["event_enemy_killed_value"] == 2
    assert boundary["contracts"]["mission_event"][
        "exact_same_or_next_update_visibility_proven"
    ] is False
    assert boundary["contracts"]["credit"][
        "environment_generates_mech_xp_or_kill_bucket"
    ] is False
    assert boundary["contracts"]["credit"][
        "i_mission_damage_is_health_delta_not_death_credit"
    ] is True
    assert boundary["contracts"]["onkill"] == {
        "all_nonempty_values_are_localization_keys": True,
        "matching_lua_function_definition_count": 0,
        "mechanics_implemented_in_get_skill_effect": True,
        "native_only_offset_consumers_exhausted": False,
        "shipped_lua_callback_field_proven": False,
        "shipped_lua_occurrence_count": 7,
        "shipped_nonempty_value_count": 6,
    }


def test_native_event_frame_visibility_record_closes_board_death_timing():
    record = _mission_provenance_record("native-event-frame-visibility")
    assert record["coverage"] == "partial"
    assert record["sources"] == [
        {
            "path": "scripts/missions/missions.lua",
            "sha256": (
                "505c02a8668ba2e39d868f95051ede81c"
                "6cc1611f1e409219b6caa4fbe1d0257"
            ),
            "symbols": [
                "Mission:BaseUpdate",
                "Mission.KilledVek",
                "EVENT_ENEMY_KILLED",
            ],
        }
    ]
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["src/observatory/event_frame_visibility.py"] == {
        "build_event_frame_visibility_map",
        "validate_event_frame_visibility_map",
        "validate_event_frame_visibility_map_binding",
    }
    assert implementations[
        "scripts/itb_observatory_event_frame_visibility.py"
    ] == {"main"}
    assert implementations["rust_solver/src/board.rs"] == {
        "record_enemy_kill",
        "unit_counts_for_mission_kill",
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "13 reviewed regions" in facts
    assert "16 instruction-aligned control windows" in facts
    assert "nine direct edges" in facts
    assert "one direct pending-event publisher call" in facts
    assert "Game vtable maps +0x04" in facts
    assert "Board master/effect update before" in facts
    assert "same-update Mission:BaseUpdate cannot read it" in facts
    assert "next ordinary active-battle outer update" in facts
    assert "no simulator semantic change or version bump is required" in facts
    gaps = " ".join(record["known_gaps"])
    assert "event producers elsewhere" in gaps
    assert "cached-controller transfer helper" in gaps
    assert "not a fixed wall-clock duration" in gaps
    assert "macOS and other Windows depot equivalence" in gaps

    repo_root = Path(__file__).resolve().parents[1]
    visibility = json.loads((
        repo_root
        / "data"
        / "observatory"
        / "native"
        / "windows_build_13725832_31fe35265598_event_frame_visibility.json"
    ).read_text(encoding="utf-8"))
    assert visibility["summary"]["exact_event_frame_visibility_proven"] is True
    assert visibility["summary"]["same_outer_update_visibility"] is False
    assert visibility["summary"]["next_ordinary_outer_update_visibility"] is True
    assert visibility["contracts"]["board_death_visibility"][
        "visibility_delay_outer_updates"
    ] == 1
    assert visibility["solver_impact"]["simulator_change_required"] is False


def test_native_specialized_enemy_death_record_closes_classification_and_binds_v407():
    record = _mission_provenance_record("native-specialized-enemy-death-boundary")
    assert record["coverage"] == "partial"

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations[
        "src/observatory/specialized_enemy_death_boundary.py"
    ] == {
        "build_specialized_enemy_death_boundary_map",
        "validate_specialized_enemy_death_boundary_map",
        "validate_specialized_enemy_death_boundary_map_binding",
    }
    assert implementations[
        "scripts/itb_observatory_specialized_enemy_death.py"
    ] == {"main"}
    assert implementations["rust_solver/src/board.rs"] == {
        "unit_counts_for_mission_kill",
        "test_mission_kill_predicate_matches_native_enemy_event_gate",
        "test_acid_tank_mission_kill_keeps_native_gate_before_acid_filter",
    }
    assert implementations["rust_solver/src/lib.rs"] == {"SIMULATOR_VERSION"}
    assert implementations["src/solver/verify.py"] == {"SIMULATOR_VERSION"}
    assert implementations["src/bridge/modloader.lua"] == {
        "p:GetTeam",
        "p:IsMech",
        "pawn_def.Minor",
    }

    source_by_path = {source["path"]: source for source in record["sources"]}
    assert len(source_by_path) == 15
    assert source_by_path["scripts/global.lua"]["sha256"] == (
        "96d82d83a1620061e6fd013aa8462883e"
        "1f3764d03752757ad77fbbbd04bc9b2"
    )
    assert source_by_path["scripts/missions/bosses/boss.lua"]["sha256"] == (
        "9a957789e714c6d22d2f90bcd79dbb68"
        "c897aaa530e23d5be50cf7cf650853f1"
    )
    assert source_by_path["scripts/missions/bosses/goo.lua"]["symbols"] == [
        "BlobBoss",
        "BlobBossMed",
        "BlobBossSmall",
    ]
    assert source_by_path["scripts/missions/mission_tutorial.lua"]["symbols"] == [
        "Tank:SetMech",
        "Artillery:SetMech",
        "PunchMech:SetMech",
    ]

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "eight reviewed native regions" in facts
    assert "12 instruction-aligned control windows" in facts
    assert "one 0x1328-byte object" in facts
    assert "sole direct caller of the common death processor" in facts
    assert "17 active Minor=true Pawn definitions" in facts
    assert "21 nonempty Mission_Boss BossPawn values" in facts
    assert "BlobBossMed and BlobBossSmall" in facts
    assert "four boss-specific Minor auxiliaries" in facts
    assert "old Rust enemy-team-Mech discrepancy was therefore dormant" in facts
    assert "Simulator v407" in facts
    assert "failure_db_snapshot_sim_v406.jsonl" in facts

    gaps = " ".join(record["known_gaps"])
    assert "separate native Mech-death branch" in gaps
    assert "Mods may create enemy-team Mechs" in gaps
    assert "macOS and other Windows depot equivalence" in gaps

    repo_root = Path(__file__).resolve().parents[1]
    boundary = json.loads((
        repo_root
        / "data"
        / "observatory"
        / "native"
        / "windows_build_13725832_31fe35265598_"
        "specialized_enemy_death_boundary.json"
    ).read_text(encoding="utf-8"))
    assert boundary["summary"] == {
        "active_minor_type_count": 17,
        "boss_objective_type_count": 21,
        "call_inventory_count": 3,
        "control_window_count": 12,
        "data_anchor_count": 1,
        "dependency_count": 1,
        "direct_edge_count": 6,
        "finding_count": 7,
        "generic_factory_path_proven": True,
        "minor_boss_auxiliary_type_count": 4,
        "region_count": 8,
        "simulator_change_applied": True,
        "simulator_contradiction_found": True,
        "simulator_version": 407,
        "source_count": 15,
        "specialized_enemy_death_classes_proven": True,
        "unresolved_count": 3,
    }
    assert boundary["contracts"]["ordinary_enemy_event_predicate"] == {
        "event_2_id": 2,
        "event_2_name": "EVENT_ENEMY_KILLED",
        "event_2_required_is_mech_value": False,
        "event_2_required_minor_value": False,
        "event_2_required_team_value": 6,
        "leader_flag_is_a_gate": False,
        "mech_branch_is_separate": True,
        "minor_enemy_event_id": 12,
        "pawn_type_name_is_a_gate": False,
        "scope": "a Pawn death that reaches the common death processor",
        "tier_flag_is_a_gate": False,
    }
    assert boundary["contracts"]["solver_conformance"][
        "rust_predicate"
    ] == "enemy && !is_mech && !minor"
    assert boundary["contracts"]["solver_conformance"][
        "fixed_in_simulator_version"
    ] == 407


def test_native_corpse_classification_record_closes_static_inputs_without_timing_overclaim():
    record = _mission_provenance_record(
        "native-corpse-classification-boundary"
    )
    assert record["coverage"] == "partial"

    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations[
        "src/observatory/corpse_classification_boundary.py"
    ] == {
        "build_corpse_classification_boundary_map",
        "validate_corpse_classification_boundary_map",
        "validate_corpse_classification_boundary_map_binding",
    }
    assert implementations[
        "scripts/itb_observatory_corpse_classification.py"
    ] == {"main"}
    assert implementations["src/bridge/modloader.lua"] == {
        "p:IsCorpse",
        "pawn_def.Corpse",
        "corpse_on_death",
    }
    assert implementations["rust_solver/src/serde_bridge.rs"] == {
        "known_corpse_on_death_type",
        "corpse_on_death",
    }
    assert implementations["src/loop/commands.py"] == {
        "_mission_piston_forecast_block",
        "mission_piston_state_unknown",
    }

    source_by_path = {source["path"]: source for source in record["sources"]}
    assert len(source_by_path) == 13
    assert source_by_path["scripts/global.lua"]["sha256"] == (
        "96d82d83a1620061e6fd013aa8462883e"
        "1f3764d03752757ad77fbbbd04bc9b2"
    )
    assert source_by_path["scripts/advanced/ae_pawns.lua"]["symbols"] == [
        "Jelly_Necro1",
        "LEADER_NECRO",
    ]
    assert source_by_path[
        "scripts/missions/acid/mission_piston.lua"
    ]["symbols"] == [
        "Pawn_Piston_U",
        "Pawn_Piston_R",
        "Pawn_Piston_L",
        "Pawn_Piston_D",
    ]

    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "six native regions" in facts
    assert "27 raw-rel32 direct callers" in facts
    assert "no subclass-vtable dispatch" in facts
    assert "stores Corpse at +0xf80" in facts
    assert "maps value 12 to LEADER_NECRO" in facts
    assert "Jelly_Necro1 and LEADER_NECRO each occur only" in facts
    assert "ten explicit Corpse=true definitions" in facts
    assert "16 effective corpse types" in facts
    assert "simulator v407 remained current at its publication" in facts
    assert "independently advances the simulator to v408" in facts
    assert "later build-keyed Piston scheduler boundary closes" in facts

    gaps = " ".join(record["known_gaps"])
    assert "internal lifecycle states 2, 3, and 4" in gaps
    assert "Mission_Auto ordering for Mission_Piston" not in gaps
    assert "Mods or direct native calls may activate mutation 12" in gaps
    assert "macOS and other Windows depot equivalence" in gaps

    repo_root = Path(__file__).resolve().parents[1]
    boundary = json.loads((
        repo_root
        / "data"
        / "observatory"
        / "native"
        / "windows_build_13725832_31fe35265598_"
        "corpse_classification_boundary.json"
    ).read_text(encoding="utf-8"))
    assert boundary["summary"] == {
        "call_inventory_count": 3,
        "common_predicate_proven": True,
        "control_window_count": 10,
        "data_anchor_count": 8,
        "dependency_count": 2,
        "direct_edge_count": 1,
        "effective_corpse_type_count": 16,
        "explicit_corpse_type_count": 10,
        "finding_count": 6,
        "inherited_corpse_type_count": 6,
        "mutation_12_identity_proven": True,
        "region_count": 6,
        "shipped_mutation_12_reachable": False,
        "simulator_change_required": False,
        "simulator_contradiction_found": False,
        "simulator_version": 407,
        "source_count": 13,
        "unresolved_count": 2,
    }
    assert boundary["contracts"]["mutation_12_eligibility"][
        "registered_name"
    ] == "LEADER_NECRO"
    assert boundary["contracts"]["mutation_12_eligibility"][
        "teleporter_is_an_input"
    ] is False
    assert boundary["contracts"]["shipped_reachability"][
        "mutation_12_reachable_from_accepted_shipped_lua"
    ] is False
    assert boundary["contracts"]["solver_conformance"][
        "simulator_change_required"
    ] is False


def test_real_dormant_player_sources_record_pins_unrouted_legacy_semantics():
    record = _mission_provenance_record(
        "player-sources-dormant-experiment-structure"
    )
    assert record["coverage"] == "partial"
    assert record["implementations"] == []
    sources = {source["path"]: source for source in record["sources"]}
    assert sources["scripts/weapons_experiment.lua"] == {
        "path": "scripts/weapons_experiment.lua",
        "sha256": "75d277da5a2bd2ccd20baadd3b9aa43ba25f93eae75900da987fab08175e995d",
        "symbols": ["comment-only legacy placeholder (no Lua symbols)"],
    }
    assert sources["scripts/weapons_structure.lua"] == {
        "path": "scripts/weapons_structure.lua",
        "sha256": "a37f3379901ee5e4e8fa9c9e1596fff209868e411d39eea5d29043a231ab8353",
        "symbols": [
            "Pawn_Airfield", "AddPawn", "Structure_Force",
            "Structure_Force:GetSkillEffect", "Structure_Repair",
            "Structure_Repair:GetTargetArea", "Structure_Repair:GetSkillEffect",
        ],
    }
    assert sources["scripts/scripts.lua"]["symbols"] == ["GetScripts"]
    assert sources["scripts/weapons_base.lua"]["symbols"] == [
        "Grenade_Base", "Grenade_Base:GetTargetArea",
    ]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "comment-only legacy text" in facts
    assert "one damage at the selected center" in facts
    assert "every current TEAM_PLAYER pawn tile" in facts
    assert "dormant/unrouted legacy evidence" in facts
    gaps = " ".join(record["known_gaps"])
    assert "no stock runtime reachability" in gaps
    assert "must not be attributed to active Support_Repair" in gaps


def test_real_player_support_force_record_pins_active_drop_reachability_and_gap():
    record = _mission_provenance_record("player-weapon-support-force")
    assert record["coverage"] == "partial"
    sources = {source["path"]: source for source in record["sources"]}
    assert sources["scripts/weapons_support.lua"] == {
        "path": "scripts/weapons_support.lua",
        "sha256": "f5fc6be6bde2aae2676f29c39b45fe039d2a81537608e1f43e17ebc3ecda1855",
        "symbols": ["Support_Force", "Support_Force:GetSkillEffect"],
    }
    assert sources["scripts/weapons_base.lua"] == {
        "path": "scripts/weapons_base.lua",
        "sha256": "bdb55457746d08b46e8b62ad7cfc27f0a08bde9fab7397a4780dfe945b5f8f38",
        "symbols": ["Grenade_Base", "Grenade_Base:GetTargetArea"],
    }
    assert sources["scripts/drops.lua"] == {
        "path": "scripts/drops.lua",
        "sha256": "bfde13bbdfbdaa4f8fdb7c3f5ce0c84e4045bc538835143ec750cffaa79936ff",
        "symbols": ["weapon_list", "pod_list", "getWeaponDrop", "checkWeaponDeck"],
    }
    implementations = {
        reference["path"]: set(reference["symbols"])
        for reference in record["implementations"]
    }
    assert implementations["data/known_types.json"] == {"SupportForce"}
    assert implementations["src/model/weapons.py"] == {"Support_Force"}
    assert implementations["rust_solver/src/weapons.rs"] == {
        "WId::SupportForce", "is_support_force", "wid_from_str", "wid_to_str",
        "weapon_name",
    }
    assert implementations["rust_solver/src/solver.rs"] == {
        "get_weapon_targets", "weapon_action_has_effect", "enumerate_actions",
    }
    assert implementations["rust_solver/src/simulate.rs"] == {"simulate_weapon"}
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "every board coordinate, including the firing tile" in facts
    assert "four zero-damage cardinal SpaceDamage effects" in facts
    assert "stock drop/deck reachable" in facts
    assert "Simulator v399" in facts
    assert "64 source-legal targets" in facts
    gaps = " ".join(record["known_gaps"])
    assert "Limited=1" in gaps
    assert "exact cross-turn use depletion" in gaps
    assert "particular campaign's RNG result" in gaps


def test_real_mission_freezemines_record_pins_inherited_native_gap():
    record = _mission_provenance_record("mission-freezemines-inherited-placement")
    assert record["coverage"] == "partial"
    source = record["sources"][0]
    assert source == {
        "path": "scripts/missions/snow/mission_freezemines.lua",
        "sha256": "a1b3389a818218d42d9eb4446cabaa5716b0b116c69d4ebbfb2af1fcc188474f",
        "symbols": ["Mission_FreezeMines"],
    }
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "no active top-level callback" in facts
    gaps = " ".join(record["known_gaps"])
    assert "Mission_MineBase inherited placement" in gaps
    assert "must not be interpreted as callback coverage" in gaps


def test_real_mission_stasis_record_avoids_inferred_objective():
    record = _mission_provenance_record("mission-stasis-frozen-critical-bots")
    assert record["coverage"] == "partial"
    source = record["sources"][0]
    assert source["path"] == "scripts/missions/snow/mission_stasis.lua"
    assert source["sha256"] == (
        "1351366c1b32bb146186c61370bb0b6f1be8033dcada3d22a0a705641e6123a8"
    )
    assert source["symbols"] == [
        "Mission_Stasis", "Mission_Stasis:StartMission", "Mission_Stasis:UpdateMission",
    ]
    facts = " ".join(item["statement"] for item in record["evidence"])
    assert "does not receive Mission_Reactivation" in facts
    gaps = " ".join(record["known_gaps"])
    assert "does not infer such semantics" in gaps
    assert "no objective, completed-status, reward" in gaps
