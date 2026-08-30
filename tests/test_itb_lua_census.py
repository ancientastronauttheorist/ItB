"""Focused proofs for the build-keyed compiled Lua census."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from scripts import itb_lua_census
from src.observatory.content_inventory import create_inventory
from src.observatory.lua_census import (
    LuaCensusError,
    _build_identity,
    build_lua_census,
    encode_lua_census,
    validate_lua_census,
)


def _write_pe(path: Path, machine: int = 0x014C) -> None:
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<H", data, 132, machine)
    path.write_bytes(data)


def _installation(tmp_path: Path) -> tuple[Path, dict, dict]:
    steamapps = tmp_path / "Steam/steamapps"
    root = steamapps / "common/Into the Breach"
    (root / "scripts/localization").mkdir(parents=True)
    (root / "maps").mkdir()
    (root / "scripts/scripts.lua").write_text(
        """
function GetScripts()
    return {
        "scripts/global.lua",
        "scripts/feature.lua",
        -- "scripts/commented.lua",
        "user/missionData.lua",
        "scripts/modloader.lua",
    }
end
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    (root / "scripts/global.lua").write_text(
        """
CorpusGlobal = {}
function CorpusGlobal:outer(value)
    local secret = "TOP_SECRET_LITERAL_NEVER_PUBLISH"
    local function inner(item)
        return HostAPI:call(item, secret)
    end
    return inner(value)
end
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    (root / "scripts/feature.lua").write_text(
        """
local charset = dofile(GetWorkingDir().."scripts/localization/charset.lua")
local optional = false and dofile(dynamic_path)
Result = Engine.doThing(charset, optional)
_G[dynamic_name] = Result
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    (root / "scripts/nested.lua").write_text(
        "Dormant = function() return HostOnly end\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "scripts/localization/charset.lua").write_text(
        "return { ascii = true }\n",
        encoding="utf-8",
        newline="\n",
    )
    # The owner overlay is intentionally invalid Lua: exclusion must happen
    # before compilation, while its declared GetScripts edge remains visible.
    (root / "scripts/modloader.lua").write_text(
        "this is not valid Lua !!!\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "scripts/modloader.lua.codex-backup").write_text(
        "also not Lua\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "scripts/readme.txt").write_text("not Lua\n", encoding="utf-8")
    (root / "maps/maphelper.lua").write_text(
        "function GetMap() return SyntheticMap end\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "maps/synthetic.map").write_text(
        "SyntheticMap = { version = 7, width = 8, height = 8 }\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "maps/readme.txt").write_text("not Lua\n", encoding="utf-8")
    _write_pe(root / "Breach.exe")
    _write_pe(root / "lua5.1.dll")
    (steamapps / "appmanifest_590380.acf").write_text(
        '''
"AppState"
{
    "appid" "590380"
    "installdir" "Into the Breach"
    "buildid" "13725832"
    "InstalledDepots"
    {
        "590381" { "manifest" "123456789" "size" "1" }
    }
}
''',
        encoding="utf-8",
        newline="\n",
    )
    inventory = create_inventory(
        root,
        platform_name="windows",
        label="synthetic-lua-census",
    )
    global_entry = next(
        entry
        for entry in inventory["content"]["scripts"]["files"]
        if entry["path"] == "scripts/global.lua"
    )
    callback_index = {
        "analysis_kind": "lua_callback_provenance_index",
        "build_identity": _build_identity(inventory),
        "callbacks": [
            {
                "source_path": "scripts/global.lua",
                "source_sha256": global_entry["sha256"],
                "line": 2,
                "symbol": "CorpusGlobal:outer",
            }
        ],
    }
    return root, inventory, callback_index


def _build(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    pytest.importorskip("lupa.lua51")
    root, inventory, callback_index = _installation(tmp_path)
    result = build_lua_census(
        root,
        inventory=inventory,
        callback_index=callback_index,
    )
    return root, inventory, callback_index, result


def test_census_compiles_every_accepted_chunk_and_seals_static_routes(
    tmp_path: Path,
):
    root, inventory, callback_index, result = _build(tmp_path)

    assert result["analysis_kind"] == "itb_lua51_compiled_census"
    assert result["compiler"]["runtime_version"] == "Lua 5.1"
    assert result["compiler"]["game_chunks_executed"] is False
    expected_summary = {
        "accepted_script_lua_files": 5,
        "accepted_map_bootstrap_lua_files": 1,
        "accepted_map_data_lua_chunks": 1,
        "excluded_owner_lua_overlays": 1,
        "excluded_owner_overlay_backups": 1,
        "compiled_chunks": 7,
        "accepted_files_covered_by_load_model": 6,
        "accepted_files_unrouted_in_load_model": 1,
        "callback_definitions_crosschecked": 1,
    }
    for key, value in expected_summary.items():
        assert result["summary"][key] == value

    functions = result["functions"]
    outer = next(
        function
        for function in functions
        if function["symbol"] == "CorpusGlobal:outer"
    )
    inner = next(
        function for function in functions if function["symbol"] == "inner"
    )
    assert inner["parent_id"] == outer["id"]
    assert outer["serialized_prototype_sha256"]
    assert inner["source_span_sha256"]

    globals_by_name = {item["name"]: item for item in result["globals"]}
    assert globals_by_name["CorpusGlobal"]["classification"] == (
        "corpus_environment_defined"
    )
    assert globals_by_name["dofile"]["classification"] == (
        "lua51_standard_or_library"
    )
    assert globals_by_name["HostAPI"]["classification"] == (
        "unresolved_host_environment_candidate"
    )
    assert any(
        item["root"] == "HostAPI" and item["member"] == "call"
        for item in result["host_member_candidates"]
    )
    assert result["summary"]["global_table_index_sites"] == 1
    assert result["summary"]["global_table_write_sites"] == 1

    load_summary = result["load_graph"]["summary"]
    assert load_summary == {
        "modeled_edges": 8,
        "compiler_source_derived_edges": 5,
        "assumption_edges": 3,
        "host_bootstrap_assumptions": 2,
        "get_scripts_return_literal_edges": 4,
        "literal_dofile_site_edges": 1,
        "compiled_dofile_global_occurrences": 2,
        "unresolved_dofile_global_occurrences": 1,
        "map_directory_discovery_assumptions": 1,
        "accepted_analyzed_files": 7,
        "accepted_covered_by_load_model": 6,
        "accepted_unrouted_in_load_model": 1,
        "external_targets": 1,
        "declared_excluded_owner_overlays": 1,
        "duplicate_target_edges": 0,
    }
    edge_targets = [edge["target_path"] for edge in result["load_graph"]["edges"]]
    assert "scripts/commented.lua" not in edge_targets
    assert "user/missionData.lua" in edge_targets
    assert "scripts/modloader.lua" in edge_targets
    assert next(
        route
        for route in result["load_graph"]["file_routes"]
        if route["path"] == "scripts/nested.lua"
    )["route_status"] == "unrouted_in_static_load_model"

    rendered = encode_lua_census(result)
    assert "TOP_SECRET_LITERAL_NEVER_PUBLISH" not in rendered
    rebuilt = build_lua_census(
        root,
        inventory=inventory,
        callback_index=callback_index,
    )
    assert rebuilt == result
    verification = validate_lua_census(
        root,
        result,
        inventory=inventory,
        callback_index=callback_index,
    )
    assert verification["status"] == "verified"


def test_census_rejects_stale_inventory_and_callback_identity(tmp_path: Path):
    pytest.importorskip("lupa.lua51")
    root, inventory, callback_index = _installation(tmp_path)
    (root / "scripts/global.lua").write_text("changed\n", encoding="utf-8")
    with pytest.raises(LuaCensusError, match="does not match"):
        build_lua_census(
            root,
            inventory=inventory,
            callback_index=callback_index,
        )

    root, inventory, callback_index = _installation(tmp_path / "other")
    callback_index["build_identity"]["build_id"] = "wrong-build"
    with pytest.raises(LuaCensusError, match="callback index build identity"):
        build_lua_census(
            root,
            inventory=inventory,
            callback_index=callback_index,
        )


def test_census_rejects_compilation_failure_and_missing_callback(tmp_path: Path):
    pytest.importorskip("lupa.lua51")
    root, _, _ = _installation(tmp_path)
    (root / "scripts/nested.lua").write_text(
        "function broken() local = 1 end\n",
        encoding="utf-8",
    )
    inventory = create_inventory(
        root,
        platform_name="windows",
        label="synthetic-lua-census",
    )
    callback_index = {
        "analysis_kind": "lua_callback_provenance_index",
        "build_identity": _build_identity(inventory),
        "callbacks": [],
    }
    with pytest.raises(LuaCensusError, match="compilation failed"):
        build_lua_census(
            root,
            inventory=inventory,
            callback_index=callback_index,
        )

    root, inventory, callback_index = _installation(tmp_path / "other")
    callback_index["callbacks"][0]["symbol"] = "MissingCallback"
    with pytest.raises(LuaCensusError, match="missing from the compiled census"):
        build_lua_census(
            root,
            inventory=inventory,
            callback_index=callback_index,
        )


def test_get_scripts_requires_a_direct_returned_literal_table(tmp_path: Path):
    pytest.importorskip("lupa.lua51")
    root, _, _ = _installation(tmp_path)
    (root / "scripts/scripts.lua").write_text(
        """
function GetScripts()
    local decoy = "scripts/nested.lua"
    return {
        "scripts/global.lua",
        "scripts/feature.lua",
        "user/missionData.lua",
        "scripts/modloader.lua",
    }
end
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    inventory = create_inventory(
        root,
        platform_name="windows",
        label="synthetic-lua-census",
    )
    callback_index = {
        "analysis_kind": "lua_callback_provenance_index",
        "build_identity": _build_identity(inventory),
        "callbacks": [],
    }
    with pytest.raises(LuaCensusError, match="direct returned-table"):
        build_lua_census(
            root,
            inventory=inventory,
            callback_index=callback_index,
        )


def test_cli_atomic_writer_is_confined_and_kind_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output_root = tmp_path / "lua"
    monkeypatch.setattr(itb_lua_census, "_OUTPUT_ROOT", output_root)
    destination = output_root / "census.json"
    rendered = json.dumps(
        {"analysis_kind": "itb_lua51_compiled_census"},
        sort_keys=True,
    ) + "\n"
    itb_lua_census._write_evidence_atomically(destination, rendered)
    assert destination.read_text(encoding="utf-8") == rendered

    destination.write_text(
        json.dumps({"analysis_kind": "something_else"}),
        encoding="utf-8",
    )
    with pytest.raises(LuaCensusError, match="non-Lua-census"):
        itb_lua_census._write_evidence_atomically(destination, rendered)
    with pytest.raises(LuaCensusError, match="direct child"):
        itb_lua_census._write_evidence_atomically(
            output_root / "nested/census.json",
            rendered,
        )
