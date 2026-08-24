"""Replay the exact-build native enemy target-area callback boundary.

The preceding target-area artifact ends immediately before the Skill callback
wrapper.  This continuation binds the wrapper's Board-validity guard,
``TwoClick`` dispatch, PointList cache replacement, negative-coordinate filter,
and order-preserving return copy on Windows build 13725832.

Concrete Lua callback output is still an explicit boundary input.  This module
does not execute Lua, explain why a subclass produced a particular point order,
materialize SkillEffects, or forecast a complete enemy phase.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.observatory.enemy_target_area_boundary import (
    EnemyTargetAreaBoundaryError,
    validate_enemy_target_area_boundary_map_binding,
)
from src.observatory.path_occupancy_lifecycle import (
    PathOccupancyLifecycleError,
    validate_path_occupancy_lifecycle_map_binding,
)
from src.observatory.pe_boundary_map import (
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_enemy_target_area_callback_boundary_map"
REPLAY_KIND = "native_enemy_target_area_callback_replay"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
SIGNED_MIN = -(1 << 31)
SIGNED_MAX = (1 << 31) - 1
MAX_REPLAY_POINTS = 4096


class EnemyTargetAreaCallbackBoundaryError(RuntimeError):
    """Raised when the exact callback boundary cannot reproduce."""


REPO_ROOT = Path(__file__).resolve().parents[2]


DEPENDENCY_SPECS = (
    {
        "id": "enemy_target_area_gate",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_enemy_target_area_boundary.json"
        ),
        "file_sha256": (
            "5ccb768da7e11df3e07dc5fca7fac55398bec51dde0c3f3d5f4b0df54d3ec08b"
        ),
        "canonical_sha256": (
            "80b8f425daacfc82e5a320e9922bcd60d7c3ff676e400ea7e21d72e230d5f009"
        ),
        "role": (
            "Pins the exact ordinary/debug eligibility gate, usable-skill scan, "
            "selected-weapon normalization, and Skill resolver immediately before "
            "this callback wrapper."
        ),
    },
    {
        "id": "path_occupancy_lifecycle",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_path_occupancy_lifecycle.json"
        ),
        "file_sha256": (
            "fb0537726b65a506f9548444c90e4e17a1ea2d201f60a04ad7ff728072629805"
        ),
        "canonical_sha256": (
            "2960b1ca1f48bb31faf9c684d86e868683ae934609612ded65beb61967f6859c"
        ),
        "role": (
            "Pins the Board constructor's +0x0c secondary/path-manager vtable "
            "installation used by Skill +0x110."
        ),
    },
)


REGION_SPECS = (
    (
        "pointlist_copy",
        0x0009A8E0,
        0x0009A92F,
        "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0",
        "Ghidra PointList order-preserving copy body.",
    ),
    (
        "pointlist_replace",
        0x000C5BB0,
        0x000C5C92,
        "62157759ee3564515e63f20e297c171de6444d84732bccf7414eb208d953eefe",
        "Ghidra PointList copy/replace body used for a fresh callback result.",
    ),
    (
        "pointlist_move_assign",
        0x000E06B0,
        0x000E0718,
        "be82a2be97ee023b4db0b3ea2436ed2913e3eae0482aeb6b64e37f91bf01dd97",
        "Ghidra PointList move-assignment body used to install an empty list.",
    ),
    (
        "board_isvalid",
        0x00162280,
        0x001622A7,
        "ccc44e753f417cb103727661382ad7b18cd729f23a1bed12057027a3ef1506b1",
        "Ghidra Board coordinate-validity body.",
    ),
    (
        "addpawn",
        0x0016E8C0,
        0x0016EC8D,
        "c9031f10d38ba7cb28959b3460aec686a4366b4697accc7479638436aaa7280a",
        "Ghidra Board:AddPawn body binding a Pawn SkillManager to Board +0x0c.",
    ),
    (
        "board_isvalid_secondary_thunk",
        0x0017A9C0,
        0x0017A9C8,
        "7da4a72363beba9c6f9352ef4581c9aea060ce4b9bcc2109aa59a4a8e050492a",
        "Ghidra secondary-this thunk subtracting 0x0c before Board:IsValid.",
    ),
    (
        "skill_context_writer",
        0x002287B0,
        0x002287FD,
        "f93e7c0a7a635a68c36de4ca0c7c4071beddeee08690ece4d565c3782c0f045b",
        "Ghidra SkillManager context writer for vector Skills and Skill_Repair.",
    ),
    (
        "skill_ctor",
        0x002670B0,
        0x00267639,
        "4a0466f114c734bd512c85f5bc0834433380daead50236bf634161f0ea7d965c",
        "Ghidra generic Skill constructor initializing context and target cache.",
    ),
    (
        "target_area_callback",
        0x00269CC0,
        0x00269F12,
        "49c903372860741f8dcdc25a9db1aca6363fa4db7b328d2c9dcac8d625abe4cd",
        "Ghidra GetTargetArea/GetSecondTargetArea dispatch and cache body.",
    ),
)


CONTROL_WINDOW_SPECS = (
    (
        "context_vcall_and_origin_store",
        "target_area_callback",
        0x00269CE9,
        "8b8f100100008b45108b750c89873001000089b72c0100008b115056c745f0000000008b4214ffd0",
        (
            "Store origin at Skill +0x12c/+0x130, load context +0x110, and call "
            "its virtual slot +0x14 with that Point."
        ),
    ),
    (
        "invalid_origin_clears_and_copies",
        "target_area_callback",
        0x00269D26,
        "84c0754b8d45dc81c718010000508bcfe87569e7ff8b4ddc85c974148b45e42bc16a08c1f8035051e8addad9ff83c40c8b4d0857e8810be3ff",
        (
            "When IsValid is false, move-assign the fresh empty local into the "
            "Skill cache and copy that now-empty cache to the return value."
        ),
    ),
    (
        "two_click_and_second_target_gate",
        "target_area_callback",
        0x00269DAA,
        "8d8f34010000e8fbf5ddff84c0746983bf20020000ff746083bf24020000ff7457",
        (
            "Use GetSecondTargetArea only when TwoClick is true and neither "
            "stored second-target coordinate equals -1."
        ),
    ),
    (
        "second_target_callback_dispatch",
        "target_area_callback",
        0x00269DCB,
        "ffb724020000ffb720020000ff7510ff750c83ec188bcc8965ec68b4808300e821e0d9ff83ec18c645fc018d8f3401000054e84ef5ddff8d45d0c645fc0050e801870000508d4ddce89868e7ff8d4dd0e8a006e2ff",
        "Invoke GetSecondTargetArea(origin, second_target) and materialize its PointList.",
    ),
    (
        "regular_target_callback_dispatch",
        "target_area_callback",
        0x00269E22,
        "ff7510ff750c83ec188bcc8965e868a4808300e8d6dfd9ff83ec18c645fc028d8f3401000054e803f5ddff8d45d0c645fc0050e876880000508d4ddce84d68e7ff8b4dd085c974148b45d82bc16a08c1f8035051e885d9d9ff83c40c",
        "Invoke GetTargetArea(origin) and materialize its PointList.",
    ),
    (
        "callback_result_replaces_cache",
        "target_area_callback",
        0x00269E7E,
        "8d45dc8db718010000508bcee821bde5ff",
        "Replace Skill target cache +0x118 with the materialized callback PointList.",
    ),
    (
        "negative_coordinate_filter",
        "target_area_callback",
        0x00269E8F,
        "8b460433ff2b06c1f80385c0743a0f1f008b06833cf8007c07837cf804007d1b8b4e048d04f88d50082bca515250e8be461000834604f883c40c4f8b4604472b06c1f8033bf872c9",
        (
            "Erase each cached point whose x or y is negative, retaining encounter "
            "order, duplicates, and every point with nonnegative coordinates."
        ),
    ),
    (
        "filtered_cache_return_copy",
        "target_area_callback",
        0x00269ED7,
        "568b75088bcee8fe09e3ff",
        "Copy the filtered cache to the caller-provided return PointList.",
    ),
    (
        "skill_manager_context_writer",
        "skill_context_writer",
        0x002287B7,
        "39713c7407c74140ffffffff89713c33d28b41082b4104c1f80385c0741a8b41048b04d04289b0100100008b41082b4104c1f8033bd072e68b416889b010010000",
        (
            "Store one context on the manager, every vector Skill +0x110, and the "
            "separately owned repair Skill +0x110."
        ),
    ),
    (
        "addpawn_passes_board_secondary_context",
        "addpawn",
        0x0016E8FC,
        "399e440900007417f7d9899e440900008d430c1bc923c8518bcee8959e0b00",
        (
            "When the Pawn Board changes, pass Board +0x0c (or null) into the "
            "SkillManager context writer."
        ),
    ),
    (
        "skill_ctor_context_and_empty_cache",
        "skill_ctor",
        0x0026713F,
        "8b4508898610010000c6861401000000c7861801000000000000c7861c01000000000000c7862001000000000000",
        "Initialize Skill +0x110 from the context argument and its target cache empty.",
    ),
    (
        "pointlist_move_steals_and_zeros_source",
        "pointlist_move_assign",
        0x000E06EC,
        "8b0789068b47048946048b4708894608c70700000000c7470400000000c7470800000000",
        "Steal the source vector pointers into the destination, then zero the source.",
    ),
    (
        "pointlist_replace_memmove_order",
        "pointlist_replace",
        0x000C5BF8,
        "2bc1505152e87e892a008b4b0483c40c2b0b8b07c1f9038d04c8894704",
        "Copy an in-capacity source range contiguously and preserve its order.",
    ),
    (
        "board_isvalid_bounds",
        "board_isvalid",
        0x00162280,
        "558bec8b450885c078173b41487d128b450c85c0780b3b414c7d06b0015dc2080032c05dc20800",
        "Require nonnegative x/y strictly below Board width/height.",
    ),
    (
        "secondary_this_to_board_isvalid",
        "board_isvalid_secondary_thunk",
        0x0017A9C0,
        "83e90ce9b878feff",
        "Subtract 0x0c from this, then tail-jump to Board:IsValid.",
    ),
)


DIRECT_EDGE_SPECS = (
    (
        "addpawn_to_context_writer",
        "addpawn",
        0x0016E916,
        "e8959e0b00",
        "skill_context_writer",
        0x002287B0,
        "Bind Board +0x0c to every existing Skill when a Pawn joins a Board.",
    ),
    (
        "invalid_to_pointlist_move",
        "target_area_callback",
        0x00269D36,
        "e87569e7ff",
        "pointlist_move_assign",
        0x000E06B0,
        "Move an empty local list over the prior cache on invalid origin.",
    ),
    (
        "invalid_to_pointlist_copy",
        "target_area_callback",
        0x00269D5A,
        "e8810be3ff",
        "pointlist_copy",
        0x0009A8E0,
        "Return an order-preserving copy of the now-empty cache.",
    ),
    (
        "two_click_bool_lookup",
        "target_area_callback",
        0x00269DB0,
        "e8fbf5ddff",
        "lua_bool_getter",
        0x000493B0,
        "Read the dynamic Lua TwoClick value.",
    ),
    (
        "second_callback_lookup",
        "target_area_callback",
        0x00269DEA,
        "e821e0d9ff",
        "lua_method_lookup",
        0x00007E10,
        "Resolve the named GetSecondTargetArea method.",
    ),
    (
        "second_callback_invoke",
        "target_area_callback",
        0x00269DFD,
        "e84ef5ddff",
        "lua_object_invoke",
        0x00049350,
        "Invoke GetSecondTargetArea with origin and stored second target.",
    ),
    (
        "second_callback_convert",
        "target_area_callback",
        0x00269E0A,
        "e801870000",
        "second_target_pointlist_converter",
        0x00272510,
        "Convert the Lua callback result into a native PointList.",
    ),
    (
        "regular_callback_lookup",
        "target_area_callback",
        0x00269E35,
        "e8d6dfd9ff",
        "lua_method_lookup",
        0x00007E10,
        "Resolve the named GetTargetArea method.",
    ),
    (
        "regular_callback_invoke",
        "target_area_callback",
        0x00269E48,
        "e803f5ddff",
        "lua_object_invoke",
        0x00049350,
        "Invoke GetTargetArea with the origin.",
    ),
    (
        "regular_callback_convert",
        "target_area_callback",
        0x00269E55,
        "e876880000",
        "target_pointlist_converter",
        0x002726D0,
        "Convert the Lua callback result into a native PointList.",
    ),
    (
        "valid_to_pointlist_replace",
        "target_area_callback",
        0x00269E8A,
        "e821bde5ff",
        "pointlist_replace",
        0x000C5BB0,
        "Replace the Skill cache with the callback PointList.",
    ),
    (
        "negative_filter_memmove",
        "target_area_callback",
        0x00269EBD,
        "e8be461000",
        "crt_memmove",
        0x0036E580,
        "Shift the remaining suffix left after each rejected negative point.",
    ),
    (
        "valid_to_pointlist_copy",
        "target_area_callback",
        0x00269EDD,
        "e8fe09e3ff",
        "pointlist_copy",
        0x0009A8E0,
        "Return an order-preserving copy of the filtered cache.",
    ),
)


JUMP_EDGE_SPECS = (
    (
        "secondary_thunk_to_board_isvalid",
        "board_isvalid_secondary_thunk",
        0x0017A9C3,
        "e9b878feff",
        "board_isvalid",
        0x00162280,
        "Adjust secondary this by -0x0c and tail-dispatch to Board:IsValid.",
    ),
)


CALL_INVENTORY_SPECS = (
    (
        "target_area_callback_callers",
        0x00269CC0,
        (
            (0x0022792D, "SkillManager two-click/conservative state path"),
            (0x00228663, "SkillManager nonempty target-area query"),
            (0x00229293, "enemy candidate target-area wrapper"),
            (0x00268971, "Skill target/effect cache refresh"),
            (0x00269884, "two-click target-area visualization"),
            (0x0026A0CC, "TranslateFirstClick target-area refresh"),
        ),
    ),
    (
        "skill_context_writer_callers",
        0x002287B0,
        (
            (0x00161F0C, "native Board/Pawn lifecycle caller 1"),
            (0x00165C0E, "native Board/Pawn lifecycle caller 2"),
            (0x0016E916, "Board:AddPawn"),
            (0x001734F7, "native Board/Pawn lifecycle caller 3"),
            (0x001A03B3, "native Board/Pawn lifecycle caller 4"),
            (0x00230152, "native Pawn lifecycle caller"),
        ),
    ),
)


DATA_ANCHOR_SPECS = (
    (
        "board_secondary_isvalid_slot",
        0x0042E26C,
        ".rdata",
        "c0a95700",
        "Board +0x0c vtable slot +0x14 points to VA 0x0057a9c0.",
    ),
    (
        "get_target_area_string",
        0x004380A4,
        ".rdata",
        "4765745461726765744172656100",
        "Exact NUL-terminated GetTargetArea callback name.",
    ),
    (
        "get_second_target_area_string",
        0x004380B4,
        ".rdata",
        "4765745365636f6e645461726765744172656100",
        "Exact NUL-terminated GetSecondTargetArea callback name.",
    ),
    (
        "two_click_string",
        0x004380FC,
        ".rdata",
        "54776f436c69636b00",
        "Exact NUL-terminated TwoClick field name.",
    ),
)


INSTRUCTION_ANCHOR_SPECS = (
    (
        "new_repair_inherits_manager_context",
        0x002281BD,
        "8b55cc8b4a3c85c974088b03898810010000",
        (
            "A newly installed repair Skill copies the manager's existing context "
            "into Skill +0x110 when that context is non-null."
        ),
    ),
)


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EnemyTargetAreaCallbackBoundaryError(
            f"dependency is not a regular non-symlink file: {path}"
        )
    if path.stat().st_size > 16 * 1024 * 1024:
        raise EnemyTargetAreaCallbackBoundaryError("dependency exceeds size limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EnemyTargetAreaCallbackBoundaryError("dependency must contain an object")
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise EnemyTargetAreaCallbackBoundaryError(
            f"RVA 0x{rva:08x} is not contiguous file-backed data"
        )
    return data[offset : offset + size]


def _rel32_target(rva: int, encoded: bytes, opcode: int) -> int:
    if len(encoded) != 5 or encoded[0] != opcode:
        raise EnemyTargetAreaCallbackBoundaryError(
            "reviewed edge is not the expected rel32 instruction"
        )
    return (rva + 5 + struct.unpack_from("<i", encoded, 1)[0]) & 0xFFFFFFFF


def _raw_rel32_call_sites(image: Any, data: bytes, target_rva: int) -> set[int]:
    sites: set[int] = set()
    for section in image.sections:
        if not section.executable or section.raw_size < 5:
            continue
        start = section.raw_offset
        body = data[start : start + section.raw_size]
        cursor = 0
        while True:
            index = body.find(b"\xe8", cursor)
            if index < 0 or index + 5 > len(body):
                break
            call_rva = section.virtual_address + index
            encoded = body[index : index + 5]
            if _rel32_target(call_rva, encoded, 0xE8) == target_rva:
                sites.add(call_rva)
            cursor = index + 1
    return sites


def _require_signed(value: Any, label: str) -> int:
    if type(value) is not int or not SIGNED_MIN <= value <= SIGNED_MAX:
        raise EnemyTargetAreaCallbackBoundaryError(
            f"{label} must be a signed 32-bit integer"
        )
    return value


def _require_dimension(value: Any, label: str) -> int:
    if type(value) is not int or not 1 <= value <= SIGNED_MAX:
        raise EnemyTargetAreaCallbackBoundaryError(
            f"{label} must be a positive signed 32-bit integer"
        )
    return value


def _require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise EnemyTargetAreaCallbackBoundaryError(f"{label} must be a boolean")
    return value


def _normalize_point(value: Any, label: str) -> list[int]:
    if (
        isinstance(value, (str, bytes, bytearray))
        or not isinstance(value, Sequence)
        or len(value) != 2
    ):
        raise EnemyTargetAreaCallbackBoundaryError(
            f"{label} must be a two-integer Point array"
        )
    return [
        _require_signed(value[0], f"{label}[0]"),
        _require_signed(value[1], f"{label}[1]"),
    ]


def _normalize_points(value: Any, label: str) -> list[list[int]]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise EnemyTargetAreaCallbackBoundaryError(f"{label} must be a Point array")
    if len(value) > MAX_REPLAY_POINTS:
        raise EnemyTargetAreaCallbackBoundaryError(
            f"{label} exceeds the replay tooling limit"
        )
    return [
        _normalize_point(point, f"{label}[{index}]")
        for index, point in enumerate(value)
    ]


def replay_enemy_target_area_callback(
    *,
    board_width: Any,
    board_height: Any,
    origin: Any,
    cached_points: Any,
    two_click: Any,
    second_target: Any,
    get_target_area_points: Any,
    get_second_target_area_points: Any,
) -> dict[str, Any]:
    """Replay callback selection, target-cache mutation, filtering, and return.

    Exactly one callback PointList must be supplied for a valid origin, and it
    must match the callback selected by ``TwoClick`` plus the stored second
    target.  Neither callback input is allowed for an invalid origin because
    native code invokes neither one on that branch.
    """

    width = _require_dimension(board_width, "board_width")
    height = _require_dimension(board_height, "board_height")
    normalized_origin = _normalize_point(origin, "origin")
    cache_before = _normalize_points(cached_points, "cached_points")
    normalized_two_click = _require_bool(two_click, "two_click")
    normalized_second = _normalize_point(second_target, "second_target")

    origin_valid = (
        normalized_origin[0] >= 0
        and normalized_origin[0] < width
        and normalized_origin[1] >= 0
        and normalized_origin[1] < height
    )
    if not origin_valid:
        if get_target_area_points is not None or get_second_target_area_points is not None:
            raise EnemyTargetAreaCallbackBoundaryError(
                "invalid-origin replay must not supply callback output"
            )
        return {
            "replay_kind": REPLAY_KIND,
            "board_dimensions": [width, height],
            "origin": normalized_origin,
            "origin_valid": False,
            "two_click": normalized_two_click,
            "second_target": normalized_second,
            "selected_callback": None,
            "callback_arguments": [],
            "callback_points_consumed": None,
            "cache_before": cache_before,
            "removed_negative_points": [],
            "cache_after": [],
            "returned_points": [],
        }

    use_second = (
        normalized_two_click
        and normalized_second[0] != -1
        and normalized_second[1] != -1
    )
    if use_second:
        if get_target_area_points is not None or get_second_target_area_points is None:
            raise EnemyTargetAreaCallbackBoundaryError(
                "GetSecondTargetArea replay requires only its selected callback output"
            )
        callback = "GetSecondTargetArea"
        arguments = [normalized_origin, normalized_second]
        callback_points = _normalize_points(
            get_second_target_area_points,
            "get_second_target_area_points",
        )
    else:
        if get_target_area_points is None or get_second_target_area_points is not None:
            raise EnemyTargetAreaCallbackBoundaryError(
                "GetTargetArea replay requires only its selected callback output"
            )
        callback = "GetTargetArea"
        arguments = [normalized_origin]
        callback_points = _normalize_points(
            get_target_area_points,
            "get_target_area_points",
        )

    removed = [point for point in callback_points if point[0] < 0 or point[1] < 0]
    filtered = [point for point in callback_points if point[0] >= 0 and point[1] >= 0]
    return {
        "replay_kind": REPLAY_KIND,
        "board_dimensions": [width, height],
        "origin": normalized_origin,
        "origin_valid": True,
        "two_click": normalized_two_click,
        "second_target": normalized_second,
        "selected_callback": callback,
        "callback_arguments": arguments,
        "callback_points_consumed": callback_points,
        "cache_before": cache_before,
        "removed_negative_points": removed,
        "cache_after": filtered,
        "returned_points": list(filtered),
    }


def _dependency_records() -> list[dict[str, str]]:
    return [dict(spec) for spec in DEPENDENCY_SPECS]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "start_rva": f"0x{start:08x}",
            "end_rva_exclusive": f"0x{end:08x}",
            "size": end - start,
            "sha256": sha256,
            "section": ".text",
            "evidence_class": "fact",
            "boundary_basis": basis,
        }
        for region_id, start, end, sha256, basis in REGION_SPECS
    ]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": window_id,
            "region": region_id,
            "start_rva": f"0x{start:08x}",
            "size": len(bytes.fromhex(encoded)),
            "instruction_hex": encoded,
            "sha256": hashlib.sha256(bytes.fromhex(encoded)).hexdigest(),
            "evidence_class": "fact",
            "meaning": meaning,
        }
        for window_id, region_id, start, encoded, meaning in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "kind": "direct_rel32",
            "source_region": source_region,
            "from_rva": f"0x{call_rva:08x}",
            "instruction_hex": encoded,
            "target": target_id,
            "target_rva": f"0x{target_rva:08x}",
            "evidence_class": "fact",
            "meaning": meaning,
        }
        for (
            edge_id,
            source_region,
            call_rva,
            encoded,
            target_id,
            target_rva,
            meaning,
        ) in DIRECT_EDGE_SPECS
    ]


def _jump_edge_records() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "kind": "jump_rel32",
            "source_region": source_region,
            "from_rva": f"0x{jump_rva:08x}",
            "instruction_hex": encoded,
            "target": target_id,
            "target_rva": f"0x{target_rva:08x}",
            "evidence_class": "fact",
            "meaning": meaning,
        }
        for (
            edge_id,
            source_region,
            jump_rva,
            encoded,
            target_id,
            target_rva,
            meaning,
        ) in JUMP_EDGE_SPECS
    ]


def _call_inventory_records() -> list[dict[str, Any]]:
    return [
        {
            "id": inventory_id,
            "target_rva": f"0x{target_rva:08x}",
            "scan_scope": "all file-backed executable sections, raw E8 rel32 scan",
            "complete_direct_call_count": len(sites),
            "sites": [
                {
                    "call_rva": f"0x{site:08x}",
                    "reviewed_role": role,
                    "role_evidence_class": "inference",
                }
                for site, role in sites
            ],
            "evidence_class": "fact",
        }
        for inventory_id, target_rva, sites in CALL_INVENTORY_SPECS
    ]


def _data_anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "data_rva": f"0x{rva:08x}",
            "section": section,
            "data_hex": encoded,
            "sha256": hashlib.sha256(bytes.fromhex(encoded)).hexdigest(),
            "evidence_class": "fact",
            "meaning": meaning,
        }
        for anchor_id, rva, section, encoded, meaning in DATA_ANCHOR_SPECS
    ]


def _instruction_anchor_records() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "start_rva": f"0x{rva:08x}",
            "instruction_hex": encoded,
            "size": len(bytes.fromhex(encoded)),
            "sha256": hashlib.sha256(bytes.fromhex(encoded)).hexdigest(),
            "evidence_class": "fact",
            "meaning": meaning,
        }
        for anchor_id, rva, encoded, meaning in INSTRUCTION_ANCHOR_SPECS
    ]


def _contracts() -> dict[str, Any]:
    return {
        "input": {
            "board_dimensions": "positive signed 32-bit width and height",
            "origin": "two signed 32-bit integers",
            "cached_points": "ordered materialized PointList before the call",
            "two_click": "strict boolean Lua field value",
            "second_target": "stored Skill +0x220/+0x224 Point",
            "callback_output": (
                "exactly the selected callback's already-materialized ordered native "
                "PointList, or neither output when origin is invalid"
            ),
            "tooling_point_limit": MAX_REPLAY_POINTS,
        },
        "branch_order": [
            "Store origin in Skill +0x12c/+0x130.",
            "Call Board:IsValid through Skill +0x110 vtable slot +0x14.",
            "On invalid origin, clear the cache and return an empty PointList.",
            "Otherwise read TwoClick and test each second-target coordinate against -1.",
            "Invoke GetSecondTargetArea(origin, second_target) only when all three tests pass; otherwise invoke GetTargetArea(origin).",
            "Replace the cache with the callback PointList.",
            "Erase points with negative x or negative y in encounter order.",
            "Return an order-preserving copy of the filtered cache.",
        ],
        "filter": {
            "reject": "x < 0 or y < 0",
            "retain": (
                "all x >= 0 and y >= 0, including duplicates and positive "
                "coordinates outside current Board dimensions"
            ),
            "order": "stable encounter order",
        },
        "scope": {
            "parameterized_native_wrapper_complete": True,
            "lua_callback_point_construction_complete": False,
            "skill_effect_materialization_complete": False,
            "complete_enemy_phase_forecast": False,
        },
    }


def _vector(vector_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": vector_id,
        "input": inputs,
        "expected": replay_enemy_target_area_callback(**inputs),
    }


def _replay_vectors() -> list[dict[str, Any]]:
    base = {
        "board_width": 8,
        "board_height": 8,
        "origin": [3, 4],
        "cached_points": [[7, 7], [1, 1]],
        "two_click": False,
        "second_target": [-1, -1],
        "get_target_area_points": [[3, 3]],
        "get_second_target_area_points": None,
    }
    vectors: list[dict[str, Any]] = []

    def add(vector_id: str, **overrides: Any) -> None:
        inputs = dict(base)
        inputs.update(overrides)
        vectors.append(_vector(vector_id, inputs))

    add(
        "invalid_negative_origin_clears_nonempty_cache",
        origin=[-1, 4],
        get_target_area_points=None,
    )
    add(
        "invalid_upper_bound_clears_nonempty_cache",
        origin=[8, 7],
        get_target_area_points=None,
    )
    add(
        "regular_filters_negative_and_preserves_order_duplicates_and_positive_oob",
        get_target_area_points=[
            [2, 2],
            [-1, 2],
            [2, 2],
            [9, 12],
            [3, -1],
            [0, 0],
        ],
    )
    add(
        "two_click_dispatches_second_callback",
        two_click=True,
        second_target=[5, 6],
        get_target_area_points=None,
        get_second_target_area_points=[[5, 6], [4, 4]],
    )
    add(
        "second_x_minus_one_falls_back_to_regular",
        two_click=True,
        second_target=[-1, 6],
    )
    add(
        "second_y_minus_one_falls_back_to_regular",
        two_click=True,
        second_target=[5, -1],
    )
    add(
        "negative_non_sentinel_second_target_still_dispatches_second",
        two_click=True,
        second_target=[-2, -3],
        get_target_area_points=None,
        get_second_target_area_points=[[-2, -3], [4, 5]],
    )
    add(
        "two_click_false_ignores_complete_second_target",
        two_click=False,
        second_target=[5, 6],
    )
    add("valid_lower_board_corner", origin=[0, 0])
    add("valid_upper_board_corner", origin=[7, 7])
    add("empty_regular_callback_replaces_nonempty_cache", get_target_area_points=[])
    add(
        "signed_extremes_filter_only_negative_coordinates",
        get_target_area_points=[
            [SIGNED_MIN, 0],
            [0, SIGNED_MIN],
            [SIGNED_MAX, SIGNED_MAX],
        ],
    )
    return vectors


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "skill_context_is_board_secondary_interface",
            "evidence_class": "inference",
            "claim": (
                "Skill +0x110 is the Board +0x0c secondary/path-manager interface: "
                "Board:AddPawn passes that exact adjusted pointer, the manager writes it "
                "to all vector Skills and Skill_Repair, and slot +0x14 is the exact "
                "-0x0c this-adjust thunk to Board:IsValid."
            ),
            "limitations": [
                "Semantic names derive from joined exact control flow and the prior "
                "Board-constructor artifact; no debug symbols exist."
            ],
        },
        {
            "id": "invalid_origin_clears_cache",
            "evidence_class": "inference",
            "claim": (
                "An invalid origin invokes no Lua target-area callback, move-assigns a "
                "fresh empty PointList over the prior Skill cache, and returns empty."
            ),
            "limitations": ["The replay requires an attached, readable Board context."],
        },
        {
            "id": "two_click_callback_selection",
            "evidence_class": "inference",
            "claim": (
                "A valid origin dispatches GetSecondTargetArea only when TwoClick is true "
                "and neither second-target coordinate equals -1; all other cases dispatch "
                "GetTargetArea."
            ),
            "limitations": [
                "Values less than -1 are not rejected by this dispatch predicate."
            ],
        },
        {
            "id": "native_post_callback_filter",
            "evidence_class": "inference",
            "claim": (
                "The native wrapper replaces the cache with the callback PointList, "
                "erases only points with negative x or y, and preserves order, "
                "duplicates, and nonnegative out-of-board coordinates."
            ),
            "limitations": [
                "Lua-to-native conversion and the concrete returned points remain boundary inputs."
            ],
        },
        {
            "id": "complete_direct_caller_census",
            "evidence_class": "fact",
            "claim": (
                "The exact executable has six raw direct callers to the callback wrapper "
                "and six raw direct callers to the SkillManager context writer."
            ),
            "limitations": [
                "Raw direct-call completeness does not enumerate indirect calls or assign "
                "semantic names beyond the reviewed enclosing functions."
            ],
        },
        {
            "id": "solver_scope_unchanged",
            "evidence_class": "fact",
            "claim": (
                "The ordinary bridge still lacks future ordered Lua callback PointLists, "
                "so the settled live enemy queue remains authoritative."
            ),
            "limitations": [
                "No Rust simulator semantic or version change follows from this artifact alone."
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "lua_target_point_construction",
            "question": "What exact ordered PointList does every concrete callback return?",
            "static_status": (
                "Native selection, caching, filtering, and return order are exact; the "
                "materialized callback PointList is a replay input."
            ),
            "next_evidence": (
                "Use source semantics or a behavior-neutral callback capture only for "
                "mismatch-driven subclasses that need a Rust conformance oracle."
            ),
        },
        {
            "id": "skill_effect_materialization",
            "question": "How does the adjacent native GetSkillEffect cache body materialize effects?",
            "static_status": (
                "Its target-membership gate and GetSkillEffect/GetFinalEffect_Helper/"
                "Explosion branch family are located but are outside this PointList artifact."
            ),
            "next_evidence": (
                "Publish a separate exact-build SkillEffect materialization boundary without "
                "conflating Lua-produced effects with native postprocessing."
            ),
        },
        {
            "id": "complete_enemy_tournament_runtime_join",
            "question": "Can this wrapper become an ordinary future-action solver input?",
            "static_status": (
                "The bridge exposes settled queues, not every prospective callback PointList "
                "or the later selector-entry shared RNG state."
            ),
            "next_evidence": (
                "Capture a complete ordered tournament only if a concrete solver mismatch "
                "justifies behavior-neutral runtime observation."
            ),
        },
        {
            "id": "non_windows_or_modified_builds",
            "question": "Does this wrapper remain identical on other builds or mods?",
            "static_status": "Every address, byte, field offset, and replay claim is exact-build scoped.",
            "next_evidence": "Repeat inventory and reviewed mapping for each additional executable.",
        },
    ]


def _expected_shape() -> dict[str, Any]:
    dependencies = _dependency_records()
    regions = _region_records()
    windows = _control_window_records()
    direct_edges = _direct_edge_records()
    jump_edges = _jump_edge_records()
    call_inventories = _call_inventory_records()
    data_anchors = _data_anchor_records()
    instruction_anchors = _instruction_anchor_records()
    vectors = _replay_vectors()
    findings = _findings()
    unresolved = _unresolved()
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": {
            "platform": "windows",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "architecture": "x86",
            "bits": 32,
            "image_base": f"0x{EXPECTED_IMAGE_BASE:08x}",
        },
        "dependencies": dependencies,
        "method": {
            "tools": [
                {
                    "name": "Ghidra",
                    "version": "12.1.3",
                    "role": (
                        "Read-only function extents, direct callers, field flow, and "
                        "bounded decompiler corroboration."
                    ),
                },
                {
                    "name": "Capstone",
                    "version": "5.0.7",
                    "role": "Independent complete x86 decoding and edge verification.",
                },
                {
                    "name": "ITB exact-build verifier",
                    "version": "schema 1",
                    "role": (
                        "Dependency, executable, region, window, pointer, raw-caller, "
                        "and replay-vector validation."
                    ),
                },
            ],
            "procedure": [
                "Join Board:AddPawn, SkillManager context writes, the Board secondary vtable, and its IsValid thunk.",
                "Hash complete reviewed functions and pin instruction-aligned semantic windows and direct edges.",
                "Reimplement callback selection, cache mutation, filtering, and return as a strict pure replay.",
            ],
            "limitations": [
                "No executable bytes or proprietary decompiled source are stored beyond bounded verification windows.",
                "Function meanings remain reviewed analyst evidence even though published bytes and edges reproduce.",
                "Replay begins with already-materialized native callback PointLists and does not execute Lua.",
                "No claim is made for macOS, another Windows build, or modified native code.",
            ],
        },
        "regions": regions,
        "control_windows": windows,
        "direct_call_edges": direct_edges,
        "jump_edges": jump_edges,
        "call_inventories": call_inventories,
        "data_anchors": data_anchors,
        "instruction_anchors": instruction_anchors,
        "contracts": _contracts(),
        "replay_vectors": vectors,
        "findings": findings,
        "unresolved": unresolved,
        "solver_impact": {
            "simulator_change_required": False,
            "current_simulator_version": 408,
            "reason": (
                "The native wrapper is exact from explicit callback points, but those future "
                "ordered callback outputs are not ordinary solver inputs."
            ),
        },
        "summary": {
            "dependency_count": len(dependencies),
            "region_count": len(regions),
            "control_window_count": len(windows),
            "direct_edge_count": len(direct_edges),
            "jump_edge_count": len(jump_edges),
            "call_inventory_count": len(call_inventories),
            "data_anchor_count": len(data_anchors),
            "instruction_anchor_count": len(instruction_anchors),
            "replay_vector_count": len(vectors),
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "parameterized_native_wrapper_complete": True,
            "invalid_origin_clears_cache": True,
            "lua_callback_point_construction_complete": False,
            "skill_effect_materialization_complete": False,
            "complete_enemy_phase_forecast": False,
            "simulator_change_required": False,
            "simulator_version": 408,
        },
    }


def _verify_dependencies() -> None:
    values: dict[str, Mapping[str, Any]] = {}
    for spec in DEPENDENCY_SPECS:
        path = REPO_ROOT / spec["path"]
        raw = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"dependency file differs: {spec['id']}"
            )
        value = _read_json(path)
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"dependency fields differ: {spec['id']}"
            )
        values[spec["id"]] = value
    try:
        validate_enemy_target_area_boundary_map_binding(
            values["enemy_target_area_gate"]
        )
        validate_path_occupancy_lifecycle_map_binding(
            values["path_occupancy_lifecycle"]
        )
    except (EnemyTargetAreaBoundaryError, PathOccupancyLifecycleError) as exc:
        raise EnemyTargetAreaCallbackBoundaryError(
            f"native dependency binding differs: {exc}"
        ) from exc


def _verify_native(executable: Path) -> None:
    data, image, executable_sha256 = _load_executable(executable)
    if executable_sha256 != EXPECTED_EXECUTABLE_SHA256:
        raise EnemyTargetAreaCallbackBoundaryError("executable SHA-256 differs")
    if len(data) != EXPECTED_EXECUTABLE_SIZE:
        raise EnemyTargetAreaCallbackBoundaryError("executable size differs")
    if image.architecture != "x86" or image.bits != 32:
        raise EnemyTargetAreaCallbackBoundaryError("expected a PE32 x86 executable")
    if image.image_base != EXPECTED_IMAGE_BASE:
        raise EnemyTargetAreaCallbackBoundaryError("PE image base differs")

    region_ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        body = _region_bytes(image, data, start, end - start, ".text", region_id)
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise EnemyTargetAreaCallbackBoundaryError(f"region differs: {region_id}")
        region_ranges[region_id] = (start, end)
    decoded_regions = _decode_x86_regions(image, data, region_ranges)

    for window_id, region_id, start, expected_hex, _meaning in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(expected_hex)
        region_start, region_end = region_ranges[region_id]
        if not region_start <= start or start + len(expected) > region_end:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"control window escapes region: {window_id}"
            )
        if _bytes_at(image, data, start, len(expected)) != expected:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"control window differs: {window_id}"
            )
        cursor = start
        while cursor < start + len(expected):
            instruction = decoded_regions[region_id].get(cursor)
            if instruction is None:
                raise EnemyTargetAreaCallbackBoundaryError(
                    f"control window is not instruction-aligned: {window_id}"
                )
            cursor += len(instruction[1])
        if cursor != start + len(expected):
            raise EnemyTargetAreaCallbackBoundaryError(
                f"control window ends inside an instruction: {window_id}"
            )

    for (
        edge_id,
        _source_region,
        call_rva,
        expected_hex,
        _target_id,
        target_rva,
        _meaning,
    ) in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(expected_hex)
        actual = _bytes_at(image, data, call_rva, len(expected))
        if actual != expected or _rel32_target(call_rva, actual, 0xE8) != target_rva:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"direct edge differs: {edge_id}"
            )

    for (
        edge_id,
        _source_region,
        jump_rva,
        expected_hex,
        _target_id,
        target_rva,
        _meaning,
    ) in JUMP_EDGE_SPECS:
        expected = bytes.fromhex(expected_hex)
        actual = _bytes_at(image, data, jump_rva, len(expected))
        if actual != expected or _rel32_target(jump_rva, actual, 0xE9) != target_rva:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"jump edge differs: {edge_id}"
            )

    for inventory_id, target_rva, sites in CALL_INVENTORY_SPECS:
        expected_sites = {site for site, _role in sites}
        if _raw_rel32_call_sites(image, data, target_rva) != expected_sites:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"direct-call inventory differs: {inventory_id}"
            )

    for anchor_id, rva, expected_section, expected_hex, _meaning in DATA_ANCHOR_SPECS:
        expected = bytes.fromhex(expected_hex)
        section = next(
            (
                candidate
                for candidate in image.sections
                if candidate.virtual_address <= rva
                and rva + len(expected)
                <= candidate.virtual_address + candidate.raw_size
            ),
            None,
        )
        if section is None or section.name != expected_section:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"data anchor section differs: {anchor_id}"
            )
        if _bytes_at(image, data, rva, len(expected)) != expected:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"data anchor differs: {anchor_id}"
            )
        if anchor_id == "board_secondary_isvalid_slot" and struct.unpack(
            "<I", expected
        )[0] != EXPECTED_IMAGE_BASE + 0x0017A9C0:
            raise EnemyTargetAreaCallbackBoundaryError(
                "Board secondary IsValid vtable pointer target differs"
            )

    instruction_ranges: dict[str, tuple[int, int]] = {}
    for anchor_id, rva, expected_hex, _meaning in INSTRUCTION_ANCHOR_SPECS:
        expected = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, rva, len(expected)) != expected:
            raise EnemyTargetAreaCallbackBoundaryError(
                f"instruction anchor differs: {anchor_id}"
            )
        instruction_ranges[anchor_id] = (rva, rva + len(expected))
    _decode_x86_regions(image, data, instruction_ranges)


def build_enemy_target_area_callback_boundary_map(executable: Path) -> dict[str, Any]:
    """Build the exact expected artifact after verifying native inputs."""
    _verify_dependencies()
    _verify_native(executable)
    return _expected_shape()


def validate_enemy_target_area_callback_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the executable."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise EnemyTargetAreaCallbackBoundaryError(
            "target-area callback boundary fields differ"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "parameterized_native_wrapper_complete": True,
        "invalid_origin_clears_cache": True,
        "lua_callback_point_construction_complete": False,
        "skill_effect_materialization_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def validate_enemy_target_area_callback_boundary_map(
    executable: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the artifact and reject byte, dependency, or replay drift."""
    expected = build_enemy_target_area_callback_boundary_map(executable)
    if dict(value) != expected:
        raise EnemyTargetAreaCallbackBoundaryError(
            "target-area callback map differs from exact-build analysis"
        )
    result = validate_enemy_target_area_callback_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_enemy_target_area_callback_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
