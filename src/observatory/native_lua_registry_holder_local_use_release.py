"""Exact census for the bounded native Lua registry-holder local-use seam.

The artifact built here is deliberately narrower than a lifetime or ownership
proof. It seals one native producer, every atlas-decoded reference to that
producer, and the syntactic local use/release grammar in all 46 direct callers.
"""
from __future__ import annotations

import copy
import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_indirect_settable_publications import (
    _build_cfg,
    _dominators,
    _graph_maps,
    _path_nodes,
    _writes_esi,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _canonical_bytes,
    _canonical_sha256,
    _decode_range,
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_registry_holder_local_use_release_census"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_IMAGE_BASE = 0x00400000
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_TERMINAL = "74b762e486611a6dc71325276d9e8e92b7894de30f99bacf9e301e894c85bb85"
_PRODUCER = 0x00057970
_PRODUCER_SIZE = 107
_PRODUCER_BODY_SHA256 = (
    "a2a4f2291ef2d6afb98599d9f713d9f2ebe3bace50aea021ba0b46a859e1f501"
)
_PRODUCER_CFG_SHA256 = (
    "99d2047c3855ed0211ceb85bb854707a4bac5f8a6be129cbb5106f583ca568d3"
)

_CALLERS = (
    0x00054740,
    0x00054870,
    0x000549A0,
    0x00054AD0,
    0x00054C00,
    0x00054D30,
    0x00054E60,
    0x00054FA0,
    0x000550D0,
    0x0028F3F0,
    0x0028F520,
    0x0028F650,
    0x0028F780,
    0x0028F8B0,
    0x0028F9E0,
    0x0028FB10,
    0x0028FC40,
    0x0028FD70,
    0x0028FEA0,
    0x0028FFD0,
    0x00290100,
    0x00290230,
    0x00290360,
    0x00290490,
    0x002905C0,
    0x002906F0,
    0x00290820,
    0x00290950,
    0x00290A80,
    0x00290BB0,
    0x00290CE0,
    0x00290E10,
    0x00290F40,
    0x00291070,
    0x002911A0,
    0x002912D0,
    0x00291400,
    0x00291530,
    0x00291660,
    0x00291790,
    0x002918C0,
    0x002919F0,
    0x00291B20,
    0x00291C50,
    0x00291D80,
    0x00291EB0,
)

_CALLER_CFG_SHA256 = {
    0x00054740: "2da8aaa0f9098c9deae52644e0d064f9900346e824ee66a9a3bb8fab77354c23",
    0x00054870: "3001ed25b40fca374735a4b488a6e8cf4c05128da5d195ada8fe80a496aca818",
    0x000549A0: "23240709dcf2b903ad29d46eb9ce1e3341366dcf67b247d6c2aba39b083646fb",
    0x00054AD0: "c9c65e3197507b7956d882fc25d137e088b274bdeeff3ecf690d9f8475bdf8bd",
    0x00054C00: "f5d153c8932ef74eb4606f88b678725c492ae1384d9c58c4c329aba7e64b9dbf",
    0x00054D30: "c9f1fe474d892792c22e52a0dfa59f10b7f7c76b7921c16371b3ff4e5682eb73",
    0x00054E60: "d1ab6cfcabd1dd0bb95419dd7de1dedc45abb74df209acc4aeeeaf42867150c7",
    0x00054FA0: "a47a21437a63cef08b2540fc619f748c9d5617ad97e8e91d6d064256e3969a20",
    0x000550D0: "6a32635e5d3e135b2089e25094e596d497252f351b7386d49a53508c26789bab",
    0x0028F3F0: "f6e89266be65f36f0372a699ca86b28c75bd7d8e61b99e6a3e7c59db89ecdb6c",
    0x0028F520: "b050e0866c4c3d7590ed6243e418b14d85bc1b8fff912f7d0bb7f488ec4d2c05",
    0x0028F650: "afd98b95e12e2f8340d38b848bbf68c11f891af6d18e72634083c2c27bdf8068",
    0x0028F780: "c1ac072978ebab25e1c677fcbfe523d81c7a380247d0e95193d0791e5153baff",
    0x0028F8B0: "8addef5e663aec9f79e79dd2ea36c8c14ad67bcb7f2b2e211f5ad436b3e826c4",
    0x0028F9E0: "5bf11e36b96d9ca05c733460b1ec53ca93c52ce88a68772c52b888f571f7c294",
    0x0028FB10: "a393da7d4d3a7970044f280f67c5987d727ae04269a286171358ffcfb23e36e5",
    0x0028FC40: "c0c40ee02ef121625e24b0a47f67636b56fb39a61f2ae360fcd343a8616e04a7",
    0x0028FD70: "bd21a9e88c22273a437fb5307d3dc9a2db5cc7159dfa20d2d614bfb8f3950d86",
    0x0028FEA0: "1228aa8109f1f4dd58daf75feab2e081a9e5bfcedf1df1fc5b46ea1ec7726a6f",
    0x0028FFD0: "40663db42079d320ea131ada44e1a63a08a544f2c18561aaa25187d3b4f0b471",
    0x00290100: "0faebd25df77c59353c557539901bd2635124e509b2c369edfeb9f9fd2429222",
    0x00290230: "25fa3c739d2ce1a28aba6a4dc05f4e51cf2402cf9c9edac4b2b4993b527129b8",
    0x00290360: "78b97049f18f5025bd25ae05d7a58132ba6810d2dc49adb42976e63602b6cc4b",
    0x00290490: "a7eae5c943ad82af7c8edbb4a7c594e8b133f2957b28162aae56d037d4ba351e",
    0x002905C0: "7a3e59f6565af3cf72d2c4feea227cfd400503628047fa5826e80f38e5604fea",
    0x002906F0: "4a4d86c0aa6f4e0ec166e9df3e4f8b580522311fd7e86f40ba642584d50ed0b0",
    0x00290820: "c135d08eef13b7422edaee423a6bced733186021b0fca812d58fa4631b6e11c4",
    0x00290950: "62438c4d3f06e8aee1a39c366875d304f4065057563cb7fc3587b92472d4d8a8",
    0x00290A80: "0dde5ab0c55bc473ddc296eb7ab8aca638079dc9fd2aa38f50ebc96968b6bd92",
    0x00290BB0: "d04d4041e1d419b3ab54dce202bace198b14cd07d17bc4ec8d5d65125cedf8c9",
    0x00290CE0: "5c14e9d49c783a5ec497e1e51efe21508084789433bbb3c97fb40b55e12d69a2",
    0x00290E10: "f5a0dee3740c8bf495910846e9fbb4944f3acfd25d6a199acc6916f18ce683ee",
    0x00290F40: "c74ce397ff1ced09e3e0c88bb415a83562eedac29397485d75c8659b6456e1bf",
    0x00291070: "d713a04b22aa8d6663cfb60ac530ae6621ef5ac53d87c7ed78fa8b5acbbd839d",
    0x002911A0: "f872c12d11dfc457d8566be23d6e1d4b1b69bf19ac60c50cf224009e27bcd89f",
    0x002912D0: "4cfb6612f790e856e4da54f5a3b0bdbe881d80a199b3a8fb18b2dc3e3c721ece",
    0x00291400: "55ec21edfc9aac8352f7116ef0778b99ac5d4910c92a4435db2fe605c5351047",
    0x00291530: "b4286d37d8946f47b5b4762f8dbb60bd7431988d994860a656396ef0da71eb45",
    0x00291660: "12ba762cb48cd3a4e3c159d2223f45ac340129dff26177919ea2dc866c3f2404",
    0x00291790: "0d99c28f83a3d19265001445c375e7cb01ea933085e64d91d29be5deea275678",
    0x002918C0: "825ee7bc2678275f848957416171818a9b55188ffa5fa1baadcaabe7b93f0921",
    0x002919F0: "c23b6cf3570d304c4f73e8f00f30af322455747c30fe9dff3c692b678684a586",
    0x00291B20: "14bd65cd4df9e12bc31a0e95467254c42b0ef170f830d4291e2e29f94d8b72ef",
    0x00291C50: "c7f8b934aeeb4a0990d6cf7ebae7ebfc39b4c3282112168712f2583f1c1f1e0e",
    0x00291D80: "4755399eea36532eb2687c6e09964d72ff4a30077442ea2e90ad6083cdf8b36c",
    0x00291EB0: "961e744d743bcca24a7e46c8a28985cf13b9207b57b18353340a7a3a246c3aca",
}

_IAT = {
    "lua_pushcclosure": 0x003D64A0,
    "lua_rawgeti": 0x003D64C0,
    "lua_pushvalue": 0x003D64E4,
    "luaL_ref": 0x003D64E8,
    "luaL_unref": 0x003D64EC,
    "lua_settop": 0x003D6510,
    "lua_settable": 0x003D6550,
}
_PRODUCER_DIRECT_APIS = (
    "lua_rawgeti",
    "lua_rawgeti",
    "lua_pushcclosure",
    "lua_pushvalue",
    "luaL_ref",
    "lua_settop",
)
_CALLER_DIRECT_APIS = ("lua_pushvalue", "lua_settable")
_REGISTER_NAMES = ("EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI")
_REGISTER_CALL_RELS = (0x5E, 0x81, 0x99, 0xA9, 0xCC, 0xE9)

_TERMINAL_SEQUENCE_ROLES = (
    "first_reference_push", "load_state_edi", "load_holder_ebx",
    "first_registry_index", "first_state_push", "first_rawgeti",
    "load_second_reference_owner", "second_reference_push",
    "second_registry_index", "second_state_push", "second_rawgeti",
    "upvalue_count_two", "callback_push", "closure_state_push",
    "pushcclosure", "top_index_minus_one", "pushvalue_state",
    "store_holder_state", "store_holder_noref", "pushvalue",
    "ref_registry_index", "ref_state_push", "luaL_ref",
    "settop_index_minus_two", "settop_state_push", "store_holder_reference",
    "lua_settop", "argument_cleanup", "return_holder", "restore_edi",
    "restore_ebx", "restore_ebp", "return",
)


def _point_spec(role: str, rel: int, encoded_hex: str, **meaning: Any) -> dict[str, Any]:
    return {"role": role, "relative_offset": rel, "encoded": bytes.fromhex(encoded_hex), "meaning": meaning}


_CALLER_POINT_SPECS = (
    _point_spec("holder_destination", 0x25, "8d4c2414", operation="lea", stack_offset=20, destination_register="ECX"),
    _point_spec("constructor_argument", 0x29, "50", operation="push", source_register="EAX"),
    _point_spec("constructor_cleanup", 0x2F, "83c404", operation="cdecl_stack_cleanup", bytes=4),
    _point_spec("holder_capture", 0x35, "8bd8", operation="register_copy", source_register="EAX", destination_register="EBX"),
    _point_spec("rawgeti_stage", 0x45, "8b35c0647d00", operation="iat_load", api="lua_rawgeti", destination_register="ESI"),
    _point_spec("first_rawgeti_call", 0x5E, "ffd6", operation="register_call", register="ESI"),
    _point_spec("holder_reference_read", 0x73, "ff7304", operation="push_memory_value", base_register="EBX", field_offset=4),
    _point_spec("separate_temporary_ebx_reuse", 0x76, "8b5c241c", operation="stack_load", stack_offset=28, destination_register="EBX"),
    _point_spec("holder_lookup_registry_index", 0x7A, "68f0d8ffff", operation="push_immediate", value=-10000),
    _point_spec("separate_lookup_state_push", 0x7F, "ff33", operation="push_memory_value", base_register="EBX", field_offset=0),
    _point_spec("holder_reference_rawgeti_call", 0x81, "ffd6", operation="register_call", register="ESI"),
    _point_spec("settop_stage", 0x90, "8b3510657d00", operation="iat_load", api="lua_settop", destination_register="ESI"),
    _point_spec("first_settop_call", 0x99, "ffd6", operation="register_call", register="ESI"),
    _point_spec("second_settop_call", 0xA9, "ffd6", operation="register_call", register="ESI"),
    _point_spec("holder_release_state_load", 0xAE, "8b442414", operation="stack_load", stack_offset=20, destination_register="EAX"),
    _point_spec("unref_stage", 0xB2, "8b35ec647d00", operation="iat_load", api="luaL_unref", destination_register="ESI"),
    _point_spec("holder_state_guard", 0xB8, "85c0", operation="zero_test", register="EAX"),
    _point_spec("holder_state_null_branch", 0xBA, "7415", operation="branch_if_zero", target_relative_offset=0xD1),
    _point_spec("holder_release_reference_load", 0xBC, "8b4c2418", operation="stack_load", stack_offset=24, destination_register="ECX"),
    _point_spec("holder_reference_sentinel_guard", 0xC0, "83f9fe", operation="compare_immediate", register="ECX", value=-2),
    _point_spec("holder_reference_sentinel_branch", 0xC3, "740c", operation="branch_if_equal", target_relative_offset=0xD1),
    _point_spec("holder_reference_argument", 0xC5, "51", operation="push", source_register="ECX"),
    _point_spec("holder_release_registry_index", 0xC6, "68f0d8ffff", operation="push_immediate", value=-10000),
    _point_spec("holder_state_argument", 0xCB, "50", operation="push", source_register="EAX"),
    _point_spec("holder_unref_call", 0xCC, "ffd6", operation="register_call", register="ESI"),
    _point_spec("holder_unref_cleanup", 0xCE, "83c40c", operation="cdecl_stack_cleanup", bytes=12),
    _point_spec("second_release_state_load", 0xD1, "8b44241c", operation="stack_load", stack_offset=28, destination_register="EAX"),
    _point_spec("second_release_state_guard", 0xD5, "85c0", operation="zero_test", register="EAX"),
    _point_spec("second_release_state_null_branch", 0xD7, "7415", operation="branch_if_zero", target_relative_offset=0xEE),
    _point_spec("second_release_reference_load", 0xD9, "8b4c2420", operation="stack_load", stack_offset=32, destination_register="ECX"),
    _point_spec("second_release_sentinel_guard", 0xDD, "83f9fe", operation="compare_immediate", register="ECX", value=-2),
    _point_spec("second_release_sentinel_branch", 0xE0, "740c", operation="branch_if_equal", target_relative_offset=0xEE),
    _point_spec("second_release_reference_argument", 0xE2, "51", operation="push", source_register="ECX"),
    _point_spec("second_release_registry_index", 0xE3, "68f0d8ffff", operation="push_immediate", value=-10000),
    _point_spec("second_release_state_argument", 0xE8, "50", operation="push", source_register="EAX"),
    _point_spec("second_unref_call", 0xE9, "ffd6", operation="register_call", register="ESI"),
    _point_spec("second_unref_cleanup", 0xEB, "83c40c", operation="cdecl_stack_cleanup", bytes=12),
)

_STAGE_SPECS = (
    ("lua_rawgeti", 0x45, (
        (0x5E, (0x45, 0x4B, 0x4D, 0x51, 0x54, 0x57, 0x5C, 0x5E)),
        (0x81, (0x45, 0x4B, 0x4D, 0x51, 0x54, 0x57, 0x5C, 0x5E, 0x60, 0x64, 0x67, 0x69, 0x6C, 0x6D, 0x73, 0x76, 0x7A, 0x7F, 0x81)),
    )),
    ("lua_settop", 0x90, (
        (0x99, (0x90, 0x96, 0x98, 0x99)),
        (0xA9, (0x90, 0x96, 0x98, 0x99, 0x9B, 0x9F, 0xA2, 0xA4, 0xA6, 0xA8, 0xA9)),
    )),
    ("luaL_unref", 0xB2, (
        (0xCC, (0xB2, 0xB8, 0xBA, 0xBC, 0xC0, 0xC3, 0xC5, 0xC6, 0xCB, 0xCC)),
        (0xE9, (0xB2, 0xB8, 0xBA, 0xBC, 0xC0, 0xC3, 0xC5, 0xC6, 0xCB, 0xCC, 0xCE, 0xD1, 0xD5, 0xD7, 0xD9, 0xDD, 0xE0, 0xE2, 0xE3, 0xE8, 0xE9)),
    )),
)

_METHOD = {
    "accepted_chain": "One exact registry-holder producer and the complete all-operand atlas reference partition are sealed. Each caller's local holder use and guarded release are retained as bounded syntactic facts.",
    "abi_premises": [
        "Lua 5.1 LUA_REGISTRYINDEX is -10000",
        "Lua 5.1 LUA_NOREF is -2",
        "32-bit Windows cdecl preserves ESI across calls",
        "a 32-bit near-call return value is carried in EAX",
    ],
    "structural_boundary": "PE-free validation reconstructs the complete artifact from canonical-pinned prerequisites plus the sealed body, CFG, and instruction profile and rejects any unknown or altered nested field. Instruction decoding, operand classification, register access, CFG construction, and exhaustive atlas traversal require an exact executable rebuild.",
    "holder_window_boundary": "The EBX audit begins at the constructor return capture and ends immediately before EBX is overwritten from a separate stack temporary. It is an exhaustive syntactic register-use audit only within that decoded instruction window.",
    "not_claimed": [
        "runtime reachability, execution, frequency, call success, or registry-reference validity",
        "raw-lookup state equality with holder state, ownership, type identity, persistence, lifetime, destruction, or field clearing",
        "absence of later uses, indirect or un-atlased callers, arbitrary callee mutation, or a complete resource lifetime",
        "semantic attribution of the second stack-pair release to the constructed holder",
        "source-level C++ or Lua equivalence",
    ],
}


class NativeLuaRegistryHolderError(RuntimeError):
    """Raised when the sealed registry-holder profile cannot be reproduced."""


def _require_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    item = _mapping(value, label)
    if set(item) != expected:
        raise NativeLuaRegistryHolderError(f"{label} keys differ")
    return item


def _fact_from_bytes(rva: int, encoded: bytes) -> dict[str, Any]:
    return {"rva": _hex(rva), "size": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}


def _fact(instruction: Any, image_base: int) -> dict[str, Any]:
    return _fact_from_bytes(instruction.address - image_base, bytes(instruction.bytes))


def _function_shape(function: Mapping[str, Any], entry: int, size: int, label: str) -> Mapping[str, Any]:
    ranges = _array(function.get("ranges"), f"{label}.ranges")
    if function.get("thunk") is not False or function.get("body_size") != size or len(ranges) != 1:
        raise NativeLuaRegistryHolderError(f"{label} body shape changed")
    span = _mapping(ranges[0], f"{label}.ranges[0]")
    if _rva(span.get("start_rva"), f"{label} range start") != entry or span.get("size") != size:
        raise NativeLuaRegistryHolderError(f"{label} range boundary changed")
    body_sha = function.get("body_sha256")
    if not isinstance(body_sha, str) or len(body_sha) != 64:
        raise NativeLuaRegistryHolderError(f"{label} body digest changed")
    return span


def _imports(direct: Mapping[str, Any]) -> None:
    imports = {item.get("name"): item for item in _array(direct.get("lua_imports"), "direct calls.lua_imports") if isinstance(item, Mapping)}
    for name, iat in _IAT.items():
        item = imports.get(name)
        if not isinstance(item, Mapping) or item.get("library") != "lua5.1.dll" or _rva(item.get("iat_rva"), f"{name} IAT") != iat:
            raise NativeLuaRegistryHolderError(f"{name} import identity changed")


def _terminal_holder(terminal: Mapping[str, Any]) -> Mapping[str, Any]:
    if terminal.get("analysis_kind") != "pe_native_lua_cclosure_terminal_disposition_census" or _canonical_sha256(terminal) != _TERMINAL:
        raise NativeLuaRegistryHolderError("terminal prerequisite identity changed")
    rows = [item for item in _array(terminal.get("dispositions"), "terminal dispositions") if isinstance(item, Mapping) and item.get("disposition_kind") == "registry_reference_holder"]
    if len(rows) != 1:
        raise NativeLuaRegistryHolderError("terminal holder partition changed")
    row = rows[0]
    wanted = {
        "caller_entry_rva": _hex(_PRODUCER), "callback_call_rva": "0x000579a2",
        "callback_entry_rva": "0x002eaa50", "state_register": "edi",
        "holder_register": "ebx", "registry_index": -10000,
        "initial_reference_sentinel": -2, "literal_upvalue_count": 2,
        "returned_register": "ebx",
    }
    if any(row.get(key) != value for key, value in wanted.items()):
        raise NativeLuaRegistryHolderError("terminal holder record changed")
    sequence = _array(row.get("reviewed_sequence"), "terminal holder reviewed_sequence")
    if tuple(item.get("role") for item in sequence if isinstance(item, Mapping)) != _TERMINAL_SEQUENCE_ROLES:
        raise NativeLuaRegistryHolderError("terminal holder sequence roles changed")
    previous_end: int | None = None
    for index, raw in enumerate(sequence):
        item = _require_keys(raw, {"role", "rva", "size", "sha256"}, f"terminal sequence[{index}]")
        rva = _rva(item["rva"], f"terminal sequence[{index}].rva")
        size = item.get("size")
        if type(size) is not int or size <= 0 or not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64:
            raise NativeLuaRegistryHolderError("terminal sequence instruction fact changed")
        if previous_end is not None and rva != previous_end:
            raise NativeLuaRegistryHolderError("terminal holder sequence is not contiguous")
        previous_end = rva + size
    if _rva(sequence[0]["rva"], "terminal sequence start") != 0x00057975 or previous_end != 0x000579DB:
        raise NativeLuaRegistryHolderError("terminal holder sequence boundary changed")
    return row


def _preflight(facts: Mapping[str, Any], direct: Mapping[str, Any], terminal: Mapping[str, Any]) -> tuple[dict[int, Mapping[str, Any]], Mapping[str, Any]]:
    for value, label in ((facts, "program facts"), (direct, "direct calls"), (terminal, "terminal dispositions")):
        _validate_json_tree(value, label)
    if facts.get("analysis_kind") != "pe_ghidra_program_facts" or _canonical_sha256(facts) != _FACTS:
        raise NativeLuaRegistryHolderError("program-facts identity changed")
    if direct.get("analysis_kind") != "pe_native_lua_direct_import_call_census" or _canonical_sha256(direct) != _DIRECT:
        raise NativeLuaRegistryHolderError("direct-call prerequisite identity changed")
    identity = _mapping(facts.get("identity"), "program facts.identity")
    ghidra = _mapping(facts.get("ghidra"), "program facts.ghidra")
    if identity.get("executable_sha256") != _EXE or direct.get("build_identity") != dict(identity) or terminal.get("build_identity") != dict(identity) or _rva(ghidra.get("image_base"), "Ghidra image base") != _IMAGE_BASE:
        raise NativeLuaRegistryHolderError("prerequisites have different build identities")
    _imports(direct)
    holder = _terminal_holder(terminal)
    functions = _atlas_functions(facts)
    if len(_CALLERS) != 46 or set(_CALLER_CFG_SHA256) != set(_CALLERS) or any(entry not in functions for entry in (*_CALLERS, _PRODUCER)):
        raise NativeLuaRegistryHolderError("reviewed caller frontier changed")
    return functions, holder


def _direct_index(direct: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw in _array(direct.get("records"), "direct calls.records"):
        item = _mapping(raw, "direct-call record")
        entry = _rva(item.get("entry_rva"), "direct-call entry")
        if entry in result:
            raise NativeLuaRegistryHolderError("duplicate direct Lua caller record")
        result[entry] = item
    return result


def _direct_rows(
    records: Mapping[int, Mapping[str, Any]],
    entry: int,
    expected_apis: tuple[str, ...],
    expected_rvas: tuple[int, ...],
) -> list[dict[str, Any]]:
    record = records.get(entry)
    if record is None:
        raise NativeLuaRegistryHolderError("direct Lua caller join changed")
    result = []
    for raw in _array(record.get("direct_lua_import_calls"), "direct Lua calls"):
        item = _mapping(raw, "direct Lua call")
        api = item.get("import_name")
        if api not in _IAT or item.get("library") != "lua5.1.dll" or item.get("call_form") != "x86_absolute_iat_indirect_call_ff15" or _rva(item.get("iat_rva"), "direct Lua call IAT") != _IAT[api]:
            raise NativeLuaRegistryHolderError("direct Lua call identity changed")
        result.append({
            "rva": item["call_rva"], "api": api, "iat_rva": item["iat_rva"],
            "call_form": item["call_form"], "instruction_size": item["instruction_size"],
            "instruction_sha256": item["instruction_sha256"],
        })
    if (
        tuple(item["api"] for item in result) != expected_apis
        or tuple(_rva(item["rva"], "direct Lua call RVA") for item in result)
        != expected_rvas
    ):
        raise NativeLuaRegistryHolderError("direct Lua call partition changed")
    return result


def _normalized_ghidra_edge(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = _mapping(raw, "Ghidra declared direct edge")
    return {key: item.get(key) for key in ("instruction_rva", "source_entry_rva", "target_entry_rva", "target_name", "target_rva")}


def _ghidra_edges(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [_normalized_ghidra_edge(raw) for raw in _array(facts.get("ghidra_declared_direct_calls"), "program facts.ghidra_declared_direct_calls")]


def _constructor_bytes(entry: int) -> bytes:
    return b"\xe8" + struct.pack("<i", _PRODUCER - (entry + 0x2A + 5))


def _semantic_points(entry: int) -> list[dict[str, Any]]:
    result = []
    for spec in _CALLER_POINT_SPECS:
        meaning = copy.deepcopy(spec["meaning"])
        target_rel = meaning.pop("target_relative_offset", None)
        if target_rel is not None:
            meaning["target_rva"] = _hex(entry + target_rel)
        result.append({"role": spec["role"], **_fact_from_bytes(entry + spec["relative_offset"], spec["encoded"]), "meaning": meaning})
    return result


def _stage_path_audit(entry: int) -> list[dict[str, Any]]:
    result = []
    for api, stage_rel, calls in _STAGE_SPECS:
        stage_bytes = b"\x8b\x35" + struct.pack("<I", _IMAGE_BASE + _IAT[api])
        result.append({
            "api": api, "register": "ESI", "iat_rva": _hex(_IAT[api]),
            "stage_instruction": _fact_from_bytes(entry + stage_rel, stage_bytes),
            "calls": [{
                "call_instruction": _fact_from_bytes(entry + call_rel, b"\xff\xd6"),
                "path_rvas": [_hex(entry + rel) for rel in path],
                "last_reaching_stage_rvas": [_hex(entry + stage_rel)],
                "post_stage_esi_writer_rvas": [],
            } for call_rel, path in calls],
            "cdecl_nonvolatile_esi_premise": True,
        })
    return result


def _entry_audit_expected(edges: list[dict[str, Any]], functions: Mapping[int, Mapping[str, Any]], entry: int) -> dict[str, Any]:
    end = entry + 247
    alternate = [_hex(value) for value in sorted(value for value in functions if entry < value < end)]
    incoming = []
    for edge in edges:
        target = _rva(edge.get("target_rva"), "Ghidra edge target")
        if entry <= target < end:
            incoming.append(edge)
    incoming.sort(key=lambda item: (_rva(item["target_rva"], "incoming target"), _rva(item["instruction_rva"], "incoming instruction")))
    interior = sorted({_rva(item["target_rva"], "incoming target") for item in incoming if _rva(item["target_rva"], "incoming target") != entry})
    if alternate or interior:
        raise NativeLuaRegistryHolderError("caller has an alternate modeled interior entry")
    if len(incoming) != 1 or _rva(incoming[0]["target_rva"], "incoming target") != entry:
        raise NativeLuaRegistryHolderError("caller declared-entry partition changed")
    return {
        "accepted_entry_rva": _hex(entry), "body_end_exclusive_rva": _hex(end),
        "alternate_atlas_entry_into_body": alternate,
        "ghidra_declared_direct_calls_into_body": incoming,
        "interior_declared_target_rvas": [_hex(value) for value in interior],
        "all_declared_targets_are_function_entry": True,
    }


def _holder_window_audit(entry: int) -> dict[str, Any]:
    return {
        "start_rva": _hex(entry + 0x35), "end_exclusive_rva": _hex(entry + 0x76),
        "decoded_instruction_count": 21,
        "holder_capture": _fact_from_bytes(entry + 0x35, b"\x8b\xd8"),
        "holder_register": "EBX",
        "explicit_register_mention_rvas": [_hex(entry + 0x35), _hex(entry + 0x73)],
        "memory_accesses_through_holder_register": [{**_fact_from_bytes(entry + 0x73, b"\xff\x73\x04"), "access": "read", "field_offset": 4}],
        "explicit_store_through_holder_register_rvas": [],
        "explicit_persistent_holder_copy_rvas": [],
        "syntactic_holder_address_argument_transfer_rvas": [],
        "window_end_overwrite": {**_fact_from_bytes(entry + 0x76, b"\x8b\x5c\x24\x1c"), "source_stack_offset": 28},
        "audit_scope": "capture_through_instruction_before_separate_temporary_overwrite",
    }


def _expected_caller(entry: int, function: Mapping[str, Any], edges: list[dict[str, Any]], functions: Mapping[int, Mapping[str, Any]], direct_records: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    _function_shape(function, entry, 247, f"caller {_hex(entry)}")
    constructor = _constructor_bytes(entry)
    register_calls = [{**_fact_from_bytes(entry + rel, b"\xff\xd6"), "register": "ESI"} for rel in _REGISTER_CALL_RELS]
    return {
        "entry_rva": _hex(entry), "atlas_record_sha256": atlas_record_sha256(function),
        "range_start_rva": _hex(entry), "body_size": 247,
        "body_sha256": function["body_sha256"],
        "control_flow_graph_canonical_sha256": _CALLER_CFG_SHA256[entry],
        "control_flow_graph_node_count": 90, "control_flow_graph_edge_count": 94,
        "constructor_edge": {**_fact_from_bytes(entry + 0x2A, constructor), "target_rva": _hex(_PRODUCER), "operand_class": "immediate", "operand_index": 0, "form": "x86_relative_near_call_e8"},
        "semantic_points": _semantic_points(entry),
        "local_holder": {"destination_rva": _hex(entry + 0x25), "stack_offset": 20, "return_transfer_rva": _hex(entry + 0x35), "return_abi_register": "EAX", "retained_register": "EBX"},
        "direct_lua_calls": _direct_rows(
            direct_records,
            entry,
            _CALLER_DIRECT_APIS,
            (entry + 0x6D, entry + 0x8A),
        ),
        "register_indirect_calls": register_calls,
        "call_r32_audit": [{"register": register, "call_rvas": [item["rva"] for item in register_calls] if register == "ESI" else []} for register in _REGISTER_NAMES],
        "stage_path_audit": _stage_path_audit(entry),
        "holder_register_window_audit": _holder_window_audit(entry),
        "local_use": {"reference_read_rva": _hex(entry + 0x73), "field_offset": 4, "rawgeti_call_rva": _hex(entry + 0x81), "raw_lookup_state_equality_proven": False, "separate_temporary_overwrite_rva": _hex(entry + 0x76), "separate_temporary_stack_offset": 28, "separate_state_push_rva": _hex(entry + 0x7F)},
        "local_release": {"state_stack_offset": 20, "reference_stack_offset": 24, "state_guard_rva": _hex(entry + 0xB8), "state_null_branch_target_rva": _hex(entry + 0xD1), "sentinel_guard_rva": _hex(entry + 0xC0), "sentinel_branch_target_rva": _hex(entry + 0xD1), "sentinel": -2, "unref_call_rva": _hex(entry + 0xCC), "registry_index": -10000},
        "excluded_second_release": {"state_stack_offset": 28, "reference_stack_offset": 32, "state_guard_rva": _hex(entry + 0xD5), "state_null_branch_target_rva": _hex(entry + 0xEE), "sentinel_guard_rva": _hex(entry + 0xDD), "sentinel_branch_target_rva": _hex(entry + 0xEE), "unref_call_rva": _hex(entry + 0xE9), "attributed_to_holder": False},
        "entry_audit": _entry_audit_expected(edges, functions, entry),
    }


def _expected_producer(function: Mapping[str, Any], direct_records: Mapping[int, Mapping[str, Any]], holder: Mapping[str, Any]) -> dict[str, Any]:
    _function_shape(function, _PRODUCER, _PRODUCER_SIZE, "producer")
    if function.get("body_sha256") != _PRODUCER_BODY_SHA256:
        raise NativeLuaRegistryHolderError("producer body identity changed")
    sequence = copy.deepcopy(_array(holder.get("reviewed_sequence"), "holder sequence"))
    points_by_role = {item["role"]: item for item in sequence}
    direct_calls = _direct_rows(
        direct_records,
        _PRODUCER,
        _PRODUCER_DIRECT_APIS,
        (0x00057982, 0x00057994, 0x000579A2, 0x000579B4, 0x000579C0, 0x000579CC),
    )
    for call, role in zip(
        direct_calls,
        ("first_rawgeti", "second_rawgeti", "pushcclosure", "pushvalue", "luaL_ref", "lua_settop"),
    ):
        point = points_by_role[role]
        if (
            (call["rva"], call["instruction_size"], call["instruction_sha256"])
            != (point["rva"], point["size"], point["sha256"])
        ):
            raise NativeLuaRegistryHolderError(
                "producer terminal-sequence/direct-call join changed"
            )
    return {
        "entry_rva": _hex(_PRODUCER), "atlas_record_sha256": atlas_record_sha256(function),
        "range_start_rva": _hex(_PRODUCER), "body_size": _PRODUCER_SIZE,
        "body_sha256": function["body_sha256"],
        "control_flow_graph_canonical_sha256": _PRODUCER_CFG_SHA256,
        "control_flow_graph_node_count": 37, "control_flow_graph_edge_count": 36,
        "direct_lua_calls": direct_calls,
        "reviewed_sequence": sequence,
        "holder_fields": [{"offset": 0, "source_register": "EDI"}, {"offset": 4, "initial_value": -2, "final_value": "luaL_ref_return"}],
        "producer_points": [copy.deepcopy(points_by_role[role]) for role in ("store_holder_state", "store_holder_noref", "luaL_ref", "store_holder_reference", "return_holder")],
        "constructor_abi_return_register": "EAX", "constructor_return_source_register": "EBX",
        "terminal_disposition_join": {"analysis_kind": "pe_native_lua_cclosure_terminal_disposition_census", "canonical_sha256": _TERMINAL, "callback_call_rva": holder["callback_call_rva"], "callback_entry_rva": holder["callback_entry_rva"], "disposition_kind": holder["disposition_kind"]},
    }


def _expected_references(edges: list[dict[str, Any]], functions: Mapping[int, Mapping[str, Any]]) -> list[dict[str, Any]]:
    producer_edges = [edge for edge in edges if _rva(edge.get("target_rva"), "producer edge target") == _PRODUCER]
    producer_edges.sort(key=lambda item: _rva(item["instruction_rva"], "producer edge instruction"))
    expected_pairs = [(entry, entry + 0x2A) for entry in _CALLERS]
    actual_pairs = [(_rva(item["source_entry_rva"], "producer edge source"), _rva(item["instruction_rva"], "producer edge instruction")) for item in producer_edges]
    if actual_pairs != expected_pairs:
        raise NativeLuaRegistryHolderError("Ghidra producer caller partition changed")
    result = []
    for entry, edge in zip(_CALLERS, producer_edges):
        encoded = _constructor_bytes(entry)
        result.append({
            "instruction_rva": _hex(entry + 0x2A), "instruction_size": len(encoded),
            "instruction_sha256": hashlib.sha256(encoded).hexdigest(),
            "owner_entry_rva": _hex(entry), "owner_atlas_record_sha256": atlas_record_sha256(functions[entry]),
            "target_rva": _hex(_PRODUCER), "operand_class": "immediate", "operand_index": 0,
            "call_form": "x86_relative_near_call_e8", "ghidra_declared_direct_edge": edge,
        })
    return result


def _clusters() -> list[dict[str, Any]]:
    return [
        {"name": "low_rva_cluster", "first_entry_rva": _hex(_CALLERS[0]), "last_entry_rva": _hex(_CALLERS[8]), "caller_count": 9, "body_bytes": 9 * 247},
        {"name": "high_rva_cluster", "first_entry_rva": _hex(_CALLERS[9]), "last_entry_rva": _hex(_CALLERS[-1]), "caller_count": 37, "body_bytes": 37 * 247},
    ]


def _expected_artifact(facts: Mapping[str, Any], direct: Mapping[str, Any], terminal: Mapping[str, Any]) -> dict[str, Any]:
    functions, holder = _preflight(facts, direct, terminal)
    direct_records = _direct_index(direct)
    edges = _ghidra_edges(facts)
    producer = _expected_producer(functions[_PRODUCER], direct_records, holder)
    callers = [_expected_caller(entry, functions[entry], edges, functions, direct_records) for entry in _CALLERS]
    references = _expected_references(edges, functions)
    clusters = _clusters()
    result = {
        "schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(_mapping(facts["identity"], "program facts.identity")),
        "prerequisites": {"program_facts": _FACTS, "direct_call_census": _DIRECT, "terminal_dispositions": _TERMINAL},
        "producer": producer, "callers": callers, "caller_clusters": clusters,
        "whole_atlas_reference_scan": {
            "target_rva": _hex(_PRODUCER),
            "scope": {"atlas_function_count": len(functions), "atlas_body_range_count": 25490, "decoded_bytes": 3735718, "decoded_instructions": 1153814, "operand_classes": ["absolute_memory", "immediate"], "all_declared_ranges_decoded": True},
            "references": references, "reference_count": len(references),
            "all_references_are_declared_direct_e8_calls": True,
        },
        "method": copy.deepcopy(_METHOD),
    }
    result["summary"] = {
        "declared_direct_caller_count": len(callers),
        "low_rva_cluster_caller_count": clusters[0]["caller_count"],
        "high_rva_cluster_caller_count": clusters[1]["caller_count"],
        "caller_body_bytes": sum(item["body_size"] for item in callers),
        "caller_cfg_node_count": sum(item["control_flow_graph_node_count"] for item in callers),
        "caller_cfg_edge_count": sum(item["control_flow_graph_edge_count"] for item in callers),
        "caller_direct_lua_call_count": sum(len(item["direct_lua_calls"]) for item in callers),
        "producer_direct_lua_call_count": len(producer["direct_lua_calls"]),
        "caller_register_indirect_call_count": sum(len(item["register_indirect_calls"]) for item in callers),
        "caller_semantic_point_count": sum(len(item["semantic_points"]) for item in callers),
        "holder_register_window_count": len(callers), "whole_atlas_target_reference_count": len(references),
        "all_source_body_count": len(callers) + 1,
        "all_source_body_bytes": sum(item["body_size"] for item in callers) + producer["body_size"],
        "all_source_cfg_node_count": sum(item["control_flow_graph_node_count"] for item in callers) + producer["control_flow_graph_node_count"],
        "all_source_cfg_edge_count": sum(item["control_flow_graph_edge_count"] for item in callers) + producer["control_flow_graph_edge_count"],
        "schema_violations": 0,
    }
    _assert_publication_safe(result)
    return result


def _cfg(instructions: list[Any], image: Any, entry: int, size: int, capstone_module: Any, x86: Any) -> dict[str, Any]:
    graph = _build_cfg(instructions, image.image_base, (entry, size), capstone_module, x86)
    if graph is None:
        raise NativeLuaRegistryHolderError("function CFG is incomplete")
    graph["caller_entry_rva"] = _hex(entry)
    return graph


def _verify_body_bytes(function: Mapping[str, Any], instructions: list[Any], expected_size: int, label: str) -> None:
    encoded = b"".join(bytes(instruction.bytes) for instruction in instructions)
    if len(encoded) != expected_size or hashlib.sha256(encoded).hexdigest() != function.get("body_sha256"):
        raise NativeLuaRegistryHolderError(f"{label} PE body hash changed")


def _verify_fact(by_rva: Mapping[int, Any], expected: Mapping[str, Any], image_base: int, label: str) -> Any:
    rva = _rva(expected.get("rva"), f"{label}.rva")
    instruction = by_rva.get(rva)
    if instruction is None or _fact(instruction, image_base) != {"rva": expected.get("rva"), "size": expected.get("size"), "sha256": expected.get("sha256")}:
        raise NativeLuaRegistryHolderError(f"{label} instruction differs")
    return instruction


def _verify_stage_paths(graph: Mapping[str, Any], instructions: list[Any], image: Any, expected: list[dict[str, Any]], x86: Any) -> None:
    _nodes, edges = _graph_maps(graph)
    dominators = _dominators(edges, _rva(graph["caller_entry_rva"], "CFG entry"))
    decoded = {instruction.address - image.image_base: instruction for instruction in instructions}
    for stage_index, stage in enumerate(expected):
        stage_fact = _mapping(stage["stage_instruction"], "stage instruction")
        stage_rva = _rva(stage_fact["rva"], "stage RVA")
        _verify_fact(decoded, stage_fact, image.image_base, f"stage {stage_index}")
        for call_index, raw_call in enumerate(_array(stage["calls"], "stage calls")):
            call = _mapping(raw_call, "stage call")
            call_fact = _mapping(call["call_instruction"], "stage call instruction")
            call_rva = _rva(call_fact["rva"], "stage call RVA")
            call_instruction = _verify_fact(decoded, call_fact, image.image_base, f"stage {stage_index} call {call_index}")
            if call_instruction.mnemonic != "call" or len(call_instruction.operands) != 1 or call_instruction.operands[0].type != x86.X86_OP_REG or call_instruction.operands[0].reg != x86.X86_REG_ESI or stage_rva not in dominators.get(call_rva, set()):
                raise NativeLuaRegistryHolderError("staged ESI call provenance changed")
            path = _path_nodes(edges, stage_rva, call_rva)
            writers = sorted(rva for rva in path - {stage_rva} if _writes_esi(decoded[rva], x86.X86_REG_ESI))
            if [_hex(rva) for rva in sorted(path)] != call["path_rvas"] or [_hex(rva) for rva in writers] != call["post_stage_esi_writer_rvas"] or call["last_reaching_stage_rvas"] != [_hex(stage_rva)]:
                raise NativeLuaRegistryHolderError("staged ESI path proof changed")


def _instruction_mentions_register(instruction: Any, register: int, x86: Any) -> bool:
    try:
        reads, writes = instruction.regs_access()
    except Exception as exc:  # pragma: no cover
        raise NativeLuaRegistryHolderError("Capstone register-access classification failed") from exc
    if register in reads or register in writes:
        return True
    for operand in instruction.operands:
        if operand.type == x86.X86_OP_REG and operand.reg == register:
            return True
        if operand.type == x86.X86_OP_MEM and (operand.mem.base == register or operand.mem.index == register):
            return True
    return False


def _verify_holder_window(entry: int, instructions: list[Any], image: Any, expected: Mapping[str, Any], x86: Any) -> None:
    start, end = entry + 0x35, entry + 0x76
    window = [instruction for instruction in instructions if start <= instruction.address - image.image_base < end]
    mentioned = [instruction.address - image.image_base for instruction in window if _instruction_mentions_register(instruction, x86.X86_REG_EBX, x86)]
    if len(window) != expected.get("decoded_instruction_count") or [_hex(rva) for rva in mentioned] != expected.get("explicit_register_mention_rvas"):
        raise NativeLuaRegistryHolderError("bounded EBX reference partition changed")
    by_rva = {instruction.address - image.image_base: instruction for instruction in instructions}
    _verify_fact(by_rva, expected["holder_capture"], image.image_base, "holder capture")
    access = _mapping(_array(expected["memory_accesses_through_holder_register"], "holder memory accesses")[0], "holder memory access")
    memory_instruction = _verify_fact(by_rva, access, image.image_base, "holder field read")
    memory_operands = [operand for operand in memory_instruction.operands if operand.type == x86.X86_OP_MEM and operand.mem.base == x86.X86_REG_EBX]
    if len(memory_operands) != 1 or memory_operands[0].mem.disp != 4:
        raise NativeLuaRegistryHolderError("holder field access changed")
    _verify_fact(by_rva, _mapping(expected["window_end_overwrite"], "holder window overwrite"), image.image_base, "holder window overwrite")
    if any(expected.get(field) != [] for field in ("explicit_store_through_holder_register_rvas", "explicit_persistent_holder_copy_rvas", "syntactic_holder_address_argument_transfer_rvas")):
        raise NativeLuaRegistryHolderError("holder window empty audit changed")


def _verify_caller(entry: int, function: Mapping[str, Any], instructions: list[Any], image: Any, capstone_module: Any, x86: Any, expected: Mapping[str, Any]) -> None:
    _function_shape(function, entry, 247, f"caller {_hex(entry)}")
    _verify_body_bytes(function, instructions, 247, f"caller {_hex(entry)}")
    graph = _cfg(instructions, image, entry, 247, capstone_module, x86)
    if _canonical_sha256(graph) != expected.get("control_flow_graph_canonical_sha256") or graph.get("node_count") != expected.get("control_flow_graph_node_count") or graph.get("edge_count") != expected.get("control_flow_graph_edge_count"):
        raise NativeLuaRegistryHolderError("caller CFG identity changed")
    by_rva = {instruction.address - image.image_base: instruction for instruction in instructions}
    edge = _mapping(expected["constructor_edge"], "constructor edge")
    edge_instruction = _verify_fact(by_rva, edge, image.image_base, "constructor edge")
    if bytes(edge_instruction.bytes)[:1] != b"\xe8" or edge_instruction.mnemonic != "call" or len(edge_instruction.operands) != 1 or edge_instruction.operands[0].type != x86.X86_OP_IMM or int(edge_instruction.operands[0].imm) != image.image_base + _PRODUCER:
        raise NativeLuaRegistryHolderError("constructor edge decoding changed")
    for point in _array(expected["semantic_points"], "semantic points"):
        instruction = _verify_fact(by_rva, point, image.image_base, f"semantic point {point.get('role')}")
        meaning = _mapping(point.get("meaning"), "semantic point meaning")
        if meaning.get("operation") in {"branch_if_zero", "branch_if_equal"} and (len(instruction.operands) != 1 or instruction.operands[0].type != x86.X86_OP_IMM or int(instruction.operands[0].imm) - image.image_base != _rva(meaning.get("target_rva"), "semantic branch target")):
            raise NativeLuaRegistryHolderError("semantic branch target changed")
    actual_register_calls = []
    call_r32 = {name: [] for name in _REGISTER_NAMES}
    for instruction in instructions:
        encoded = bytes(instruction.bytes)
        if len(encoded) == 2 and encoded[0] == 0xFF and 0xD0 <= encoded[1] <= 0xD7:
            call_r32[_REGISTER_NAMES[encoded[1] - 0xD0]].append(_hex(instruction.address - image.image_base))
        if instruction.mnemonic == "call" and len(instruction.operands) == 1 and instruction.operands[0].type == x86.X86_OP_REG:
            actual_register_calls.append({**_fact(instruction, image.image_base), "register": instruction.reg_name(instruction.operands[0].reg).upper()})
    if actual_register_calls != expected.get("register_indirect_calls") or [{"register": register, "call_rvas": call_r32[register]} for register in _REGISTER_NAMES] != expected.get("call_r32_audit"):
        raise NativeLuaRegistryHolderError("register-call partition changed")
    _verify_stage_paths(graph, instructions, image, _array(expected["stage_path_audit"], "stage path audit"), x86)
    _verify_holder_window(entry, instructions, image, _mapping(expected["holder_register_window_audit"], "holder window audit"), x86)


def _verify_producer(function: Mapping[str, Any], instructions: list[Any], image: Any, capstone_module: Any, x86: Any, expected: Mapping[str, Any]) -> None:
    _function_shape(function, _PRODUCER, _PRODUCER_SIZE, "producer")
    _verify_body_bytes(function, instructions, _PRODUCER_SIZE, "producer")
    graph = _cfg(instructions, image, _PRODUCER, _PRODUCER_SIZE, capstone_module, x86)
    if _canonical_sha256(graph) != expected.get("control_flow_graph_canonical_sha256") or graph.get("node_count") != expected.get("control_flow_graph_node_count") or graph.get("edge_count") != expected.get("control_flow_graph_edge_count"):
        raise NativeLuaRegistryHolderError("producer CFG identity changed")
    by_rva = {instruction.address - image.image_base: instruction for instruction in instructions}
    previous_end: int | None = None
    for index, raw in enumerate(_array(expected["reviewed_sequence"], "producer sequence")):
        item = _mapping(raw, f"producer sequence[{index}]")
        instruction = _verify_fact(by_rva, item, image.image_base, f"producer sequence[{index}]")
        rva = instruction.address - image.image_base
        if previous_end is not None and rva != previous_end:
            raise NativeLuaRegistryHolderError("producer reviewed sequence is not contiguous")
        previous_end = rva + instruction.size


def _exact_scan(data: bytes, image: Any, facts: Mapping[str, Any], functions: Mapping[int, Mapping[str, Any]], expected_scan: Mapping[str, Any], x86: Any) -> dict[int, list[Any]]:
    decoder, _version = _decoder()
    decoder.detail = True
    targets = {_PRODUCER, *_CALLERS}
    decoded_targets: dict[int, list[Any]] = {}
    references = []
    ghidra_by_instruction = {_rva(edge["instruction_rva"], "Ghidra instruction"): edge for edge in _ghidra_edges(facts)}
    range_count = byte_count = instruction_count = 0
    target_va = image.image_base + _PRODUCER
    for owner, function in sorted(functions.items()):
        ranges = _array(function.get("ranges"), "atlas function ranges")
        for raw_span in ranges:
            span = _mapping(raw_span, "atlas function range")
            start = _rva(span.get("start_rva"), "atlas range start")
            size = span.get("size")
            instructions = _decode_range(data, image, start, size, decoder)
            range_count += 1
            byte_count += size
            instruction_count += len(instructions)
            if owner in targets:
                if len(ranges) != 1:
                    raise NativeLuaRegistryHolderError("sealed body has multiple ranges")
                decoded_targets[owner] = instructions
            for instruction in instructions:
                for operand_index, operand in enumerate(instruction.operands):
                    if operand.type == x86.X86_OP_IMM:
                        value, operand_class = int(operand.imm) & 0xFFFFFFFF, "immediate"
                    elif operand.type == x86.X86_OP_MEM and operand.mem.base == x86.X86_REG_INVALID and operand.mem.index == x86.X86_REG_INVALID:
                        value, operand_class = int(operand.mem.disp) & 0xFFFFFFFF, "absolute_memory"
                    else:
                        continue
                    if value != target_va:
                        continue
                    rva = instruction.address - image.image_base
                    encoded = bytes(instruction.bytes)
                    edge = ghidra_by_instruction.get(rva)
                    if operand_class != "immediate" or operand_index != 0 or len(encoded) != 5 or encoded[0] != 0xE8 or instruction.mnemonic != "call" or edge is None:
                        raise NativeLuaRegistryHolderError("producer target has a non-E8 or undeclared atlas reference")
                    references.append({
                        "instruction_rva": _hex(rva), "instruction_size": len(encoded),
                        "instruction_sha256": hashlib.sha256(encoded).hexdigest(),
                        "owner_entry_rva": _hex(owner), "owner_atlas_record_sha256": atlas_record_sha256(function),
                        "target_rva": _hex(_PRODUCER), "operand_class": operand_class,
                        "operand_index": operand_index, "call_form": "x86_relative_near_call_e8",
                        "ghidra_declared_direct_edge": edge,
                    })
    references.sort(key=lambda item: (_rva(item["instruction_rva"], "reference instruction"), item["operand_index"]))
    scope = _mapping(expected_scan.get("scope"), "expected scan scope")
    if references != expected_scan.get("references") or (range_count, byte_count, instruction_count) != (scope.get("atlas_body_range_count"), scope.get("decoded_bytes"), scope.get("decoded_instructions")) or len(functions) != scope.get("atlas_function_count") or set(decoded_targets) != targets:
        raise NativeLuaRegistryHolderError("complete all-operand atlas scan changed")
    return decoded_targets


def build_native_lua_registry_holder_local_use_release_census(executable: Path, inventory: Mapping[str, Any], facts: Mapping[str, Any], direct: Mapping[str, Any], terminal: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild the exact producer/caller census from the sealed executable."""
    try:
        receipt = validate_native_lua_direct_call_census(executable, direct, facts, inventory=inventory)
        if receipt.get("status") != "verified" or receipt.get("evidence_sha256") != _DIRECT:
            raise NativeLuaRegistryHolderError("direct prerequisite exact verification failed")
        expected = _expected_artifact(facts, direct, terminal)
        functions, _holder = _preflight(facts, direct, terminal)
        data, image, digest = _load_executable(executable)
        if digest != _EXE or image.image_base != _IMAGE_BASE:
            raise NativeLuaRegistryHolderError("executable identity changed")
        import capstone
        import capstone.x86_const as x86
        decoded = _exact_scan(data, image, facts, functions, _mapping(expected["whole_atlas_reference_scan"], "expected scan"), x86)
        _verify_producer(functions[_PRODUCER], decoded[_PRODUCER], image, capstone, x86, _mapping(expected["producer"], "expected producer"))
        for entry, raw_expected in zip(_CALLERS, expected["callers"]):
            _verify_caller(entry, functions[entry], decoded[entry], image, capstone, x86, _mapping(raw_expected, "expected caller"))
        if _load_executable(executable)[2] != digest:
            raise NativeLuaRegistryHolderError("executable changed during rebuild")
        validate_native_lua_registry_holder_local_use_release_census_structure(expected, facts, direct, terminal)
        return expected
    except (NativeLuaDirectCallError, OSError) as exc:
        raise NativeLuaRegistryHolderError(str(exc)) from exc


def validate_native_lua_registry_holder_local_use_release_census_structure(evidence: Mapping[str, Any], facts: Mapping[str, Any], direct: Mapping[str, Any], terminal: Mapping[str, Any]) -> dict[str, Any]:
    """Reconstruct and compare every stored field without loading the PE."""
    try:
        validate_native_lua_direct_call_structure(direct, facts)
    except NativeLuaDirectCallError as exc:
        raise NativeLuaRegistryHolderError(str(exc)) from exc
    _validate_json_tree(evidence, "registry-holder evidence")
    expected = _expected_artifact(facts, direct, terminal)
    _require_keys(evidence, {"schema_version", "analysis_kind", "build_identity", "prerequisites", "producer", "callers", "caller_clusters", "whole_atlas_reference_scan", "method", "summary"}, "registry-holder evidence")
    if _canonical_bytes(evidence) != _canonical_bytes(expected):
        raise NativeLuaRegistryHolderError("registry-holder evidence differs from the complete sealed structural replay")
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified", "build_identity": dict(expected["build_identity"]), "evidence_sha256": _canonical_sha256(expected), "summary": dict(expected["summary"])}


def validate_native_lua_registry_holder_local_use_release_census(executable: Path, evidence: Mapping[str, Any], inventory: Mapping[str, Any], facts: Mapping[str, Any], direct: Mapping[str, Any], terminal: Mapping[str, Any]) -> dict[str, Any]:
    rebuilt = build_native_lua_registry_holder_local_use_release_census(executable, inventory, facts, direct, terminal)
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaRegistryHolderError("evidence differs from exact rebuild")
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified", "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}


def encode_native_lua_registry_holder_local_use_release_census(value: Mapping[str, Any]) -> str:
    _validate_json_tree(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
