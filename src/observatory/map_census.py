"""Build-keyed, non-executing census of Into the Breach map data chunks.

The census accepts only the small declarative Lua subset implemented by
``lua_data``.  It records structural facts and aggregate domains while keeping
raw source and reconstructable per-map coordinate layouts out of evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.content_inventory import InventoryError, create_inventory
from src.observatory.lua_data import (
    LuaDataChunk,
    LuaDataError,
    LuaPoint,
    LuaTable,
    LuaValue,
    parse_lua_data_chunk,
)
from src.observatory.lua_census import LuaCensusError, validate_lua_census
from src.observatory.pe_anchor_map import PEAnchorError, _inventory_identity
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    read_exact_inventory_file,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "itb_static_map_data_census"
VERIFICATION_KIND = "itb_static_map_data_census_verification"
LUA_CENSUS_ANALYSIS_KIND = "itb_lua51_compiled_census"
LUA_CENSUS_VERIFICATION_KIND = "itb_lua51_compiled_census_verification"
MAX_MAP_SOURCE_BYTES = 16 * 1024 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_PUBLISHED_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_PUBLISHED_ASSET_BASENAME_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z"
)
_MAX_PUBLISHED_IDENTIFIER_CHARACTERS = 128
_REQUIRED_ROOT_FIELDS = frozenset(
    {
        "version",
        "dimensions",
        "map",
        "spawns",
        "spawn_ids",
        "spawn_points",
        "zones",
        "tags",
    }
)
_OPTIONAL_ROOT_FIELDS = frozenset(
    {"name", "enemy_kills", "blocked_points", "blocked_type"}
)
_ROOT_FIELD_TYPES = {
    "version": "integer",
    "dimensions": "point",
    "name": "string",
    "enemy_kills": "integer",
    "map": "array",
    "spawns": "empty_array",
    "spawn_ids": "empty_array",
    "spawn_points": "empty_array",
    "zones": "keyed_point_arrays",
    "tags": "string_array",
    "blocked_points": "empty_array",
    "blocked_type": "empty_array",
}
_REQUIRED_TILE_FIELDS = frozenset({"loc", "terrain"})
_OPTIONAL_TILE_FIELD_TYPES = {
    "poison": "integer",
    "populated": "integer",
    "health_max": "integer",
    "health_min": "integer",
    "pawn": "string",
    "team": "integer",
    "lava": "boolean",
    "fire": "integer",
    "custom": "string",
}
_TILE_FIELD_TYPES = {
    "loc": "point",
    "terrain": "integer",
    **_OPTIONAL_TILE_FIELD_TYPES,
}


class MapCensusError(RuntimeError):
    """Raised when map inputs, schema, or evidence are not trustworthy."""


@dataclass(frozen=True)
class _ParsedMap:
    path: str
    size: int
    sha256: str
    chunk: LuaDataChunk
    root: dict[str, LuaValue]
    root_fields: tuple[str, ...]
    tiles: tuple[dict[str, LuaValue], ...]
    tile_fields: tuple[tuple[str, ...], ...]
    zones: tuple[tuple[str, tuple[LuaPoint, ...]], ...]
    tags: tuple[str, ...]


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MapCensusError(f"{label} must be an object")
    return value


def _canonical_sha256(value: Any) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256((rendered + "\n").encode("utf-8")).hexdigest()


def _build_identity(inventory: Mapping[str, Any]) -> dict[str, Any]:
    executable = _mapping(inventory.get("executable"), "inventory.executable")
    try:
        return _inventory_identity(
            inventory,
            sha256=executable["sha256"],
            size=executable["size"],
            architecture=executable["architecture"],
        )
    except (KeyError, PEAnchorError) as exc:
        raise MapCensusError(f"invalid inventory identity: {exc}") from exc


def _attest_installation(
    install_root: Path,
    inventory: Mapping[str, Any],
) -> tuple[Path, dict[str, Any]]:
    platform_name = inventory.get("platform")
    label = inventory.get("label")
    if type(platform_name) is not str or not platform_name:
        raise MapCensusError("inventory.platform must be text")
    if label is not None and type(label) is not str:
        raise MapCensusError("inventory.label must be text or null")
    try:
        live_inventory = create_inventory(
            install_root,
            platform_name=platform_name,
            label=label,
        )
    except (InventoryError, OSError, UnicodeError) as exc:
        raise MapCensusError(
            f"could not rebuild the installation inventory: {exc}"
        ) from exc
    if live_inventory != inventory:
        raise MapCensusError(
            "installation does not match the supplied sealed inventory"
        )
    content_root_value = live_inventory.get("content_root")
    if type(content_root_value) is not str or not content_root_value:
        raise MapCensusError("inventory.content_root must be text")
    relative = PurePosixPath(content_root_value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in content_root_value:
        raise MapCensusError("inventory.content_root is not canonical")
    root = install_root.expanduser().resolve()
    content_root = root.joinpath(*relative.parts)
    if not content_root.resolve().is_relative_to(root):
        raise MapCensusError("inventory content root escapes the installation")
    return content_root, _build_identity(live_inventory)


def _map_entries(
    inventory: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], Mapping[str, Any]]:
    content = _mapping(inventory.get("content"), "inventory.content")
    manifest = _mapping(content.get("maps"), "inventory.content.maps")
    values = manifest.get("files")
    if not isinstance(values, list):
        raise MapCensusError("inventory.content.maps.files must be an array")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        entry = _mapping(value, f"inventory map entry {index}")
        path = entry.get("path")
        size = entry.get("size")
        sha256 = entry.get("sha256")
        if type(path) is not str:
            raise MapCensusError(f"inventory map entry {index} has invalid path")
        relative = PurePosixPath(path)
        if (
            len(relative.parts) != 2
            or relative.parts[0] != "maps"
            or relative.is_absolute()
            or relative.as_posix() != path
            or "\\" in path
            or type(size) is not int
            or size < 0
            or type(sha256) is not str
            or not _SHA256_RE.fullmatch(sha256)
        ):
            raise MapCensusError(f"inventory map entry {index} is malformed")
        if path in seen:
            raise MapCensusError(f"duplicate inventory map path: {path}")
        if path != "maps/maphelper.lua" and relative.suffix != ".map":
            raise MapCensusError(f"unsupported map-directory entry: {path}")
        seen.add(path)
        entries.append({"path": path, "size": size, "sha256": sha256})
    if sum(entry["path"] == "maps/maphelper.lua" for entry in entries) != 1:
        raise MapCensusError("inventory must contain exactly one maps/maphelper.lua")
    if not any(entry["path"].endswith(".map") for entry in entries):
        raise MapCensusError("inventory contains no .map chunks")
    return sorted(entries, key=lambda entry: str(entry["path"])), manifest


def _crosscheck_lua_census(
    lua_census: Mapping[str, Any],
    *,
    verification: Mapping[str, Any],
    inventory: Mapping[str, Any],
    build_identity: Mapping[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    lua_census_sha256 = _canonical_sha256(lua_census)
    if (
        verification.get("analysis_kind") != LUA_CENSUS_VERIFICATION_KIND
        or verification.get("status") != "verified"
        or verification.get("build_identity") != build_identity
        or verification.get("evidence_sha256") != lua_census_sha256
    ):
        raise MapCensusError("Lua census verification result is malformed")
    if lua_census.get("analysis_kind") != LUA_CENSUS_ANALYSIS_KIND:
        raise MapCensusError("Lua census has the wrong analysis kind")
    if lua_census.get("build_identity") != build_identity:
        raise MapCensusError("Lua census build identity does not match inventory")
    lua_inventory = _mapping(lua_census.get("inventory"), "lua_census.inventory")
    if lua_inventory.get("canonical_sha256") != _canonical_sha256(inventory):
        raise MapCensusError("Lua census inventory identity does not match")
    values = lua_census.get("files")
    if not isinstance(values, list):
        raise MapCensusError("lua_census.files must be an array")
    records: dict[str, Mapping[str, Any]] = {}
    for index, value in enumerate(values):
        record = _mapping(value, f"Lua census file {index}")
        path = record.get("path")
        if type(path) is not str:
            raise MapCensusError(f"Lua census file {index} has invalid path")
        if path in records:
            raise MapCensusError(f"duplicate Lua census path: {path}")
        records[path] = record

    expected_map_paths = {
        entry["path"] for entry in entries if entry["path"].endswith(".map")
    }
    accepted_map_paths = {
        path
        for path, record in records.items()
        if record.get("disposition") == "accepted_map_data_lua_analyzed"
    }
    if accepted_map_paths != expected_map_paths:
        raise MapCensusError("Lua census accepted-map set does not match inventory")

    for entry in entries:
        path = entry["path"]
        record = records.get(path)
        if record is None:
            raise MapCensusError(f"Lua census is missing {path}")
        expected_disposition = (
            "accepted_map_bootstrap_lua_analyzed"
            if path == "maps/maphelper.lua"
            else "accepted_map_data_lua_analyzed"
        )
        expected = {
            "collection": "maps",
            "size": entry["size"],
            "sha256": entry["sha256"],
            "disposition": expected_disposition,
            "compile_status": "compiled_not_executed",
            "compiled_chunks": 1,
        }
        if any(record.get(key) != value for key, value in expected.items()):
            raise MapCensusError(f"Lua census record does not attest {path}")
        if path.endswith(".map") and record.get("function_prototypes") != 0:
            raise MapCensusError(f"map chunk unexpectedly defines functions: {path}")

    helper = records["maps/maphelper.lua"]
    return {
        "analysis_kind": lua_census.get("analysis_kind"),
        "canonical_sha256": lua_census_sha256,
        "verification": {
            "analysis_kind": verification.get("analysis_kind"),
            "status": verification.get("status"),
            "evidence_sha256": verification.get("evidence_sha256"),
        },
        "compiled_map_chunks": len(expected_map_paths),
        "maphelper": {
            "path": "maps/maphelper.lua",
            "size": helper.get("size"),
            "sha256": helper.get("sha256"),
            "compile_status": helper.get("compile_status"),
            "function_prototypes": helper.get("function_prototypes"),
            "instruction_count": helper.get("instruction_count"),
        },
    }


def _value_type(value: LuaValue) -> str:
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is str:
        return "string"
    if isinstance(value, LuaPoint):
        return "point"
    if isinstance(value, LuaTable):
        return "table"
    raise MapCensusError(f"unsupported parsed value type: {type(value).__name__}")


def _require_value_type(value: LuaValue, expected: str, label: str) -> None:
    if _value_type(value) != expected:
        raise MapCensusError(f"{label} must be {expected}")
    if expected == "string" and not value:
        raise MapCensusError(f"{label} must not be empty")


def _require_published_identifier(
    value: str,
    label: str,
    *,
    asset_basename: bool = False,
) -> None:
    pattern = (
        _PUBLISHED_ASSET_BASENAME_RE
        if asset_basename
        else _PUBLISHED_IDENTIFIER_RE
    )
    if (
        len(value) > _MAX_PUBLISHED_IDENTIFIER_CHARACTERS
        or not pattern.fullmatch(value)
    ):
        kind = "asset basename" if asset_basename else "identifier"
        raise MapCensusError(
            f"{label} is not a bounded publishable {kind}"
        )


def _validate_map_chunk(
    path: str,
    *,
    size: int,
    sha256: str,
    chunk: LuaDataChunk,
) -> _ParsedMap:
    relative = PurePosixPath(path)
    stem = relative.stem
    if chunk.global_name != stem:
        raise MapCensusError(
            f"{path}: global {chunk.global_name!r} does not match file stem"
        )
    root = chunk.value.require_pure_keyed(f"{path} root")
    root_fields = tuple(entry.key for entry in chunk.value.entries)
    present = set(root)
    missing = _REQUIRED_ROOT_FIELDS - present
    unknown = present - _REQUIRED_ROOT_FIELDS - _OPTIONAL_ROOT_FIELDS
    if missing:
        raise MapCensusError(f"{path}: missing root fields: {sorted(missing)}")
    if unknown:
        raise MapCensusError(f"{path}: unknown root fields: {sorted(unknown)}")
    if ("blocked_points" in root) != ("blocked_type" in root):
        raise MapCensusError(f"{path}: blocked_points and blocked_type must pair")

    _require_value_type(root["version"], "integer", f"{path}.version")
    _require_value_type(root["dimensions"], "point", f"{path}.dimensions")
    dimensions = root["dimensions"]
    assert isinstance(dimensions, LuaPoint)
    if dimensions.x <= 0 or dimensions.y <= 0:
        raise MapCensusError(f"{path}: dimensions must be positive")
    if "name" in root:
        _require_value_type(root["name"], "string", f"{path}.name")
        if root["name"] != stem:
            raise MapCensusError(f"{path}: name field does not match file stem")
    if "enemy_kills" in root:
        _require_value_type(root["enemy_kills"], "integer", f"{path}.enemy_kills")

    for field in (
        "spawns",
        "spawn_ids",
        "spawn_points",
        "blocked_points",
        "blocked_type",
    ):
        if field not in root:
            continue
        value = root[field]
        if not isinstance(value, LuaTable):
            raise MapCensusError(f"{path}.{field} must be an empty array")
        if value.require_pure_array(f"{path}.{field}"):
            raise MapCensusError(f"{path}.{field} has an unsupported nonempty schema")

    map_value = root["map"]
    if not isinstance(map_value, LuaTable):
        raise MapCensusError(f"{path}.map must be an array")
    tile_values = map_value.require_pure_array(f"{path}.map")
    tiles: list[dict[str, LuaValue]] = []
    tile_fields: list[tuple[str, ...]] = []
    locations: set[tuple[int, int]] = set()
    for index, value in enumerate(tile_values):
        if not isinstance(value, LuaTable):
            raise MapCensusError(f"{path}.map[{index}] must be a keyed table")
        tile = value.require_pure_keyed(f"{path}.map[{index}]")
        fields = tuple(entry.key for entry in value.entries)
        tile_present = set(tile)
        missing_tile = _REQUIRED_TILE_FIELDS - tile_present
        unknown_tile = tile_present - set(_TILE_FIELD_TYPES)
        if missing_tile:
            raise MapCensusError(
                f"{path}.map[{index}] missing fields: {sorted(missing_tile)}"
            )
        if unknown_tile:
            raise MapCensusError(
                f"{path}.map[{index}] unknown fields: {sorted(unknown_tile)}"
            )
        for field, expected_type in _TILE_FIELD_TYPES.items():
            if field in tile:
                _require_value_type(
                    tile[field], expected_type, f"{path}.map[{index}].{field}"
                )
        if "pawn" in tile:
            assert isinstance(tile["pawn"], str)
            _require_published_identifier(
                tile["pawn"], f"{path}.map[{index}].pawn"
            )
        if "custom" in tile:
            assert isinstance(tile["custom"], str)
            _require_published_identifier(
                tile["custom"],
                f"{path}.map[{index}].custom",
                asset_basename=True,
            )
        location = tile["loc"]
        assert isinstance(location, LuaPoint)
        coordinate = (location.x, location.y)
        if not (0 <= location.x < dimensions.x and 0 <= location.y < dimensions.y):
            raise MapCensusError(f"{path}.map[{index}].loc is out of bounds")
        if coordinate in locations:
            raise MapCensusError(f"{path}: duplicate tile location {coordinate}")
        locations.add(coordinate)
        tiles.append(tile)
        tile_fields.append(fields)

    zones_value = root["zones"]
    if not isinstance(zones_value, LuaTable):
        raise MapCensusError(f"{path}.zones must be a keyed table")
    zones_mapping = zones_value.require_pure_keyed(f"{path}.zones")
    zones: list[tuple[str, tuple[LuaPoint, ...]]] = []
    for key, value in zones_mapping.items():
        if not key:
            raise MapCensusError(f"{path}.zones contains an empty key")
        _require_published_identifier(key, f"{path}.zones key")
        if not isinstance(value, LuaTable):
            raise MapCensusError(f"{path}.zones.{key} must be a point array")
        raw_points = value.require_pure_array(f"{path}.zones.{key}")
        points: list[LuaPoint] = []
        coordinates: set[tuple[int, int]] = set()
        for index, point in enumerate(raw_points):
            if not isinstance(point, LuaPoint):
                raise MapCensusError(f"{path}.zones.{key}[{index}] must be a point")
            coordinate = (point.x, point.y)
            if not (0 <= point.x < dimensions.x and 0 <= point.y < dimensions.y):
                raise MapCensusError(
                    f"{path}.zones.{key}[{index}] is out of bounds"
                )
            if coordinate in coordinates:
                raise MapCensusError(
                    f"{path}.zones.{key} contains duplicate point {coordinate}"
                )
            coordinates.add(coordinate)
            points.append(point)
        zones.append((key, tuple(points)))

    tags_value = root["tags"]
    if not isinstance(tags_value, LuaTable):
        raise MapCensusError(f"{path}.tags must be a string array")
    raw_tags = tags_value.require_pure_array(f"{path}.tags")
    tags: list[str] = []
    for index, tag in enumerate(raw_tags):
        _require_value_type(tag, "string", f"{path}.tags[{index}]")
        assert isinstance(tag, str)
        _require_published_identifier(tag, f"{path}.tags[{index}]")
        if tag in tags:
            raise MapCensusError(f"{path}.tags contains duplicate {tag!r}")
        tags.append(tag)

    return _ParsedMap(
        path=path,
        size=size,
        sha256=sha256,
        chunk=chunk,
        root=root,
        root_fields=root_fields,
        tiles=tuple(tiles),
        tile_fields=tuple(tile_fields),
        zones=tuple(zones),
        tags=tuple(tags),
    )


def _scalar_key(value: LuaValue) -> tuple[str, Any]:
    kind = _value_type(value)
    if kind == "point":
        assert isinstance(value, LuaPoint)
        return kind, (value.x, value.y)
    if kind == "table":
        raise MapCensusError("tables cannot be scalar domain values")
    return kind, value


def _domain_records(counter: Counter[tuple[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(item: tuple[tuple[str, Any], int]) -> str:
        (kind, value), _ = item
        return json.dumps([kind, value], ensure_ascii=False, separators=(",", ":"))

    records = []
    for (kind, value), occurrences in sorted(counter.items(), key=sort_key):
        normalized_value = list(value) if kind == "point" else value
        records.append(
            {"type": kind, "value": normalized_value, "occurrences": occurrences}
        )
    return records


def _schema_records(
    counter: Counter[tuple[str, ...]], count_name: str
) -> list[dict[str, Any]]:
    return [
        {"fields": list(fields), count_name: counter[fields]}
        for fields in sorted(counter)
    ]


def _counted_integer_records(
    counter: Counter[int], count_name: str
) -> list[dict[str, Any]]:
    return [
        {"value": value, count_name: counter[value]} for value in sorted(counter)
    ]


def _map_record(parsed: _ParsedMap) -> dict[str, Any]:
    tile_schemas = Counter(parsed.tile_fields)
    terrain = Counter(int(tile["terrain"]) for tile in parsed.tiles)
    optional_tile_fields = Counter(
        field
        for tile in parsed.tiles
        for field in tile
        if field not in _REQUIRED_TILE_FIELDS
    )
    zones = [
        {"key": key, "point_count": len(points)}
        for key, points in parsed.zones
    ]
    return {
        "path": parsed.path,
        "size": parsed.size,
        "sha256": parsed.sha256,
        "global_name": parsed.chunk.global_name,
        "global_matches_file_stem": True,
        "root_field_sequence": list(parsed.root_fields),
        "name_field": {
            "present": "name" in parsed.root,
            "matches_file_stem": "name" not in parsed.root
            or parsed.root["name"] == PurePosixPath(parsed.path).stem,
        },
        "version": parsed.root["version"],
        "dimensions": [parsed.root["dimensions"].x, parsed.root["dimensions"].y],
        "optional_root_fields": sorted(set(parsed.root) & _OPTIONAL_ROOT_FIELDS),
        "tile_count": len(parsed.tiles),
        "tile_schema_counts": _schema_records(tile_schemas, "tiles"),
        "terrain_counts": _counted_integer_records(terrain, "tiles"),
        "optional_tile_field_counts": [
            {"field": field, "tiles": optional_tile_fields[field]}
            for field in sorted(optional_tile_fields)
        ],
        "zone_count": len(parsed.zones),
        "zones": zones,
        "tag_count": len(parsed.tags),
    }


def build_map_census(
    install_root: Path,
    *,
    inventory: Mapping[str, Any],
    lua_census: Mapping[str, Any],
    callback_index: Mapping[str, Any],
    rustc: Path | None = None,
) -> dict[str, Any]:
    """Parse and summarize every sealed map chunk without executing Lua."""
    if not isinstance(inventory, Mapping):
        raise MapCensusError("inventory must be an object")
    if not isinstance(lua_census, Mapping):
        raise MapCensusError("Lua census must be an object")
    if not isinstance(callback_index, Mapping):
        raise MapCensusError("callback index must be an object")
    content_root, build_identity = _attest_installation(install_root, inventory)
    entries, maps_manifest = _map_entries(inventory)
    try:
        lua_verification = validate_lua_census(
            install_root,
            lua_census,
            inventory=inventory,
            callback_index=callback_index,
            rustc=rustc,
        )
    except LuaCensusError as exc:
        raise MapCensusError(f"Lua census verification failed: {exc}") from exc
    lua_crosscheck = _crosscheck_lua_census(
        lua_census,
        verification=lua_verification,
        inventory=inventory,
        build_identity=build_identity,
        entries=entries,
    )

    parsed_maps: list[_ParsedMap] = []
    for entry in entries:
        path = entry["path"]
        if path == "maps/maphelper.lua":
            continue
        if entry["size"] > MAX_MAP_SOURCE_BYTES:
            raise MapCensusError(f"{path} exceeds the map source size limit")
        try:
            text = read_exact_inventory_file(
                content_root,
                PurePosixPath(path),
                expected_size=entry["size"],
                expected_sha256=entry["sha256"],
            )
            if len(text.encode("utf-8")) != entry["size"]:
                raise MapCensusError(f"UTF-8 round trip changed source bytes: {path}")
            chunk = parse_lua_data_chunk(text)
            parsed = _validate_map_chunk(
                path,
                size=entry["size"],
                sha256=entry["sha256"],
                chunk=chunk,
            )
        except (LuaDataError, WeaponCoverageError) as exc:
            raise MapCensusError(f"{path}: {exc}") from exc
        parsed_maps.append(parsed)

    root_schemas: Counter[tuple[str, ...]] = Counter()
    root_presence: Counter[str] = Counter()
    root_types: dict[str, Counter[str]] = defaultdict(Counter)
    root_domains: dict[str, Counter[tuple[str, Any]]] = defaultdict(Counter)
    tile_counts: Counter[int] = Counter()
    tile_schemas: Counter[tuple[str, ...]] = Counter()
    tile_field_types: dict[str, Counter[str]] = defaultdict(Counter)
    tile_domains: dict[str, Counter[tuple[str, Any]]] = defaultdict(Counter)
    location_x_domain: set[int] = set()
    location_y_domain: set[int] = set()
    location_domain: set[tuple[int, int]] = set()
    zone_domain: dict[str, Counter[str]] = defaultdict(Counter)
    tag_domain: dict[str, Counter[str]] = defaultdict(Counter)

    for parsed in parsed_maps:
        root_schemas[parsed.root_fields] += 1
        tile_counts[len(parsed.tiles)] += 1
        for field, value in parsed.root.items():
            root_presence[field] += 1
            if isinstance(value, LuaTable):
                root_types[field]["table"] += 1
            else:
                root_types[field][_value_type(value)] += 1
                if field != "name":
                    root_domains[field][_scalar_key(value)] += 1
        for tile, fields in zip(parsed.tiles, parsed.tile_fields, strict=True):
            tile_schemas[fields] += 1
            for field, value in tile.items():
                tile_field_types[field][_value_type(value)] += 1
                if field == "loc":
                    assert isinstance(value, LuaPoint)
                    location_x_domain.add(value.x)
                    location_y_domain.add(value.y)
                    location_domain.add((value.x, value.y))
                else:
                    tile_domains[field][_scalar_key(value)] += 1
        for key, points in parsed.zones:
            zone_domain[key]["maps"] += 1
            zone_domain[key]["points"] += len(points)
            zone_domain[key]["empty_zones"] += not points
        for tag in parsed.tags:
            tag_domain[tag]["maps"] += 1
            tag_domain[tag]["occurrences"] += 1

    records = [_map_record(parsed) for parsed in parsed_maps]
    total_tiles = sum(len(parsed.tiles) for parsed in parsed_maps)
    total_zone_points = sum(
        len(points) for parsed in parsed_maps for _, points in parsed.zones
    )
    total_zones = sum(len(parsed.zones) for parsed in parsed_maps)
    helper_entry = next(
        entry for entry in entries if entry["path"] == "maps/maphelper.lua"
    )
    map_revision = maps_manifest.get("revision_sha256")
    if (
        type(map_revision) is not str
        or not _SHA256_RE.fullmatch(map_revision)
        or build_identity.get("maps_revision_sha256") != map_revision
    ):
        raise MapCensusError("inventory maps revision identity is malformed")

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": build_identity,
        "inventory": {
            "label": inventory.get("label"),
            "canonical_sha256": _canonical_sha256(inventory),
            "maps_revision_sha256": map_revision,
            "map_directory_entries": len(entries),
            "map_directory_bytes": sum(entry["size"] for entry in entries),
        },
        "lua_census_crosscheck": lua_crosscheck,
        "method": {
            "source_execution": False,
            "parser": "strict_non_executing_lua_data_subset",
            "accepted_chunk_form": "IDENTIFIER = TABLE EOF",
            "accepted_values": [
                "nonnegative_integer",
                "unescaped_short_string",
                "boolean",
                "Point(integer,integer)",
                "nested_table",
            ],
            "accepted_comments": "Lua line comments only",
            "maphelper_handling": (
                "identity and compiled-not-executed status are crosschecked; "
                "behavior is outside this data census"
            ),
            "publication_policy": (
                "source identity hashes, per-map non-coordinate counts, and "
                "aggregate bounded identifier domains; no raw source, "
                "layout-derived hashes, per-map coordinates, or per-map "
                "tag membership"
            ),
            "limitations": [
                "static source grammar and observed values do not prove "
                "native consumer semantics",
                "numeric terrain and field values remain identifiers until "
                "separately mapped",
                "omitted-tile defaults and runtime mutations are outside this artifact",
                "map load success, registration order, selection, and "
                "reachability are not inferred",
            ],
        },
        "schema": {
            "required_root_fields": sorted(_REQUIRED_ROOT_FIELDS),
            "optional_root_fields": sorted(_OPTIONAL_ROOT_FIELDS),
            "root_field_types": dict(sorted(_ROOT_FIELD_TYPES.items())),
            "paired_root_fields": [["blocked_points", "blocked_type"]],
            "required_tile_fields": sorted(_REQUIRED_TILE_FIELDS),
            "optional_tile_field_types": dict(
                sorted(_OPTIONAL_TILE_FIELD_TYPES.items())
            ),
            "coordinates": "unique and within declared dimensions per collection",
            "tags": "ordered, unique, nonempty strings",
            "unsupported_nonempty_tables": [
                "spawns",
                "spawn_ids",
                "spawn_points",
                "blocked_points",
                "blocked_type",
            ],
        },
        "observations": {
            "root_field_presence": [
                {"field": field, "maps": root_presence[field]}
                for field in sorted(root_presence)
            ],
            "root_field_sequences": _schema_records(root_schemas, "maps"),
            "root_field_type_counts": [
                {
                    "field": field,
                    "types": [
                        {"type": kind, "occurrences": count}
                        for kind, count in sorted(root_types[field].items())
                    ],
                }
                for field in sorted(root_types)
            ],
            "root_scalar_domains": [
                {"field": field, "values": _domain_records(root_domains[field])}
                for field in sorted(root_domains)
            ],
            "tile_count_distribution": _counted_integer_records(
                tile_counts, "maps"
            ),
            "tile_field_schemas": _schema_records(tile_schemas, "tiles"),
            "tile_field_type_counts": [
                {
                    "field": field,
                    "types": [
                        {"type": kind, "occurrences": count}
                        for kind, count in sorted(tile_field_types[field].items())
                    ],
                }
                for field in sorted(tile_field_types)
            ],
            "tile_scalar_domains": [
                {"field": field, "values": _domain_records(tile_domains[field])}
                for field in sorted(tile_domains)
            ],
            "tile_location_domain": {
                "x": sorted(location_x_domain),
                "y": sorted(location_y_domain),
                "unique_points": len(location_domain),
                "occurrences": total_tiles,
            },
            "zone_key_domain": [
                {
                    "key": key,
                    "maps": zone_domain[key]["maps"],
                    "points": zone_domain[key]["points"],
                    "empty_zones": zone_domain[key]["empty_zones"],
                }
                for key in sorted(zone_domain)
            ],
            "tag_domain": [
                {
                    "tag": tag,
                    "maps": tag_domain[tag]["maps"],
                    "occurrences": tag_domain[tag]["occurrences"],
                }
                for tag in sorted(tag_domain)
            ],
        },
        "maps": records,
        "maphelper": {
            "path": helper_entry["path"],
            "size": helper_entry["size"],
            "sha256": helper_entry["sha256"],
            "compile_status": lua_crosscheck["maphelper"]["compile_status"],
            "behavior_scope": "separate Lua/native loader evidence",
        },
        "summary": {
            "map_directory_entries": len(entries),
            "map_data_chunks": len(parsed_maps),
            "maphelper_lua_files": 1,
            "map_directory_bytes": sum(entry["size"] for entry in entries),
            "strictly_parsed_chunks": len(parsed_maps),
            "compiled_chunks_crosschecked": lua_crosscheck["compiled_map_chunks"],
            "global_names_matching_file_stems": len(parsed_maps),
            "name_fields_present": sum("name" in parsed.root for parsed in parsed_maps),
            "name_fields_absent": sum(
                "name" not in parsed.root for parsed in parsed_maps
            ),
            "root_field_schemas": len(root_schemas),
            "explicit_tiles": total_tiles,
            "minimum_explicit_tiles_per_map": min(
                len(item.tiles) for item in parsed_maps
            ),
            "maximum_explicit_tiles_per_map": max(
                len(item.tiles) for item in parsed_maps
            ),
            "tile_field_schemas": len(tile_schemas),
            "unique_tile_locations_observed": len(location_domain),
            "maps_with_unique_in_bounds_tile_locations": len(parsed_maps),
            "maps_with_empty_spawn_tables": sum(
                all(
                    not parsed.root[field].entries
                    for field in ("spawns", "spawn_ids", "spawn_points")
                )
                for parsed in parsed_maps
            ),
            "maps_with_block_field_pair": sum(
                "blocked_points" in parsed.root for parsed in parsed_maps
            ),
            "maps_with_enemy_kills_field": sum(
                "enemy_kills" in parsed.root for parsed in parsed_maps
            ),
            "zone_keys": len(zone_domain),
            "zone_instances": total_zones,
            "zone_points": total_zone_points,
            "maps_with_zones": sum(bool(parsed.zones) for parsed in parsed_maps),
            "tags": sum(len(parsed.tags) for parsed in parsed_maps),
            "tag_values": len(tag_domain),
            "maps_with_tags": sum(bool(parsed.tags) for parsed in parsed_maps),
            "schema_violations": 0,
        },
    }


def validate_map_census(
    install_root: Path,
    evidence: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
    lua_census: Mapping[str, Any],
    callback_index: Mapping[str, Any],
    rustc: Path | None = None,
) -> dict[str, Any]:
    """Rebuild and exact-compare a normalized map census."""
    if not isinstance(evidence, Mapping):
        raise MapCensusError("evidence must be an object")
    expected = build_map_census(
        install_root,
        inventory=inventory,
        lua_census=lua_census,
        callback_index=callback_index,
        rustc=rustc,
    )
    if evidence != expected:
        raise MapCensusError(
            "map census does not match the exact installation and inputs"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": expected["build_identity"],
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": expected["summary"],
    }


def encode_map_census(value: Mapping[str, Any]) -> str:
    """Encode census or verification output deterministically."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
