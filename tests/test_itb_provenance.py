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
