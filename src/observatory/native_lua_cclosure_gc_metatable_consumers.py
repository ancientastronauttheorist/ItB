"""Fail-closed census of five native ``__gc`` metatable publications.

The census deliberately joins the already-normalized immediate-closure,
setfield, table-setter, and key-provenance artifacts instead of recovering a
meaning from a literal name.  Four records are conditional bootstrap table
construction/store chains; the fifth is the raw ``luabind.function`` cache and
its one decoded direct consumer.  It is static evidence only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_lua_cclosure_setfield_publications import (
    _canonical_bytes, _canonical_sha256, _validate_json_tree,
    validate_native_lua_cclosure_setfield_publication_structure,
)
from src.observatory.native_lua_cclosure_table_setter_publications import (
    validate_native_lua_cclosure_table_setter_publication_structure,
)
from src.observatory.native_lua_cclosure_table_key_provenance import (
    validate_native_lua_cclosure_table_key_provenance_structure,
    validate_native_lua_cclosure_table_key_provenance_census, _enhanced_cfg,
)
from src.observatory.native_lua_cclosure_indirect_settable_publications import (
    _dominators, _entry_audit, _reachable,
)
from src.observatory.native_lua_direct_calls import _load_executable, _decoder
from src.observatory.native_lua_cclosure_setfield_publications import _atlas_functions, _decode_range
from src.observatory.native_function_accounting import atlas_record_sha256


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_cclosure_gc_metatable_consumers"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_BOOTSTRAP_ENTRY = "0x002e6900"
_HELPER_ENTRY = "0x002ea4e0"
_CONSUMER_ENTRY = "0x002ea820"
_GC_LITERAL = {
    "rva": "0x0043bf84", "text": "__gc", "byte_length_excluding_nul": 4,
    "nul_terminated_bytes_sha256": "6b3cc554d45a56ed43995cc307f4481a80680a993cd06b4ecfef70986c17997e",
    "section_name": ".rdata", "section_rva": "0x003d6000",
    "section_characteristics": "0x40000040", "section_writable": False,
}
_REGISTRY = (
    ("__luabind_classes", "0x0043bf18", "d9b53c957a9924e6583d6b1931dfc280dfff360c1a81042f6264b3d285d355fa", 24, "0x002e69f1", "0x002e6c30", "staged_indirect", "lua_settable", "0x002e6a03", "0x002e6a08", "0x002e6a30"),
    ("__luabind_class_id_map", "0x0042a86c", "9ff3832e39fd8abb51ed203f64ef8a5b9c518d8f72156c942d3b99e7a056cd61", 12, "0x002e6a8c", "0x002e6840", "setfield", "lua_setfield", "0x002e6a9d", "0x002e6aa9", "0x002e6ab5"),
    ("__luabind_cast_graph", "0x0043bf6c", "2c6601dedc983c9694b1c556740cbe937c23189effa02a9d6129090e336f8800", 4, "0x002e6af9", "0x002e6880", "setfield", "lua_setfield", "0x002e6b0a", "0x002e6b16", "0x002e6b22"),
    ("__luabind_class_map", "0x00420fa8", "79d79631d86216b5e947d500c8c800cb872d14004794f546f7099c0c4c451183", 12, "0x002e6b66", "0x002e68b0", "setfield", "lua_setfield", "0x002e6b77", "0x002e6b83", "0x002e6b8f"),
)
_FUNCTION_LITERAL = {
    "rva": "0x0043c570", "text": "luabind.function", "byte_length_excluding_nul": 16,
    "nul_terminated_bytes_sha256": "151c5227a1df5d9eb41c7bb391a21b8ba42be9fa4d6a6a96f95bd9e19a25d796",
    "section_name": ".rdata", "section_rva":"0x003d6000", "section_characteristics": "0x40000040", "section_writable": False,
}
_CORE = (
 ("bootstrap_caller",0x4CAA0,114,"f10f71d05330bede8c22353dfcdc846698199e1c73b75a838a4db4236bbfe84b","5e3a44ee9526a8f3ed7fb3e1a911277d83c050f2b53acda420a7f1db00cd6fd2",39,39,"61e11efac08e0c223b3ec60ea86224f6d78ce4f417dcbff9bfd9ba3e4eb7fcb2"),
 ("bootstrap_initializer",0x2E6900,811,"0723567170e15f7f36f25c97f15257ce9aabaaff57ace1bdf7778810a9158886","81d4b667a6b0d8f7d3fd30ae48dd64e5fb9da6d92317f8e4e86abf81539d3fbe",260,265,"3366932fbf51a111e3cbdb190c3dd0153b1ac504fef5ca97379cfdba00be2f6a"),
 ("initializer_join",0x2EBB30,89,"711a6653796f690359556b58fb1158b76d6a213a2a43c476299daf4c375a4c70","2770bd67ecee65db91bd3a69441b5e42d94b316ed20b974ef5094c770e9aa9b7",31,30,"10643e77d2331e634c8e6a875534731a7200aeb014ebdd430bbe589bcb788a23"),
 ("initializer_subtree_one",0x2EB990,202,"b9c8fea4e75e340f47cdda145ecc1cd44d06656fea9f783096e300aea63fb7eb","008cb2fe2fb3bacfe58aa0fb2e2d5f031ca9e3c12303b1391c3338dba43990a3",77,76,"68673d956494b254ff399cfb221719ae0361f95dd9ad99aaa66c4aa22b07e3a0"),
 ("initializer_subtree_two",0x2EBA60,202,"26ea09e0235e5ec6910a3de43d628f22f239dec5f46842e05a41fb2e862f670d","3a83a46e93535ea47e8bef370f9bf1884ecb9d0dc4be9e47e6127e1539ac18d9",77,76,"f63bcaf4b59e8a39b688839f30c683aa43625cfaf3ce493c57e6978fbc7c8e6c"),
 ("property_initializer",0x2EA2D0,245,"87e765ce2290b8320efb30cb7e110e8ae67783793b968aecd01827f6bd00d9c1","9bebfe870176e21574adce7ab56dc323785c19e0cdb73d03afc267a3edf84c1f",89,91,"eb72d84b7ad57f610bc595f6b68d52b5e4f221f64a6e1d44456bce3b3cad93d9"),
 ("raw_cache_helper",0x2EA4E0,136,"5f9a4aaec50ec8236da729ec16b25f59a5e606053a13468fda28d644052598f5","4ef06177a94fc20e9f22528fcd6202ba6853ba62cd93cdc695b0e45cd6a7e490",47,47,"05056dbad1b7f5e8c3d4d9645f961634f6da587917f9d6c8368d451b2f25bb40"),
 ("raw_cache_consumer",0x2EA820,125,"7ccb69986751a399d34584c44c0c52c68da088fe85a5e8a62743964cbcc4db0c","f325fd434c226798d70dcb82ce08868f9ea8589f52ee4c5ce63459d80124689b",47,46,"52b70b0a2dc41fb580b86bcf6cb26b8b4b4b2e52a3b4120ac01bcd4c43dadb48"),
)
_STAGED = {0x2E6900:(("ESI","lua_settable",0x2E69F7,(0x2E6A03,0x2E6A30,0x2E6AB5,0x2E6B22,0x2E6B8F,0x2E6BB0,0x2E6BD1)),("EBX","lua_pushstring",0x2E6989,(0x2E6995,0x2E69C8,0x2E69E8,0x2E6A38,0x2E6ABD,0x2E6B2A,0x2E6B97,0x2E6BB8,0x2E6BF7)),("ESI","lua_pushlightuserdata",0x2E6BD3,(0x2E6BDF,0x2E6BE3))),0x2EA4E0:(("EBX","lua_pushstring",0x2EA4E1,(0x2EA4F0,0x2EA529,0x2EA548)),),0x2EB990:(("EDI","lua_pushstring",0x2EB9A7,(0x2EB9B3,0x2EB9CF,0x2EB9F3,0x2EBA10,0x2EBA2D)),("EBX","lua_rawset",0x2EB9BE,(0x2EB9C7,0x2EB9E6,0x2EBA06,0x2EBA23,0x2EBA42)),("ESI","lua_pushcclosure",0x2EB9D9,(0x2EB9DF,0x2EB9FF,0x2EBA1C,0x2EBA3D))),0x2EBA60:(("EDI","lua_pushstring",0x2EBA77,(0x2EBA83,0x2EBA9F,0x2EBAC3,0x2EBAE0,0x2EBAFD)),("EBX","lua_rawset",0x2EBA8E,(0x2EBA97,0x2EBAB6,0x2EBAD6,0x2EBAF3,0x2EBB12)),("ESI","lua_pushcclosure",0x2EBAA9,(0x2EBAAF,0x2EBACF,0x2EBAEC,0x2EBB0D))),0x2EA2D0:(("ESI","lua_setfield",0x2EA2E9,(0x2EA2F7,0x2EA33B,0x2EA352,0x2EA366)),("EBX","lua_pushcclosure",0x2EA310,(0x2EA31E,0x2EA331,0x2EA345,0x2EA35C,0x2EA3AD)))}

# Every semantic assertion retained from the survey has an explicit decoded
# instruction witness.  ``meaning`` is deliberately declarative; exact rebuild
# checks the instruction text, bytes, adjacency, and branch operands below.
_POINTS = (
 ("bootstrap_state_zero_test",0x4CAAA,"cmp","dword ptr [esi + 0x10], 0",{"constant":0}),
 ("bootstrap_state_nonzero_branch",0x4CAAE,"jne","0x44cab9",{"target_rva":"0x0004cab9"}),
 ("bootstrap_state_argument",0x4CACF,"push","dword ptr [esi + 0x10]",{"source":"[esi+0x10]"}),
 ("bootstrap_state_transfer",0x4CAD8,"mov","ecx, dword ptr [esi + 0x10]",{"destination":"ecx","source":"[esi+0x10]"}),
 ("bootstrap_initializer_call",0x4CADE,"call","0x6e6900",{"target_rva":"0x002e6900"}),
 ("bootstrap_lookup_key",0x2E698F,"push","0x83bf18",{"literal_rva":"0x0043bf18"}),
 ("bootstrap_lookup_registry_selector",0x2E6997,"push","0xffffd8f0",{"index":-10000}),
 ("bootstrap_lookup_value_index",0x2E69A3,"push","-1",{"index":-1}),
 ("bootstrap_null_test",0x2E69BA,"test","esi, esi",{"register":"esi"}),
 ("bootstrap_nonzero_gate",0x2E69BC,"jne","0x6e6c19",{"target_rva":"0x002e6c19","fallthrough_rva":"0x002e69c2"}),
 ("classes_key",0x2E69C2,"push","0x83bf18",{"literal_rva":"0x0043bf18"}),
 ("classes_userdata_size",0x2E69CA,"push","0x18",{"value":24}),
 ("classes_createtable_nrec",0x2E69D3,"push","esi",{"value":0}),
 ("classes_createtable_narr",0x2E69D4,"push","esi",{"value":0}),
 ("classes_gc_key",0x2E69E2,"push","0x83bf84",{"literal_rva":"0x0043bf84"}),
 ("classes_gc_upvalues",0x2E69EA,"push","esi",{"value":0}),
 ("classes_gc_settable_index",0x2E6A00,"push","-3",{"index":-3}),
 ("classes_metatable_index",0x2E6A05,"push","-2",{"index":-2}),
 ("classes_registry_selector",0x2E6A2A,"push","0xffffd8f0",{"index":-10000}),
 ("class_id_key",0x2E6A32,"push","0x82a86c",{"literal_rva":"0x0042a86c"}),
 ("class_id_userdata_size",0x2E6A3A,"push","0xc",{"value":12}),
 ("class_id_createtable_nrec",0x2E6A76,"push","0",{"value":0}),
 ("class_id_createtable_narr",0x2E6A78,"push","0",{"value":0}),
 ("class_id_gc_upvalues",0x2E6A84,"push","0",{"value":0}),
 ("class_id_gc_key",0x2E6A95,"push","0x83bf84",{"literal_rva":"0x0043bf84"}),
 ("class_id_gc_setfield_index",0x2E6A9A,"push","-2",{"index":-2}),
 ("class_id_metatable_index",0x2E6AA6,"push","-2",{"index":-2}),
 ("class_id_registry_selector",0x2E6AAF,"push","0xffffd8f0",{"index":-10000}),
 ("cast_graph_key",0x2E6AB7,"push","0x83bf6c",{"literal_rva":"0x0043bf6c"}),
 ("cast_graph_userdata_size",0x2E6ABF,"push","4",{"value":4}),
 ("cast_graph_createtable_nrec",0x2E6AE3,"push","0",{"value":0}),
 ("cast_graph_createtable_narr",0x2E6AE5,"push","0",{"value":0}),
 ("cast_graph_gc_upvalues",0x2E6AF1,"push","0",{"value":0}),
 ("cast_graph_gc_key",0x2E6B02,"push","0x83bf84",{"literal_rva":"0x0043bf84"}),
 ("cast_graph_gc_setfield_index",0x2E6B07,"push","-2",{"index":-2}),
 ("cast_graph_metatable_index",0x2E6B13,"push","-2",{"index":-2}),
 ("cast_graph_registry_selector",0x2E6B1C,"push","0xffffd8f0",{"index":-10000}),
 ("class_map_key",0x2E6B24,"push","0x820fa8",{"literal_rva":"0x00420fa8"}),
 ("class_map_userdata_size",0x2E6B2C,"push","0xc",{"value":12}),
 ("class_map_createtable_nrec",0x2E6B50,"push","0",{"value":0}),
 ("class_map_createtable_narr",0x2E6B52,"push","0",{"value":0}),
 ("class_map_gc_upvalues",0x2E6B5E,"push","0",{"value":0}),
 ("class_map_gc_key",0x2E6B6F,"push","0x83bf84",{"literal_rva":"0x0043bf84"}),
 ("class_map_gc_setfield_index",0x2E6B74,"push","-2",{"index":-2}),
 ("class_map_metatable_index",0x2E6B80,"push","-2",{"index":-2}),
 ("class_map_registry_selector",0x2E6B89,"push","0xffffd8f0",{"index":-10000}),
 ("raw_cache_key_lookup",0x2EA4EA,"push","0x83c570",{"literal_rva":"0x0043c570"}),
 ("raw_lookup_registry_selector",0x2EA4F2,"push","0xffffd8f0",{"index":-10000}),
 ("raw_type_index",0x2EA4FE,"push","-1",{"index":-1}),
 ("raw_table_type",0x2EA50A,"cmp","eax, 5",{"value":5}),
 ("raw_hit_branch",0x2EA50D,"je","0x6ea565",{"target_rva":"0x002ea565","miss_rva":"0x002ea50f"}),
 ("raw_miss_settop_index",0x2EA50F,"push","-2",{"index":-2}),
 ("raw_createtable_nrec",0x2EA518,"push","0",{"value":0}),
 ("raw_createtable_narr",0x2EA51A,"push","0",{"value":0}),
 ("raw_gc_key",0x2EA523,"push","0x83bf84",{"literal_rva":"0x0043bf84"}),
 ("raw_gc_upvalues",0x2EA52B,"push","0",{"value":0}),
 ("raw_gc_set_index",0x2EA539,"push","-3",{"index":-3}),
 ("raw_cache_key_store",0x2EA542,"push","0x83c570",{"literal_rva":"0x0043c570"}),
 ("raw_duplicate_index",0x2EA54A,"push","-2",{"index":-2}),
 ("raw_store_registry_selector",0x2EA556,"push","0xffffd8f0",{"index":-10000}),
 ("consumer_userdata_size",0x2EA82C,"push","4",{"value":4}),
 ("consumer_metatable_index",0x2EA841,"push","-2",{"index":-2}),
 ("consumer_upvalue_count",0x2EA858,"push","2",{"value":2}),
 ("consumer_duplicate_index",0x2EA867,"push","-1",{"index":-1}),
 ("consumer_ref_registry_selector",0x2EA879,"push","0xffffd8f0",{"index":-10000}),
 ("consumer_cleanup_index",0x2EA885,"push","-2",{"index":-2}),
)

_ADJACENCIES = (
 ("bootstrap_state_gate",0x4CAAA,0x4CAB0),("bootstrap_openlibs_argument",0x4CACF,0x4CAD2),
 ("bootstrap_state_to_initializer",0x4CAD8,0x4CADE),
 ("bootstrap_lookup_key_call",0x2E698F,0x2E6995),("bootstrap_lookup_selector_call",0x2E6997,0x2E699D),("bootstrap_lookup_result_call",0x2E69A3,0x2E69A6),("bootstrap_gate",0x2E69BA,0x2E69BC),
 ("classes_key_call",0x2E69C2,0x2E69C8),("classes_userdata_call",0x2E69CA,0x2E69CD),("classes_createtable_call",0x2E69D3,0x2E69D9),("classes_closure_call",0x2E69E2,0x2E69F1),("classes_gc_setter",0x2E6A00,0x2E6A03),("classes_metatable_setter",0x2E6A05,0x2E6A08),("classes_registry_store",0x2E6A2A,0x2E6A30),
 ("class_id_key_call",0x2E6A32,0x2E6A38),("class_id_userdata_call",0x2E6A3A,0x2E6A3D),("class_id_createtable_call",0x2E6A76,0x2E6A7B),("class_id_closure_call",0x2E6A84,0x2E6A8C),("class_id_gc_setter",0x2E6A95,0x2E6A9D),("class_id_metatable_setter",0x2E6AA6,0x2E6AA9),("class_id_registry_store",0x2E6AAF,0x2E6AB5),
 ("cast_graph_key_call",0x2E6AB7,0x2E6ABD),("cast_graph_userdata_call",0x2E6ABF,0x2E6AC2),("cast_graph_createtable_call",0x2E6AE3,0x2E6AE8),("cast_graph_closure_call",0x2E6AF1,0x2E6AF9),("cast_graph_gc_setter",0x2E6B02,0x2E6B0A),("cast_graph_metatable_setter",0x2E6B13,0x2E6B16),("cast_graph_registry_store",0x2E6B1C,0x2E6B22),
 ("class_map_key_call",0x2E6B24,0x2E6B2A),("class_map_userdata_call",0x2E6B2C,0x2E6B2F),("class_map_createtable_call",0x2E6B50,0x2E6B55),("class_map_closure_call",0x2E6B5E,0x2E6B66),("class_map_gc_setter",0x2E6B6F,0x2E6B77),("class_map_metatable_setter",0x2E6B80,0x2E6B83),("class_map_registry_store",0x2E6B89,0x2E6B8F),
 ("raw_lookup",0x2EA4EA,0x2EA4F8),("raw_type_gate",0x2EA4FE,0x2EA50D),("raw_miss_pop",0x2EA50F,0x2EA512),("raw_create",0x2EA518,0x2EA51D),("raw_gc_closure",0x2EA523,0x2EA533),("raw_gc_store",0x2EA539,0x2EA53C),("raw_cache_duplicate",0x2EA542,0x2EA54D),("raw_cache_store",0x2EA556,0x2EA55C),
 ("consumer_userdata",0x2EA82C,0x2EA82F),("consumer_helper_to_metatable",0x2EA835,0x2EA846),("consumer_closure",0x2EA84C,0x2EA85E),("consumer_duplicate",0x2EA867,0x2EA873),("consumer_registry_ref",0x2EA879,0x2EA87F),("consumer_cleanup",0x2EA885,0x2EA88B),
)


class NativeLuaCClosureGcMetatableConsumersError(RuntimeError):
    """Raised for stale or malformed GC metatable evidence."""


def _source(document: Mapping[str, Any], kind: str) -> dict[str, str]:
    if document.get("analysis_kind") != kind:
        raise NativeLuaCClosureGcMetatableConsumersError("prerequisite analysis kind differs")
    return {"analysis_kind": kind, "canonical_sha256": _canonical_sha256(document)}


def _rva(value: str) -> int:
    if type(value) is not str or not value.startswith("0x"):
        raise NativeLuaCClosureGcMetatableConsumersError("RVA is malformed")
    return int(value, 16)


def _require_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise NativeLuaCClosureGcMetatableConsumersError(f"{label} fields differ")


def _calls(direct: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in direct.get("records", []):
        for call in record.get("direct_lua_import_calls", []):
            if call.get("call_rva") in result:
                raise NativeLuaCClosureGcMetatableConsumersError("direct Lua call RVAs repeat")
            result[call.get("call_rva")] = {"entry_rva": record.get("entry_rva"), **call}
    return result


def _semantic_point_records(data: bytes, image: Any) -> list[dict[str, Any]]:
    """Decode and normalize every instruction-backed semantic point."""
    decoder, _ = _decoder(); decoder.detail = True
    result = []
    for role, rva, mnemonic, op_str, meaning in _POINTS:
        off = image.rva_to_file_offset(rva)
        if off is None:
            raise NativeLuaCClosureGcMetatableConsumersError("semantic point is not file backed")
        decoded = list(decoder.disasm(data[off:off + 16], image.image_base + rva, count=2))
        if not decoded or decoded[0].mnemonic != mnemonic or decoded[0].op_str != op_str:
            raise NativeLuaCClosureGcMetatableConsumersError("semantic point instruction differs")
        instruction = decoded[0]; raw = bytes(instruction.bytes)
        result.append({
            "role": role, "instruction_rva": f"0x{rva:08x}",
            "instruction_size": len(raw), "instruction_sha256": hashlib.sha256(raw).hexdigest(),
            "mnemonic": instruction.mnemonic, "operand_text": instruction.op_str,
            "next_rva": f"0x{rva + len(raw):08x}", "meaning": dict(meaning),
        })
    return result


def _semantic_adjacency_records(data: bytes, image: Any) -> list[dict[str, Any]]:
    decoder, _ = _decoder(); decoder.detail = True; result=[]
    for role,start,end in _ADJACENCIES:
        off=image.rva_to_file_offset(start)
        if off is None: raise NativeLuaCClosureGcMetatableConsumersError("semantic adjacency is not file backed")
        decoded=[]
        for instruction in decoder.disasm(data[off:off+(end-start)+16],image.image_base+start):
            rva=instruction.address-image.image_base
            if rva>end: break
            decoded.append(instruction)
            if rva==end: break
        if not decoded or decoded[0].address-image.image_base!=start or decoded[-1].address-image.image_base!=end:
            raise NativeLuaCClosureGcMetatableConsumersError("semantic adjacency endpoints differ")
        for left,right in zip(decoded,decoded[1:]):
            if left.address+left.size!=right.address: raise NativeLuaCClosureGcMetatableConsumersError("semantic adjacency is not contiguous")
        result.append({"role":role,"start_rva":f"0x{start:08x}","end_rva":f"0x{end:08x}","instructions":[{"rva":f"0x{i.address-image.image_base:08x}","size":i.size,"sha256":hashlib.sha256(bytes(i.bytes)).hexdigest(),"mnemonic":i.mnemonic,"operand_text":i.op_str} for i in decoded]})
    return result


def _last_reaching_stage_definitions(
    instructions: list[Any], graph: Mapping[str, Any], image_base: int,
    register: str, stage_rvas: set[int], call_rvas: set[int], x86: Any,
) -> dict[int, list[int]]:
    """May-reaching definitions, treating x86 cdecl EBX/ESI/EDI as nonvolatile.

    A non-call instruction that writes the staged register kills the prior
    definition.  A stage instruction generates itself.  The fixed point over
    the exact decoded CFG proves the complete last-definition set at each call.
    """
    register_id = {"EBX": x86.X86_REG_EBX, "ESI": x86.X86_REG_ESI, "EDI": x86.X86_REG_EDI}[register]
    by_rva = {i.address - image_base: i for i in instructions}
    successors = {
        _rva(node["rva"]): [_rva(value) for value in node.get("successor_rvas", [])]
        for node in graph.get("nodes", [])
    }
    predecessors = {rva: [] for rva in by_rva}
    for source, targets in successors.items():
        for target in targets:
            if target in predecessors: predecessors[target].append(source)
    incoming = {rva: set() for rva in by_rva}; outgoing = {rva: set() for rva in by_rva}
    changed = True
    while changed:
        changed = False
        for rva in sorted(by_rva):
            new_in = set().union(*(outgoing[p] for p in predecessors[rva])) if predecessors[rva] else set()
            instruction = by_rva[rva]
            writes = register_id in instruction.regs_access()[1]
            if rva in stage_rvas:
                new_out = {rva}
            elif writes and instruction.mnemonic != "call":
                new_out = set()
            else:
                new_out = set(new_in)
            if new_in != incoming[rva] or new_out != outgoing[rva]:
                incoming[rva], outgoing[rva] = new_in, new_out
                changed = True
    return {rva: sorted(incoming[rva]) for rva in call_rvas}


def _core_body_records(facts: Mapping[str, Any], direct: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = _atlas_functions(facts); all_calls = _calls(direct); records=[]
    for role,entry,size,body,atlas,nodes,edges,cfg in _CORE:
        f=functions.get(entry)
        if f is None or f.get("thunk") is not False or f.get("body_size")!=size or f.get("body_sha256")!=body or atlas_record_sha256(f)!=atlas:
            raise NativeLuaCClosureGcMetatableConsumersError("core body or atlas identity differs")
        ranges=f.get("ranges")
        if not isinstance(ranges,list) or len(ranges)!=1 or _rva(ranges[0].get("start_rva"))!=entry or ranges[0].get("size")!=size:
            raise NativeLuaCClosureGcMetatableConsumersError("core range differs")
        entry_audit=None
        if entry in _STAGED:
            # Audit the entire contiguous function interior, which is a strict
            # superset of every stage-to-call proof region in this body.
            interior=set(range(entry+1,entry+size))
            atlas_entries,declared_entries=_entry_audit(facts,functions,entry,interior)
            if atlas_entries or declared_entries:
                raise NativeLuaCClosureGcMetatableConsumersError("staged proof body has an alternate modeled entry")
            entry_audit={"scope":"entire_contiguous_function_body_after_declared_entry","alternate_atlas_entry_rvas":atlas_entries,"declared_direct_call_entries":declared_entries,"sole_modeled_external_entry":True,"unmodeled_entry_premise":"indirect, exception, callback, or externally fabricated entries absent from atlas functions and Ghidra-declared direct-call facts are not claimed"}
        direct_rows=[]
        for rva, item in sorted((_rva(r),v) for r,v in all_calls.items() if v.get("entry_rva")==f"0x{entry:08x}"):
            if item.get("library")!="lua5.1.dll" or item.get("call_form")!="x86_absolute_iat_indirect_call_ff15": raise NativeLuaCClosureGcMetatableConsumersError("core direct Lua call form differs")
            direct_rows.append({k:item[k] for k in ("call_rva","import_name","iat_rva","call_form","instruction_size","instruction_sha256")})
        staged=[]
        for register,api,stage,calls in _STAGED.get(entry,()):
            staged.append({"register":register,"api":api,"stage_rva":f"0x{stage:08x}","calls":[{"call_rva":f"0x{x:08x}","last_reaching_stage_rvas":[f"0x{stage:08x}"]} for x in calls],"premise":"x86 cdecl preserves EBX, ESI, and EDI across calls"})
        audit=[]
        for low in range(8):
            opcode=f"ffd{low:x}"; call_rvas=[]
            for _register,_api,_stage,calls in _STAGED.get(entry,()):
                expected={"EBX":"ffd3","ESI":"ffd6","EDI":"ffd7"}[_register]
                if expected==opcode: call_rvas += [f"0x{x:08x}" for x in calls]
            audit.append({"opcode_hex":opcode,"call_rvas":call_rvas})
        records.append({"role":role,"entry_rva":f"0x{entry:08x}","atlas_record_sha256":atlas,"body_size":size,"body_sha256":body,"control_flow_graph_canonical_sha256":cfg,"control_flow_graph_node_count":nodes,"control_flow_graph_edge_count":edges,"direct_lua_calls":direct_rows,"staged_lua_calls":staged,"call_r32_audit":audit,"staged_proof_entry_audit":entry_audit})
    if sum(len(x["direct_lua_calls"]) for x in records)!=61 or sum(len(y["calls"]) for x in records for y in x["staged_lua_calls"])!=58:
        raise NativeLuaCClosureGcMetatableConsumersError("core Lua call partition count differs")
    return records


def _callback_identities(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    expected=((0x2E6C30,58,"50a7849dc71af7790dcdf28d1cb53735f9b19de05bf74c2dc06a536bcb5ca53c","f238fd47a54e68d8bcf2b78ef18ce27c0917f5afe55139cc5afb0f1273405ecc"),(0x2E6840,58,"e304e0e0e68f5266e6ad400d950b0ce39ca57ca6d517dc0c8e0873847683a087","e759873ebdebdd205a0cbdc758701883c7302c9cbbc767888bad174d14d5e669"),(0x2E6880,47,"fe3f015008893bb5486bb04ce326e64cc99533006cca817b51b34cd1bc0c9e29","adadbd50871d7733e9c5a18ac886c24b0fcc056db93e7639fcf5b0dd276d557b"),(0x2E68B0,71,"407e02b34fb9b785dfd04168bd31ba78b71b733ae96db40aee4fc9bc3b02fe82","78905d68fa790e8ed61f226c7a340071cb1cfd6cb3b772f03ba02fe2eef43821"),(0x2EA4B0,33,"8a33265accb6ace9d75f2b125d1d25f9b46b3d52a8835ef199ae607a906c5b35","ced5cc883286ebf3bdd45adbbd9c096f1a2a9ad97aa8bc98edf3f43f0bdc6423"))
    fs=_atlas_functions(facts); result=[]
    for entry,size,body,atlas in expected:
        f=fs.get(entry)
        if f is None or f.get("body_size")!=size or f.get("body_sha256")!=body or atlas_record_sha256(f)!=atlas: raise NativeLuaCClosureGcMetatableConsumersError("callback identity differs")
        result.append({"entry_rva":f"0x{entry:08x}","body_size":size,"body_sha256":body,"atlas_record_sha256":atlas})
    return result


def _bootstrap_stack_trace(source: str) -> list[dict[str, Any]]:
    rows = [
        {"operation":"push registry key","before":"B","after":"B,K"},
        {"operation":"lua_newuserdata(size)","before":"B,K","after":"B,K,U"},
        {"operation":"lua_createtable(0,0)","before":"B,K,U","after":"B,K,U,T"},
    ]
    if source == "staged_indirect":
        rows += [
            {"operation":"push __gc key","before":"B,K,U,T","after":"B,K,U,T,G"},
            {"operation":"lua_pushcclosure(callback,0)","before":"B,K,U,T,G","after":"B,K,U,T,G,C"},
            {"operation":"lua_settable(-3)","before":"B,K,U,T,G,C","after":"B,K,U,T"},
        ]
    else:
        rows += [
            {"operation":"lua_pushcclosure(callback,0)","before":"B,K,U,T","after":"B,K,U,T,C"},
            {"operation":"lua_setfield(-2,__gc)","before":"B,K,U,T,C","after":"B,K,U,T"},
        ]
    rows += [
        {"operation":"lua_setmetatable(-2)","before":"B,K,U,T","after":"B,K,U"},
        {"operation":"lua_settable(LUA_REGISTRYINDEX)","before":"B,K,U","after":"B"},
    ]
    return rows


def _initializer_stack_proof() -> dict[str, Any]:
    return {
        "entry_shape":"B,K,U", "join_shape":"B,K,U", "net_effect":0,
        "steps":[
            {"call_rva":"0x002ebb54","callee_entry_rva":"0x002eb990","before":"B,K,U","after":"B,K,U","reason":"created table is consumed by luaL_ref"},
            {"call_rva":"0x002ebb5e","callee_entry_rva":"0x002eba60","before":"B,K,U","after":"B,K,U","reason":"created table is consumed by luaL_ref"},
            {"call_rva":"0x002ebb68","callee_entry_rva":"0x002ea2d0","before":"B,K,U","after":"B,K,U,T","reason":"property initializer leaves one table"},
            {"call_rva":"0x002ebb73","callee_entry_rva":"luaL_ref","before":"B,K,U,T","after":"B,K,U","reason":"parent consumes the property table"},
        ],
        "premise":"normal returns only; no runtime execution or retained-reference validity is claimed",
    }


def _raw_stack_trace() -> dict[str, Any]:
    return {
        "entry_shape":"B,U", "join_shape":"B,U,T",
        "lookup":[
            {"operation":"push cache key","before":"B,U","after":"B,U,K"},
            {"operation":"lua_rawget(LUA_REGISTRYINDEX)","before":"B,U,K","after":"B,U,V"},
            {"operation":"lua_type(-1) and compare with 5","before":"B,U,V","after":"B,U,V"},
        ],
        "hit":[{"operation":"type-5 branch","before":"B,U,T","after":"B,U,T"}],
        "miss":[
            {"operation":"lua_settop(-2)","before":"B,U,V","after":"B,U"},
            {"operation":"lua_createtable(0,0)","before":"B,U","after":"B,U,T"},
            {"operation":"push __gc key","before":"B,U,T","after":"B,U,T,G"},
            {"operation":"lua_pushcclosure(callback,0)","before":"B,U,T,G","after":"B,U,T,G,C"},
            {"operation":"lua_rawset(-3)","before":"B,U,T,G,C","after":"B,U,T"},
            {"operation":"push cache key","before":"B,U,T","after":"B,U,T,K"},
            {"operation":"lua_pushvalue(-2)","before":"B,U,T,K","after":"B,U,T,K,T"},
            {"operation":"lua_rawset(LUA_REGISTRYINDEX)","before":"B,U,T,K,T","after":"B,U,T"},
        ],
        "consumer":[
            {"operation":"lua_setmetatable(-2)","before":"B,U,T","after":"B,U"},
            {"operation":"lua_pushlightuserdata(pointer)","before":"B,U","after":"B,U,P"},
            {"operation":"lua_pushcclosure(dynamic,2)","before":"B,U,P","after":"B,C"},
            {"operation":"lua_pushvalue(-1)","before":"B,C","after":"B,C,C"},
            {"operation":"luaL_ref(LUA_REGISTRYINDEX)","before":"B,C,C","after":"B,C"},
            {"operation":"lua_settop(-2)","before":"B,C","after":"B"},
        ],
    }


def _exact_core_bodies(data: bytes, image: Any, facts: Mapping[str, Any], direct: Mapping[str, Any]) -> None:
    import capstone
    import capstone.x86_const as x86
    decoder,_=_decoder(); decoder.detail=True; functions=_atlas_functions(facts)
    imports={x.get("name"):_rva(x.get("iat_rva")) for x in direct.get("lua_imports",[]) if isinstance(x,Mapping) and x.get("library")=="lua5.1.dll"}
    for expected, record in zip(_CORE,_core_body_records(facts,direct)):
        _role,entry,size,body,_atlas,nodes,edges,cfg=expected; f=functions[entry]; ranges=f.get("ranges")
        if not isinstance(ranges,list) or len(ranges)!=1 or _rva(ranges[0].get("start_rva"))!=entry or ranges[0].get("size")!=size: raise NativeLuaCClosureGcMetatableConsumersError("core range differs")
        off=image.rva_to_file_offset(entry)
        if off is None or hashlib.sha256(data[off:off+size]).hexdigest()!=body: raise NativeLuaCClosureGcMetatableConsumersError("core PE body bytes differ")
        ins=_decode_range(data,image,entry,size,decoder); graph=_enhanced_cfg(ins,image.image_base,(entry,size),capstone,x86); graph["caller_entry_rva"]=f"0x{entry:08x}"
        for node,instruction in zip(graph["nodes"],ins): node["writes_esi"]=x86.X86_REG_ESI in instruction.regs_access()[1]
        if _canonical_sha256(graph)!=cfg or graph["node_count"]!=nodes or graph["edge_count"]!=edges: raise NativeLuaCClosureGcMetatableConsumersError("core enhanced CFG differs")
        decoded={i.address-image.image_base:i for i in ins}
        cfg_edges={_rva(node["rva"]):{_rva(value) for value in node.get("successor_rvas",[])} for node in graph["nodes"]}
        reachable=_reachable(cfg_edges,entry); dominators=_dominators(cfg_edges,entry)
        for call in record["direct_lua_calls"]:
            i=decoded.get(_rva(call["call_rva"]));
            if i is None or hashlib.sha256(bytes(i.bytes)).hexdigest()!=call["instruction_sha256"]: raise NativeLuaCClosureGcMetatableConsumersError("core direct call bytes differ")
        expected_audit={item["opcode_hex"]:item["call_rvas"] for item in record["call_r32_audit"]}
        actual={f"ffd{x:x}":[] for x in range(8)}
        for i in ins:
            raw=bytes(i.bytes)
            if len(raw)==2 and raw[0]==0xff and 0xd0<=raw[1]<=0xd7: actual[raw.hex()].append(f"0x{i.address-image.image_base:08x}")
        if actual!=expected_audit: raise NativeLuaCClosureGcMetatableConsumersError("core all-eight call-r32 audit differs")
        for staged in record["staged_lua_calls"]:
            reg=staged["register"]; stage=_rva(staged["stage_rva"]); i=decoded.get(stage); iat=imports.get(staged["api"]); prefix={"EBX":b"\x8b\x1d","ESI":b"\x8b\x35","EDI":b"\x8b\x3d"}[reg]; opcode={"EBX":b"\xff\xd3","ESI":b"\xff\xd6","EDI":b"\xff\xd7"}[reg]
            if i is None or iat is None or bytes(i.bytes)!=prefix+(image.image_base+iat).to_bytes(4,"little"): raise NativeLuaCClosureGcMetatableConsumersError("staged Lua IAT provenance differs")
            calls={_rva(item["call_rva"]) for item in staged["calls"]}
            if any(decoded.get(r) is None or bytes(decoded[r].bytes)!=opcode for r in calls): raise NativeLuaCClosureGcMetatableConsumersError("staged Lua call partition differs")
            if stage not in reachable or any(call not in reachable or stage not in dominators.get(call,set()) for call in calls): raise NativeLuaCClosureGcMetatableConsumersError("staged Lua import load does not dominate every call")
            reaching=_last_reaching_stage_definitions(ins,graph,image.image_base,reg,{stage},calls,x86)
            expected_reaching={_rva(item["call_rva"]):[_rva(value) for value in item["last_reaching_stage_rvas"]] for item in staged["calls"]}
            if reaching != expected_reaching: raise NativeLuaCClosureGcMetatableConsumersError("staged Lua last-reaching definition differs")


def _call(calls: Mapping[str, dict[str, Any]], rva: str, api: str, entry: str) -> dict[str, Any]:
    item = calls.get(rva)
    if item is None or item.get("import_name") != api or item.get("entry_rva") != entry or item.get("library") != "lua5.1.dll":
        raise NativeLuaCClosureGcMetatableConsumersError("direct Lua API partition differs")
    return {key: item[key] for key in ("call_rva", "import_name", "iat_rva", "call_form", "instruction_size", "instruction_sha256")}


def _find(items: list[Mapping[str, Any]], call_rva: str) -> Mapping[str, Any]:
    found = [item for item in items if item.get("callback_call_rva") == call_rva]
    if len(found) != 1:
        raise NativeLuaCClosureGcMetatableConsumersError("publication partition differs")
    return found[0]


def _reference_rows(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions=_atlas_functions(facts)
    rows=((0x4CADE,0x4CAA0,0x2E6900,"1dda8f3c89f4ba237a6946aae07dd2b8fba7e96c391d30f7b4a590577aab1a86","bootstrap_direct_call"),(0x2E69EB,0x2E6900,0x2E6C30,"af5f277a5f2cdca7db5519be56370a7262b408308652c505efb52c3a6da9abfe","bootstrap_closure_producer"),(0x2E6A86,0x2E6900,0x2E6840,"fa6de6e57e8c52334b61840202b802998e69195d00c9193db49c6fcbf267de3d","bootstrap_closure_producer"),(0x2E6AF3,0x2E6900,0x2E6880,"5c672359fc90ca1e50ea49640b1b3c8af40443a3cd5b926e2a41658202c4faa8","bootstrap_closure_producer"),(0x2E6B60,0x2E6900,0x2E68B0,"88e2af70e98bddb923d768bd066028d99d2dd844d597bb3fcb2416a563ce36ae","bootstrap_closure_producer"),(0x2EA52D,0x2EA4E0,0x2EA4B0,"0c5bb0b932a478617cb71e8c1731d6bce10a0b8c099b440273202573476aa1c3","raw_cache_closure_producer"),(0x2EA839,0x2EA820,0x2EA4E0,"4d69f8c93aa015125f5a77cac8cd71130a8d48233d3e2d7c896fdf83e382448c","raw_helper_direct_consumer"))
    return [{"instruction_rva":f"0x{i:08x}","instruction_size":5,"instruction_sha256":sha,"owner_entry_rva":f"0x{o:08x}","owner_atlas_record_sha256":atlas_record_sha256(functions[o]),"target_rva":f"0x{t:08x}","operand_class":"immediate","operand_index":0,"use_class":use} for i,o,t,sha,use in rows]


def _subtree_edges(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions=_atlas_functions(facts); rows=((0x2E6A25,0x2E6900,0x2EBB30,"db05259bae8acf96acf037c5c93ab6c666dbce1ea3437178480098c0e35c963e"),(0x2EBB54,0x2EBB30,0x2EB990,"cb8c54bf5e58aa1dbf5ac8b381a66ac6a828dccd1803d353ca0cabddc4757214"),(0x2EBB5E,0x2EBB30,0x2EBA60,"7add4fa4fcac6eb0461992f73e07abbfda662741bc68e78e5cd59771b807b723"),(0x2EBB68,0x2EBB30,0x2EA2D0,"d6ea1f27958b2f3e3fdec9c9f9778c8ac80df1caba16b66b91e866fd134b7d90"))
    return [{"instruction_rva":f"0x{i:08x}","instruction_size":5,"instruction_sha256":sha,"source_entry_rva":f"0x{o:08x}","source_atlas_record_sha256":atlas_record_sha256(functions[o]),"target_entry_rva":f"0x{t:08x}"} for i,o,t,sha in rows]


def _exact_target_and_subtree_scans(data: bytes, image: Any, facts: Mapping[str, Any]) -> None:
    """Decode every atlas range; constants above are accepted only if rediscovered."""
    import capstone.x86_const as x86
    decoder,_=_decoder(); decoder.detail=True; functions=_atlas_functions(facts)
    targets={image.image_base+x:x for x in (0x2E6900,0x2E6C30,0x2E6840,0x2E6880,0x2E68B0,0x2EA4B0,0x2EA4E0)}; use={0x4CADE:"bootstrap_direct_call",0x2E69EB:"bootstrap_closure_producer",0x2E6A86:"bootstrap_closure_producer",0x2E6AF3:"bootstrap_closure_producer",0x2E6B60:"bootstrap_closure_producer",0x2EA52D:"raw_cache_closure_producer",0x2EA839:"raw_helper_direct_consumer"}; found=[]; ranges=total=count=0
    for owner,function in sorted(functions.items()):
        for span in function.get("ranges",[]):
            start=_rva(span.get("start_rva")); size=span.get("size")
            ins=_decode_range(data,image,start,size,decoder); ranges+=1; total+=size; count+=len(ins)
            for instruction in ins:
                for index,operand in enumerate(instruction.operands):
                    if operand.type==x86.X86_OP_IMM: value=int(operand.imm)&0xffffffff; kind="immediate"
                    elif operand.type==x86.X86_OP_MEM and operand.mem.base==x86.X86_REG_INVALID and operand.mem.index==x86.X86_REG_INVALID: value=int(operand.mem.disp)&0xffffffff; kind="absolute_memory"
                    else: continue
                    if value in targets:
                        rva=instruction.address-image.image_base
                        if rva not in use: raise NativeLuaCClosureGcMetatableConsumersError("central target reference is unclassified")
                        raw=bytes(instruction.bytes); found.append({"instruction_rva":f"0x{rva:08x}","instruction_size":len(raw),"instruction_sha256":hashlib.sha256(raw).hexdigest(),"owner_entry_rva":f"0x{owner:08x}","owner_atlas_record_sha256":atlas_record_sha256(function),"target_rva":f"0x{targets[value]:08x}","operand_class":kind,"operand_index":index,"use_class":use[rva]})
    if found!=_reference_rows(facts) or (ranges,total,count)!=(25490,3735718,1153814): raise NativeLuaCClosureGcMetatableConsumersError("full atlas target-reference scan differs")
    facts_edges={(row.get("instruction_rva"),row.get("source_entry_rva"),row.get("target_entry_rva") or row.get("target_rva")) for row in facts.get("ghidra_declared_direct_calls",[]) if isinstance(row,Mapping)}
    for edge in _subtree_edges(facts):
        if (edge["instruction_rva"],edge["source_entry_rva"],edge["target_entry_rva"]) not in facts_edges: raise NativeLuaCClosureGcMetatableConsumersError("initializer subtree Ghidra edge differs")
        rva=_rva(edge["instruction_rva"]); off=image.rva_to_file_offset(rva)
        if off is None or hashlib.sha256(data[off:off+edge["instruction_size"]]).hexdigest()!=edge["instruction_sha256"]: raise NativeLuaCClosureGcMetatableConsumersError("initializer subtree call bytes differ")


def _literal_from_pe(data: bytes, pe: Any, expected: Mapping[str, Any]) -> dict[str, Any]:
    rva = _rva(expected["rva"])
    try:
        text = pe._read_rva_c_string(rva, "literal", maximum_bytes=65)
        off = pe.rva_to_file_offset(rva)
        section = pe.section_for_offset(off)
    except Exception as exc:
        raise NativeLuaCClosureGcMetatableConsumersError("literal is not exact PE-backed ASCII") from exc
    raw = text.encode("ascii") + b"\0"
    result = dict(expected)
    result["text"] = text; result["nul_terminated_bytes_sha256"] = hashlib.sha256(raw).hexdigest()
    result["section_name"] = section.name; result["section_rva"] = f"0x{section.virtual_address:08x}"
    result["section_characteristics"] = f"0x{section.characteristics:08x}"; result["section_writable"] = bool(section.characteristics & 0x80000000)
    if result != dict(expected):
        raise NativeLuaCClosureGcMetatableConsumersError("literal bytes or section differ")
    return result


def _check_exact_build(executable: Path, facts: Mapping[str, Any]) -> tuple[bytes, Any]:
    data, pe, digest = _load_executable(executable)
    identity = facts.get("identity")
    if not isinstance(identity, Mapping) or digest != _EXE_SHA256 or identity.get("executable_sha256") != digest:
        raise NativeLuaCClosureGcMetatableConsumersError("executable identity differs")
    return data, pe


def _internal_edges(facts: Mapping[str, Any]) -> set[tuple[str, str]]:
    edges = set()
    for row in facts.get("ghidra_declared_direct_calls", []):
        source, target = row.get("instruction_rva"), row.get("target_rva")
        if isinstance(source, str) and isinstance(target, str): edges.add((source, target))
    return edges


def build_native_lua_cclosure_gc_metatable_consumers(
    executable: Path, direct_calls: Mapping[str, Any], callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any], direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any], table_key_provenance: Mapping[str, Any],
    program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the five-record census from an exact executable and prerequisites."""
    _validate_json_tree(inventory, "inventory"); _validate_json_tree(program_facts, "program facts")
    _check_exact_build(executable, program_facts)
    # The table-key verifier recursively checks the direct/callback/setfield and
    # indirect publication grammar; repeat narrower structures to retain the
    # composed prerequisite boundary under both PE and PE-free validation.
    validate_native_lua_cclosure_setfield_publication_structure(setfield_publications, direct_calls, callback_census, program_facts)
    validate_native_lua_cclosure_table_setter_publication_structure(direct_table_setter_publications, direct_calls, callback_census, setfield_publications, program_facts)
    validate_native_lua_cclosure_table_key_provenance_structure(table_key_provenance, direct_calls, callback_census, setfield_publications, direct_table_setter_publications, indirect_settable_publications, program_facts)
    receipt=validate_native_lua_cclosure_table_key_provenance_census(executable,table_key_provenance,direct_calls,callback_census,setfield_publications,direct_table_setter_publications,indirect_settable_publications,program_facts,inventory=inventory)
    data, pe = _check_exact_build(executable, program_facts)
    _exact_core_bodies(data, pe, program_facts, direct_calls)
    _exact_target_and_subtree_scans(data, pe, program_facts)
    calls = _calls(direct_calls)
    edges = _internal_edges(program_facts)
    if {("0x0004cade", _BOOTSTRAP_ENTRY), ("0x002ea839", _HELPER_ENTRY)} - edges:
        raise NativeLuaCClosureGcMetatableConsumersError("required direct caller edge is absent")
    key_pub = {item["callback_call_rva"]: item for item in table_key_provenance.get("publications", []) if item.get("key", {}).get("text") == "__gc"}
    setfield = {item["callback_call_rva"]: item for item in setfield_publications.get("publications", []) if item.get("key_text") == "__gc"}
    if set(key_pub) != {"0x002e69f1", "0x002ea533"} or set(setfield) != {"0x002e6a8c", "0x002e6af9", "0x002e6b66"}:
        raise NativeLuaCClosureGcMetatableConsumersError("five-site __gc partition differs")
    registry_literals = {}
    for text, rva, digest, *_rest in _REGISTRY:
        registry_literals[text] = _literal_from_pe(data, pe, {
            "rva": rva, "text": text, "byte_length_excluding_nul": len(text),
            "nul_terminated_bytes_sha256": digest, "section_name": ".rdata", "section_rva":"0x003d6000",
            "section_characteristics": "0x40000040", "section_writable": False,
        })
    records = []
    for text, rva, digest, size, site, callback, source, setter, setter_call, metatable_call, store_call in _REGISTRY:
        publication = key_pub[site] if source == "staged_indirect" else setfield[site]
        records.append({
            "record_kind": "conditional_bootstrap_registry_metatable", "registry_key": registry_literals[text],
            "userdata_size": size, "callback_call_rva": site, "callback_entry_rva": callback,
            "publication_source": source, "publication": publication,
            "metatable_consumer": _call(calls, metatable_call, "lua_setmetatable", _BOOTSTRAP_ENTRY),
            # The registry stores are intentionally retained as a mixed
            # direct/staged identity: the table-key prerequisite proves the
            # staged ESI form where present, while this artifact only joins the
            # exact final call boundary and API identity.
            "registry_store": {"call_rva": store_call, "import_name": "lua_settable", "call_form": "staged_esi", "stage_rva":"0x002e69f7"},
            "stack_trace": _bootstrap_stack_trace(source),
            "conditional_null_gate": {"test_rva": "0x002e69ba", "branch_rva": "0x002e69bc", "fallthrough_rva": "0x002e69c2", "nonzero_target_rva": "0x002e6c19"},
        })
    records.append({
        "record_kind": "raw_cached_function_metatable_consumer", "callback_call_rva": "0x002ea533", "callback_entry_rva": "0x002ea4b0",
        "publication_source": "direct", "publication": key_pub["0x002ea533"], "cache_key": _literal_from_pe(data, pe, _FUNCTION_LITERAL),
        "cache": {"lookup": _call(calls, "0x002ea4f8", "lua_rawget", _HELPER_ENTRY), "type": _call(calls, "0x002ea501", "lua_type", _HELPER_ENTRY), "table_type_constant": 5, "miss_settop": _call(calls, "0x002ea512", "lua_settop", _HELPER_ENTRY), "store": _call(calls, "0x002ea55c", "lua_rawset", _HELPER_ENTRY), "raw_access": True},
        "consumer": {"direct_call_rva": "0x002ea839", "callee_entry_rva": _HELPER_ENTRY, "userdata": _call(calls, "0x002ea82f", "lua_newuserdata", _CONSUMER_ENTRY), "userdata_size": 4, "between_helper_and_next_lua_call": [{"rva":"0x002ea83e","size":3,"sha256":"849f48aadaada9f124f163691d4edb662630d9ee338916176879c197c9b4d1e1"},{"rva":"0x002ea841","size":2,"sha256":"f5bf58accfc3eb20bbebd7022558c76ae4acb85e17018c9933271d097da5bbf8"},{"rva":"0x002ea843","size":1,"sha256":"8de0b3c47f112c59745f717a626932264c422a7563954872e237b223af4ad643"},{"rva":"0x002ea844","size":2,"sha256":"6eaef7f6b7489043a110404072ca5eb0c2cbdd27c1bf1a303b372af0f6328374"}], "next_lua_api_call": True, "setmetatable": _call(calls, "0x002ea846", "lua_setmetatable", _CONSUMER_ENTRY), "closure": _call(calls, "0x002ea85e", "lua_pushcclosure", _CONSUMER_ENTRY), "upvalue_count": 2, "duplicate": _call(calls, "0x002ea873", "lua_pushvalue", _CONSUMER_ENTRY), "registry_ref": _call(calls, "0x002ea87f", "luaL_ref", _CONSUMER_ENTRY), "cleanup": _call(calls, "0x002ea88b", "lua_settop", _CONSUMER_ENTRY)},
        "stack_trace": _raw_stack_trace(),
    })
    result = {
        "schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(program_facts["identity"]),
        "atlas": _source(program_facts, "pe_ghidra_program_facts"),
        "direct_call_census": _source(direct_calls, "pe_native_lua_direct_import_call_census"),
        "callback_census": _source(callback_census, "pe_native_lua_immediate_cclosure_callback_census"),
        "setfield_publication_census": _source(setfield_publications, "pe_native_lua_immediate_cclosure_setfield_publication_census"),
        "direct_table_setter_publication_census": _source(direct_table_setter_publications, "pe_native_lua_immediate_cclosure_direct_table_setter_publication_census"),
        "indirect_settable_publication_census": _source(indirect_settable_publications, "pe_native_lua_immediate_cclosure_indirect_settable_publication_census"),
        "table_key_provenance_census": _source(table_key_provenance, "pe_native_lua_cclosure_table_key_provenance_census"),
        "shared_gc_literal": _literal_from_pe(data, pe, _GC_LITERAL),
        "semantic_points": _semantic_point_records(data, pe),
        "semantic_adjacencies": _semantic_adjacency_records(data, pe),
        "source_bodies": _core_body_records(program_facts, direct_calls),
        "callback_identities": _callback_identities(program_facts),
        "table_key_provenance_receipt": {"analysis_kind":receipt["analysis_kind"],"status":receipt["status"],"evidence_sha256":receipt["evidence_sha256"]},
        "target_reference_scan": {"target_rvas":["0x002e6900","0x002e6c30","0x002e6840","0x002e6880","0x002e68b0","0x002ea4b0","0x002ea4e0"],"scope":{"atlas_function_count":len(_atlas_functions(program_facts)),"atlas_range_count":25490,"decoded_byte_count":3735718,"decoded_instruction_count":1153814,"all_declared_ranges_decoded":True,"operand_classes":["absolute_memory","immediate"]},"references":_reference_rows(program_facts)},
        "initializer_subtree": {"direct_edges":_subtree_edges(program_facts),"stack_proof":_initializer_stack_proof()},
        "bootstrap_caller": {"entry_rva": "0x0004caa0", "luaL_newstate_call_rva": "0x0004cab0", "luaL_openlibs_call_rva": "0x0004cad2", "state_transfer": {"rva": "0x0004cad8", "size": 3, "sha256": "dffe399673ee631e67b2044c87b339a6ecc9e93e21e2e3a569c6791989f64e69", "register": "ecx", "source": "[esi+0x10]"}, "cdecl_cleanup_before_call": {"rva":"0x0004cadb","size":3,"sha256":"2fd40b052ecdb09c0b4b6c5745e92654c7f03e8bf0bf726ef470fa45fe5b20d0"}, "direct_call_rva": "0x0004cade", "callee_entry_rva": _BOOTSTRAP_ENTRY},
        "helper_consumer_call_boundary": {"caller_entry_rva": _CONSUMER_ENTRY, "state_transfer": {"rva":"0x002ea835","size":2,"sha256":"4b114be14a1901cce6f7a0f927756e414400942123cd365bfe5043a4b118045f","register":"ecx","source":"ebx"}, "userdata_pointer_save": {"rva":"0x002ea837","size":2,"sha256":"234f8f2031d456cbb66a9a4907f797ba3e97e213bae11b112af85390c778cb8c","register":"esi","source":"eax"}, "direct_call_rva":"0x002ea839","callee_entry_rva":_HELPER_ENTRY},
        "records": records,
        "method": {"publication_partition": "exactly five of the ten normalized immediate-C-closure setter publications are keyed by __gc", "partition_scope": "this excludes other native construction grammars, including staged rawset writes in initializer helpers 0x002eb990 and 0x002eba60", "cache_boundary": "the four asserted bootstrap chains use the common lua_gettable lookup and their four lua_settable registry stores; only the fifth asserted cache uses lua_rawget/lua_rawset", "staged_call_premise":"x86 cdecl preserves EBX, ESI, and EDI across calls; exact CFG dominance and reaching-definition replay prove every staged call's last stage; atlas entries and Ghidra-declared direct targets prove the function entry is the sole modeled external entry", "not_claimed": ["runtime execution, reachability, persistence, or lifetime", "registry-entry absence, dynamic type beyond the explicit type-5 hit test, or later mutation", "runtime __gc dispatch, finalization, destructor/free semantics, ownership, allocation origin, or source-level identity", "all native __gc construction, dynamically keyed code, Lua code, or completeness beyond the finite normalized immediate-C-closure setter and table-key provenance universes", "indirect, exception, callback, or externally fabricated entries absent from atlas functions and Ghidra-declared direct-call facts"]},
        "summary": {"gc_publication_consumer_records": 5, "conditional_bootstrap_records": 4, "raw_cache_records": 1, "setfield_publications": 3, "table_setter_publications": 2, "bootstrap_registry_stores": 4, "direct_helper_consumers": 1, "source_body_count":8,"source_body_bytes":1924,"source_cfg_node_count":667,"source_cfg_edge_count":670,"direct_lua_call_count":61,"staged_lua_call_count":58,"semantic_point_count":len(_POINTS),"semantic_adjacency_count":len(_ADJACENCIES),"target_reference_count":7,"initializer_subtree_edge_count":4,"callback_identity_count":5,"schema_violations": 0},
    }
    validate_native_lua_cclosure_gc_metatable_consumers_structure(result, direct_calls, callback_census, setfield_publications, direct_table_setter_publications, indirect_settable_publications, table_key_provenance, program_facts)
    return result


def validate_native_lua_cclosure_gc_metatable_consumers_structure(
    evidence: Mapping[str, Any], direct_calls: Mapping[str, Any], callback_census: Mapping[str, Any], setfield_publications: Mapping[str, Any], direct_table_setter_publications: Mapping[str, Any], indirect_settable_publications: Mapping[str, Any], table_key_provenance: Mapping[str, Any], program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """PE-free replay of the retained partitions, paths, literals, and claims."""
    _validate_json_tree(evidence, "evidence")
    _require_keys(evidence, {"schema_version","analysis_kind","build_identity","atlas","direct_call_census","callback_census","setfield_publication_census","direct_table_setter_publication_census","indirect_settable_publication_census","table_key_provenance_census","shared_gc_literal","semantic_points","semantic_adjacencies","source_bodies","callback_identities","table_key_provenance_receipt","target_reference_scan","initializer_subtree","bootstrap_caller","helper_consumer_call_boundary","records","method","summary"}, "top-level evidence")
    validate_native_lua_cclosure_setfield_publication_structure(setfield_publications, direct_calls, callback_census, program_facts)
    validate_native_lua_cclosure_table_setter_publication_structure(direct_table_setter_publications, direct_calls, callback_census, setfield_publications, program_facts)
    validate_native_lua_cclosure_table_key_provenance_structure(table_key_provenance, direct_calls, callback_census, setfield_publications, direct_table_setter_publications, indirect_settable_publications, program_facts)
    expected_sources = {
        "atlas": _source(program_facts, "pe_ghidra_program_facts"), "direct_call_census": _source(direct_calls, "pe_native_lua_direct_import_call_census"), "callback_census": _source(callback_census, "pe_native_lua_immediate_cclosure_callback_census"), "setfield_publication_census": _source(setfield_publications, "pe_native_lua_immediate_cclosure_setfield_publication_census"), "direct_table_setter_publication_census": _source(direct_table_setter_publications, "pe_native_lua_immediate_cclosure_direct_table_setter_publication_census"), "indirect_settable_publication_census": _source(indirect_settable_publications, "pe_native_lua_immediate_cclosure_indirect_settable_publication_census"), "table_key_provenance_census": _source(table_key_provenance, "pe_native_lua_cclosure_table_key_provenance_census")}
    if evidence.get("schema_version") != SCHEMA_VERSION or evidence.get("analysis_kind") != ANALYSIS_KIND or evidence.get("build_identity") != program_facts.get("identity") or any(evidence.get(k) != v for k,v in expected_sources.items()):
        raise NativeLuaCClosureGcMetatableConsumersError("artifact identity or prerequisite canonical digest differs")
    if evidence.get("shared_gc_literal") != _GC_LITERAL:
        raise NativeLuaCClosureGcMetatableConsumersError("shared __gc literal differs")
    expected_receipt={"analysis_kind":"pe_native_lua_cclosure_table_key_provenance_census_verification","status":"verified","evidence_sha256":_canonical_sha256(table_key_provenance)}
    if evidence.get("table_key_provenance_receipt") != expected_receipt: raise NativeLuaCClosureGcMetatableConsumersError("table-key exact receipt differs")
    expected_scan={"target_rvas":["0x002e6900","0x002e6c30","0x002e6840","0x002e6880","0x002e68b0","0x002ea4b0","0x002ea4e0"],"scope":{"atlas_function_count":len(_atlas_functions(program_facts)),"atlas_range_count":25490,"decoded_byte_count":3735718,"decoded_instruction_count":1153814,"all_declared_ranges_decoded":True,"operand_classes":["absolute_memory","immediate"]},"references":_reference_rows(program_facts)}
    if evidence.get("target_reference_scan") != expected_scan or evidence.get("initializer_subtree") != {"direct_edges":_subtree_edges(program_facts),"stack_proof":_initializer_stack_proof()}: raise NativeLuaCClosureGcMetatableConsumersError("target scan or initializer subtree differs")
    points=evidence.get("semantic_points")
    if not isinstance(points,list) or len(points)!=len(_POINTS): raise NativeLuaCClosureGcMetatableConsumersError("semantic point partition differs")
    for point,spec in zip(points,_POINTS):
        role,rva,mnemonic,operand,meaning=spec
        _require_keys(point,{"role","instruction_rva","instruction_size","instruction_sha256","mnemonic","operand_text","next_rva","meaning"},"semantic point")
        if point.get("role")!=role or point.get("instruction_rva")!=f"0x{rva:08x}" or point.get("mnemonic")!=mnemonic or point.get("operand_text")!=operand or point.get("meaning")!=meaning or point.get("next_rva")!=f"0x{rva+point.get('instruction_size',0):08x}" or type(point.get("instruction_size")) is not int or point["instruction_size"]<=0 or type(point.get("instruction_sha256")) is not str or len(point["instruction_sha256"])!=64:
            raise NativeLuaCClosureGcMetatableConsumersError("semantic point grammar differs")
    adjacencies=evidence.get("semantic_adjacencies")
    if not isinstance(adjacencies,list) or len(adjacencies)!=len(_ADJACENCIES): raise NativeLuaCClosureGcMetatableConsumersError("semantic adjacency partition differs")
    for row,(role,start,end) in zip(adjacencies,_ADJACENCIES):
        _require_keys(row,{"role","start_rva","end_rva","instructions"},"semantic adjacency")
        instructions=row.get("instructions")
        if row.get("role")!=role or row.get("start_rva")!=f"0x{start:08x}" or row.get("end_rva")!=f"0x{end:08x}" or not isinstance(instructions,list) or not instructions or instructions[0].get("rva")!=f"0x{start:08x}" or instructions[-1].get("rva")!=f"0x{end:08x}": raise NativeLuaCClosureGcMetatableConsumersError("semantic adjacency grammar differs")
        for instruction in instructions: _require_keys(instruction,{"rva","size","sha256","mnemonic","operand_text"},"semantic adjacency instruction")
    adjacency_instructions={instruction["rva"]:instruction for row in adjacencies for instruction in row["instructions"]}
    for point in points:
        witness=adjacency_instructions.get(point["instruction_rva"])
        if witness is None or witness!={"rva":point["instruction_rva"],"size":point["instruction_size"],"sha256":point["instruction_sha256"],"mnemonic":point["mnemonic"],"operand_text":point["operand_text"]}:
            raise NativeLuaCClosureGcMetatableConsumersError("semantic point/adjacency replay differs")
    key_pub = {
        item["callback_call_rva"]: item
        for item in table_key_provenance.get("publications", [])
        if item.get("key", {}).get("text") == "__gc"
    }
    setfield = {
        item["callback_call_rva"]: item
        for item in setfield_publications.get("publications", [])
        if item.get("key_text") == "__gc"
    }
    if set(key_pub) != {"0x002e69f1", "0x002ea533"} or set(setfield) != {
        "0x002e6a8c", "0x002e6af9", "0x002e6b66"
    }:
        raise NativeLuaCClosureGcMetatableConsumersError(
            "five-site __gc partition differs"
        )
    calls=_calls(direct_calls)
    if evidence.get("bootstrap_caller") != {"entry_rva":"0x0004caa0","luaL_newstate_call_rva":"0x0004cab0","luaL_openlibs_call_rva":"0x0004cad2","state_transfer":{"rva":"0x0004cad8","size":3,"sha256":"dffe399673ee631e67b2044c87b339a6ecc9e93e21e2e3a569c6791989f64e69","register":"ecx","source":"[esi+0x10]"},"cdecl_cleanup_before_call":{"rva":"0x0004cadb","size":3,"sha256":"2fd40b052ecdb09c0b4b6c5745e92654c7f03e8bf0bf726ef470fa45fe5b20d0"},"direct_call_rva":"0x0004cade","callee_entry_rva":_BOOTSTRAP_ENTRY}:
        raise NativeLuaCClosureGcMetatableConsumersError("bootstrap caller/state transfer differs")
    if evidence.get("helper_consumer_call_boundary") != {"caller_entry_rva":_CONSUMER_ENTRY,"state_transfer":{"rva":"0x002ea835","size":2,"sha256":"4b114be14a1901cce6f7a0f927756e414400942123cd365bfe5043a4b118045f","register":"ecx","source":"ebx"},"userdata_pointer_save":{"rva":"0x002ea837","size":2,"sha256":"234f8f2031d456cbb66a9a4907f797ba3e97e213bae11b112af85390c778cb8c","register":"esi","source":"eax"},"direct_call_rva":"0x002ea839","callee_entry_rva":_HELPER_ENTRY}:
        raise NativeLuaCClosureGcMetatableConsumersError("helper consumer/state transfer differs")
    rows = evidence.get("records")
    if not isinstance(rows, list) or len(rows) != 5:
        raise NativeLuaCClosureGcMetatableConsumersError("complete five-record partition differs")
    bootstrap, raw = rows[:4], rows[4]
    if [r.get("registry_key",{}).get("text") for r in bootstrap] != [x[0] for x in _REGISTRY]:
        raise NativeLuaCClosureGcMetatableConsumersError("registry key order differs")
    for row, exp in zip(bootstrap, _REGISTRY):
        text,rva,digest,size,site,callback,source,setter,setter_call,meta,store=exp
        _require_keys(row,{"record_kind","registry_key","userdata_size","callback_call_rva","callback_entry_rva","publication_source","publication","metatable_consumer","registry_store","stack_trace","conditional_null_gate"},"bootstrap record")
        if row.get("record_kind") != "conditional_bootstrap_registry_metatable" or row.get("userdata_size") != size or row.get("callback_call_rva") != site or row.get("callback_entry_rva") != callback or row.get("publication_source") != source or row.get("registry_key") != {"rva":rva,"text":text,"byte_length_excluding_nul":len(text),"nul_terminated_bytes_sha256":digest,"section_name":".rdata","section_rva":"0x003d6000","section_characteristics":"0x40000040","section_writable":False} or row.get("stack_trace") != _bootstrap_stack_trace(source) or row.get("conditional_null_gate") != {"test_rva":"0x002e69ba","branch_rva":"0x002e69bc","fallthrough_rva":"0x002e69c2","nonzero_target_rva":"0x002e6c19"}:
            raise NativeLuaCClosureGcMetatableConsumersError("bootstrap grammar differs")
        if row.get("metatable_consumer") != _call(calls,meta,"lua_setmetatable",_BOOTSTRAP_ENTRY) or row.get("registry_store") != {"call_rva":store,"import_name":"lua_settable","call_form":"staged_esi","stage_rva":"0x002e69f7"}:
            raise NativeLuaCClosureGcMetatableConsumersError("bootstrap consumer/store order differs")
        expected_publication=key_pub[site] if source=="staged_indirect" else setfield[site]
        if row.get("publication") != expected_publication or row.get("publication",{}).get("setter_call_rva") != setter_call or row.get("publication",{}).get("callback_call_rva") != site:
            raise NativeLuaCClosureGcMetatableConsumersError("publication join differs")
    between=[{"rva":"0x002ea83e","size":3,"sha256":"849f48aadaada9f124f163691d4edb662630d9ee338916176879c197c9b4d1e1"},{"rva":"0x002ea841","size":2,"sha256":"f5bf58accfc3eb20bbebd7022558c76ae4acb85e17018c9933271d097da5bbf8"},{"rva":"0x002ea843","size":1,"sha256":"8de0b3c47f112c59745f717a626932264c422a7563954872e237b223af4ad643"},{"rva":"0x002ea844","size":2,"sha256":"6eaef7f6b7489043a110404072ca5eb0c2cbdd27c1bf1a303b372af0f6328374"}]
    _require_keys(raw,{"record_kind","callback_call_rva","callback_entry_rva","publication_source","publication","cache_key","cache","consumer","stack_trace"},"raw record")
    _require_keys(raw.get("cache"),{"lookup","type","table_type_constant","miss_settop","store","raw_access"},"raw cache")
    _require_keys(raw.get("consumer"),{"direct_call_rva","callee_entry_rva","userdata","userdata_size","between_helper_and_next_lua_call","next_lua_api_call","setmetatable","closure","upvalue_count","duplicate","registry_ref","cleanup"},"raw consumer")
    if raw.get("record_kind") != "raw_cached_function_metatable_consumer" or raw.get("callback_call_rva") != "0x002ea533" or raw.get("callback_entry_rva") != "0x002ea4b0" or raw.get("publication_source")!="direct" or raw.get("publication") != key_pub["0x002ea533"] or raw.get("cache_key") != _FUNCTION_LITERAL or raw.get("cache",{}).get("raw_access") is not True or raw.get("cache",{}).get("table_type_constant") != 5 or raw.get("consumer",{}).get("direct_call_rva") != "0x002ea839" or raw.get("consumer",{}).get("callee_entry_rva") != _HELPER_ENTRY or raw.get("consumer",{}).get("userdata_size") != 4 or raw.get("consumer",{}).get("upvalue_count") != 2 or raw.get("consumer",{}).get("between_helper_and_next_lua_call") != between or raw.get("consumer",{}).get("next_lua_api_call") is not True or raw.get("stack_trace") != _raw_stack_trace():
        raise NativeLuaCClosureGcMetatableConsumersError("raw cache/helper consumer grammar differs")
    for field, api, rva in (("lookup","lua_rawget","0x002ea4f8"),("type","lua_type","0x002ea501"),("miss_settop","lua_settop","0x002ea512"),("store","lua_rawset","0x002ea55c")):
        if raw["cache"].get(field) != _call(calls,rva,api,_HELPER_ENTRY): raise NativeLuaCClosureGcMetatableConsumersError("raw cache API classification differs")
    for field,api,rva in (("userdata","lua_newuserdata","0x002ea82f"),("setmetatable","lua_setmetatable","0x002ea846"),("closure","lua_pushcclosure","0x002ea85e"),("duplicate","lua_pushvalue","0x002ea873"),("registry_ref","luaL_ref","0x002ea87f"),("cleanup","lua_settop","0x002ea88b")):
        if raw["consumer"].get(field)!=_call(calls,rva,api,_CONSUMER_ENTRY): raise NativeLuaCClosureGcMetatableConsumersError("raw consumer API classification differs")
    bodies=_core_body_records(program_facts,direct_calls)
    if evidence.get("source_bodies") != bodies: raise NativeLuaCClosureGcMetatableConsumersError("core body/direct/staged partition differs")
    if evidence.get("callback_identities") != _callback_identities(program_facts): raise NativeLuaCClosureGcMetatableConsumersError("callback identity partition differs")
    expected_method={"publication_partition":"exactly five of the ten normalized immediate-C-closure setter publications are keyed by __gc","partition_scope":"this excludes other native construction grammars, including staged rawset writes in initializer helpers 0x002eb990 and 0x002eba60","cache_boundary":"the four asserted bootstrap chains use the common lua_gettable lookup and their four lua_settable registry stores; only the fifth asserted cache uses lua_rawget/lua_rawset","staged_call_premise":"x86 cdecl preserves EBX, ESI, and EDI across calls; exact CFG dominance and reaching-definition replay prove every staged call's last stage; atlas entries and Ghidra-declared direct targets prove the function entry is the sole modeled external entry","not_claimed":["runtime execution, reachability, persistence, or lifetime","registry-entry absence, dynamic type beyond the explicit type-5 hit test, or later mutation","runtime __gc dispatch, finalization, destructor/free semantics, ownership, allocation origin, or source-level identity","all native __gc construction, dynamically keyed code, Lua code, or completeness beyond the finite normalized immediate-C-closure setter and table-key provenance universes","indirect, exception, callback, or externally fabricated entries absent from atlas functions and Ghidra-declared direct-call facts"]}
    if evidence.get("method")!=expected_method: raise NativeLuaCClosureGcMetatableConsumersError("method or nonclaims differ")
    expected_summary={"gc_publication_consumer_records":5,"conditional_bootstrap_records":4,"raw_cache_records":1,"setfield_publications":3,"table_setter_publications":2,"bootstrap_registry_stores":4,"direct_helper_consumers":1,"source_body_count":len(bodies),"source_body_bytes":sum(x["body_size"] for x in bodies),"source_cfg_node_count":sum(x["control_flow_graph_node_count"] for x in bodies),"source_cfg_edge_count":sum(x["control_flow_graph_edge_count"] for x in bodies),"direct_lua_call_count":sum(len(x["direct_lua_calls"]) for x in bodies),"staged_lua_call_count":sum(len(y["calls"]) for x in bodies for y in x["staged_lua_calls"]),"semantic_point_count":len(_POINTS),"semantic_adjacency_count":len(_ADJACENCIES),"target_reference_count":len(expected_scan["references"]),"initializer_subtree_edge_count":len(_subtree_edges(program_facts)),"callback_identity_count":len(_callback_identities(program_facts)),"schema_violations":0}
    if evidence.get("summary") != expected_summary: raise NativeLuaCClosureGcMetatableConsumersError("summary differs")
    return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(program_facts["identity"]),"evidence_sha256":_canonical_sha256(evidence),"summary":expected_summary}


def validate_native_lua_cclosure_gc_metatable_consumers(
    executable: Path, evidence: Mapping[str, Any], direct_calls: Mapping[str, Any], callback_census: Mapping[str, Any], setfield_publications: Mapping[str, Any], direct_table_setter_publications: Mapping[str, Any], indirect_settable_publications: Mapping[str, Any], table_key_provenance: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any],
) -> dict[str, Any]:
    rebuilt=build_native_lua_cclosure_gc_metatable_consumers(executable,direct_calls,callback_census,setfield_publications,direct_table_setter_publications,indirect_settable_publications,table_key_provenance,program_facts,inventory=inventory)
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt): raise NativeLuaCClosureGcMetatableConsumersError("evidence differs from exact rebuild")
    return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}


def encode_native_lua_cclosure_gc_metatable_consumers(value: Mapping[str, Any]) -> str:
    _validate_json_tree(value)
    return json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+"\n"
