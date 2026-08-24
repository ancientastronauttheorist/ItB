#!/usr/bin/env python3
"""Build and attest the dormant x86 ScorePositioning x87 observer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_itb_observatory_rng_core_observer as common


SOURCE = ROOT / "src" / "native" / "observatory_score_positioning_x87_observer.c"
OBSERVER_VERSION = "observatory-score-positioning-x87-observer/1"
EXPORT_NAME = "luaopen_itb_observatory_score_positioning_x87_observer"

EXPECTED_BUILD_ID = "13725832"
EXPECTED_ARCHITECTURE = "x86"
EXPECTED_EXECUTABLE_SHA256 = common.EXPECTED_EXECUTABLE_SHA256
EXPECTED_EXECUTABLE_SIZE = common.EXPECTED_EXECUTABLE_SIZE
EXPECTED_PE_TIMESTAMP = common.EXPECTED_PE_TIMESTAMP
EXPECTED_PE_SIZE_OF_IMAGE = common.EXPECTED_PE_SIZE_OF_IMAGE
EXPECTED_INVENTORY_CANONICAL_SHA256 = (
    "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
)

EXPECTED_LUA_SHA256 = (
    "0157f0c34e72b32e63ebf3fdd9a21215de674b51b6d1750ebe545ef3093a0c14"
)
EXPECTED_LUA_SIZE = 419_840
EXPECTED_LUA_PE_TIMESTAMP = 0x5A686CD2
EXPECTED_LUA_PE_SIZE_OF_IMAGE = 0x0006B000
EXPECTED_LUA_TOINTEGER_RVA = 0x000016D0
EXPECTED_LUA_TOINTEGER_SIZE = 125
EXPECTED_LUA_TOINTEGER_SHA256 = (
    "2d935d28eefdd86c2035f20567820a17c7bc0b9941b5343bf3475fcf7c30b2ab"
)
EXPECTED_LUA_FLD_RVA = 0x00001726
EXPECTED_LUA_FISTP_RVA = 0x00001729
EXPECTED_LUA_CONVERSION_BYTES = bytes.fromhex("dd45f0db5de4")

EXPECTED_SCORE_POSITIONING_RVA = 0x000F7870
EXPECTED_SCORE_POSITIONING_SIZE = 124
EXPECTED_SCORE_POSITIONING_SHA256 = (
    "9794db437203d18af0ce5245bc178f537e20f715b192c671cc7ecde7d279a42a"
)
EXPECTED_SCORE_POSITIONING_CALL_RVA = 0x000F78D5
EXPECTED_SCORE_POSITIONING_CALL_BYTES = bytes.fromhex("e8960e0000")
EXPECTED_SCORE_POSITIONING_AFTER_NAMED_RVA = 0x000F78DA

EXPECTED_NAMED_INVOKER_RVA = 0x000F8770
EXPECTED_NAMED_INVOKER_SIZE = 259
EXPECTED_NAMED_INVOKER_SHA256 = (
    "59607f3c4741577e11c570b31aeb3dfaadec00d85ec8a69e024a7f06760e584e"
)
EXPECTED_NAMED_INVOKER_HELPER_CALL_RVA = 0x000F87DD
EXPECTED_NAMED_INVOKER_HELPER_CALL_BYTES = bytes.fromhex("e8ae020000")
EXPECTED_NAMED_INVOKER_AFTER_HELPER_RVA = 0x000F87E2

EXPECTED_INTEGER_HELPER_RVA = 0x000F8A90
EXPECTED_INTEGER_HELPER_SIZE = 294
EXPECTED_INTEGER_HELPER_SHA256 = (
    "1f979a7f27695df192b75d20e076aa1a6c5ad83a2f5657d6858e1c01d4f45704"
)
EXPECTED_INTEGER_CALL_RVA = 0x000F8B89
EXPECTED_INTEGER_CALL_BYTES = bytes.fromhex("ff15f0647d00")
EXPECTED_INTEGER_HELPER_AFTER_LUA_RVA = 0x000F8B8F
EXPECTED_LUA_TOINTEGER_IAT_RVA = 0x003D64F0
EXPECTED_DR7 = 0x00000001

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ObserverBuildError(RuntimeError):
    """Raised when a build or attestation cannot be trusted."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _canonical_object_sha256(value: Any) -> str:
    data = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(data)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--lua-dll", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--native-boundaries", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _region(boundaries: dict[str, Any], region_id: str) -> dict[str, Any]:
    regions = boundaries.get("regions")
    if not isinstance(regions, list):
        raise ObserverBuildError("boundary map regions must be an array")
    matches = [
        value
        for value in regions
        if isinstance(value, dict) and value.get("id") == region_id
    ]
    if len(matches) != 1:
        raise ObserverBuildError(f"boundary map needs one {region_id} region")
    return matches[0]


def _expect_region(
    boundaries: dict[str, Any],
    region_id: str,
    rva: int,
    size: int,
    digest: str,
) -> None:
    region = _region(boundaries, region_id)
    if (
        region.get("start_rva") != f"0x{rva:08x}"
        or region.get("size") != size
        or region.get("sha256") != digest
        or region.get("section") != ".text"
        or region.get("evidence_class") != "fact"
    ):
        raise ObserverBuildError(f"boundary map {region_id} region differs")


def _exact_region(
    data: bytes,
    image: common.PEImage,
    rva: int,
    size: int,
    digest: str,
    label: str,
) -> bytes:
    section = image.section_for_rva(rva)
    if not section.executable:
        raise ObserverBuildError(f"{label} is not in an executable section")
    offset = image.rva_to_offset(rva, size)
    body = data[offset : offset + size]
    if len(body) != size or _sha256(body) != digest:
        raise ObserverBuildError(f"{label} bytes differ")
    return body


def _exact_bytes(
    data: bytes,
    image: common.PEImage,
    rva: int,
    expected: bytes,
    label: str,
) -> bytes:
    offset = image.rva_to_offset(rva, len(expected))
    found = data[offset : offset + len(expected)]
    if found != expected or not image.section_for_rva(rva).executable:
        raise ObserverBuildError(f"{label} bytes differ")
    return found


def _direct_rel32_target(call_rva: int, call_bytes: bytes) -> int:
    if len(call_bytes) != 5 or call_bytes[0] != 0xE8:
        raise ObserverBuildError("reviewed direct call is malformed")
    (relative,) = struct.unpack_from("<i", call_bytes, 1)
    return (call_rva + 5 + relative) & 0xFFFFFFFF


def _pe_named_export_rvas(data: bytes, image: common.PEImage) -> dict[str, int]:
    if image.export_rva == 0 or image.export_size < 40:
        raise ObserverBuildError("PE has no export directory")
    directory_offset = image.rva_to_offset(image.export_rva, 40)
    (
        _characteristics,
        _timestamp,
        _major_minor,
        _name_rva,
        _base,
        function_count,
        name_count,
        functions_rva,
        names_rva,
        ordinals_rva,
    ) = struct.unpack_from("<IIIII IIIII".replace(" ", ""), data, directory_offset)
    if function_count == 0 or name_count == 0 or name_count > 65_536:
        raise ObserverBuildError("PE export directory counts are invalid")
    functions_offset = image.rva_to_offset(functions_rva, function_count * 4)
    names_offset = image.rva_to_offset(names_rva, name_count * 4)
    ordinals_offset = image.rva_to_offset(ordinals_rva, name_count * 2)
    exports: dict[str, int] = {}
    for index in range(name_count):
        (name_rva,) = struct.unpack_from("<I", data, names_offset + index * 4)
        name_offset = image.rva_to_offset(name_rva)
        end = data.find(b"\0", name_offset, min(len(data), name_offset + 512))
        if end < 0:
            raise ObserverBuildError("PE export name is unterminated")
        try:
            name = data[name_offset:end].decode("ascii", errors="strict")
        except UnicodeDecodeError as exc:
            raise ObserverBuildError("PE export name is not ASCII") from exc
        (ordinal,) = struct.unpack_from("<H", data, ordinals_offset + index * 2)
        if ordinal >= function_count:
            raise ObserverBuildError("PE export ordinal is outside function table")
        (function_rva,) = struct.unpack_from(
            "<I", data, functions_offset + ordinal * 4
        )
        if image.export_rva <= function_rva < image.export_rva + image.export_size:
            raise ObserverBuildError("forwarded PE export is not accepted")
        if name in exports:
            raise ObserverBuildError("duplicate PE export name")
        exports[name] = function_rva
    return exports


def _validate_inventory(
    inventory_path: Path,
    executable_path: Path,
    lua_path: Path,
) -> tuple[dict[str, Any], str, str]:
    try:
        inventory, inventory_bytes = common._load_json(inventory_path, "inventory")
    except (common.ObserverBuildError, OSError) as exc:
        raise ObserverBuildError(str(exc)) from exc
    canonical_sha = _canonical_object_sha256(inventory)
    if canonical_sha != EXPECTED_INVENTORY_CANONICAL_SHA256:
        raise ObserverBuildError("inventory is not the pinned canonical inventory")
    executable = inventory.get("executable")
    libraries = inventory.get("native_libraries")
    lua_matches = [
        value
        for value in libraries if isinstance(value, dict) and value.get("path") == "lua5.1.dll"
    ] if isinstance(libraries, list) else []
    if (
        inventory.get("schema_version") != 1
        or inventory.get("app_id") != "590380"
        or inventory.get("platform") != "windows"
        or not isinstance(executable, dict)
        or executable.get("path") != executable_path.name
        or executable.get("sha256") != EXPECTED_EXECUTABLE_SHA256
        or executable.get("size") != EXPECTED_EXECUTABLE_SIZE
        or len(lua_matches) != 1
        or lua_matches[0].get("path") != lua_path.name
        or lua_matches[0].get("sha256") != EXPECTED_LUA_SHA256
        or lua_matches[0].get("size") != EXPECTED_LUA_SIZE
    ):
        raise ObserverBuildError("inventory executable or Lua identity differs")
    return inventory, canonical_sha, _sha256(inventory_bytes)


def _validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    try:
        executable = common._stable_bytes(args.executable, "Breach.exe")
        lua = common._stable_bytes(args.lua_dll, "lua5.1.dll")
        boundaries, boundary_bytes = common._load_json(
            args.native_boundaries, "native boundaries"
        )
    except (common.ObserverBuildError, OSError) as exc:
        raise ObserverBuildError(str(exc)) from exc
    if (
        len(executable) != EXPECTED_EXECUTABLE_SIZE
        or _sha256(executable) != EXPECTED_EXECUTABLE_SHA256
    ):
        raise ObserverBuildError("Breach.exe does not match the pinned build")
    if len(lua) != EXPECTED_LUA_SIZE or _sha256(lua) != EXPECTED_LUA_SHA256:
        raise ObserverBuildError("lua5.1.dll does not match the pinned build")
    executable_image = common._parse_pe(executable)
    lua_image = common._parse_pe(lua)
    if (
        executable_image.machine != 0x014C
        or executable_image.timestamp != EXPECTED_PE_TIMESTAMP
        or executable_image.size_of_image != EXPECTED_PE_SIZE_OF_IMAGE
        or executable_image.image_base != 0x00400000
    ):
        raise ObserverBuildError("Breach.exe PE identity differs")
    if (
        lua_image.machine != 0x014C
        or lua_image.timestamp != EXPECTED_LUA_PE_TIMESTAMP
        or lua_image.size_of_image != EXPECTED_LUA_PE_SIZE_OF_IMAGE
        or lua_image.image_base != 0x10000000
    ):
        raise ObserverBuildError("lua5.1.dll PE identity differs")

    identity = boundaries.get("identity")
    if (
        boundaries.get("schema_version") != 1
        or boundaries.get("analysis_kind") != "pe_reviewed_boundary_map"
        or not isinstance(identity, dict)
        or identity.get("platform") != "windows"
        or identity.get("architecture") != EXPECTED_ARCHITECTURE
        or identity.get("build_id") != EXPECTED_BUILD_ID
        or identity.get("executable_sha256") != EXPECTED_EXECUTABLE_SHA256
        or identity.get("executable_size") != EXPECTED_EXECUTABLE_SIZE
    ):
        raise ObserverBuildError("native boundary identity differs")
    _expect_region(
        boundaries,
        "score_positioning",
        EXPECTED_SCORE_POSITIONING_RVA,
        EXPECTED_SCORE_POSITIONING_SIZE,
        EXPECTED_SCORE_POSITIONING_SHA256,
    )
    _expect_region(
        boundaries,
        "named_integer_invoker",
        EXPECTED_NAMED_INVOKER_RVA,
        EXPECTED_NAMED_INVOKER_SIZE,
        EXPECTED_NAMED_INVOKER_SHA256,
    )
    score_body = _exact_region(
        executable,
        executable_image,
        EXPECTED_SCORE_POSITIONING_RVA,
        EXPECTED_SCORE_POSITIONING_SIZE,
        EXPECTED_SCORE_POSITIONING_SHA256,
        "ScorePositioning",
    )
    invoker_body = _exact_region(
        executable,
        executable_image,
        EXPECTED_NAMED_INVOKER_RVA,
        EXPECTED_NAMED_INVOKER_SIZE,
        EXPECTED_NAMED_INVOKER_SHA256,
        "named integer invoker",
    )
    helper_body = _exact_region(
        executable,
        executable_image,
        EXPECTED_INTEGER_HELPER_RVA,
        EXPECTED_INTEGER_HELPER_SIZE,
        EXPECTED_INTEGER_HELPER_SHA256,
        "integer helper",
    )
    score_call = _exact_bytes(
        executable,
        executable_image,
        EXPECTED_SCORE_POSITIONING_CALL_RVA,
        EXPECTED_SCORE_POSITIONING_CALL_BYTES,
        "ScorePositioning call",
    )
    invoker_call = _exact_bytes(
        executable,
        executable_image,
        EXPECTED_NAMED_INVOKER_HELPER_CALL_RVA,
        EXPECTED_NAMED_INVOKER_HELPER_CALL_BYTES,
        "named invoker helper call",
    )
    integer_call = _exact_bytes(
        executable,
        executable_image,
        EXPECTED_INTEGER_CALL_RVA,
        EXPECTED_INTEGER_CALL_BYTES,
        "lua_tointeger IAT call",
    )
    if (
        _direct_rel32_target(EXPECTED_SCORE_POSITIONING_CALL_RVA, score_call)
        != EXPECTED_NAMED_INVOKER_RVA
        or _direct_rel32_target(
            EXPECTED_NAMED_INVOKER_HELPER_CALL_RVA, invoker_call
        )
        != EXPECTED_INTEGER_HELPER_RVA
    ):
        raise ObserverBuildError("reviewed ScorePositioning call chain differs")
    if integer_call[:2] != b"\xff\x15" or struct.unpack_from(
        "<I", integer_call, 2
    )[0] != 0x00400000 + EXPECTED_LUA_TOINTEGER_IAT_RVA:
        raise ObserverBuildError("lua_tointeger IAT operand differs")

    lua_tointeger = _exact_region(
        lua,
        lua_image,
        EXPECTED_LUA_TOINTEGER_RVA,
        EXPECTED_LUA_TOINTEGER_SIZE,
        EXPECTED_LUA_TOINTEGER_SHA256,
        "lua_tointeger",
    )
    conversion = _exact_bytes(
        lua,
        lua_image,
        EXPECTED_LUA_FLD_RVA,
        EXPECTED_LUA_CONVERSION_BYTES,
        "lua_tointeger FLD/FISTP conversion",
    )
    if _pe_named_export_rvas(lua, lua_image).get("lua_tointeger") != (
        EXPECTED_LUA_TOINTEGER_RVA
    ):
        raise ObserverBuildError("lua_tointeger export RVA differs")
    inventory, inventory_sha, inventory_file_sha = _validate_inventory(
        args.inventory, args.executable, args.lua_dll
    )
    boundary_sha = _canonical_object_sha256(boundaries)
    if _SHA256_RE.fullmatch(boundary_sha) is None:
        raise ObserverBuildError("boundary-map digest is malformed")
    return {
        "executable": executable,
        "executable_image": executable_image,
        "lua": lua,
        "lua_image": lua_image,
        "inventory": inventory,
        "inventory_canonical_sha256": inventory_sha,
        "inventory_file_sha256": inventory_file_sha,
        "boundary_map_canonical_sha256": boundary_sha,
        "boundary_map_file_sha256": _sha256(boundary_bytes),
        "score_body": score_body,
        "invoker_body": invoker_body,
        "helper_body": helper_body,
        "score_call": score_call,
        "invoker_call": invoker_call,
        "integer_call": integer_call,
        "lua_tointeger": lua_tointeger,
        "conversion": conversion,
    }


def _hardware_breakpoint_plan(
    source_sha256: str, identities: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "observatory_score_positioning_x87_hardware_breakpoint_plan",
        "observer_version": OBSERVER_VERSION,
        "identity": {
            "platform": "windows",
            "architecture": EXPECTED_ARCHITECTURE,
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "lua_dll_sha256": EXPECTED_LUA_SHA256,
            "lua_dll_size": EXPECTED_LUA_SIZE,
            "inventory_sha256": identities["inventory_canonical_sha256"],
            "boundary_map_sha256": identities["boundary_map_canonical_sha256"],
            "source_sha256": source_sha256,
        },
        "breakpoint": {
            "slot": "DR0",
            "kind": "x86_execute_length_1_current_thread_only",
            "image": "lua5.1.dll",
            "semantic_boundary": "lua_tointeger_immediately_before_fistp",
            "rva": f"0x{EXPECTED_LUA_FISTP_RVA:08x}",
            "expected_prebytes_hex": EXPECTED_LUA_CONVERSION_BYTES[3:].hex(),
            "expected_prebytes_sha256": _sha256(
                EXPECTED_LUA_CONVERSION_BYTES[3:]
            ),
            "observed_field": "CONTEXT.FloatSave.ControlWord",
        },
        "accepted_frame_chain": [
            {
                "frame": "lua_tointeger",
                "return_image": "Breach.exe",
                "return_rva": f"0x{EXPECTED_INTEGER_HELPER_AFTER_LUA_RVA:08x}",
            },
            {
                "frame": "integer_helper",
                "return_image": "Breach.exe",
                "return_rva": f"0x{EXPECTED_NAMED_INVOKER_AFTER_HELPER_RVA:08x}",
            },
            {
                "frame": "named_integer_invoker",
                "return_image": "Breach.exe",
                "return_rva": f"0x{EXPECTED_SCORE_POSITIONING_AFTER_NAMED_RVA:08x}",
            },
        ],
        "reviewed_call_chain": [
            {
                "caller": "ScorePositioning",
                "call_rva": f"0x{EXPECTED_SCORE_POSITIONING_CALL_RVA:08x}",
                "callee": "named_integer_invoker",
            },
            {
                "caller": "named_integer_invoker",
                "call_rva": f"0x{EXPECTED_NAMED_INVOKER_HELPER_CALL_RVA:08x}",
                "callee": "integer_helper",
            },
            {
                "caller": "integer_helper",
                "call_rva": f"0x{EXPECTED_INTEGER_CALL_RVA:08x}",
                "callee": "lua5.1.dll!lua_tointeger",
            },
        ],
        "debug_register_contract": {
            "arm_rejects_any_nonzero_dr0_dr1_dr2_dr3_or_dr7": True,
            "dr7_exact": f"0x{EXPECTED_DR7:08x}",
            "transition": "private_RaiseException_handled_by_VEH",
            "accepted_observation_self_clears_dr0_dr1_dr2_dr3_dr6_dr7": True,
            "finish_requires_exact_owned_state_before_clear": True,
        },
        "capture_contract": {
            "record_capacity": 1,
            "thread_capacity": 1,
            "rounding_control_mask": "0x0c00",
            "rounding_modes": {
                "0x0000": "nearest_even",
                "0x0400": "down",
                "0x0800": "up",
                "0x0c00": "toward_zero",
            },
        },
        "mutation_contract": {
            "executable_bytes_modified": False,
            "lua_bytes_modified": False,
            "page_protection_changed": False,
            "gateway_allocated": False,
            "detour_installed": False,
            "x87_control_word_modified": False,
            "mxcsr_modified": False,
        },
        "hot_contract": {
            "allocation": False,
            "file_io": False,
            "lua_or_game_calls": False,
            "locks": False,
            "clocks": False,
            "windows_api_calls": False,
            "x87_sse_mmx_avx_instructions": False,
        },
    }


def _c_bytes(name: str, data: bytes) -> str:
    values = ", ".join(f"0x{value:02x}" for value in data)
    return f"static const unsigned char {name}[{len(data)}] = {{{values}}};"


def _generated_include(identities: dict[str, Any], plan_sha256: str) -> bytes:
    executable_digest = bytes.fromhex(EXPECTED_EXECUTABLE_SHA256)
    lua_digest = bytes.fromhex(EXPECTED_LUA_SHA256)
    text = f"""/* Generated; do not edit or install independently. */
#ifndef OBSERVATORY_SCORE_POSITIONING_X87_BUILD_INC
#define OBSERVATORY_SCORE_POSITIONING_X87_BUILD_INC

#define OBS_BUILD_ID \"{EXPECTED_BUILD_ID}\"
#define OBS_EXECUTABLE_SHA256 \"{EXPECTED_EXECUTABLE_SHA256}\"
#define OBS_EXECUTABLE_SIZE {EXPECTED_EXECUTABLE_SIZE}LL
#define OBS_PE_TIMESTAMP 0x{EXPECTED_PE_TIMESTAMP:08x}u
#define OBS_PE_SIZE_OF_IMAGE 0x{EXPECTED_PE_SIZE_OF_IMAGE:08x}u
#define OBS_LUA_SHA256 \"{EXPECTED_LUA_SHA256}\"
#define OBS_LUA_SIZE {EXPECTED_LUA_SIZE}LL
#define OBS_LUA_PE_TIMESTAMP 0x{EXPECTED_LUA_PE_TIMESTAMP:08x}u
#define OBS_LUA_PE_SIZE_OF_IMAGE 0x{EXPECTED_LUA_PE_SIZE_OF_IMAGE:08x}u
#define OBS_INVENTORY_SHA256 \"{identities['inventory_canonical_sha256']}\"
#define OBS_BOUNDARY_MAP_SHA256 \"{identities['boundary_map_canonical_sha256']}\"
#define OBS_HW_PLAN_SHA256 \"{plan_sha256}\"

#define OBS_SCORE_POSITIONING_CALL_RVA 0x{EXPECTED_SCORE_POSITIONING_CALL_RVA:08x}u
#define OBS_SCORE_POSITIONING_CALL_SIZE {len(EXPECTED_SCORE_POSITIONING_CALL_BYTES)}u
#define OBS_SCORE_POSITIONING_AFTER_NAMED_RVA 0x{EXPECTED_SCORE_POSITIONING_AFTER_NAMED_RVA:08x}u
#define OBS_NAMED_INVOKER_HELPER_CALL_RVA 0x{EXPECTED_NAMED_INVOKER_HELPER_CALL_RVA:08x}u
#define OBS_NAMED_INVOKER_HELPER_CALL_SIZE {len(EXPECTED_NAMED_INVOKER_HELPER_CALL_BYTES)}u
#define OBS_NAMED_INVOKER_AFTER_HELPER_RVA 0x{EXPECTED_NAMED_INVOKER_AFTER_HELPER_RVA:08x}u
#define OBS_INTEGER_CALL_RVA 0x{EXPECTED_INTEGER_CALL_RVA:08x}u
#define OBS_INTEGER_CALL_RVA_TEXT \"0x{EXPECTED_INTEGER_CALL_RVA:08x}\"
#define OBS_INTEGER_CALL_PREFIX_SIZE 2u
#define OBS_INTEGER_HELPER_AFTER_LUA_RVA 0x{EXPECTED_INTEGER_HELPER_AFTER_LUA_RVA:08x}u
#define OBS_LUA_TOINTEGER_IAT_RVA 0x{EXPECTED_LUA_TOINTEGER_IAT_RVA:08x}u
#define OBS_LUA_TOINTEGER_RVA 0x{EXPECTED_LUA_TOINTEGER_RVA:08x}u
#define OBS_LUA_TOINTEGER_RVA_TEXT \"0x{EXPECTED_LUA_TOINTEGER_RVA:08x}\"
#define OBS_LUA_CONVERSION_RVA 0x{EXPECTED_LUA_FISTP_RVA:08x}u
#define OBS_LUA_CONVERSION_RVA_TEXT \"0x{EXPECTED_LUA_FISTP_RVA:08x}\"
#define OBS_LUA_CONVERSION_SIZE {len(EXPECTED_LUA_CONVERSION_BYTES[3:])}u

{_c_bytes('OBS_EXECUTABLE_SHA256_BYTES', executable_digest)}
{_c_bytes('OBS_LUA_SHA256_BYTES', lua_digest)}
{_c_bytes('OBS_SCORE_POSITIONING_CALL_BYTES', EXPECTED_SCORE_POSITIONING_CALL_BYTES)}
{_c_bytes('OBS_NAMED_INVOKER_HELPER_CALL_BYTES', EXPECTED_NAMED_INVOKER_HELPER_CALL_BYTES)}
{_c_bytes('OBS_INTEGER_CALL_PREFIX', EXPECTED_INTEGER_CALL_BYTES[:2])}
{_c_bytes('OBS_LUA_CONVERSION_BYTES', EXPECTED_LUA_CONVERSION_BYTES[3:])}

#endif
"""
    return text.encode("ascii")


def _attest_source(source: bytes) -> dict[str, Any]:
    try:
        text = source.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise ObserverBuildError("observer source must remain ASCII") from exc
    if text.count("__declspec(dllexport)") != 1 or text.count(EXPORT_NAME) != 1:
        raise ObserverBuildError("observer source must expose exactly one Lua opener")
    if "DllMain" in text:
        raise ObserverBuildError("observer source must have no loader-time behavior")
    start = text.find("/* OBS_HOT_PATH_BEGIN")
    end = text.find("/* OBS_HOT_PATH_END */")
    if start < 0 or end <= start:
        raise ObserverBuildError("observer hot-path markers are missing")
    hot = text[start:end]
    banned_hot = (
        "HeapAlloc",
        "VirtualAlloc",
        "VirtualProtect",
        "WriteProcessMemory",
        "CreateFile",
        "ReadFile",
        "g_lua_gettop",
        "g_luaL_error",
        "g_lua_createtable",
        "g_lua_push",
        "g_lua_setfield",
        "RaiseException",
        "GetCurrentThreadId",
        "QueryPerformance",
        "EnterCriticalSection",
        "malloc",
        "free(",
        "fopen",
    )
    found = [name for name in banned_hot if name in hot]
    if found:
        raise ObserverBuildError(f"observer hot path contains cold API text: {found}")
    required_hot = (
        '#pragma code_seg(push, ".obshot")',
        "observer_score_positioning_x87_veh",
        "context->Dr0 = (DWORD)g_lua_conversion_address",
        "context->Dr7 = OBS_DR7_EXACT",
        "context->ContextFlags |= CONTEXT_DEBUG_REGISTERS",
        "context->Dr0 = 0",
        "context->Dr7 = 0",
        "context->EFlags |= OBS_EFLAGS_RF",
        "context->FloatSave.ControlWord",
        "OBS_INTEGER_HELPER_AFTER_LUA_RVA",
        "OBS_NAMED_INVOKER_AFTER_HELPER_RVA",
        "OBS_SCORE_POSITIONING_AFTER_NAMED_RVA",
        "hot_range_readable",
    )
    if any(value not in hot for value in required_hot):
        raise ObserverBuildError("observer VEH source contract differs")
    banned_source = (
        "WriteProcessMemory",
        "CreateRemoteThread",
        "OpenProcess",
        "VirtualProtect",
        "FlushInstructionCache",
        "DebugActiveProcess",
        "_controlfp",
        "_control87",
        "fesetround",
        "_mm_setcsr",
        "fldcw",
        "ldmxcsr",
    )
    found_source = [name for name in banned_source if name in text]
    if found_source:
        raise ObserverBuildError(
            f"observer source contains forbidden mutation surface: {found_source}"
        )
    return {
        "source_sha256": _sha256(source),
        "hot_source_sha256": _sha256(hot.encode("ascii")),
        "executable_mutation_api_text_absent": True,
        "floating_control_mutation_text_absent": True,
        "private_debug_register_transition_present": True,
        "fixed_single_record_present": "static obs_record g_record" in text,
        "exact_three_frame_filter_present": True,
    }


def _attest_hot_section(data: bytes, image: common.PEImage) -> dict[str, Any]:
    try:
        import capstone
        import capstone.x86_const as x86_const
        from capstone.x86 import X86_OP_IMM
    except ImportError as exc:
        raise ObserverBuildError("Capstone 5.0.7 is required for VEH proof") from exc
    if capstone.__version__ != "5.0.7":
        raise ObserverBuildError(f"unreviewed Capstone version: {capstone.__version__}")
    matches = [section for section in image.sections if section.name == ".obshot"]
    if len(matches) != 1:
        raise ObserverBuildError("compiled observer needs one .obshot section")
    section = matches[0]
    if not section.executable or section.virtual_size <= 0:
        raise ObserverBuildError("compiled .obshot section is not executable")
    raw = data[section.raw_offset : section.raw_offset + section.virtual_size]
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instructions = list(decoder.disasm(raw, image.image_base + section.virtual_address))
    if not instructions or sum(value.size for value in instructions) != len(raw):
        raise ObserverBuildError("compiled VEH does not decode contiguously")
    vector_groups = tuple(
        getattr(x86_const, name)
        for name in (
            "X86_GRP_FPU",
            "X86_GRP_MMX",
            "X86_GRP_SSE1",
            "X86_GRP_SSE2",
            "X86_GRP_AVX",
            "X86_GRP_AVX2",
        )
        if hasattr(x86_const, name)
    )
    start = image.image_base + section.virtual_address
    end = start + len(raw)
    calls: list[str] = []
    branches = 0
    returns = 0
    for instruction in instructions:
        if instruction.group(capstone.CS_GRP_CALL):
            calls.append(f"0x{instruction.address:08x}")
        if instruction.group(capstone.CS_GRP_RET):
            returns += 1
        if instruction.group(capstone.CS_GRP_JUMP):
            branches += 1
            if (
                len(instruction.operands) != 1
                or instruction.operands[0].type != X86_OP_IMM
                or not start <= instruction.operands[0].imm < end
            ):
                raise ObserverBuildError("compiled VEH has an external/indirect jump")
        if any(instruction.group(group) for group in vector_groups):
            raise ObserverBuildError("compiled VEH changes vector/MMX/x87 state")
        if instruction.mnemonic in {"int", "int1", "int3", "syscall", "sysenter", "hlt"}:
            raise ObserverBuildError(
                f"compiled VEH contains forbidden {instruction.mnemonic}"
            )
    if calls:
        raise ObserverBuildError(f"compiled VEH contains hot-path calls: {calls}")
    if returns == 0:
        raise ObserverBuildError("compiled VEH has no return")
    return {
        "section_rva": f"0x{section.virtual_address:08x}",
        "section_size": len(raw),
        "section_sha256": _sha256(raw),
        "instruction_count": len(instructions),
        "branch_count": branches,
        "return_count": returns,
        "direct_or_indirect_call_count": 0,
        "windows_api_call_count": 0,
        "x87_sse_mmx_avx_instruction_count": 0,
    }


def _normalize_output(value: str, temporary_root: Path) -> str:
    result = value.strip()
    for spelling, replacement in (
        (str(temporary_root), "<temporary-build>"),
        (temporary_root.as_posix(), "<temporary-build>"),
        (str(ROOT), "<source-root>"),
        (ROOT.as_posix(), "<source-root>"),
    ):
        result = result.replace(spelling, replacement)
    return result


def _compile_once(environment: dict[str, str], include_data: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="itb_observatory_score_x87_") as raw:
        temporary = Path(raw)
        (temporary / "observatory_score_positioning_x87_build.inc").write_bytes(
            include_data
        )
        dll = temporary / "itb_observatory_score_positioning_x87_observer.dll"
        obj = temporary / "observatory_score_positioning_x87_observer.obj"
        cl = shutil.which("cl.exe", path=environment.get("PATH"))
        linker = shutil.which("link.exe", path=environment.get("PATH"))
        if cl is None or linker is None:
            raise ObserverBuildError("MSVC compiler or linker disappeared")
        compile_command = [
            cl,
            "/nologo",
            "/c",
            "/TC",
            "/O2",
            "/Oi",
            "/Ob3",
            "/Oy",
            "/W4",
            "/WX",
            "/GS-",
            "/Gy",
            "/Zl",
            f"/I{temporary}",
            f"/Fo{obj}",
            str(SOURCE),
        ]
        compiled = subprocess.run(
            compile_command,
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if compiled.returncode != 0:
            detail = (compiled.stderr or compiled.stdout).strip()
            raise ObserverBuildError(
                "MSVC compilation failed" + (f": {detail}" if detail else "")
            )
        link_command = [
            linker,
            "/NOLOGO",
            "/DLL",
            "/NOENTRY",
            "/NODEFAULTLIB",
            f"/OUT:{dll}",
            "/INCREMENTAL:NO",
            "/Brepro",
            "/OPT:REF",
            "/OPT:ICF",
            str(obj),
            "kernel32.lib",
            "bcrypt.lib",
        ]
        linked = subprocess.run(
            link_command,
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if linked.returncode != 0:
            detail = (linked.stderr or linked.stdout).strip()
            raise ObserverBuildError(
                "MSVC link failed" + (f": {detail}" if detail else "")
            )
        compiler_stdout = _normalize_output(
            "\n".join(
                value for value in (compiled.stdout, linked.stdout) if value.strip()
            ),
            temporary,
        )
        module = common._stable_bytes(dll, "compiled observer")
    image = common._parse_pe(module)
    if image.machine != 0x014C or image.entry_point != 0:
        raise ObserverBuildError("compiled observer is not an inert x86 DLL")
    exports = common._pe_exports(module, image)
    if exports != [EXPORT_NAME]:
        raise ObserverBuildError(f"compiled observer exports differ: {exports}")
    imports = sorted(name.lower() for name in common._pe_imports(module, image))
    if not set(imports) <= {"bcrypt.dll", "kernel32.dll"} or "kernel32.dll" not in imports:
        raise ObserverBuildError(f"compiled observer imports differ: {imports}")
    mutation_names = (
        b"VirtualProtect",
        b"WriteProcessMemory",
        b"CreateRemoteThread",
        b"FlushInstructionCache",
        b"DebugActiveProcess",
        b"_controlfp",
        b"_control87",
        b"fesetround",
    )
    if any(name in module for name in mutation_names):
        raise ObserverBuildError("compiled observer imports a forbidden mutation API")
    return {
        "module": module,
        "module_sha256": _sha256(module),
        "exports": exports,
        "imports": imports,
        "compiler_stdout": compiler_stdout,
        "machine_attestation": {
            "loader_entry_absent": True,
            "pe_entry_point_rva": "0x00000000",
            "veh": _attest_hot_section(module, image),
            "executable_mutation_api_imports_absent": True,
            "floating_control_mutation_api_imports_absent": True,
        },
    }


def _write_create_only(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ObserverBuildError(f"immutable output already exists: {path.name}") from exc


def build_observer(args: argparse.Namespace) -> int:
    identities = _validate_inputs(args)
    source = common._stable_bytes(SOURCE, "observer source")
    source_attestation = _attest_source(source)
    source_sha = _sha256(source)
    plan = _hardware_breakpoint_plan(source_sha, identities)
    plan_data = _canonical_json(plan)
    plan_sha = _sha256(plan_data)
    include_data = _generated_include(identities, plan_sha)
    try:
        environment, compiler = common._msvc_environment()
    except (common.ObserverBuildError, OSError, subprocess.SubprocessError) as exc:
        raise ObserverBuildError(str(exc)) from exc
    first = _compile_once(environment, include_data)
    second = _compile_once(environment, include_data)
    for field in (
        "module",
        "module_sha256",
        "exports",
        "imports",
        "compiler_stdout",
        "machine_attestation",
    ):
        if first[field] != second[field]:
            raise ObserverBuildError(f"independent reproducibility builds differ: {field}")
    module = first["module"]
    module_sha = first["module_sha256"]
    output_root = Path(os.path.abspath(args.output_root.expanduser()))
    stem = f"itb_observatory_score_positioning_x87_observer_{module_sha}"
    module_path = output_root / f"{stem}.dll"
    receipt_path = output_root / f"{stem}.dll.receipt.json"
    plan_path = output_root / (
        f"windows_build_{EXPECTED_BUILD_ID}_score_positioning_x87_plan_{plan_sha}.json"
    )
    receipt = {
        "schema_version": 1,
        "kind": "observatory_score_positioning_x87_observer_build",
        "observer_version": OBSERVER_VERSION,
        "module_filename": module_path.name,
        "module_sha256": module_sha,
        "module_size": len(module),
        "architecture": EXPECTED_ARCHITECTURE,
        "export_name": EXPORT_NAME,
        "exports": first["exports"],
        "imports": first["imports"],
        "source_path": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": source_sha,
        "generated_include_sha256": _sha256(include_data),
        "source_attestation": source_attestation,
        "machine_attestation": first["machine_attestation"],
        "compiler": compiler,
        "compiler_stdout": first["compiler_stdout"],
        "reproducibility": {
            "independent_build_count": 2,
            "module_bytes_identical": True,
            "attestations_identical": True,
        },
        "compile_flags": [
            "/c",
            "/TC",
            "/O2",
            "/Oi",
            "/Ob3",
            "/Oy",
            "/W4",
            "/WX",
            "/GS-",
            "/Gy",
            "/Zl",
            "/DLL",
            "/NOENTRY",
            "/NODEFAULTLIB",
            "/INCREMENTAL:NO",
            "/Brepro",
            "/OPT:REF",
            "/OPT:ICF",
        ],
        "build_id": EXPECTED_BUILD_ID,
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": EXPECTED_EXECUTABLE_SIZE,
        "lua_dll_sha256": EXPECTED_LUA_SHA256,
        "lua_dll_size": EXPECTED_LUA_SIZE,
        "inventory_canonical_sha256": identities["inventory_canonical_sha256"],
        "inventory_file_sha256": identities["inventory_file_sha256"],
        "boundary_map_canonical_sha256": identities[
            "boundary_map_canonical_sha256"
        ],
        "boundary_map_file_sha256": identities["boundary_map_file_sha256"],
        "score_positioning_rva": f"0x{EXPECTED_SCORE_POSITIONING_RVA:08x}",
        "score_positioning_sha256": EXPECTED_SCORE_POSITIONING_SHA256,
        "named_integer_invoker_rva": f"0x{EXPECTED_NAMED_INVOKER_RVA:08x}",
        "named_integer_invoker_sha256": EXPECTED_NAMED_INVOKER_SHA256,
        "integer_helper_rva": f"0x{EXPECTED_INTEGER_HELPER_RVA:08x}",
        "integer_helper_sha256": EXPECTED_INTEGER_HELPER_SHA256,
        "integer_call_rva": f"0x{EXPECTED_INTEGER_CALL_RVA:08x}",
        "integer_call_bytes_hex": EXPECTED_INTEGER_CALL_BYTES.hex(),
        "lua_tointeger_rva": f"0x{EXPECTED_LUA_TOINTEGER_RVA:08x}",
        "lua_tointeger_sha256": EXPECTED_LUA_TOINTEGER_SHA256,
        "lua_fld_rva": f"0x{EXPECTED_LUA_FLD_RVA:08x}",
        "lua_fistp_rva": f"0x{EXPECTED_LUA_FISTP_RVA:08x}",
        "lua_conversion_bytes_hex": EXPECTED_LUA_CONVERSION_BYTES.hex(),
        "hardware_breakpoint_plan_filename": plan_path.name,
        "hardware_breakpoint_plan_sha256": plan_sha,
        "loaded_or_armed": False,
        "executable_bytes_modified": False,
        "lua_bytes_modified": False,
        "floating_control_state_modified": False,
    }
    _write_create_only(module_path, module)
    _write_create_only(plan_path, plan_data)
    _write_create_only(receipt_path, _canonical_json(receipt))
    if common._stable_bytes(module_path, "published observer") != module:
        raise ObserverBuildError("published observer failed byte verification")
    print(
        f"observer={module_path} sha256={module_sha} size={len(module)} "
        f"receipt={receipt_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return build_observer(args)
    except (ObserverBuildError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
