"""Tests for build-keyed player-weapon lexical coverage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.itb_weapon_coverage import main as coverage_main
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    analyze_player_weapon_ids,
)


HASH = "a" * 64


def _write(path: Path, text: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    path.write_bytes(data)
    return {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _inventory(entries: list[dict]) -> dict:
    return {
        "platform": "windows",
        "executable": {"architecture": "x86", "sha256": HASH},
        "steam": {
            "build_id": "1",
            "installed_depots": [{"manifest": "2"}],
        },
        "content": {
            "scripts": {"revision_sha256": "b" * 64, "files": entries},
            "maps": {"revision_sha256": "c" * 64},
        },
    }


def _fixture(tmp_path: Path) -> tuple[dict, Path, Path]:
    content_root = tmp_path / "game"
    prime = (
        "Prime_Test = Skill:new{\n}\n"
        "function Prime_Test:GetSkillEffect(p1,p2)\nend\n"
    )
    ranged = "Ranged_Missing = Skill:new { Damage = 1 }\n"
    ignored = "Vek_Test = Skill:new{\n}\n"
    entries = []
    for relative, text in [
        ("scripts/weapons_prime.lua", prime),
        ("scripts/weapons_ranged.lua", ranged),
        ("scripts/weapons_enemy.lua", ignored),
    ]:
        metadata = _write(content_root / relative, text)
        entries.append({"path": relative, **metadata})
    rust_source = tmp_path / "weapons.rs"
    rust_source.write_text(
        "#[repr(u8)]\n"
        "pub enum WId {\n"
        "  None = 0,\n"
        "  PrimeTest = 1,\n"
        "  EnemyTest = 2,\n"
        "  Other = 3,\n"
        "}\n"
        'pub fn wid_from_str(s: &str) -> WId {\n'
        '  match s {\n'
        '    "Prime_Test" => WId::PrimeTest,\n'
        '    "Enemy_Test" => WId::EnemyTest,\n'
        "    _ => WId::None,\n"
        "  }\n"
        "}\n"
        "pub fn wid_to_str(id: WId) -> &'static str { \"\" }\n",
        encoding="utf-8",
    )
    return _inventory(entries), content_root, rust_source


def test_lexical_coverage_is_exact_deterministic_and_scoped(tmp_path: Path):
    inventory, content_root, rust_source = _fixture(tmp_path)
    first = analyze_player_weapon_ids(
        inventory,
        content_root=content_root,
        rust_source=rust_source,
    )
    inventory["content"]["scripts"]["files"].reverse()
    second = analyze_player_weapon_ids(
        inventory,
        content_root=content_root,
        rust_source=rust_source,
    )
    rust_source.write_bytes(
        rust_source.read_bytes().replace(b"\r\n", b"\n")
    )
    third = analyze_player_weapon_ids(
        inventory,
        content_root=content_root,
        rust_source=rust_source,
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(
        second, sort_keys=True
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(
        third, sort_keys=True
    )
    assert str(tmp_path) not in json.dumps(first)
    assert [source["path"] for source in first["files"]] == [
        "scripts/weapons_prime.lua",
        "scripts/weapons_ranged.lua",
    ]
    definitions = {
        item["lua_id"]: item for item in first["definitions"]
    }
    assert definitions["Prime_Test"]["rust_mapping"] == {
        "status": "exact",
        "wid_variant": "PrimeTest",
        "discriminant": 1,
    }
    assert definitions["Prime_Test"]["methods"] == ["GetSkillEffect"]
    assert definitions["Ranged_Missing"]["rust_mapping"]["status"] == "absent"
    assert "Vek_Test" not in definitions
    assert first["summary"] == {
        "source_files": 2,
        "constructor_candidates": 2,
        "aliases": 0,
        "definition_instances": 2,
        "unique_lua_ids": 2,
        "exact_wid_mapped_unique_ids": 1,
        "absent_wid_mapping_unique_ids": 1,
        "ambiguous_lua_ids": 0,
        "rust_only_mappings": 1,
        "many_to_one_wid_variants": 0,
    }
    assert "weapon behavior" in first["method"]["not_claimed"]


def test_coverage_fails_closed_on_stale_inventory_hash(tmp_path: Path):
    inventory, content_root, rust_source = _fixture(tmp_path)
    inventory["content"]["scripts"]["files"][0]["sha256"] = "0" * 64
    with pytest.raises(WeaponCoverageError, match="stale"):
        analyze_player_weapon_ids(
            inventory,
            content_root=content_root,
            rust_source=rust_source,
        )


def test_coverage_rejects_duplicate_rust_mapping(tmp_path: Path):
    inventory, content_root, rust_source = _fixture(tmp_path)
    rust_source.write_text(
        "#[repr(u8)]\n"
        "pub enum WId {\n"
        "  None = 0,\n"
        "  PrimeTest = 1,\n"
        "  Other = 2,\n"
        "}\n"
        'pub fn wid_from_str(s: &str) -> WId {\n'
        '  match s {\n'
        '    "Prime_Test" => WId::PrimeTest,\n'
        '    "Prime_Test" => WId::Other,\n'
        "  }\n"
        "}\n"
        "pub fn wid_to_str(id: WId) -> &'static str { \"\" }\n",
        encoding="utf-8",
    )
    with pytest.raises(WeaponCoverageError, match="duplicate"):
        analyze_player_weapon_ids(
            inventory,
            content_root=content_root,
            rust_source=rust_source,
        )


def test_coverage_cli_emits_json(tmp_path: Path, capsys):
    inventory, content_root, rust_source = _fixture(tmp_path)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    assert (
        coverage_main(
            [
                str(inventory_path),
                str(content_root),
                "--rust-source",
                str(rust_source),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["analysis_kind"] == "lua_rust_weapon_id_index"
    assert output["rust_source"]["path"] == "weapons.rs"


def test_coverage_cli_reports_invalid_json_without_traceback(
    tmp_path: Path, capsys
):
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text('{"duplicate": 1, "duplicate": 2}')
    assert coverage_main([str(inventory_path), str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error:")


def test_lua_lexer_ignores_opaque_and_function_local_candidates(
    tmp_path: Path,
):
    inventory, content_root, rust_source = _fixture(tmp_path)
    prime_path = content_root / "scripts/weapons_prime.lua"
    prime = """
-- Fake_Line = Skill:new{}
--[=[
Fake_Long_Comment = Skill:new{}
]=]
local Fake_Local = Skill:new{}
local short = "Fake_String = Skill:new{}"
local long = [==[Fake_Long_String = Skill:new{}]==]
Prime_Active = Skill:new
{
}
Prime_Referenced = Skill:new(Prime_Referenced)
Fake_Reference_Suffix = Skill:new(Prime_Referenced) + 1
Fake_Table_Suffix = Skill:new{} + 1
if enabled then
  Prime_Conditional = Prime_Active:new{}
end
function helper()
  function Prime_Active:GetFinalEffect(p1,p2)
  end
  Fake_Function_Global = Skill:new{}
  do
    Fake_Nested_Do = Skill:new{}
  end
end
Prime_Alias = Prime_Active
Not_An_Alias = MissingTarget
"""
    metadata = _write(prime_path, prime)
    inventory["content"]["scripts"]["files"][0].update(metadata)
    rust_source.write_text(
        "#[repr(u8)]\n"
        "pub enum WId {\n"
        "  None = 0,\n"
        "  PrimeActive = 1,\n"
        "  PrimeConditional = 2,\n"
        "  PrimeReferenced = 3,\n"
        "  PrimeAlias = 4,\n"
        "}\n"
        "pub fn wid_from_str(s: &str) -> WId {\n"
        "  match s {\n"
        '    "Prime_Active" => WId::PrimeActive,\n'
        '    "Prime_Conditional" => WId::PrimeConditional,\n'
        '    "Prime_Referenced" => WId::PrimeReferenced,\n'
        '    "Prime_Alias" => WId::PrimeAlias,\n'
        "    _ => WId::None,\n"
        "  }\n"
        "}\n"
        "pub fn wid_to_str(id: WId) -> &'static str { \"\" }\n",
        encoding="utf-8",
    )
    result = analyze_player_weapon_ids(
        inventory,
        content_root=content_root,
        rust_source=rust_source,
    )
    prime_definitions = [
        item
        for item in result["definitions"]
        if item["source_path"] == "scripts/weapons_prime.lua"
    ]
    assert {
        item["lua_id"] for item in prime_definitions
    } == {
        "Prime_Active",
        "Prime_Conditional",
        "Prime_Referenced",
        "Prime_Alias",
    }
    referenced = next(
        item
        for item in prime_definitions
        if item["lua_id"] == "Prime_Referenced"
    )
    assert referenced["definition_kind"] == "constructor-reference"
    assert referenced["constructor_argument"] == "Prime_Referenced"
    assert next(
        item
        for item in prime_definitions
        if item["lua_id"] == "Prime_Active"
    )["methods"] == []
    assert result["summary"]["constructor_candidates"] == 4
    assert result["summary"]["aliases"] == 1


def test_many_to_one_rust_mappings_are_preserved(tmp_path: Path):
    inventory, content_root, rust_source = _fixture(tmp_path)
    rust_source.write_text(
        "#[repr(u8)]\n"
        "pub enum WId {\n"
        "  None = 0,\n"
        "  Shared = 1,\n"
        "}\n"
        "pub fn wid_from_str(s: &str) -> WId {\n"
        "  match s {\n"
        '    "Prime_Test" => WId::Shared,\n'
        '    "Ranged_Missing" => WId::Shared,\n'
        "    _ => WId::None,\n"
        "  }\n"
        "}\n"
        "pub fn wid_to_str(id: WId) -> &'static str { \"\" }\n",
        encoding="utf-8",
    )
    result = analyze_player_weapon_ids(
        inventory,
        content_root=content_root,
        rust_source=rust_source,
    )
    assert result["many_to_one_wid_mappings"] == [
        {
            "wid_variant": "Shared",
            "discriminant": 1,
            "lua_ids": ["Prime_Test", "Ranged_Missing"],
        }
    ]


def test_duplicate_lua_ids_are_ambiguous_not_last_wins(tmp_path: Path):
    inventory, content_root, rust_source = _fixture(tmp_path)
    ranged_path = content_root / "scripts/weapons_ranged.lua"
    metadata = _write(
        ranged_path,
        "Prime_Test = OtherParent:new{}\n"
        "Ranged_Missing = Skill:new{}\n",
    )
    inventory["content"]["scripts"]["files"][1].update(metadata)
    result = analyze_player_weapon_ids(
        inventory,
        content_root=content_root,
        rust_source=rust_source,
    )
    duplicate_entries = [
        item for item in result["definitions"] if item["lua_id"] == "Prime_Test"
    ]
    assert len(duplicate_entries) == 2
    assert {
        item["rust_mapping"]["status"] for item in duplicate_entries
    } == {"ambiguous-lua-definition"}
    assert result["summary"]["ambiguous_lua_ids"] == 1


def test_variant_grouping_requires_an_exact_active_base(tmp_path: Path):
    inventory, content_root, rust_source = _fixture(tmp_path)
    prime_path = content_root / "scripts/weapons_prime.lua"
    metadata = _write(
        prime_path,
        "Prime_Base = Skill:new{}\n"
        "Prime_Base_A = Prime_Base:new{}\n"
        "Prime_Base_AB = Prime_Base:new{}\n"
        "Prime_Orphan_A = Skill:new{}\n",
    )
    inventory["content"]["scripts"]["files"][0].update(metadata)
    result = analyze_player_weapon_ids(
        inventory,
        content_root=content_root,
        rust_source=rust_source,
    )
    definitions = {
        item["lua_id"]: item for item in result["definitions"]
    }
    assert definitions["Prime_Base_A"]["family_id"] == "Prime_Base"
    assert definitions["Prime_Base_A"]["variant"] == "A"
    assert definitions["Prime_Base_AB"]["family_id"] == "Prime_Base"
    assert definitions["Prime_Base_AB"]["variant"] == "AB"
    assert definitions["Prime_Orphan_A"]["family_id"] == "Prime_Orphan_A"
    assert definitions["Prime_Orphan_A"]["variant"] is None


def test_rust_mapping_to_missing_wid_fails_closed(tmp_path: Path):
    inventory, content_root, rust_source = _fixture(tmp_path)
    rust_source.write_text(
        "#[repr(u8)]\n"
        "pub enum WId {\n"
        "  None = 0,\n"
        "}\n"
        "pub fn wid_from_str(s: &str) -> WId {\n"
        "  match s {\n"
        '    "Prime_Test" => WId::Missing,\n'
        "    _ => WId::None,\n"
        "  }\n"
        "}\n"
        "pub fn wid_to_str(id: WId) -> &'static str { \"\" }\n",
        encoding="utf-8",
    )
    with pytest.raises(WeaponCoverageError, match="missing WId"):
        analyze_player_weapon_ids(
            inventory,
            content_root=content_root,
            rust_source=rust_source,
        )


def test_rust_comments_do_not_create_variants_or_mappings(tmp_path: Path):
    inventory, content_root, rust_source = _fixture(tmp_path)
    rust_source.write_text(
        'const FAKE: &str = r#"pub enum WId {\n'
        '  RawGhost = 88,\n'
        '}\n'
        'pub fn wid_from_str(s: &str) -> WId {\n'
        '  "Raw_Ghost" => WId::RawGhost,\n'
        '}\n"#;\n'
        "/*\n"
        "#[repr(u8)]\n"
        "pub enum WId { GhostBoundary = 99, }\n"
        "*/\n"
        "#[repr(u8)]\n"
        "pub enum WId {\n"
        "  None = 0,\n"
        "  PrimeTest = 1,\n"
        "  /* Ghost = 2, /* nested */ */\n"
        "}\n"
        "pub fn wid_from_str(s: &str) -> WId {\n"
        "  match s {\n"
        '    "Prime_Test" => WId::PrimeTest,\n'
        '    /* "Ghost_ID" => WId::Ghost, */\n'
        '    // "Line_Ghost" => WId::Ghost,\n'
        "    _ => WId::None,\n"
        "  }\n"
        "}\n"
        "pub fn wid_to_str(id: WId) -> &'static str { \"\" }\n",
        encoding="utf-8",
    )
    result = analyze_player_weapon_ids(
        inventory,
        content_root=content_root,
        rust_source=rust_source,
    )
    assert result["rust_source"]["wid_variants"] == 2
    assert result["rust_source"]["wid_from_str_mappings"] == 1
    assert result["definitions"][0]["rust_mapping"]["wid_variant"] == (
        "PrimeTest"
    )


def test_aliases_must_reach_an_active_constructor(tmp_path: Path):
    inventory, content_root, rust_source = _fixture(tmp_path)
    prime_path = content_root / "scripts/weapons_prime.lua"
    metadata = _write(
        prime_path,
        "Prime_Root = Skill:new{}\n"
        "Prime_Chain_B = Prime_Root\n"
        "Prime_Chain_A = Prime_Chain_B\n"
        "Dangling_A = Dangling_B\n"
        "Dangling_B = Missing\n"
        "Cycle_A = Cycle_B\n"
        "Cycle_B = Cycle_A\n",
    )
    inventory["content"]["scripts"]["files"][0].update(metadata)
    result = analyze_player_weapon_ids(
        inventory,
        content_root=content_root,
        rust_source=rust_source,
    )
    ids = {item["lua_id"] for item in result["definitions"]}
    assert {"Prime_Root", "Prime_Chain_A", "Prime_Chain_B"} <= ids
    assert not ids.intersection(
        {"Dangling_A", "Dangling_B", "Cycle_A", "Cycle_B"}
    )
