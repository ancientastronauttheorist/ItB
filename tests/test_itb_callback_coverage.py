"""Tests for exact Lua callback-to-provenance lexical coverage."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.itb_callback_coverage import main as callback_coverage_main
from src.observatory.callback_coverage import (
    CallbackCoverageError,
    analyze_lua_callback_provenance,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _write(path: Path, text: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    path.write_bytes(data)
    return {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _fixture(tmp_path: Path) -> tuple[dict, dict, Path, Path]:
    content_root = tmp_path / "game"
    global_metadata = _write(
        content_root / "scripts/global.lua",
        "-- function Ghost:Commented() end\n"
        'local opaque = "function Ghost:String() end"\n'
        "function ScorePositioning(point, pawn)\n"
        "  function Nested:Hidden()\n"
        "  end\n"
        "end\n"
        "function Skill:GetTargetScore(p1, p2)\n"
        "end\n"
        "Assigned.Callback = function()\n"
        "end\n"
        "Multi.Line =\n"
        "function\n"
        "()\n"
        "end\n"
        "function Package.Skill:GetTargetArea(p1)\n"
        "end\n"
        "local function LocalOnly()\n"
        "end\n"
        "local\n"
        "function MultilineLocal()\n"
        "end\n"
        "local\n"
        "LocalAssigned = function()\n"
        "end\n"
        "function Invalid:Middle:Tail()\n"
        "end\n"
        "Invalid:Assignment = function()\n"
        "end\n",
    )
    enemy_metadata = _write(
        content_root / "scripts/weapons_enemy.lua",
        "function FireflyAtk1:GetSkillEffect(p1, p2)\n"
        "end\n"
        "function ScorePositioning()\n"
        "end\n",
    )
    tides_metadata = _write(
        content_root / "scripts/missions/grass/mission_tides.lua",
        "function Env_Tides:Plan()\n"
        "end\n",
    )
    boss_metadata = _write(
        content_root / "scripts/advanced/bosses/starfish.lua",
        "function StarfishAtkB1:GetTargetScore(p1, p2)\n"
        "end\n",
    )
    inventory = {
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
                    {
                        "path": "scripts/global.lua",
                        **global_metadata,
                    },
                    {
                        "path": "scripts/weapons_enemy.lua",
                        **enemy_metadata,
                    },
                    {
                        "path": "scripts/missions/grass/mission_tides.lua",
                        **tides_metadata,
                    },
                    {
                        "path": "scripts/advanced/bosses/starfish.lua",
                        **boss_metadata,
                    },
                ],
            },
            "maps": {"revision_sha256": HASH_C},
        },
    }
    provenance = {
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
                        "sha256": global_metadata["sha256"],
                        "symbols": [
                            "ScorePositioning",
                            "Assigned.Callback",
                            "Skill:*",
                        ],
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
                        "statement": "The exact callbacks are indexed.",
                    }
                ],
                "known_gaps": ["Behavioral equivalence is unresolved."],
            }
        ],
    }
    inventory_path = tmp_path / provenance["inventory"]
    inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    rust_path = tmp_path / "rust_solver/src/turn_projection.rs"
    rust_path.parent.mkdir(parents=True)
    rust_path.write_text(
        "// requeue_enemies_heuristic test_projection",
        encoding="utf-8",
    )
    return inventory, provenance, content_root, inventory_path


def test_callback_coverage_is_exact_scoped_and_deterministic(tmp_path: Path):
    inventory, provenance, content_root, _inventory_path = _fixture(tmp_path)
    first = analyze_lua_callback_provenance(
        provenance,
        inventory,
        content_root=content_root,
        repo_root=tmp_path,
    )
    reordered_inventory = deepcopy(inventory)
    reordered_inventory["content"]["scripts"]["files"].reverse()
    (tmp_path / provenance["inventory"]).write_text(
        json.dumps(reordered_inventory),
        encoding="utf-8",
    )
    second = analyze_lua_callback_provenance(
        provenance,
        reordered_inventory,
        content_root=content_root,
        repo_root=tmp_path,
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(
        second,
        sort_keys=True,
    )
    assert str(tmp_path) not in json.dumps(first)
    callbacks = {
        (item["source_path"], item["symbol"]): item
        for item in first["callbacks"]
    }
    assert set(callbacks) == {
        ("scripts/global.lua", "ScorePositioning"),
        ("scripts/global.lua", "Skill:GetTargetScore"),
        ("scripts/global.lua", "Assigned.Callback"),
        ("scripts/global.lua", "Multi.Line"),
        ("scripts/global.lua", "Package.Skill:GetTargetArea"),
        ("scripts/weapons_enemy.lua", "FireflyAtk1:GetSkillEffect"),
        ("scripts/weapons_enemy.lua", "ScorePositioning"),
        ("scripts/missions/grass/mission_tides.lua", "Env_Tides:Plan"),
        (
            "scripts/advanced/bosses/starfish.lua",
            "StarfishAtkB1:GetTargetScore",
        ),
    }
    assert callbacks[
        ("scripts/global.lua", "ScorePositioning")
    ]["indexed_by"] == ["enemy-scoring"]
    assert callbacks[
        ("scripts/global.lua", "Assigned.Callback")
    ]["status"] == "indexed"
    assert callbacks[
        ("scripts/global.lua", "Skill:GetTargetScore")
    ]["status"] == "unindexed"
    assert callbacks[
        ("scripts/weapons_enemy.lua", "FireflyAtk1:GetSkillEffect")
    ]["status"] == "unindexed"
    assert callbacks[
        ("scripts/weapons_enemy.lua", "ScorePositioning")
    ]["status"] == "unindexed"
    assert first["summary"] == {
        "source_files": 4,
        "callback_definitions": 9,
        "unique_path_symbols": 9,
        "indexed_callbacks": 2,
        "unindexed_callbacks": 7,
        "provenance_records_used": 1,
    }
    assert first["categories"] == [
        {
            "category": "enemy-scoring",
            "callbacks": 5,
            "indexed_callbacks": 2,
            "unindexed_callbacks": 3,
        },
        {
            "category": "enemy-weapons",
            "callbacks": 3,
            "indexed_callbacks": 0,
            "unindexed_callbacks": 3,
        },
        {
            "category": "environments",
            "callbacks": 1,
            "indexed_callbacks": 0,
            "unindexed_callbacks": 1,
        },
        {
            "category": "missions",
            "callbacks": 1,
            "indexed_callbacks": 0,
            "unindexed_callbacks": 1,
        },
    ]


def test_callback_coverage_fails_closed_on_stale_source(tmp_path: Path):
    inventory, provenance, content_root, _inventory_path = _fixture(tmp_path)
    (content_root / "scripts/global.lua").write_text(
        "function Changed() end\n",
        encoding="utf-8",
    )
    with pytest.raises(CallbackCoverageError, match="stale"):
        analyze_lua_callback_provenance(
            provenance,
            inventory,
            content_root=content_root,
            repo_root=tmp_path,
        )


def test_callback_coverage_cli_emits_json(tmp_path: Path, capsys):
    inventory, provenance, content_root, inventory_path = _fixture(tmp_path)
    provenance_path = tmp_path / "provenance.json"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    assert (
        callback_coverage_main(
            [
                str(provenance_path),
                str(inventory_path),
                str(content_root),
                "--repo-root",
                str(tmp_path),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["analysis_kind"] == "lua_callback_provenance_index"
    assert output["summary"]["callback_definitions"] == 9


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda inventory: inventory["content"]["scripts"]["files"][1].update(
                {"path": "../weapons_enemy.lua"}
            ),
            "normalized relative path",
        ),
        (
            lambda inventory: inventory["content"]["scripts"]["files"][1].update(
                {"size": "invalid"}
            ),
            "invalid inventory size/hash",
        ),
    ],
)
def test_callback_coverage_translates_inventory_helper_failures(
    tmp_path: Path,
    mutation,
    message: str,
):
    inventory, provenance, content_root, inventory_path = _fixture(tmp_path)
    mutation(inventory)
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    with pytest.raises(CallbackCoverageError, match=message):
        analyze_lua_callback_provenance(
            provenance,
            inventory,
            content_root=content_root,
            repo_root=tmp_path,
        )


def test_callback_coverage_cli_reports_bad_file_metadata_without_traceback(
    tmp_path: Path,
    capsys,
):
    inventory, provenance, content_root, inventory_path = _fixture(tmp_path)
    inventory["content"]["scripts"]["files"][1]["size"] = "invalid"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    provenance_path = tmp_path / "provenance.json"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    assert (
        callback_coverage_main(
            [
                str(provenance_path),
                str(inventory_path),
                str(content_root),
                "--repo-root",
                str(tmp_path),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")


def test_callback_coverage_cli_reports_invalid_json_without_traceback(
    tmp_path: Path,
    capsys,
):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text('{"duplicate": 1, "duplicate": 2}', encoding="utf-8")
    assert (
        callback_coverage_main(
            [str(bad_path), str(bad_path), str(tmp_path)]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")
