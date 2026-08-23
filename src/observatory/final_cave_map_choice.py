"""Reproduce the exact-build Final Cave map-choice boundary.

This follow-up closes the two deliberately open questions in the immutable
Final Cave startup artifact that can be answered offline: how ``RandomMap``
builds its candidate list, and whether ``random_int(1)`` advances the native
RNG.  It binds the answer to both the exact executable/content revision and
the current installation's Win32 directory-enumeration order.

The concrete cave map still cannot be forecast without the shared CRT RNG
state immediately before the two map-selection draws.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import struct
from collections.abc import Mapping, Sequence
from ctypes import wintypes
from pathlib import Path
from typing import Any

from src.observatory.content_inventory import InventoryError, build_manifest
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "final_cave_map_choice_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_BASE_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
EXPECTED_MAPS_REVISION_SHA256 = (
    "a16ed060190402ab83d5968c000917c9979944dd11beb154329ba002cfcb28d4"
)
EXPECTED_DIRECTORY_ENTRY_COUNT = 377
EXPECTED_MAP_REGISTRATION_COUNT = 376
EXPECTED_DIRECTORY_ORDER_SHA256 = (
    "b6536213370b25da2387eae604d6b4b4047d558da88f63292b0a1542ffcc5cfc"
)
EXPECTED_REGISTRATION_ORDER_SHA256 = (
    "6f89f1e48f963dbb896cc82fe61b4c9367ab61639bf1881d9745495227cc6112"
)
EXPECTED_MAPHELPER_INDEX = 226
SUPERSEDED_STARTUP_ARTIFACT_SHA256 = (
    "4cf2f05a267ed87a8cf5b14edbc874343a3969cef2dfb98e849f645ec177f942"
)
PE_BOUNDARY_ARTIFACT_SHA256 = (
    "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
)


class FinalCaveMapChoiceError(RuntimeError):
    """Raised when the reviewed Final Cave map-choice map cannot be reproduced."""


SOURCE_SPECS = (
    {
        "path": "maps/maphelper.lua",
        "size": 2_093,
        "sha256": (
            "f6455082a050f734ccc60ef3df6914619f5a250832a79f71e3ad6f1758431077"
        ),
        "symbols": ["AddMap", "RandomMap"],
        "reviewed_lines": [[2, 12], [49, 86]],
    },
    {
        "path": "scripts/global.lua",
        "size": 17_363,
        "sha256": (
            "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
        ),
        "symbols": ["random_element"],
        "reviewed_lines": [[560, 565]],
    },
    {
        "path": "scripts/missions/missions.lua",
        "size": 29_573,
        "sha256": (
            "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257"
        ),
        "symbols": ["Mission.MapVetoes", "Mission:GetMapTag"],
        "reviewed_lines": [[67, 79], [505, 511]],
    },
    {
        "path": "scripts/missions/final/mission_final.lua",
        "size": 3_318,
        "sha256": (
            "f92875ba570871b7b3184adb168105c8f29150398b8b14e87a863f67d6c61e29"
        ),
        "symbols": ["Mission_Final", "Mission_Final.NextPhase"],
        "reviewed_lines": [[3, 14]],
    },
    {
        "path": "scripts/missions/final/mission_final_two.lua",
        "size": 4_887,
        "sha256": (
            "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c"
        ),
        "symbols": ["Mission_Final_Cave", "Mission_Final_Cave.MapTags"],
        "reviewed_lines": [[3, 14]],
    },
)


CANDIDATE_SPECS = (
    ("cave1", 110),
    ("cave2", 111),
    ("cave3", 112),
    ("cave4", 113),
    ("cave5", 114),
    ("caveAE1", 115),
    ("caveAE2", 116),
    ("caveAE3", 117),
    ("caveAE4", 118),
)


REGION_SPECS = (
    {
        "id": "map_bootstrap",
        "start": 0x0016CFF0,
        "end": 0x0016D2E4,
        "sha256": (
            "30d803f49998606f470555e5772364a69e311082f426bc1f3daba9335e3c3a7f"
        ),
    },
    {
        "id": "directory_enumerator",
        "start": 0x0009F230,
        "end": 0x0009F50E,
        "sha256": (
            "d2c13c105a2347f4347004b7c330d933654ba4a59dcf47e51a0959aa1bb4e9a2"
        ),
    },
    {
        "id": "map_selector",
        "start": 0x00182AF0,
        "end": 0x00182F26,
        "sha256": (
            "c6190e9784cd302c39f0784bd263c9112c277522cd8e1fc54694b85a383a3761"
        ),
    },
    {
        "id": "used_map_lookup",
        "start": 0x000801C0,
        "end": 0x00080269,
        "sha256": (
            "a869c51bb5ca9259db62300844586b855b9a31343f5fcfd7c224533c7c699d50"
        ),
    },
    {
        "id": "used_map_insert",
        "start": 0x000DD880,
        "end": 0x000DD9DD,
        "sha256": (
            "eb2dd02758fdae437339c05459a921e43b38e7b315dfb8222db27158aacbff1f"
        ),
    },
    {
        "id": "used_map_clear",
        "start": 0x00198430,
        "end": 0x0019849B,
        "sha256": (
            "6ec5874cf0ec26dda7cce0b6130cd63bcdf1efcdbc610d3a17bf644255361dcf"
        ),
    },
    {
        "id": "new_game",
        "start": 0x0020C3F0,
        "end": 0x0020C740,
        "sha256": (
            "e23788866a80d562032dfb9cb3311657e3e405491318915d2c5f62dbc26f86f8"
        ),
    },
    {
        "id": "random_int_1",
        "start": 0x000E0C20,
        "end": 0x000E0C3A,
        "sha256": (
            "76e4d6f1289067724a2b6a8348ef91cb772a9bb12f6debf07b66efc11a6dd70e"
        ),
    },
    {
        "id": "rng_core",
        "start": 0x00387F16,
        "end": 0x00387F37,
        "sha256": (
            "3d7a67186e320b23a31d2ca6f9281211b373b60d44f35531cf4369da45cf0179"
        ),
    },
)


STRING_ANCHOR_SPECS = (
    {
        "id": "maphelper_path",
        "region_id": "map_bootstrap",
        "reference_rva": 0x0016D03C,
        "instruction_hex": "6840e98200",
        "string_rva": 0x0042E940,
        "text": "maps/maphelper.lua",
        "role": "helper loaded before map enumeration",
    },
    {
        "id": "maps_directory",
        "region_id": "map_bootstrap",
        "reference_rva": 0x0016D08A,
        "instruction_hex": "6868e98200",
        "string_rva": 0x0042E968,
        "text": "maps",
        "role": "directory passed to the native enumerator",
    },
    {
        "id": "maphelper_skip",
        "region_id": "map_bootstrap",
        "reference_rva": 0x0016D107,
        "instruction_hex": "685ce98200",
        "string_rva": 0x0042E95C,
        "text": "maphelper",
        "role": "entry-name substring excluded from the registration loop",
    },
    {
        "id": "maps_prefix",
        "region_id": "map_bootstrap",
        "reference_rva": 0x0016D126,
        "instruction_hex": "6828e68200",
        "string_rva": 0x0042E628,
        "text": "maps/",
        "role": "prefix used to load each enumerated map entry",
    },
    {
        "id": "add_map",
        "region_id": "map_bootstrap",
        "reference_rva": 0x0016D24B,
        "instruction_hex": "6820e68200",
        "string_rva": 0x0042E620,
        "text": "AddMap",
        "role": "Lua registration callback after removing four filename characters",
    },
    {
        "id": "random_map",
        "region_id": "map_selector",
        "reference_rva": 0x00182D25,
        "instruction_hex": "6828f28200",
        "string_rva": 0x0042F228,
        "text": "RandomMap",
        "role": "Lua candidate filter and choice callback",
    },
)


DATA_ANCHOR_SPECS = (
    {
        "id": "sector_argument",
        "region_id": "map_selector",
        "reference_rva": 0x00182CBD,
        "instruction_hex": "6878688d00",
        "target_va": 0x008D6878,
        "role": "persistent sector-type string passed as RandomMap argument two",
    },
    {
        "id": "used_map_lookup_registry",
        "region_id": "map_selector",
        "reference_rva": 0x00182E4A,
        "instruction_hex": "b960688d00",
        "target_va": 0x008D6860,
        "role": "used-map hash registry queried before accepting a candidate",
    },
    {
        "id": "used_map_insert_registry",
        "region_id": "map_selector",
        "reference_rva": 0x00182E7D,
        "instruction_hex": "b960688d00",
        "target_va": 0x008D6860,
        "role": "same registry updated after accepting a candidate",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "bootstrap_loads_maphelper",
        "region_id": "map_bootstrap",
        "start_rva": 0x0016D038,
        "instruction_hex": (
            "8bcc8bd06840e98200e8dad4edff83c404b9a85789006a00e88bfeedff"
        ),
        "meaning": "Load maps/maphelper.lua before enumerating map entries.",
    },
    {
        "id": "bootstrap_enumerates_maps",
        "region_id": "map_bootstrap",
        "start_rva": 0x0016D086,
        "instruction_hex": (
            "8bcc8bd06868e98200e88cd4edff83c4048d4d9432d2e88f21f3ff"
        ),
        "meaning": "Pass maps to the native directory enumerator.",
    },
    {
        "id": "bootstrap_skips_maphelper",
        "region_id": "map_bootstrap",
        "start_rva": 0x0016D100,
        "instruction_hex": (
            "6a096a008d0c3e685ce98200e8df28eeff83f8ff0f854c010000"
        ),
        "meaning": "Skip an enumerated entry whose name contains maphelper.",
    },
    {
        "id": "bootstrap_strips_extension_and_adds_map",
        "region_id": "map_bootstrap",
        "start_rva": 0x0016D20B,
        "instruction_hex": (
            "83ec1803d78965a08bcc8b421083c0fc506a00518bcae8ca5ef2ff83ec18"
            "c645fc078bccc741140f000000c74110000000008379141072048b01eb028b"
            "c16a066820e68200c60000e878ade9ffb9a8578900c645fc03e8fa9b0000"
        ),
        "meaning": (
            "Remove the final four filename characters and invoke AddMap in "
            "enumeration order."
        ),
    },
    {
        "id": "find_first_file",
        "region_id": "directory_enumerator",
        "start_rva": 0x0009F379,
        "instruction_hex": (
            "6a0468241182008d4d08e8f8b1faff837d1c108d8d98feffff8d45080f4345"
            "085150ff1524617d00898594feffff83f8ff0f8417010000"
        ),
        "meaning": "Begin unsorted directory enumeration with FindFirstFileA.",
    },
    {
        "id": "append_find_next_and_close",
        "region_id": "directory_enumerator",
        "start_rva": 0x0009F468,
        "instruction_hex": (
            "8d45d8508d8d84feffffe8a902fbffc645fc018b45ec83f810720f6a014050"
            "ff75d8e87183f6ff83c40c8b9d94feffff8d8598feffff5053ff1520617d00"
            "85c00f8502ffffff53ff151c617d00"
        ),
        "meaning": (
            "Append each returned name, loop with FindNextFileA, and close the "
            "search handle without a sorting call."
        ),
    },
    {
        "id": "sector_and_random_map_arguments",
        "region_id": "map_selector",
        "start_rva": 0x00182CBD,
        "instruction_hex": (
            "6878688d00c60000e80654e8ff83ec18c645fc088bcc8965b4c741140f0000"
            "00c74110000000008379141072048b01eb028bc16affc600008d45bc6a0050"
            "e8d053e8ff83ec18c645fc098bccc741140f000000c7411000000000837914"
            "1072048b01eb028bc16a096828f28200c60000e89e52e8ff8d45d4c645fc05"
            "50b9a8578900e85ca9f8ff"
        ),
        "meaning": (
            "Construct the persistent sector string and mission tag arguments, "
            "then dispatch RandomMap."
        ),
    },
    {
        "id": "veto_used_map_retry_and_accept",
        "region_id": "map_selector",
        "start_rva": 0x00182DA1,
        "instruction_hex": (
            "8b4da0b8abaaaa2a8b759c32db2bce895db8f7e9c1fa028bc2c1e81f03c289"
            "45b0745c837e141072048b16eb028bd6837f141072078b078945b4eb03897db4"
            "8b5e108bc3395f108b4db40f42471050e8bb93eeff83c40485c075188b4710"
            "3bc372118b4db8b8010000000fb6c90f46c8894db883c618836db00175a78b"
            "5db88b571483fa1072048b0feb028bcf8b471003c183fa1072048b0feb028bcf"
            "51575051e8d9b4eeff83c408b960688d00508d45a850e867d3efff837da800"
            "750484db74138b45ac8b5d94408945ac83f80a0f8cbcfdffff837f1000740f"
            "57b960688d00e8f9a9f5ffc6401801"
        ),
        "meaning": (
            "Reject a mission-vetoed or already-used map, retry at most ten "
            "times, then record the accepted nonempty map."
        ),
    },
    {
        "id": "new_game_clears_used_maps",
        "region_id": "new_game",
        "start_rva": 0x0020C481,
        "instruction_hex": (
            "6a07685ca88200c60000e840bbdfff6a00b938608900e8a4670000e88fbff8ff"
        ),
        "meaning": "The reviewed startNewGame path clears the used-map registry.",
    },
    {
        "id": "random_int_one_argument_body",
        "region_id": "random_int_1",
        "start_rva": 0x000E0C20,
        "instruction_hex": (
            "558bec837d0800750433c05dc3e8e4722a0099f77d088bc25dc3"
        ),
        "meaning": (
            "Return zero without a draw only for max zero; every nonzero max "
            "calls the shared RNG and returns its signed remainder."
        ),
    },
    {
        "id": "shared_msvc_rng_step",
        "region_id": "rng_core",
        "start_rva": 0x00387F16,
        "instruction_hex": (
            "e8176e0000694818fd43030081c1c39e2600894818c1e91081e1ff7f00008b"
            "c1c3"
        ),
        "meaning": (
            "Advance the 32-bit state with multiplier 0x343fd and increment "
            "0x269ec3, then return bits 16 through 30."
        ),
    },
)


CALL_EDGE_SPECS = (
    {
        "id": "bootstrap_to_directory_enumerator",
        "kind": "direct_rel32",
        "source_region": "map_bootstrap",
        "from_rva": 0x0016D09C,
        "instruction_hex": "e88f21f3ff",
        "target_region": "directory_enumerator",
        "target_rva": 0x0009F230,
    },
    {
        "id": "selector_to_used_map_lookup",
        "kind": "direct_rel32",
        "source_region": "map_selector",
        "from_rva": 0x00182E54,
        "instruction_hex": "e867d3efff",
        "target_region": "used_map_lookup",
        "target_rva": 0x000801C0,
    },
    {
        "id": "selector_to_used_map_insert",
        "kind": "direct_rel32",
        "source_region": "map_selector",
        "from_rva": 0x00182E82,
        "instruction_hex": "e8f9a9f5ff",
        "target_region": "used_map_insert",
        "target_rva": 0x000DD880,
    },
    {
        "id": "new_game_to_used_map_clear",
        "kind": "direct_rel32",
        "source_region": "new_game",
        "from_rva": 0x0020C49C,
        "instruction_hex": "e88fbff8ff",
        "target_region": "used_map_clear",
        "target_rva": 0x00198430,
    },
    {
        "id": "random_int_to_rng_core",
        "kind": "direct_rel32",
        "source_region": "random_int_1",
        "from_rva": 0x000E0C2D,
        "instruction_hex": "e8e4722a00",
        "target_region": "rng_core",
        "target_rva": 0x00387F16,
    },
    {
        "id": "enumerator_to_find_first_file_a",
        "kind": "iat_indirect",
        "source_region": "directory_enumerator",
        "from_rva": 0x0009F39B,
        "instruction_hex": "ff1524617d00",
        "library": "KERNEL32.dll",
        "name": "FindFirstFileA",
        "iat_rva": 0x003D6124,
    },
    {
        "id": "enumerator_to_find_next_file_a",
        "kind": "iat_indirect",
        "source_region": "directory_enumerator",
        "from_rva": 0x0009F4A0,
        "instruction_hex": "ff1520617d00",
        "library": "KERNEL32.dll",
        "name": "FindNextFileA",
        "iat_rva": 0x003D6120,
    },
    {
        "id": "enumerator_to_find_close",
        "kind": "iat_indirect",
        "source_region": "directory_enumerator",
        "from_rva": 0x0009F4AF,
        "instruction_hex": "ff151c617d00",
        "library": "KERNEL32.dll",
        "name": "FindClose",
        "iat_rva": 0x003D611C,
    },
)


_TAGS_RE = re.compile(r'\["tags"\]\s*=\s*\{([^}]*)\}')
_QUOTED_RE = re.compile(r'"([^"]+)"')
_MAP_ROOT_RE = re.compile(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{")


class _FileTime(ctypes.Structure):
    _fields_ = (("low", wintypes.DWORD), ("high", wintypes.DWORD))


class _Win32FindDataA(ctypes.Structure):
    _fields_ = (
        ("attributes", wintypes.DWORD),
        ("creation_time", _FileTime),
        ("last_access_time", _FileTime),
        ("last_write_time", _FileTime),
        ("size_high", wintypes.DWORD),
        ("size_low", wintypes.DWORD),
        ("reserved_0", wintypes.DWORD),
        ("reserved_1", wintypes.DWORD),
        ("file_name", ctypes.c_char * 260),
        ("alternate_file_name", ctypes.c_char * 14),
    )


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _order_sha256(names: Sequence[str]) -> str:
    return hashlib.sha256(("\n".join(names) + "\n").encode("utf-8")).hexdigest()


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise FinalCaveMapChoiceError(
            f"RVA 0x{rva:08x} is not contiguous file-backed data"
        )
    section = next(
        (
            candidate
            for candidate in image.sections
            if candidate.virtual_address <= rva
            and rva + size
            <= candidate.virtual_address + candidate.raw_size
        ),
        None,
    )
    if section is None or not section.executable:
        raise FinalCaveMapChoiceError(
            f"RVA 0x{rva:08x} is not executable file-backed data"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCaveMapChoiceError(
            f"RVA 0x{rva:08x} is not an E8 rel32 call"
        )
    delta = struct.unpack_from("<i", encoded, 1)[0]
    return (rva + 5 + delta) & 0xFFFFFFFF


def _native_directory_entries(directory: Path) -> list[str]:
    """Return the same unsorted ANSI Win32 enumeration consumed by the game."""
    if os.name != "nt":
        raise FinalCaveMapChoiceError(
            "exact directory-order verification requires Windows"
        )
    try:
        pattern = (str(directory.resolve(strict=True)) + r"\*").encode("mbcs")
    except (OSError, UnicodeEncodeError) as exc:
        raise FinalCaveMapChoiceError(
            "maps directory cannot be represented for FindFirstFileA"
        ) from exc

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    find_first = kernel32.FindFirstFileA
    find_first.argtypes = (ctypes.c_char_p, ctypes.POINTER(_Win32FindDataA))
    find_first.restype = ctypes.c_void_p
    find_next = kernel32.FindNextFileA
    find_next.argtypes = (ctypes.c_void_p, ctypes.POINTER(_Win32FindDataA))
    find_next.restype = wintypes.BOOL
    find_close = kernel32.FindClose
    find_close.argtypes = (ctypes.c_void_p,)
    find_close.restype = wintypes.BOOL

    value = _Win32FindDataA()
    handle = find_first(pattern, ctypes.byref(value))
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise FinalCaveMapChoiceError(
            f"FindFirstFileA failed with Windows error {ctypes.get_last_error()}"
        )
    names: list[str] = []
    pending_error: FinalCaveMapChoiceError | None = None
    try:
        while True:
            raw_name = bytes(value.file_name).split(b"\0", 1)[0]
            try:
                name = raw_name.decode("mbcs")
            except UnicodeDecodeError as exc:
                raise FinalCaveMapChoiceError(
                    "FindFirstFileA returned an undecodable entry name"
                ) from exc
            if name not in {".", ".."}:
                names.append(name)
            if find_next(handle, ctypes.byref(value)):
                continue
            error = ctypes.get_last_error()
            if error != 18:  # ERROR_NO_MORE_FILES
                pending_error = FinalCaveMapChoiceError(
                    f"FindNextFileA failed with Windows error {error}"
                )
            break
    finally:
        if not find_close(handle) and pending_error is None:
            pending_error = FinalCaveMapChoiceError(
                f"FindClose failed with Windows error {ctypes.get_last_error()}"
            )
    if pending_error is not None:
        raise pending_error
    return names


def _map_metadata(path: Path) -> tuple[str, tuple[str, ...]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FinalCaveMapChoiceError(f"cannot read map tags: {path.name}") from exc
    match = _TAGS_RE.search(text)
    root_match = _MAP_ROOT_RE.search(text)
    if root_match is None:
        raise FinalCaveMapChoiceError(f"map root is missing: {path.name}")
    tags = () if match is None else tuple(_QUOTED_RE.findall(match.group(1)))
    return root_match.group(1), tags


def _expected_sources() -> list[dict[str, Any]]:
    return [
        {
            "path": spec["path"],
            "size": spec["size"],
            "sha256": spec["sha256"],
            "symbols": spec["symbols"],
            "reviewed_lines": spec["reviewed_lines"],
            "evidence_class": "fact",
        }
        for spec in SOURCE_SPECS
    ]


def _source_set_sha256() -> str:
    return _canonical_sha256({"sources": _expected_sources()})


def _expected_regions() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "start_rva": f"0x{spec['start']:08x}",
            "end_rva_exclusive": f"0x{spec['end']:08x}",
            "size": spec["end"] - spec["start"],
            "sha256": spec["sha256"],
            "section": ".text",
            "boundary_basis": (
                "Ghidra 12.1.3 function body corroborated by complete "
                "Capstone 5.0.7 decoding from the reviewed entry."
            ),
        }
        for spec in REGION_SPECS
    ]


def _expected_string_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "evidence_class": "fact",
            "reference_rva": f"0x{spec['reference_rva']:08x}",
            "instruction_hex": spec["instruction_hex"],
            "string_rva": f"0x{spec['string_rva']:08x}",
            "text": spec["text"],
            "role": spec["role"],
        }
        for spec in STRING_ANCHOR_SPECS
    ]


def _expected_data_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "evidence_class": "fact",
            "reference_rva": f"0x{spec['reference_rva']:08x}",
            "instruction_hex": spec["instruction_hex"],
            "target_va": f"0x{spec['target_va']:08x}",
            "role": spec["role"],
        }
        for spec in DATA_ANCHOR_SPECS
    ]


def _expected_windows() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "start_rva": f"0x{spec['start_rva']:08x}",
            "size": len(bytes.fromhex(spec["instruction_hex"])),
            "sha256": hashlib.sha256(
                bytes.fromhex(spec["instruction_hex"])
            ).hexdigest(),
            "instruction_hex": spec["instruction_hex"],
            "evidence_class": "fact",
            "meaning": spec["meaning"],
        }
        for spec in CONTROL_WINDOW_SPECS
    ]


def _expected_edges() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for spec in CALL_EDGE_SPECS:
        item = {
            "id": spec["id"],
            "kind": spec["kind"],
            "source_region": spec["source_region"],
            "from_rva": f"0x{spec['from_rva']:08x}",
            "instruction_hex": spec["instruction_hex"],
            "evidence_class": "fact",
        }
        if spec["kind"] == "direct_rel32":
            item["target"] = {
                "type": "region",
                "region": spec["target_region"],
                "rva": f"0x{spec['target_rva']:08x}",
            }
        else:
            item["target"] = {
                "type": "import",
                "library": spec["library"],
                "name": spec["name"],
                "iat_rva": f"0x{spec['iat_rva']:08x}",
            }
        result.append(item)
    return result


def _map_registration_contract() -> dict[str, Any]:
    return {
        "native_directory_api": [
            "FindFirstFileA",
            "FindNextFileA",
            "FindClose",
        ],
        "sorting_step_present": False,
        "directory_entry_count": EXPECTED_DIRECTORY_ENTRY_COUNT,
        "directory_order_sha256": EXPECTED_DIRECTORY_ORDER_SHA256,
        "maphelper_entry_index_zero_based": EXPECTED_MAPHELPER_INDEX,
        "maphelper_loaded_before_enumeration": True,
        "maphelper_entry_skipped_during_registration": True,
        "other_installed_entry_types": {".map": 376},
        "registration_count": EXPECTED_MAP_REGISTRATION_COUNT,
        "registration_order_sha256": EXPECTED_REGISTRATION_ORDER_SHA256,
        "registration_transform": (
            "For each non-maphelper entry in Win32 enumeration order, load "
            "maps/<entry>, remove the final four filename characters, and "
            "invoke AddMap. AddMap preserves first insertion order."
        ),
        "filesystem_order_warning": (
            "Directory order is installation state, not file-content state. "
            "Reinstallation or copying can change raw RNG-to-map mapping "
            "without changing executable or map hashes."
        ),
    }


def _candidate_records() -> list[dict[str, Any]]:
    return [
        {
            "candidate_index_zero_based": index,
            "rng_remainder": index,
            "map_name": name,
            "path": f"maps/{name}.map",
            "map_list_index_zero_based": map_list_index,
            "tags": ["final_cave", "volcano"],
            "advanced_edition_name": "AE" in name,
            "evidence_class": "fact",
        }
        for index, (name, map_list_index) in enumerate(CANDIDATE_SPECS)
    ]


def _random_map_contract() -> dict[str, Any]:
    return {
        "input_tag": "final_cave",
        "input_sector": "volcano",
        "sector_value_evidence_class": "inference",
        "sector_value_basis": (
            "The same persistent native string is used as the sector-type "
            "argument for map selection and getRainChance. The surface Final "
            "mission was selected from the exact final_island pool, whose 15 "
            "maps all require the volcano sector and have no any_sector tag; "
            "CreateNextPhase does not replace that string before cave selection."
        ),
        "candidate_filter": [
            "iterate MAP_LIST with ipairs, preserving registration order",
            "ignore map names matt and justin",
            "require one tag equal to final_cave",
            "require one tag equal to volcano or any_sector",
        ],
        "empty_result": "return an empty string without an RNG draw",
        "nonempty_result": "return candidates[random_int(#candidates) + 1]",
        "advanced_edition_filter_present": False,
        "candidate_count": len(CANDIDATE_SPECS),
        "candidate_order": _candidate_records(),
        "mission_map_vetoes": [],
        "mission_map_veto_basis": (
            "Mission_Final_Cave does not override the inherited empty "
            "Mission.MapVetoes table."
        ),
        "native_retry_policy": (
            "Reject a selected name found in mission vetoes or the used-map "
            "registry, retrying at most ten attempts."
        ),
        "ordinary_first_transition_attempts": 1,
        "ordinary_first_transition_basis": (
            "startNewGame clears the used-map registry; exact shipped mission "
            "selection sources expose final_cave only on Mission_Final_Cave, "
            "and no cave map is explicitly named elsewhere before the first "
            "surface-to-cave transition. Therefore no candidate can already "
            "be used on that ordinary path."
        ),
    }


def _rng_contract() -> dict[str, Any]:
    return {
        "core": {
            "state_width_bits": 32,
            "transition": "state = state * 0x343fd + 0x269ec3 (mod 2^32)",
            "output": "(state >> 16) & 0x7fff",
        },
        "random_int_one_argument": {
            "max_zero": "return 0 without advancing the RNG",
            "max_nonzero": "advance once and return rng_output % max",
        },
        "ordinary_first_transition_draws_before_environment": [
            {
                "ordinal": 1,
                "source": "Mission:GetMapTag -> random_element(MapTags)",
                "max": 1,
                "advances_rng": True,
                "result": 0,
                "semantic_result": "final_cave",
            },
            {
                "ordinal": 2,
                "source": "RandomMap(final_cave, volcano)",
                "max": 9,
                "advances_rng": True,
                "result": "second_rng_output % 9",
                "semantic_result": "candidate_order[result]",
            },
        ],
        "draw_count": 2,
        "pre_draw_state_available_to_solver": False,
        "concrete_map_forecast_proven": False,
    }


def _method() -> dict[str, Any]:
    return {
        "boundary_review": (
            "Ghidra 12.1.3 function/reference/decompiler review identified "
            "map bootstrap, unsorted Win32 enumeration, map selection retry, "
            "used-map registry, and one-argument random_int boundaries."
        ),
        "byte_verification": (
            "Capstone 5.0.7 redecodes every pinned function and control window; "
            "the verifier checks direct targets and named PE IAT imports."
        ),
        "source_review": (
            "Exact source hashes bind AddMap, RandomMap, random_element, "
            "mission tags, inherited vetoes, and the Final phase identity."
        ),
        "installation_order_review": (
            "The verifier calls FindFirstFileA/FindNextFileA directly and "
            "rejects drift in the full entry and registration order hashes."
        ),
        "limitations": [
            "Native addresses apply only to the pinned Windows executable.",
            "The directory-order binding applies to this exact installation state.",
            "The sector value is a static cross-call inference, not a runtime capture.",
            "A modded or debug state that pre-marks cave maps can trigger retries.",
            "The shared CRT state before draw one is not exposed by ordinary "
            "bridge state.",
            "No macOS equivalence is claimed.",
        ],
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "random_map_is_shipped_lua",
            "evidence_class": "fact",
            "claim": (
                "RandomMap is exact shipped Lua, not an opaque native selector: "
                "it preserves MAP_LIST order, applies tag plus sector filtering, "
                "and makes one random_int candidate draw for a nonempty result."
            ),
            "supports": ["maps/maphelper.lua", "random_map"],
        },
        {
            "id": "installation_order",
            "evidence_class": "inference",
            "claim": (
                "Native bootstrap loads maphelper first, obtains map entries "
                "through unsorted FindFirstFileA/FindNextFileA enumeration, and "
                "registers all 376 installed .map files in returned order."
            ),
            "supports": [
                "bootstrap_loads_maphelper",
                "bootstrap_enumerates_maps",
                "append_find_next_and_close",
                "bootstrap_strips_extension_and_adds_map",
            ],
        },
        {
            "id": "all_nine_cave_maps_are_eligible",
            "evidence_class": "fact",
            "claim": (
                "The exact current installation yields cave1 through cave5, "
                "then caveAE1 through caveAE4. All nine match final_cave plus "
                "volcano; RandomMap contains no Advanced Edition filter."
            ),
            "supports": ["map_registration", "random_map_contract"],
        },
        {
            "id": "ordinary_first_transition_has_one_attempt",
            "evidence_class": "inference",
            "claim": (
                "The first ordinary surface-to-cave transition has one "
                "RandomMap attempt: cave vetoes are empty and no cave candidate "
                "is source-reachable into the new-game used-map registry earlier."
            ),
            "supports": [
                "veto_used_map_retry_and_accept",
                "new_game_clears_used_maps",
                "random_map_contract",
            ],
        },
        {
            "id": "random_int_one_advances",
            "evidence_class": "fact",
            "claim": (
                "On the exact executable, random_int(1) calls the shared RNG "
                "once and returns zero; only random_int(0) skips advancement."
            ),
            "supports": [
                "random_int_one_argument_body",
                "random_int_to_rng_core",
            ],
        },
        {
            "id": "two_draw_map_boundary",
            "evidence_class": "inference",
            "claim": (
                "Before Env_Final startup on the ordinary first transition, "
                "draw one is the one-entry final_cave tag choice and draw two "
                "selects candidate index rng_output modulo nine."
            ),
            "supports": ["rng_contract", "ordinary_first_transition_has_one_attempt"],
        },
        {
            "id": "solver_boundary",
            "evidence_class": "inference",
            "claim": (
                "This closes map filtering, order, call count, and modulo "
                "semantics but does not expose the pre-draw CRT state. The Rust "
                "solver should still consume a fresh settled bridge state after "
                "the phase change instead of forecasting a concrete map."
            ),
            "supports": ["two_draw_map_boundary", "rng_contract"],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "pre_draw_crt_state",
            "question": "What is the shared CRT state immediately before GetMapTag?",
            "static_status": (
                "Both draw semantics and all nine remainder mappings are exact; "
                "ordinary bridge/save state does not expose this native state."
            ),
            "next_evidence": (
                "Capture the native RNG state at the already-proven phase boundary "
                "only if concrete cross-stage forecasting becomes useful."
            ),
        },
        {
            "id": "nonstandard_used_map_state",
            "question": "Can a modded/debug restore pre-mark a cave candidate as used?",
            "static_status": (
                "The native retry is exact and ordinary first-transition absence "
                "is proven from shipped reachability; arbitrary modified state is not."
            ),
            "next_evidence": (
                "Treat such a state as out of scope or capture the registry."
            ),
        },
        {
            "id": "downstream_startup_rng",
            "question": "What concrete lava path, placement, and spawn draws follow?",
            "static_status": (
                "The first two calls are now exact, but their unknown incoming "
                "state and later Board/native branches still prevent replay."
            ),
            "next_evidence": (
                "Retain a settled cave bridge snapshot or capture RNG state."
            ),
        },
    ]


def _summary() -> dict[str, Any]:
    return {
        "reviewed_source_count": len(SOURCE_SPECS),
        "region_count": len(REGION_SPECS),
        "string_anchor_count": len(STRING_ANCHOR_SPECS),
        "data_anchor_count": len(DATA_ANCHOR_SPECS),
        "control_window_count": len(CONTROL_WINDOW_SPECS),
        "call_edge_count": len(CALL_EDGE_SPECS),
        "candidate_count": len(CANDIDATE_SPECS),
        "finding_count": len(_findings()),
        "unresolved_count": len(_unresolved()),
        "random_map_algorithm_proven": True,
        "candidate_order_installation_bound": True,
        "advanced_edition_filter_absent": True,
        "random_int_one_advancement_proven": True,
        "ordinary_first_transition_draw_count": 2,
        "concrete_map_forecast_proven": False,
        "simulator_change_required": False,
    }


def _expected_shape() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "image_base": f"0x{EXPECTED_IMAGE_BASE:08x}",
            "base_inventory_scripts_revision_sha256": (
                EXPECTED_BASE_SCRIPTS_REVISION_SHA256
            ),
            "reviewed_source_set_sha256": _source_set_sha256(),
            "maps_revision_sha256": EXPECTED_MAPS_REVISION_SHA256,
        },
        "supporting_artifacts": [
            {
                "artifact": (
                    "data/observatory/native/"
                    "windows_build_13725832_31fe35265598_pe_boundaries.json"
                ),
                "artifact_sha256": PE_BOUNDARY_ARTIFACT_SHA256,
                "supports": [
                    "lua_rng_registration",
                    "lua_rng_leaf_contracts",
                    "shared_rng_core",
                ],
            }
        ],
        "supersedes": {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_final_cave_startup.json"
            ),
            "artifact_sha256": SUPERSEDED_STARTUP_ARTIFACT_SHA256,
            "resolved_gap_ids": ["native_random_map"],
            "narrowed_gap_ids": ["native_rng_state"],
            "correction": (
                "The immutable startup artifact correctly left random_int(1) "
                "open. Exact PE evidence now proves it advances one RNG step."
            ),
        },
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
            "lua_files": _expected_sources(),
        },
        "method": _method(),
        "regions": _expected_regions(),
        "string_anchors": _expected_string_anchors(),
        "data_anchors": _expected_data_anchors(),
        "control_windows": _expected_windows(),
        "call_edges": _expected_edges(),
        "map_registration": _map_registration_contract(),
        "random_map_contract": _random_map_contract(),
        "rng_contract": _rng_contract(),
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": _summary(),
    }


def _verify_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise FinalCaveMapChoiceError("content root is not a directory")
    for spec in SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise FinalCaveMapChoiceError(
                f"missing reviewed source {spec['path']}"
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FinalCaveMapChoiceError(
                f"reviewed source escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise FinalCaveMapChoiceError(
                f"reviewed source is not a regular non-symlink file: {spec['path']}"
            )
        data = resolved.read_bytes()
        if (
            len(data) != spec["size"]
            or hashlib.sha256(data).hexdigest() != spec["sha256"]
        ):
            raise FinalCaveMapChoiceError(
                f"reviewed source identity differs: {spec['path']}"
            )


def _verify_map_order(content_root: Path) -> None:
    root = content_root.resolve()
    try:
        manifest = build_manifest(root, "maps")
    except InventoryError as exc:
        raise FinalCaveMapChoiceError(str(exc)) from exc
    if manifest["revision_sha256"] != EXPECTED_MAPS_REVISION_SHA256:
        raise FinalCaveMapChoiceError("maps revision differs")

    entries = _native_directory_entries(root / "maps")
    if (
        len(entries) != EXPECTED_DIRECTORY_ENTRY_COUNT
        or _order_sha256(entries) != EXPECTED_DIRECTORY_ORDER_SHA256
    ):
        raise FinalCaveMapChoiceError("native maps directory order differs")
    if entries[EXPECTED_MAPHELPER_INDEX] != "maphelper.lua":
        raise FinalCaveMapChoiceError("maphelper directory position differs")

    manifest_names = {
        Path(entry["path"]).name for entry in manifest["files"]
    }
    if len(manifest_names) != len(manifest["files"]) or set(entries) != manifest_names:
        raise FinalCaveMapChoiceError("native directory entries differ from manifest")
    if any((root / "maps" / name).is_symlink() for name in entries):
        raise FinalCaveMapChoiceError("maps directory contains a symlink")
    if any(not (root / "maps" / name).is_file() for name in entries):
        raise FinalCaveMapChoiceError("maps directory contains a non-file entry")

    registered_files = [name for name in entries if "maphelper" not in name]
    if (
        len(registered_files) != EXPECTED_MAP_REGISTRATION_COUNT
        or any(Path(name).suffix != ".map" for name in registered_files)
    ):
        raise FinalCaveMapChoiceError("native map registration file set differs")
    registered_names = [name[:-4] for name in registered_files]
    if _order_sha256(registered_names) != EXPECTED_REGISTRATION_ORDER_SHA256:
        raise FinalCaveMapChoiceError("native map registration order differs")

    tags_by_name: dict[str, tuple[str, ...]] = {}
    for filename in registered_files:
        name = filename[:-4]
        defined_name, tags = _map_metadata(root / "maps" / filename)
        if defined_name != name:
            raise FinalCaveMapChoiceError(
                f"AddMap global name differs for {filename}"
            )
        tags_by_name[name] = tags
    expected_positions = {name: position for name, position in CANDIDATE_SPECS}
    observed_positions = {
        name: index
        for index, name in enumerate(registered_names)
        if name in expected_positions
    }
    if observed_positions != expected_positions:
        raise FinalCaveMapChoiceError("cave MAP_LIST positions differ")

    candidates = [
        name
        for name in registered_names
        if name not in {"matt", "justin"}
        and "final_cave" in tags_by_name[name]
        and (
            "volcano" in tags_by_name[name]
            or "any_sector" in tags_by_name[name]
        )
    ]
    if candidates != [name for name, _position in CANDIDATE_SPECS]:
        raise FinalCaveMapChoiceError("RandomMap cave candidate order differs")
    if any(tags_by_name[name] != ("final_cave", "volcano") for name in candidates):
        raise FinalCaveMapChoiceError("cave candidate tags differ")

    final_surface = [
        name for name in registered_names if "final_island" in tags_by_name[name]
    ]
    if len(final_surface) != 15 or any(
        set(tags_by_name[name]) != {"volcano", "final_island"}
        for name in final_surface
    ):
        raise FinalCaveMapChoiceError("Final surface sector-tag basis differs")


def _verify_native_boundaries(executable: Path) -> None:
    data, image, digest = _load_executable(executable)
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCaveMapChoiceError("executable identity differs")

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        try:
            body = _region_bytes(
                image,
                data,
                spec["start"],
                spec["end"] - spec["start"],
                ".text",
                spec["id"],
            )
        except Exception as exc:
            raise FinalCaveMapChoiceError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalCaveMapChoiceError(f"region {spec['id']} bytes differ")
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCaveMapChoiceError(str(exc)) from exc

    for spec in STRING_ANCHOR_SPECS:
        text = spec["text"].encode("ascii") + b"\0"
        offset = image.rva_span_to_file_offset(spec["string_rva"], len(text))
        if offset is None or data[offset : offset + len(text)] != text:
            raise FinalCaveMapChoiceError(f"string anchor {spec['id']} differs")
        encoded = bytes.fromhex(spec["instruction_hex"])
        if _bytes_at(image, data, spec["reference_rva"], len(encoded)) != encoded:
            raise FinalCaveMapChoiceError(
                f"string reference {spec['id']} differs"
            )
        instruction = decoded[spec["region_id"]].get(spec["reference_rva"])
        if instruction is None or instruction[1] != encoded:
            raise FinalCaveMapChoiceError(
                f"string reference {spec['id']} is not an instruction"
            )
        expected_va = image.image_base + spec["string_rva"]
        if struct.pack("<I", expected_va) not in encoded:
            raise FinalCaveMapChoiceError(
                f"string reference {spec['id']} target differs"
            )

    for spec in DATA_ANCHOR_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        if _bytes_at(image, data, spec["reference_rva"], len(encoded)) != encoded:
            raise FinalCaveMapChoiceError(f"data anchor {spec['id']} differs")
        instruction = decoded[spec["region_id"]].get(spec["reference_rva"])
        if instruction is None or instruction[1] != encoded:
            raise FinalCaveMapChoiceError(
                f"data anchor {spec['id']} is not an instruction"
            )
        if struct.pack("<I", spec["target_va"]) not in encoded:
            raise FinalCaveMapChoiceError(
                f"data anchor {spec['id']} target differs"
            )

    regions = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise FinalCaveMapChoiceError(f"control window {spec['id']} differs")
        region = regions[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalCaveMapChoiceError(
                f"control window {spec['id']} escapes its region"
            )
        instructions = decoded[spec["region_id"]]
        cursor = start
        while cursor < start + len(encoded):
            instruction = instructions.get(cursor)
            if instruction is None:
                raise FinalCaveMapChoiceError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalCaveMapChoiceError(
                f"control window {spec['id']} ends inside an instruction"
            )

    imports = image.imports()
    for spec in CALL_EDGE_SPECS:
        expected = bytes.fromhex(spec["instruction_hex"])
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        if instruction is None or instruction[1] != expected:
            raise FinalCaveMapChoiceError(f"call edge {spec['id']} bytes differ")
        if spec["kind"] == "direct_rel32":
            if _direct_target(spec["from_rva"], expected) != spec["target_rva"]:
                raise FinalCaveMapChoiceError(
                    f"call edge {spec['id']} target differs"
                )
            if spec["target_rva"] not in decoded[spec["target_region"]]:
                raise FinalCaveMapChoiceError(
                    f"call edge {spec['id']} target is not an instruction"
                )
            continue
        if len(expected) != 6 or expected[:2] != b"\xff\x15":
            raise FinalCaveMapChoiceError(
                f"call edge {spec['id']} is not an IAT call"
            )
        if struct.unpack_from("<I", expected, 2)[0] != (
            image.image_base + spec["iat_rva"]
        ):
            raise FinalCaveMapChoiceError(
                f"call edge {spec['id']} IAT slot differs"
            )
        if not any(
            record["iat_rva"] == f"0x{spec['iat_rva']:08x}"
            and str(record["library"]).casefold() == spec["library"].casefold()
            and record["name"] == spec["name"]
            for record in imports
        ):
            raise FinalCaveMapChoiceError(
                f"call edge {spec['id']} import differs"
            )


def build_final_cave_map_choice_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build and exact-installation map-choice map."""
    _verify_sources(content_root)
    _verify_map_order(content_root)
    _verify_native_boundaries(executable)
    return _expected_shape()


def validate_final_cave_map_choice_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalCaveMapChoiceError("map-choice map must be an object")
    if dict(value) != _expected_shape():
        raise FinalCaveMapChoiceError("map-choice map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "random_map_algorithm_proven": True,
        "candidate_order_installation_bound": True,
        "random_int_one_advancement_proven": True,
        "ordinary_first_transition_draw_count": 2,
        "concrete_map_forecast_proven": False,
        "simulator_change_required": False,
    }


def validate_final_cave_map_choice_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and reject source, map-order, byte, address, or prose drift."""
    expected = build_final_cave_map_choice_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCaveMapChoiceError(
            "map-choice map differs from exact-build analysis"
        )
    result = validate_final_cave_map_choice_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_cave_map_choice_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
