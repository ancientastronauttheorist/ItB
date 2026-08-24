"""Bind native Pawn positioning helpers to their shipped Lua defaults.

The Windows Pawn bindings do not read opaque native score fields.  The exact
``GetDangerScore`` body prefixes ``ScoreDanger`` with ``Get`` and invokes the
resulting Lua ``GetScoreDanger`` method.  ``GetCustomPositionScore`` invokes
the literal Lua ``GetPositionScore`` method with the candidate Point.  The
shipped ``CreateClass(Pawn)`` call synthesizes both getters from the base Pawn
fields, whose only active shipped assignments are ``-10`` and ``0``.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.pe_anchor_map import PEAnchorError, PEImage
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    lua_function_spans,
    mask_lua_opaque,
    read_exact_inventory_file,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_enemy_position_score_helpers_boundary"
REPLAY_KIND = "stock_enemy_position_score_helpers_replay"
EXPECTED_BUILD_ID = "13725832"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_LUA_DLL_SHA256 = (
    "0157f0c34e72b32e63ebf3fdd9a21215de674b51b6d1750ebe545ef3093a0c14"
)
EXPECTED_SCRIPTS_REVISION = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
EXPECTED_INVENTORY_CANONICAL_SHA256 = (
    "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
)
EXPECTED_SHIPPED_LUA_FILE_COUNT = 152
IMAGE_BASE = 0x00400000


class EnemyPositionScoreHelpersBoundaryError(RuntimeError):
    """Raised when the exact source/native helper join differs."""


SOURCE_REGIONS = (
    {
        "id": "create_class",
        "source_path": "scripts/global.lua",
        "symbol": "CreateClass",
        "line": 86,
        "body_size": 430,
        "body_sha256": (
            "214fce796c535562d79f4cdeef89be1e098b7652b2444c6957702b6a6aed29f9"
        ),
    },
    {
        "id": "pawn_defaults_and_getter_install",
        "source_path": "scripts/global.lua",
        "symbol": "Pawn / CreateClass(Pawn)",
        "line": 107,
        "body_size": 1330,
        "body_sha256": (
            "8f38b9c9ec4bb4acc43da66118ff1399f2ec43e342336155b332bf8c94e68ff9"
        ),
    },
)


NATIVE_REGIONS = (
    {
        "id": "get_danger_score_registration",
        "image": "Breach.exe",
        "start_rva": "0x0027c040",
        "size": 37,
        "sha256": "984bd78ae114f2637501d831932ac3bf91bea4e486adc2b934fec04c6e2de9f5",
        "meaning": (
            "Registers GetDangerScore with the unique member pointer "
            "0x006397f0 (RVA 0x002397f0)."
        ),
    },
    {
        "id": "get_custom_position_score_registration_callsite",
        "image": "Breach.exe",
        "start_rva": "0x0027c6af",
        "size": 33,
        "sha256": "0e0cd0c6f67446f57b12522f7a48dadc636849db9716c151c3c074897b21a0c5",
        "meaning": (
            "Passes the unique member pointer 0x0063c5f0 to the dedicated "
            "GetCustomPositionScore binding constructor."
        ),
    },
    {
        "id": "get_custom_position_score_binding_constructor",
        "image": "Breach.exe",
        "start_rva": "0x0028cf50",
        "size": 160,
        "sha256": "b80bcfb21dc07d04bea789dcbf3f3a48694eb8a5876a1506656e55b275c65364",
        "meaning": (
            "Hard-codes the GetCustomPositionScore registration name at "
            "VA 0x008391e0."
        ),
    },
    {
        "id": "pawn_get_danger_score",
        "image": "Breach.exe",
        "start_rva": "0x002397f0",
        "size": 57,
        "sha256": "07d477c77050dd56456f47323bbf8a7d2d742bae4b69ed08ed9e53063e5c4aa5",
        "meaning": (
            "Passes the ScoreDanger literal to the prefixed integer getter "
            "on the Pawn script object at +0x94."
        ),
    },
    {
        "id": "pawn_get_custom_position_score",
        "image": "Breach.exe",
        "start_rva": "0x0023c5f0",
        "size": 147,
        "sha256": "cfe0638fe491baa6eac09cce493680916f46f4152e4a2057636e9dd8ffbedc7e",
        "meaning": (
            "Looks up literal GetPositionScore and invokes it with the x/y "
            "candidate Point through the integer-returning call wrapper."
        ),
    },
    {
        "id": "prefixed_integer_getter",
        "image": "Breach.exe",
        "start_rva": "0x00049290",
        "size": 181,
        "sha256": "e93780ade10c743dfbadd0d4032493b7e4fa8da26ed230715b842061577b0c0c",
        "meaning": (
            "Returns zero for an absent script object; otherwise concatenates "
            "Get with the supplied field name and invokes the generated getter."
        ),
    },
    {
        "id": "named_method_lookup",
        "image": "Breach.exe",
        "start_rva": "0x00049350",
        "size": 82,
        "sha256": "3741dfe3df3bb4b4f1567efb5af0dfb4cd45f05b4e0226bf0e603e05566eaf96",
        "meaning": "Resolves the supplied method name on the Pawn script object.",
    },
    {
        "id": "no_argument_integer_call_wrapper",
        "image": "Breach.exe",
        "start_rva": "0x000494c0",
        "size": 345,
        "sha256": "8a41bafd282d1cf65648d8966db32d294f98572a178eceed37e65eae1d2bd5b6",
        "meaning": "Builds the CallMethod dispatch used by GetScoreDanger.",
    },
    {
        "id": "no_argument_integer_conversion",
        "image": "Breach.exe",
        "start_rva": "0x000499d0",
        "size": 330,
        "sha256": "ccd19ecdc7b47020439e5c934b51019e06682a2b8130a5989ae3b7b994f167f9",
        "meaning": (
            "Calls the Lua method, requires LUA_TNUMBER, and imports "
            "lua_tointeger through IAT VA 0x007d64f0."
        ),
    },
    {
        "id": "point_integer_call_wrapper",
        "image": "Breach.exe",
        "start_rva": "0x00244380",
        "size": 343,
        "sha256": "d492781c51a7a8160ef98c7979fde909a6199966de91d1027bc43420c33c9c02",
        "meaning": "Builds the Point-bearing GetPositionScore method call.",
    },
    {
        "id": "point_integer_conversion",
        "image": "Breach.exe",
        "start_rva": "0x00244510",
        "size": 340,
        "sha256": "39be0df7ca5ca5b43f55a2c34b86047524c29e7a31c8a05228004c1b5fc69fa7",
        "meaning": (
            "Calls the Lua method with the Point, requires LUA_TNUMBER, and "
            "imports lua_tointeger through IAT VA 0x007d64f0."
        ),
    },
    {
        "id": "lua_tointeger",
        "image": "lua5.1.dll",
        "start_rva": "0x000016d0",
        "size": 125,
        "sha256": "2d935d28eefdd86c2035f20567820a17c7bc0b9941b5343bf3475fcf7c30b2ab",
        "conversion_instruction_hex": "dd45f0db5de4",
        "meaning": (
            "Converts the Lua double with x87 FISTP; the shipped helper "
            "defaults -10 and 0 are exact under every rounding-control mode."
        ),
    },
)


NATIVE_STRINGS = (
    {
        "id": "score_danger_field",
        "rva": "0x00436960",
        "value": "ScoreDanger",
        "reference_instruction_rva": "0x0023980c",
        "reference_count": 1,
    },
    {
        "id": "get_position_score_method",
        "rva": "0x00436aec",
        "value": "GetPositionScore",
        "reference_instruction_rva": "0x0023c642",
        "reference_count": 1,
    },
    {
        "id": "get_danger_score_registration_name",
        "rva": "0x00438fec",
        "value": "GetDangerScore",
        "reference_instruction_rva": "0x0027c059",
        "reference_count": 1,
    },
    {
        "id": "get_custom_position_score_registration_name",
        "rva": "0x004391e0",
        "value": "GetCustomPositionScore",
        "reference_instruction_rva": "0x0028cf9f",
        "reference_count": 1,
    },
    {
        "id": "getter_prefix",
        "rva": "0x0041fe68",
        "value": "Get",
        "reference_instruction_rva": "0x000492d4",
        "reference_count": 5,
    },
    {
        "id": "call_method_global",
        "rva": "0x0041ff08",
        "value": "CallMethod",
        "reference_instruction_rva": "0x00049b32",
        "reference_count": 4,
    },
)


UNIQUE_POINTERS = (
    {
        "id": "get_danger_score_member_pointer",
        "target_va": "0x006397f0",
        "reference_instruction_rva": "0x0027c043",
        "reference_count": 1,
    },
    {
        "id": "get_custom_position_score_member_pointer",
        "target_va": "0x0063c5f0",
        "reference_instruction_rva": "0x0027c6b2",
        "reference_count": 1,
    },
)


CALL_EDGES = (
    {
        "id": "danger_member_to_prefixed_getter",
        "instruction_rva": "0x0023981f",
        "target_rva": "0x00049290",
        "instruction_hex": "e86cfae0ff",
    },
    {
        "id": "prefixed_getter_to_no_argument_wrapper",
        "instruction_rva": "0x00049313",
        "target_rva": "0x000494c0",
        "instruction_hex": "e8a8010000",
    },
    {
        "id": "custom_member_to_named_lookup",
        "instruction_rva": "0x0023c660",
        "target_rva": "0x00049350",
        "instruction_hex": "e8ebcce0ff",
    },
    {
        "id": "custom_member_to_point_wrapper",
        "instruction_rva": "0x0023c66c",
        "target_rva": "0x00244380",
        "instruction_hex": "e80f7d0000",
    },
    {
        "id": "no_argument_wrapper_to_integer_conversion",
        "instruction_rva": "0x0004951c",
        "target_rva": "0x000499d0",
        "instruction_hex": "e8af040000",
    },
    {
        "id": "point_wrapper_to_integer_conversion",
        "instruction_rva": "0x002443e0",
        "target_rva": "0x00244510",
        "instruction_hex": "e82b010000",
    },
)


SOURCE_CENSUS = {
    "scanned_inventory_script_file_count": 305,
    "scanned_shipped_lua_file_count": EXPECTED_SHIPPED_LUA_FILE_COUNT,
    "excluded_local_loader": "scripts/modloader.lua",
    "active_occurrences": {
        "ScoreDanger": [
            {"path": "scripts/global.lua", "line": 141, "column": 2}
        ],
        "PositionScore": [
            {"path": "scripts/global.lua", "line": 149, "column": 2}
        ],
        "GetScoreDanger": [],
        "GetPositionScore": [],
        "GetCustomPositionScore": [
            {"path": "scripts/global.lua", "line": 475, "column": 22}
        ],
    },
    "explicit_override_count": 0,
}


def _canonical_sha256(value: Mapping[str, Any] | list[Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_rva(value: str) -> int:
    return int(value, 16)


def replay_stock_enemy_position_score_helpers() -> dict[str, Any]:
    """Return the exact inherited helper results for unmodified shipped Pawns."""

    return {
        "replay_kind": REPLAY_KIND,
        "scope": "unmodified shipped Lua Pawn definitions",
        "danger_score": {
            "native_binding": "Pawn:GetDangerScore",
            "lua_method": "GetScoreDanger",
            "field": "ScoreDanger",
            "lua_value": -10,
            "native_integer": -10,
        },
        "custom_position_score": {
            "native_binding": "Pawn:GetCustomPositionScore",
            "lua_method": "GetPositionScore",
            "argument": "candidate Point",
            "field": "PositionScore",
            "lua_value": 0,
            "native_integer": 0,
        },
        "x87_rounding_invariant": True,
    }


def _find_active_occurrences(
    sources: Mapping[str, str], token: str
) -> list[dict[str, Any]]:
    pattern = re.compile(rf"\b{re.escape(token)}\b")
    result: list[dict[str, Any]] = []
    for path in sorted(sources):
        text = sources[path]
        masked = mask_lua_opaque(text)
        for match in pattern.finditer(masked):
            line_start = text.rfind("\n", 0, match.start()) + 1
            result.append(
                {
                    "path": path,
                    "line": text.count("\n", 0, match.start()) + 1,
                    "column": match.start() - line_start + 1,
                }
            )
    return result


def _inventory_scripts(
    content_root: Path, inventory: Mapping[str, Any]
) -> dict[str, str]:
    try:
        block = inventory["content"]["scripts"]
        entries = block["files"]
        if (
            block["file_count"] != SOURCE_CENSUS["scanned_inventory_script_file_count"]
            or block["revision_sha256"] != EXPECTED_SCRIPTS_REVISION
        ):
            raise KeyError("script inventory summary")
    except (KeyError, TypeError) as exc:
        raise EnemyPositionScoreHelpersBoundaryError(
            "script inventory fields differ"
        ) from exc
    sources: dict[str, str] = {}
    try:
        for entry in entries:
            relative = PurePosixPath(entry["path"])
            if (
                relative.suffix != ".lua"
                or relative.as_posix() == SOURCE_CENSUS["excluded_local_loader"]
            ):
                continue
            sources[relative.as_posix()] = read_exact_inventory_file(
                content_root,
                relative,
                expected_size=entry["size"],
                expected_sha256=entry["sha256"],
            )
    except (KeyError, TypeError, WeaponCoverageError) as exc:
        raise EnemyPositionScoreHelpersBoundaryError(
            f"script inventory/source differs: {exc}"
        ) from exc
    if len(sources) != EXPECTED_SHIPPED_LUA_FILE_COUNT:
        raise EnemyPositionScoreHelpersBoundaryError(
            "shipped Lua source count differs"
        )
    return sources


def _verify_source(content_root: Path, inventory: Mapping[str, Any]) -> None:
    if not isinstance(inventory, Mapping):
        raise EnemyPositionScoreHelpersBoundaryError("inventory must be an object")
    if _canonical_sha256(inventory) != EXPECTED_INVENTORY_CANONICAL_SHA256:
        raise EnemyPositionScoreHelpersBoundaryError("inventory fields differ")
    sources = _inventory_scripts(content_root, inventory)
    text = sources.get("scripts/global.lua")
    if text is None:
        raise EnemyPositionScoreHelpersBoundaryError("global.lua is absent")
    try:
        spans = lua_function_spans(mask_lua_opaque(text))
    except WeaponCoverageError as exc:
        raise EnemyPositionScoreHelpersBoundaryError(
            f"global.lua structure differs: {exc}"
        ) from exc
    matches = [
        (start, end)
        for start, end in spans
        if text.startswith("function CreateClass", start)
    ]
    if len(matches) != 1:
        raise EnemyPositionScoreHelpersBoundaryError("CreateClass boundary differs")
    create_start, create_end = matches[0]
    pawn_start = text.find("Pawn = {", create_end)
    install = "CreateClass(Pawn)"
    pawn_end = text.find(install, pawn_start)
    if pawn_start < 0 or pawn_end < 0:
        raise EnemyPositionScoreHelpersBoundaryError("Pawn default region differs")
    pawn_end += len(install)
    regions = ((create_start, create_end), (pawn_start, pawn_end))
    for spec, (start, end) in zip(SOURCE_REGIONS, regions, strict=True):
        raw = text[start:end].encode("utf-8")
        if (
            text.count("\n", 0, start) + 1 != spec["line"]
            or len(raw) != spec["body_size"]
            or hashlib.sha256(raw).hexdigest() != spec["body_sha256"]
        ):
            raise EnemyPositionScoreHelpersBoundaryError(
                f"source region differs: {spec['id']}"
            )
    actual_occurrences = {
        token: _find_active_occurrences(sources, token)
        for token in SOURCE_CENSUS["active_occurrences"]
    }
    if actual_occurrences != SOURCE_CENSUS["active_occurrences"]:
        raise EnemyPositionScoreHelpersBoundaryError(
            "active Pawn score occurrence census differs"
        )


def _read_inventory_binary(
    content_root: Path,
    inventory: Mapping[str, Any],
    *,
    path_name: str,
    expected_sha256: str,
) -> bytes:
    try:
        if path_name == "Breach.exe":
            entry = inventory["executable"]
        else:
            entry = next(
                item
                for item in inventory["native_libraries"]
                if item.get("path") == path_name
            )
    except (KeyError, StopIteration, TypeError) as exc:
        raise EnemyPositionScoreHelpersBoundaryError(
            f"{path_name} inventory entry differs"
        ) from exc
    candidate = content_root / path_name
    if candidate.is_symlink() or not candidate.is_file():
        raise EnemyPositionScoreHelpersBoundaryError(
            f"{path_name} is not a regular non-symlink file"
        )
    before = candidate.stat()
    raw = candidate.read_bytes()
    after = candidate.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(raw) != entry.get("size")
        or hashlib.sha256(raw).hexdigest() != entry.get("sha256")
        or entry.get("sha256") != expected_sha256
    ):
        raise EnemyPositionScoreHelpersBoundaryError(
            f"{path_name} differs from accepted inventory"
        )
    return raw


def _region_bytes(image: PEImage, raw: bytes, rva: int, size: int) -> bytes:
    try:
        offset = image.rva_span_to_file_offset(rva, size)
    except PEAnchorError as exc:
        raise EnemyPositionScoreHelpersBoundaryError(
            f"PE region differs at RVA 0x{rva:08x}: {exc}"
        ) from exc
    if offset is None:
        raise EnemyPositionScoreHelpersBoundaryError(
            f"PE region is unmapped at RVA 0x{rva:08x}"
        )
    return raw[offset : offset + size]


def _verify_native(content_root: Path, inventory: Mapping[str, Any]) -> None:
    executable = _read_inventory_binary(
        content_root,
        inventory,
        path_name="Breach.exe",
        expected_sha256=EXPECTED_EXECUTABLE_SHA256,
    )
    lua_dll = _read_inventory_binary(
        content_root,
        inventory,
        path_name="lua5.1.dll",
        expected_sha256=EXPECTED_LUA_DLL_SHA256,
    )
    try:
        executable_image = PEImage(executable)
        lua_image = PEImage(lua_dll)
    except PEAnchorError as exc:
        raise EnemyPositionScoreHelpersBoundaryError(
            f"PE image differs: {exc}"
        ) from exc
    for spec in NATIVE_REGIONS:
        body = _region_bytes(
            lua_image if spec["image"] == "lua5.1.dll" else executable_image,
            lua_dll if spec["image"] == "lua5.1.dll" else executable,
            _parse_rva(spec["start_rva"]),
            spec["size"],
        )
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise EnemyPositionScoreHelpersBoundaryError(
                f"native region differs: {spec['id']}"
            )
        conversion = spec.get("conversion_instruction_hex")
        if conversion is not None and bytes.fromhex(conversion) not in body:
            raise EnemyPositionScoreHelpersBoundaryError(
                "lua_tointeger conversion instruction differs"
            )
    for spec in NATIVE_STRINGS:
        encoded = spec["value"].encode("ascii") + b"\0"
        if _region_bytes(
            executable_image,
            executable,
            _parse_rva(spec["rva"]),
            len(encoded),
        ) != encoded:
            raise EnemyPositionScoreHelpersBoundaryError(
                f"native string differs: {spec['id']}"
            )
        absolute = IMAGE_BASE + _parse_rva(spec["rva"])
        if executable.count(struct.pack("<I", absolute)) != spec["reference_count"]:
            raise EnemyPositionScoreHelpersBoundaryError(
                f"native string reference count differs: {spec['id']}"
            )
    for spec in UNIQUE_POINTERS:
        target = int(spec["target_va"], 16)
        if executable.count(struct.pack("<I", target)) != spec["reference_count"]:
            raise EnemyPositionScoreHelpersBoundaryError(
                f"native pointer reference count differs: {spec['id']}"
            )
    for edge in CALL_EDGES:
        encoded = bytes.fromhex(edge["instruction_hex"])
        if _region_bytes(
            executable_image,
            executable,
            _parse_rva(edge["instruction_rva"]),
            len(encoded),
        ) != encoded:
            raise EnemyPositionScoreHelpersBoundaryError(
                f"native call edge differs: {edge['id']}"
            )


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "native_registrations_are_exact",
            "classification": "fact",
            "claim": (
                "The unique GetDangerScore and GetCustomPositionScore member "
                "pointers resolve to exact 57-byte and 147-byte Pawn bodies."
            ),
        },
        {
            "id": "danger_score_uses_generated_getter",
            "classification": "fact",
            "claim": (
                "GetDangerScore supplies ScoreDanger to a helper that prefixes "
                "Get, dispatches GetScoreDanger, requires a Lua number, and "
                "extracts it with lua_tointeger."
            ),
        },
        {
            "id": "custom_position_uses_get_position_score",
            "classification": "fact",
            "claim": (
                "GetCustomPositionScore resolves literal GetPositionScore and "
                "passes the candidate Point before integer extraction."
            ),
        },
        {
            "id": "create_class_synthesizes_both_getters",
            "classification": "fact",
            "claim": (
                "CreateClass synthesizes Get<member> methods returning "
                "self[member]; CreateClass(Pawn) therefore installs both score "
                "getters from the pinned base fields."
            ),
        },
        {
            "id": "shipped_defaults_have_no_explicit_override",
            "classification": "fact",
            "claim": (
                "Across all 152 inventoried shipped Lua files (excluding the "
                "local modloader), the only active "
                "ScoreDanger and PositionScore tokens are the base assignments "
                "-10 and 0; neither generated getter name occurs explicitly."
            ),
        },
        {
            "id": "stock_results_are_rounding_invariant",
            "classification": "fact",
            "claim": (
                "The installed lua_tointeger still uses x87 FISTP, but exact "
                "integer-valued defaults -10 and 0 produce the same result in "
                "all four rounding-control modes."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "runtime_or_modded_field_mutation",
            "question": "Can runtime code or a mod replace either inherited score value/getter?",
            "static_status": (
                "The exact shipped active Lua census contains no explicit "
                "override. Runtime mutation and non-inventoried mods remain "
                "outside this immutable stock-content claim."
            ),
        }
    ]


def _expected_shape() -> dict[str, Any]:
    findings = _findings()
    unresolved = _unresolved()
    replay = replay_stock_enemy_position_score_helpers()
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": {
            "platform": "windows",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "lua5_1_sha256": EXPECTED_LUA_DLL_SHA256,
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION,
        },
        "dependencies": [
            {
                "id": "accepted_local_inventory",
                "path": (
                    "data/observatory/inventories/"
                    "windows_build_13725832_31fe35265598_local_modified.json"
                ),
                "canonical_sha256": EXPECTED_INVENTORY_CANONICAL_SHA256,
                "role": "Pins the exact executable, Lua DLL, and source corpus.",
            }
        ],
        "source_regions": [dict(spec) for spec in SOURCE_REGIONS],
        "source_census": json.loads(json.dumps(SOURCE_CENSUS)),
        "native_regions": [dict(spec) for spec in NATIVE_REGIONS],
        "native_strings": [dict(spec) for spec in NATIVE_STRINGS],
        "unique_member_pointers": [dict(spec) for spec in UNIQUE_POINTERS],
        "call_edges": [dict(spec) for spec in CALL_EDGES],
        "contracts": {
            "danger_native_binding": "Pawn:GetDangerScore",
            "danger_field_literal": "ScoreDanger",
            "danger_generated_method": "GetScoreDanger",
            "custom_native_binding": "Pawn:GetCustomPositionScore",
            "custom_method_literal": "GetPositionScore",
            "custom_method_argument": "candidate Point",
            "custom_field": "PositionScore",
            "create_class_getter_rule": "Get<member>(self,pawn) -> self[member]",
            "unmodified_shipped_danger_score": -10,
            "unmodified_shipped_custom_position_score": 0,
            "native_integer_api": "lua_tointeger",
            "native_conversion_instruction": "x87 FISTP dword",
            "stock_defaults_require_runtime_rounding_mode": False,
            "absent_script_object_danger_fallback": 0,
        },
        "replay_vectors": [
            {"id": "unmodified_shipped_pawn_defaults", "expected": replay}
        ],
        "findings": findings,
        "unresolved": unresolved,
        "closure": {
            "native_registrations_complete": True,
            "native_helper_call_paths_complete": True,
            "shipped_source_default_census_complete": True,
            "unmodified_shipped_results_complete": True,
            "runtime_or_modded_field_mutation_complete": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
        "summary": {
            "dependency_count": 1,
            "source_region_count": len(SOURCE_REGIONS),
            "scanned_shipped_lua_file_count": EXPECTED_SHIPPED_LUA_FILE_COUNT,
            "native_region_count": len(NATIVE_REGIONS),
            "native_string_count": len(NATIVE_STRINGS),
            "call_edge_count": len(CALL_EDGES),
            "replay_vector_count": 1,
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "unmodified_shipped_results_complete": True,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def build_enemy_position_score_helpers_boundary(
    content_root: Path, inventory: Mapping[str, Any]
) -> dict[str, Any]:
    """Build the exact source/native helper join after verifying pinned bytes."""

    _verify_source(content_root, inventory)
    _verify_native(content_root, inventory)
    return _expected_shape()


def validate_enemy_position_score_helpers_boundary_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable fields and replay without external reads."""

    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise EnemyPositionScoreHelpersBoundaryError(
            "enemy position score helper fields differ"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "native_helper_call_paths_complete": True,
        "shipped_source_default_census_complete": True,
        "unmodified_shipped_results_complete": True,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_position_score_helpers_boundary(
    content_root: Path,
    inventory: Mapping[str, Any],
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and reject executable, DLL, source, or replay drift."""

    expected = build_enemy_position_score_helpers_boundary(content_root, inventory)
    if dict(value) != expected:
        raise EnemyPositionScoreHelpersBoundaryError(
            "enemy position score helper map differs from exact analysis"
        )
    result = validate_enemy_position_score_helpers_boundary_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_position_score_helpers_boundary(
    value: Mapping[str, Any],
) -> str:
    """Return deterministic UTF-8 JSON."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
