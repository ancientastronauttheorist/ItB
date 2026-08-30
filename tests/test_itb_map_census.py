"""Focused proofs for the build-keyed static map-data census."""

from __future__ import annotations

import copy
import json
import struct
from pathlib import Path

import pytest

from scripts import itb_map_census
from src.observatory.content_inventory import create_inventory
from src.observatory.lua_census import LuaCensusError
import src.observatory.map_census as map_census_module
from src.observatory.map_census import (
    MapCensusError,
    _build_identity,
    _canonical_sha256,
    build_map_census,
    encode_map_census,
    validate_map_census,
)


def _write_pe(path: Path, machine: int = 0x014C) -> None:
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<H", data, 132, machine)
    path.write_bytes(data)


def _default_map() -> str:
    return """
synthetic = {
    ["version"] = 7,
    ["dimensions"] = Point(8,8),
    ["name"] = "synthetic",
    ["map"] = {
        {["loc"]=Point(1,2),["terrain"]=4,["custom"]="ground_test.png"},
        {["loc"]=Point(3,4),["terrain"]=1,["populated"]=1,["health_max"]=4},
    },
    ["spawns"] = {},
    ["spawn_ids"] = {},
    ["spawn_points"] = {},
    ["zones"] = {["deployment"]={Point(0,0),Point(1,0)}},
    ["tags"] = {"generic","any_sector"},
    ["blocked_points"] = {},
    ["blocked_type"] = {},
}
-- RAW_SOURCE_SENTINEL_MUST_NOT_BE_PUBLISHED
""".lstrip()


def _installation(
    tmp_path: Path,
    *,
    map_source: str | None = None,
) -> tuple[Path, dict, dict, dict]:
    steamapps = tmp_path / "Steam/steamapps"
    root = steamapps / "common/Into the Breach"
    (root / "scripts").mkdir(parents=True)
    (root / "maps").mkdir()
    (root / "maps/maphelper.lua").write_text(
        "function AddMap(name) return name end\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "maps/synthetic.map").write_text(
        map_source or _default_map(),
        encoding="utf-8",
        newline="\n",
    )
    _write_pe(root / "Breach.exe")
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
        label="synthetic-map-census",
    )
    files = []
    for entry in inventory["content"]["maps"]["files"]:
        is_helper = entry["path"] == "maps/maphelper.lua"
        files.append(
            {
                **entry,
                "collection": "maps",
                "disposition": (
                    "accepted_map_bootstrap_lua_analyzed"
                    if is_helper
                    else "accepted_map_data_lua_analyzed"
                ),
                "compile_status": "compiled_not_executed",
                "compiled_chunks": 1,
                "function_prototypes": 1 if is_helper else 0,
                "instruction_count": 5 if is_helper else 20,
            }
        )
    lua_census = {
        "schema_version": 1,
        "analysis_kind": "itb_lua51_compiled_census",
        "build_identity": _build_identity(inventory),
        "inventory": {"canonical_sha256": _canonical_sha256(inventory)},
        "files": files,
    }
    callback_index = {"analysis_kind": "synthetic_callback_index"}
    return root, inventory, lua_census, callback_index


@pytest.fixture(autouse=True)
def _verified_synthetic_lua_census(monkeypatch: pytest.MonkeyPatch):
    def verify(
        install_root: Path,
        evidence: dict,
        *,
        inventory: dict,
        callback_index: dict,
        rustc: Path | None = None,
    ) -> dict:
        del install_root, callback_index, rustc
        identity = _build_identity(inventory)
        if evidence.get("build_identity") != identity:
            raise LuaCensusError("synthetic Lua census build identity mismatch")
        return {
            "analysis_kind": "itb_lua51_compiled_census_verification",
            "status": "verified",
            "build_identity": identity,
            "evidence_sha256": _canonical_sha256(evidence),
        }

    monkeypatch.setattr(map_census_module, "validate_lua_census", verify)


def test_map_census_is_deterministic_and_does_not_publish_layouts(tmp_path: Path):
    root, inventory, lua_census, callback_index = _installation(tmp_path)
    result = build_map_census(
        root,
        inventory=inventory,
        lua_census=lua_census,
        callback_index=callback_index,
    )

    assert result["analysis_kind"] == "itb_static_map_data_census"
    assert result["summary"] == {
        "map_directory_entries": 2,
        "map_data_chunks": 1,
        "maphelper_lua_files": 1,
        "map_directory_bytes": sum(
            entry["size"] for entry in inventory["content"]["maps"]["files"]
        ),
        "strictly_parsed_chunks": 1,
        "compiled_chunks_crosschecked": 1,
        "global_names_matching_file_stems": 1,
        "name_fields_present": 1,
        "name_fields_absent": 0,
        "root_field_schemas": 1,
        "explicit_tiles": 2,
        "minimum_explicit_tiles_per_map": 2,
        "maximum_explicit_tiles_per_map": 2,
        "tile_field_schemas": 2,
        "unique_tile_locations_observed": 2,
        "maps_with_unique_in_bounds_tile_locations": 1,
        "maps_with_empty_spawn_tables": 1,
        "maps_with_block_field_pair": 1,
        "maps_with_enemy_kills_field": 0,
        "zone_keys": 1,
        "zone_instances": 1,
        "zone_points": 2,
        "maps_with_zones": 1,
        "tags": 2,
        "tag_values": 2,
        "maps_with_tags": 1,
        "schema_violations": 0,
    }
    rendered = encode_map_census(result)
    assert "RAW_SOURCE_SENTINEL_MUST_NOT_BE_PUBLISHED" not in rendered
    assert "Point(1,2)" not in rendered
    assert "ground_test.png" in rendered
    assert "normalized_data_sha256" not in rendered
    assert "ordered_tiles_sha256" not in rendered
    assert "ordered_points_sha256" not in rendered
    assert "ordered_zones_sha256" not in rendered
    assert "ordered_tags_sha256" not in rendered
    map_record = result["maps"][0]
    assert set(map_record) == {
        "dimensions",
        "global_matches_file_stem",
        "global_name",
        "name_field",
        "optional_root_fields",
        "optional_tile_field_counts",
        "path",
        "root_field_sequence",
        "sha256",
        "size",
        "tag_count",
        "terrain_counts",
        "tile_count",
        "tile_schema_counts",
        "version",
        "zone_count",
        "zones",
    }
    assert all(
        set(zone) == {"key", "point_count"} for zone in map_record["zones"]
    )

    rebuilt = build_map_census(
        root,
        inventory=inventory,
        lua_census=lua_census,
        callback_index=callback_index,
    )
    assert rebuilt == result
    verification = validate_map_census(
        root,
        result,
        inventory=inventory,
        lua_census=lua_census,
        callback_index=callback_index,
    )
    assert verification["status"] == "verified"
    assert verification["evidence_sha256"] == _canonical_sha256(result)


def test_map_census_rejects_stale_installation_and_lua_crosscheck(tmp_path: Path):
    root, inventory, lua_census, callback_index = _installation(tmp_path)
    (root / "maps/synthetic.map").write_text(
        _default_map() + "-- changed\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(MapCensusError, match="does not match the supplied"):
        build_map_census(
            root,
            inventory=inventory,
            lua_census=lua_census,
            callback_index=callback_index,
        )

    root, inventory, lua_census, callback_index = _installation(tmp_path / "other")
    stale = copy.deepcopy(lua_census)
    stale["build_identity"]["build_id"] = "999"
    with pytest.raises(MapCensusError, match="build identity"):
        build_map_census(
            root,
            inventory=inventory,
            lua_census=stale,
            callback_index=callback_index,
        )


@pytest.mark.parametrize(
    "map_body, message",
    [
        (
            '{["loc"]=Point(1,2),["terrain"]=4},'
            '{["loc"]=Point(1,2),["terrain"]=3}',
            "duplicate tile location",
        ),
        ('{["loc"]=Point(8,2),["terrain"]=4}', "out of bounds"),
        ('{["loc"]=Point(1,2),["terrain"]=4,["mystery"]=1}', "unknown fields"),
    ],
)
def test_map_census_rejects_invalid_tile_schema(
    tmp_path: Path,
    map_body: str,
    message: str,
):
    source = _default_map().replace(
        '{["loc"]=Point(1,2),["terrain"]=4,["custom"]="ground_test.png"},\n'
        '        {["loc"]=Point(3,4),["terrain"]=1,["populated"]=1,["health_max"]=4}',
        map_body,
    )
    root, inventory, lua_census, callback_index = _installation(
        tmp_path, map_source=source
    )
    with pytest.raises(MapCensusError, match=message):
        build_map_census(
            root,
            inventory=inventory,
            lua_census=lua_census,
            callback_index=callback_index,
        )


def test_map_census_rejects_name_mismatch_and_nonempty_source_table(tmp_path: Path):
    mismatched = _default_map().replace('"name"] = "synthetic"', '"name"] = "other"')
    root, inventory, lua_census, callback_index = _installation(
        tmp_path / "name", map_source=mismatched
    )
    with pytest.raises(MapCensusError, match="name field"):
        build_map_census(
            root,
            inventory=inventory,
            lua_census=lua_census,
            callback_index=callback_index,
        )

    nonempty = _default_map().replace('["spawns"] = {}', '["spawns"] = {1}')
    root, inventory, lua_census, callback_index = _installation(
        tmp_path / "spawns", map_source=nonempty
    )
    with pytest.raises(MapCensusError, match="unsupported nonempty schema"):
        build_map_census(
            root,
            inventory=inventory,
            lua_census=lua_census,
            callback_index=callback_index,
        )


def test_map_census_requires_actual_lua_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root, inventory, lua_census, callback_index = _installation(tmp_path)

    def reject(*args, **kwargs):
        del args, kwargs
        raise LuaCensusError("deliberate verifier rejection")

    monkeypatch.setattr(map_census_module, "validate_lua_census", reject)
    with pytest.raises(MapCensusError, match="deliberate verifier rejection"):
        build_map_census(
            root,
            inventory=inventory,
            lua_census=lua_census,
            callback_index=callback_index,
        )


def test_map_census_rejects_unpublishable_string_domains(tmp_path: Path):
    source = _default_map().replace(
        '"ground_test.png"', '"arbitrary prose must not enter evidence"'
    )
    root, inventory, lua_census, callback_index = _installation(
        tmp_path, map_source=source
    )
    with pytest.raises(MapCensusError, match="bounded publishable asset basename"):
        build_map_census(
            root,
            inventory=inventory,
            lua_census=lua_census,
            callback_index=callback_index,
        )


def test_cli_atomic_writer_is_confined_and_kind_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output_root = tmp_path / "maps"
    monkeypatch.setattr(itb_map_census, "_OUTPUT_ROOT", output_root)
    destination = output_root / "census.json"
    rendered = json.dumps(
        {"analysis_kind": "itb_static_map_data_census"},
        sort_keys=True,
    ) + "\n"
    itb_map_census._write_evidence_atomically(destination, rendered)
    assert destination.read_text(encoding="utf-8") == rendered

    destination.write_text(
        json.dumps({"analysis_kind": "something_else"}),
        encoding="utf-8",
    )
    with pytest.raises(MapCensusError, match="non-map-census"):
        itb_map_census._write_evidence_atomically(destination, rendered)
    with pytest.raises(MapCensusError, match="direct child"):
        itb_map_census._write_evidence_atomically(
            output_root / "nested/census.json",
            rendered,
        )
