"""Fail-closed static receipt for the six-byte 0x0039cb98 FF25 thunk.

The KERNEL32 import row is PE metadata only.  This module deliberately makes
no claim about loader resolution, runtime execution, target behavior, or a
normal return.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _decode_range,
    _exact_keys,
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_class_factory_chain import (
    _validated_graphs,
    _with_edi_writes,
)
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError,
    _REGISTER_NAMES,
    _canonical_bytes,
    _canonical_sha256,
    _normalized_declared_edge,
    _source_identity,
)
from src.observatory.native_lua_cclosure_table_key_provenance import _enhanced_cfg
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary import (
    ANALYSIS_KIND as PARENT_KIND,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PARENT = "1385ca599a7442b2b18a45206619d520b19db1b5a2fa9c0ba5b54908831462a5"
_BASE = 0x400000
_ENTRY = 0x39CB98
_RAW = "ff2570617d00"
_BODY = "ffc413f0835bbd8fe8ffadeea407c5e87981b4bbe61676bebb1253a2b9d3f458"
_ATLAS = "52917cb57766349ba4060b37b1d09f0b0d4ef87be974755358ec90d6c78467d6"
_CFG = "1b553e3e7adf738d6c579800a0b4a87fad454e18d1cba0243b6bd78ad9252580"
_IAT_RVA, _IAT_VA = 0x3D6170, 0x7D6170
_IMPORT = {
    "evidence_class": "fact",
    "library": "KERNEL32.dll",
    "name": "RtlUnwind",
    "ordinal": None,
    "hint": 1048,
    "iat_rva": "0x003d6170",
}
_REFS = (
    (
        0x378889,
        0x378840,
        "e80a430200",
        "fb7ccdd6763c0e720899e85d14807536fed151f65b66ce0bb2a7aa4f91ff767b",
    ),
    (
        0x378913,
        0x378900,
        "e880420200",
        "ff85646fbf11165d0a1c06e141836f40d94786e14f342e678d939ec9abc091d2",
    ),
    (
        0x378B7D,
        0x378B6E,
        "e816400200",
        "e58ae61360dfe3582ded9e78d44ae9c56e1226ebad653da407ed81b5f39ab4bc",
    ),
)
_SCOPE = {
    "atlas_function_count": 25312,
    "atlas_body_range_count": 25490,
    "decoded_bytes": 3735718,
    "decoded_instructions": 1153814,
    "all_declared_ranges_decoded": True,
    "operand_classes": ["absolute_memory", "immediate"],
}
_RAW_BINDING = {
    "pe_bits": 32,
    "import_directory_rva": "0x0048eca4",
    "import_directory_size": 220,
    "import_directory_file_offset": "0x0048dca4",
    "import_directory_sha256": "788f7357cb31ba62895740d67e0d8a0f6bf962c467ec801a29cf9044d522fd65",
    "descriptor_count": 10,
    "descriptor_index": 7,
    "descriptor_rva": "0x0048ed30",
    "descriptor_file_offset": "0x0048dd30",
    "descriptor_size": 20,
    "descriptor_sha256": "fe01ec3285fd8be5c0857ae597b2ac4a14de3579860f5f3577a6bdbe8595bc10",
    "original_first_thunk_rva": "0x0048ed80",
    "timestamp": 0,
    "forwarder_chain": 0,
    "first_thunk_rva": "0x003d6000",
    "library_name_rva": "0x004905fe",
    "library_name_file_offset": "0x0048f5fe",
    "library_nul_terminated_size": 13,
    "library_nul_terminated_sha256": "f8efc1f27ef6c525f7fd20dcb8d65e8197e97410eced20db4d323dfbf230a2a4",
    "thunk_index": 92,
    "lookup_thunk_rva": "0x0048eef0",
    "lookup_thunk_file_offset": "0x0048def0",
    "lookup_thunk_raw_value": "0x00490d30",
    "lookup_thunk_sha256": "2e964745bc4c58ca4f2c1c775ba21e17a8922a25064d96a0774b0fc8eed19ff3",
    "iat_slot_rva": "0x003d6170",
    "iat_slot_file_offset": "0x003d5170",
    "iat_slot_raw_value": "0x00490d30",
    "iat_slot_sha256": "2e964745bc4c58ca4f2c1c775ba21e17a8922a25064d96a0774b0fc8eed19ff3",
    "import_by_name_rva": "0x00490d30",
    "import_by_name_file_offset": "0x0048fd30",
    "hint_and_name_nul_terminated_size": 12,
    "hint_and_name_nul_terminated_sha256": "2450fd92b600521950069d40872922d88d7e26c6d6eceafbed60afb9812974cb",
    "hint": 1048,
    "name": "RtlUnwind",
    "metadata_only": True,
}
_RAW_BINDING.update(
    {
        "import_record_count": 342,
        "named_import_count": 342,
        "ordinal_import_count": 0,
        "kernel32_import_count": 139,
        "matching_name_count": 1,
        "matching_iat_slot_count": 1,
        "null_descriptor_index": 10,
        "null_descriptor_rva": "0x0048ed6c",
        "null_descriptor_file_offset": "0x0048dd6c",
        "null_descriptor_size": 20,
        "null_descriptor_sha256": "de47c9b27eb8d300dbb5f2c353e632c393262cf06340c4fa7f1b40c4cbd36f90",
        "kernel32_thunk_terminator_index": 139,
        "lookup_terminator_rva": "0x0048efac",
        "lookup_terminator_file_offset": "0x0048dfac",
        "iat_terminator_rva": "0x003d622c",
        "iat_terminator_file_offset": "0x003d522c",
        "thunk_terminator_size": 4,
        "thunk_terminator_sha256": "df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119",
    }
)


class NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
    RuntimeError
):
    pass


def _bad(message: str) -> None:
    raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
        message
    )


def _same(a: Any, b: Any) -> bool:
    return _canonical_bytes(a) == _canonical_bytes(b)


def _compact_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _instruction(rva: int, raw: str) -> dict[str, Any]:
    blob = bytes.fromhex(raw)
    return {
        "rva": _hex(rva),
        "size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def _audit() -> list[dict[str, Any]]:
    return [{"register": r, "call_rvas": []} for r in _REGISTER_NAMES]


def _identity(
    value: Mapping[str, Any], kind: str, digest: str, label: str
) -> dict[str, Any]:
    return _source_identity(value, kind, digest, label)


def _facts_identity(facts: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(facts.get("summary"), "facts summary")
    return {
        **_identity(facts, "pe_ghidra_program_facts", _FACTS, "program facts"),
        "function_count": summary.get("function_count"),
        "body_range_count": summary.get("body_range_count"),
        "function_body_bytes": summary.get("function_body_bytes"),
    }


def _preflight(
    parent: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    identity = _mapping(facts.get("identity"), "facts identity")
    if identity.get("executable_sha256") != _EXE or not all(
        _same(x.get("build_identity"), dict(identity)) for x in (parent, direct)
    ):
        _bad("prerequisite build identity differs")
    if _canonical_sha256(parent) != _PARENT:
        _bad("parent receipt differs")
    return (
        _facts_identity(facts),
        _identity(parent, PARENT_KIND, _PARENT, "adjacent-callee-cluster parent"),
        _identity(direct, DIRECT_KIND, _DIRECT, "direct calls"),
    )


def _decode() -> list[Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    out = list(decoder.disasm(bytes.fromhex(_RAW), _BASE + _ENTRY))
    if len(out) != 1 or bytes(out[0].bytes) != bytes.fromhex(_RAW):
        _bad("root bytes do not decode")
    return out


def _graph(ins: list[Any] | None = None) -> dict[str, Any]:
    import capstone, capstone.x86_const as x

    out = _with_edi_writes(
        _enhanced_cfg(
            _decode() if ins is None else ins, _BASE, (_ENTRY, 6), capstone, x
        ),
        _decode() if ins is None else ins,
        x,
    )
    out["caller_entry_rva"] = _hex(_ENTRY)
    if (out.get("node_count"), out.get("edge_count"), _canonical_sha256(out)) != (
        1,
        0,
        _CFG,
    ):
        _bad("CFG differs")
    node = _array(out.get("nodes"), "nodes")[0]
    if node.get("flow_kind") != "indirect_jump" or node.get("successor_rvas") != []:
        _bad("indirect-jump CFG differs")
    return out


def _raw_import_binding(image: Any | None = None) -> dict[str, Any]:
    if image is None:
        return dict(_RAW_BINDING)
    if image.bits != 32 or len(image.data_directories) <= 1:
        _bad("PE bits/import directory differs")
    rva, size = image.data_directories[1]
    off = image.rva_span_to_file_offset(rva, size)
    if (rva, size, off) != (0x48ECA4, 220, 0x48DCA4) or hashlib.sha256(
        image.data[off : off + size]
    ).hexdigest() != _RAW_BINDING["import_directory_sha256"]:
        _bad("import directory differs")
    rows = [
        struct.unpack_from("<IIIII", image.data, off + i * 20)
        for i in range(size // 20)
    ]
    null_offset = image.rva_span_to_file_offset(rva + 10 * 20, 20)
    if (
        len(rows) != 11
        or any(not any(x) for x in rows[:10])
        or any(rows[10])
        or null_offset != 0x48DD6C
        or hashlib.sha256(image.data[null_offset : null_offset + 20]).hexdigest()
        != _RAW_BINDING["null_descriptor_sha256"]
    ):
        _bad("import descriptors differ")
    desc = rows[7]
    doff = image.rva_span_to_file_offset(rva + 7 * 20, 20)
    if (
        desc != (0x48ED80, 0, 0, 0x4905FE, 0x3D6000)
        or doff != 0x48DD30
        or hashlib.sha256(image.data[doff : doff + 20]).hexdigest()
        != _RAW_BINDING["descriptor_sha256"]
    ):
        _bad("KERNEL32 descriptor differs")
    library = b"KERNEL32.dll\0"
    lo = image.rva_span_to_file_offset(desc[3], len(library))
    if (
        lo != 0x48F5FE
        or image.data[lo : lo + len(library)] != library
        or hashlib.sha256(library).hexdigest()
        != _RAW_BINDING["library_nul_terminated_sha256"]
    ):
        _bad("library name differs")
    idx = (_IAT_RVA - desc[4]) // 4
    if idx != 92 or desc[4] + idx * 4 != _IAT_RVA:
        _bad("thunk arithmetic differs")
    ilt = desc[0] + idx * 4
    iat = desc[4] + idx * 4
    io = image.rva_span_to_file_offset(ilt, 4)
    ao = image.rva_span_to_file_offset(iat, 4)
    if (ilt, iat, io, ao) != (0x48EEF0, _IAT_RVA, 0x48DEF0, 0x3D5170):
        _bad("thunk span differs")
    a = image.data[io : io + 4]
    b = image.data[ao : ao + 4]
    if (
        hashlib.sha256(a).hexdigest() != _RAW_BINDING["lookup_thunk_sha256"]
        or hashlib.sha256(b).hexdigest() != _RAW_BINDING["iat_slot_sha256"]
    ):
        _bad("thunk bytes differ")
    value = struct.unpack_from("<I", image.data, io)[0]
    if value != 0x490D30 or struct.unpack_from("<I", image.data, ao)[0] != value:
        _bad("ILT/IAT relation differs")
    lookup_end = image.rva_span_to_file_offset(desc[0] + 139 * 4, 4)
    iat_end = image.rva_span_to_file_offset(desc[4] + 139 * 4, 4)
    if (
        (lookup_end, iat_end) != (0x48DFAC, 0x3D522C)
        or image.data[lookup_end : lookup_end + 4] != b"\0\0\0\0"
        or image.data[iat_end : iat_end + 4] != b"\0\0\0\0"
        or hashlib.sha256(image.data[lookup_end : lookup_end + 4]).hexdigest()
        != _RAW_BINDING["thunk_terminator_sha256"]
    ):
        _bad("KERNEL32 thunk terminator differs")
    no = image.rva_span_to_file_offset(value, 12)
    hn = image.data[no : no + 12]
    if (
        no != 0x48FD30
        or hashlib.sha256(hn).hexdigest()
        != _RAW_BINDING["hint_and_name_nul_terminated_sha256"]
        or struct.unpack_from("<H", hn)[0] != 1048
        or hn[2:] != b"RtlUnwind\0"
    ):
        _bad("hint/name differs")
    imports = image.imports()
    by_name = [x for x in imports if x.get("name") == "RtlUnwind"]
    by_slot = [x for x in imports if x.get("iat_rva") == _hex(_IAT_RVA)]
    if (
        len(imports) != 342
        or sum(x.get("name") is not None for x in imports) != 342
        or sum(x.get("ordinal") is not None for x in imports) != 0
        or sum(x.get("library") == "KERNEL32.dll" for x in imports) != 139
        or len(by_name) != 1
        or len(by_slot) != 1
        or not _same(by_name[0], _IMPORT)
        or not _same(by_slot[0], _IMPORT)
    ):
        _bad("parsed import uniqueness differs")

    directory_bytes = image.data[off : off + size]
    descriptor_bytes = image.data[doff : doff + 20]
    null_descriptor_bytes = image.data[null_offset : null_offset + 20]
    lookup_terminator_bytes = image.data[lookup_end : lookup_end + 4]
    iat_terminator_bytes = image.data[iat_end : iat_end + 4]
    iat_value = struct.unpack_from("<I", image.data, ao)[0]
    observed = {
        "pe_bits": image.bits,
        "import_directory_rva": _hex(rva),
        "import_directory_size": size,
        "import_directory_file_offset": _hex(off),
        "import_directory_sha256": hashlib.sha256(directory_bytes).hexdigest(),
        "descriptor_count": sum(1 for row in rows if any(row)),
        "descriptor_index": 7,
        "descriptor_rva": _hex(rva + 7 * 20),
        "descriptor_file_offset": _hex(doff),
        "descriptor_size": len(descriptor_bytes),
        "descriptor_sha256": hashlib.sha256(descriptor_bytes).hexdigest(),
        "original_first_thunk_rva": _hex(desc[0]),
        "timestamp": desc[1],
        "forwarder_chain": desc[2],
        "first_thunk_rva": _hex(desc[4]),
        "library_name_rva": _hex(desc[3]),
        "library_name_file_offset": _hex(lo),
        "library_nul_terminated_size": len(library),
        "library_nul_terminated_sha256": hashlib.sha256(library).hexdigest(),
        "thunk_index": idx,
        "lookup_thunk_rva": _hex(ilt),
        "lookup_thunk_file_offset": _hex(io),
        "lookup_thunk_raw_value": _hex(value),
        "lookup_thunk_sha256": hashlib.sha256(a).hexdigest(),
        "iat_slot_rva": _hex(iat),
        "iat_slot_file_offset": _hex(ao),
        "iat_slot_raw_value": _hex(iat_value),
        "iat_slot_sha256": hashlib.sha256(b).hexdigest(),
        "import_by_name_rva": _hex(value),
        "import_by_name_file_offset": _hex(no),
        "hint_and_name_nul_terminated_size": len(hn),
        "hint_and_name_nul_terminated_sha256": hashlib.sha256(hn).hexdigest(),
        "hint": struct.unpack_from("<H", hn)[0],
        "name": hn[2:-1].decode("ascii"),
        "metadata_only": True,
        "import_record_count": len(imports),
        "named_import_count": sum(row.get("name") is not None for row in imports),
        "ordinal_import_count": sum(row.get("ordinal") is not None for row in imports),
        "kernel32_import_count": sum(
            row.get("library") == "KERNEL32.dll" for row in imports
        ),
        "matching_name_count": len(by_name),
        "matching_iat_slot_count": len(by_slot),
        "null_descriptor_index": 10,
        "null_descriptor_rva": _hex(rva + 10 * 20),
        "null_descriptor_file_offset": _hex(null_offset),
        "null_descriptor_size": len(null_descriptor_bytes),
        "null_descriptor_sha256": hashlib.sha256(null_descriptor_bytes).hexdigest(),
        "kernel32_thunk_terminator_index": 139,
        "lookup_terminator_rva": _hex(desc[0] + 139 * 4),
        "lookup_terminator_file_offset": _hex(lookup_end),
        "iat_terminator_rva": _hex(desc[4] + 139 * 4),
        "iat_terminator_file_offset": _hex(iat_end),
        "thunk_terminator_size": len(lookup_terminator_bytes),
        "thunk_terminator_sha256": hashlib.sha256(lookup_terminator_bytes).hexdigest(),
    }
    if iat_terminator_bytes != lookup_terminator_bytes or not _same(
        observed, _RAW_BINDING
    ):
        _bad("published raw PE import binding differs")
    return observed


def _syntax(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    outgoing = {
        site
        for site, edge in _edges(facts).items()
        if _rva(edge.get("source_entry_rva"), "outgoing source") == _ENTRY
    }
    if outgoing:
        _bad("declared outgoing direct-edge partition differs")
    operand = {
        "role": "typed_pe_import_iat_operand",
        "instruction": _instruction(_ENTRY, _RAW),
        "operand_class": "absolute_memory",
        "operand_index": 0,
        "operand_access": "read",
        "operand_va": _hex(_IAT_VA),
        "operand_rva": _hex(_IAT_RVA),
        "control_syntax": "x86_absolute_memory_indirect_jump_ff25",
        "section_name": ".rdata",
        "section_rva": "0x003d6000",
        "section_characteristics": "0x40000040",
        "section_writable": False,
        "file_backed": True,
        "pe_import_metadata": dict(_IMPORT),
        "raw_pe_import_table_binding": _raw_import_binding(image),
        "import_metadata_only": True,
        "contents_or_runtime_behavior_opaque": True,
    }
    if image is not None:
        section = next(
            (
                s
                for s in image.sections
                if s.virtual_address <= _IAT_RVA < s.virtual_address + s.virtual_size
            ),
            None,
        )
        if section is None or (
            section.name,
            section.virtual_address,
            section.characteristics,
            image.rva_to_file_offset(_IAT_RVA) is not None,
        ) != (".rdata", 0x3D6000, 0x40000040, True):
            _bad("IAT section differs")
    return {
        "outgoing_direct": [],
        "outgoing_direct_partition_complete": True,
        "opaque_indirect_controls": [
            {
                "role": "opaque_absolute_memory_indirect_jump",
                "instruction": _instruction(_ENTRY, _RAW),
                "operand_class": "absolute_memory",
                "operand_index": 0,
                "operand_access": "read",
                "operand_va": _hex(_IAT_VA),
                "operand_rva": _hex(_IAT_RVA),
                "control_encoding": "ff25",
                "runtime_target_opaque": True,
                "runtime_execution_or_behavior_opaque": True,
            }
        ],
        "indirect_control_partition_complete": True,
        "pe_address_operands": [operand],
        "pe_address_operand_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [],
        "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [],
        "opaque_interrupt_partition_complete": True,
        "non_pe_immediate_operands": [],
        "non_pe_immediate_operand_partition_complete": True,
        "call_r32_audit": _audit(),
        "register_call_partition_complete": True,
    }


def _edges(facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    out = {}
    for row in _array(facts.get("ghidra_declared_direct_calls"), "direct edges"):
        edge = _mapping(row, "edge")
        site = _rva(edge.get("instruction_rva"), "site")
        if site in out:
            _bad("repeated direct edge site")
        out[site] = edge
    return out


def _reference_rows(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    fs = _atlas_functions(facts)
    edges = _edges(facts)
    observed = {
        site
        for site, e in edges.items()
        if _rva(e.get("target_entry_rva"), "target") == _ENTRY
    }
    if observed != {x[0] for x in _REFS}:
        _bad("incoming edge frontier differs")
    rows = []
    for site, owner, raw, atlas in _REFS:
        edge = edges.get(site)
        f = fs.get(owner)
        if (
            edge is None
            or f is None
            or (
                _rva(edge.get("source_entry_rva"), "source"),
                _rva(edge.get("target_entry_rva"), "entry"),
                _rva(edge.get("target_rva"), "target"),
                atlas_record_sha256(f),
            )
            != (owner, _ENTRY, _ENTRY, atlas)
        ):
            _bad("incoming edge differs")
        rows.append(
            {
                "instruction_rva": _hex(site),
                "instruction_size": 5,
                "instruction_sha256": hashlib.sha256(bytes.fromhex(raw)).hexdigest(),
                "owner_entry_rva": _hex(owner),
                "owner_atlas_record_sha256": atlas,
                "target_rva": _hex(_ENTRY),
                "target_atlas_record_sha256": _ATLAS,
                "target_va": _hex(_BASE + _ENTRY),
                "operand_class": "immediate",
                "operand_index": 0,
                "use_class": "direct_call",
                "call_form": "x86_relative_near_call_e8",
                "ghidra_declared_direct_edge": _normalized_declared_edge(edge),
            }
        )
    return rows


def _scan(
    facts: Mapping[str, Any],
    data: bytes | None = None,
    image: Any | None = None,
    decoder: Any | None = None,
) -> dict[str, Any]:
    refs = _reference_rows(facts)
    owners = [
        {
            "owner_entry_rva": r["owner_entry_rva"],
            "owner_atlas_record_sha256": r["owner_atlas_record_sha256"],
            "reference_count": 1,
        }
        for r in refs
    ]
    target_owners = [{"target_rva": _hex(_ENTRY), **owner} for owner in owners]
    target_refs = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 3,
        }
    ]
    target = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 3,
            "owner_count": 3,
        }
    ]
    hashes = {
        "owner_partition": _compact_sha256(owners),
        "target_partition": _compact_sha256(target),
        "target_owner_partition": _compact_sha256(target_owners),
        "target_reference_partition": _compact_sha256(target_refs),
    }
    expected = {
        "owner_partition": "cddb714b1dbe52d2306141d582a957d11e664607609a14270f288d082efff585",
        "target_partition": "9a85aede2b378f405f672967104d51c149a63877b8449edd289b738c262bfa1d",
        "target_owner_partition": "b1010c7e6c7371094eb32586a5b6be16de549816afdfbe6cbd90c1567044b82e",
        "target_reference_partition": "c0f229f643465a024c67bd064e188e7aa6886f6177e4572c26cfceb36dcc5c8e",
    }
    if hashes != expected:
        _bad("target reference partition hashes differ")
    result = {
        "scope": dict(_SCOPE),
        "target_rvas": [_hex(_ENTRY)],
        "target_vas": [_hex(_BASE + _ENTRY)],
        "references": refs,
        "target_partition": target,
        "target_reference_partition": target_refs,
        "owner_partition": owners,
        "target_owner_partition": target_owners,
        "partition_sha256": hashes,
        "references_canonical_sha256": _compact_sha256(refs),
        "aggregates": {
            "reference_count": 3,
            "target_count": 1,
            "owner_count": 3,
            "target_owner_count": 3,
            "direct_call_count": 3,
            "comparison_count": 0,
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }
    if data is None:
        return result
    import capstone.x86_const as x

    actual = []
    tot = [0, 0, 0]
    decoder.detail = True
    for owner, f in sorted(_atlas_functions(facts).items()):
        for span in _array(f.get("ranges"), "range"):
            start = _rva(_mapping(span, "range").get("start_rva"), "start")
            size = _mapping(span, "range").get("size")
            ins = _decode_range(data, image, start, size, decoder)
            tot[0] += 1
            tot[1] += size
            tot[2] += len(ins)
            for i in ins:
                for index, op in enumerate(i.operands):
                    value = (
                        (int(op.imm) & 0xFFFFFFFF)
                        if op.type == x.X86_OP_IMM
                        else (
                            int(op.mem.disp) & 0xFFFFFFFF
                            if op.type == x.X86_OP_MEM
                            and op.mem.segment == x.X86_REG_INVALID
                            and op.mem.base == x.X86_REG_INVALID
                            and op.mem.index == x.X86_REG_INVALID
                            else None
                        )
                    )
                    if value == _BASE + _ENTRY:
                        actual.append(
                            (
                                i.address - image.image_base,
                                owner,
                                index,
                                bytes(i.bytes),
                                (
                                    "immediate"
                                    if op.type == x.X86_OP_IMM
                                    else "absolute_memory"
                                ),
                            )
                        )
    expected = [
        (site, owner, 0, bytes.fromhex(raw), "immediate")
        for site, owner, raw, _ in _REFS
    ]
    if tuple(tot) != (25490, 3735718, 1153814) or actual != expected:
        _bad("complete target operand scan differs")
    return result


def _iat_scan(
    facts: Mapping[str, Any],
    data: bytes | None = None,
    image: Any | None = None,
    decoder: Any | None = None,
) -> dict[str, Any]:
    ref = {
        "instruction_rva": _hex(_ENTRY),
        "instruction_size": 6,
        "instruction_sha256": hashlib.sha256(bytes.fromhex(_RAW)).hexdigest(),
        "owner_entry_rva": _hex(_ENTRY),
        "owner_atlas_record_sha256": _ATLAS,
        "operand_class": "absolute_memory",
        "operand_index": 0,
        "operand_access": "read",
        "operand_va": _hex(_IAT_VA),
        "operand_rva": _hex(_IAT_RVA),
        "control_syntax": "x86_absolute_memory_indirect_jump_ff25",
    }
    call = {
        "instruction_rva": "0x00371024",
        "instruction_size": 6,
        "instruction_sha256": "811e9d58df00ae081abcafa1d3e4183eb4f4757d06855297e9ced5cc4ac75667",
        "owner_entry_rva": "0x00371000",
        "owner_atlas_record_sha256": "",
        "operand_class": "absolute_memory",
        "operand_index": 0,
        "operand_access": "read",
        "operand_va": _hex(_IAT_VA),
        "operand_rva": _hex(_IAT_RVA),
        "control_syntax": "x86_absolute_memory_indirect_call_ff15",
    }
    owner = _atlas_functions(facts).get(0x371000)
    if owner is None:
        _bad("IAT call owner absent")
    call["owner_atlas_record_sha256"] = atlas_record_sha256(owner)
    refs = [call, ref]
    owners = [
        {
            "owner_entry_rva": item["owner_entry_rva"],
            "owner_atlas_record_sha256": item["owner_atlas_record_sha256"],
            "reference_count": 1,
        }
        for item in refs
    ]
    hashes = {"owner_partition": _compact_sha256(owners)}
    if hashes != {
        "owner_partition": "6ecdea808d8904feb4d2829c06b8258cbc4101bc18e1e197a6283badf69f69a9"
    }:
        _bad("IAT-slot partition hashes differ")
    result = {
        "scope": dict(_SCOPE),
        "scanned_operand_va": _hex(_IAT_VA),
        "scanned_operand_rva": _hex(_IAT_RVA),
        "references": refs,
        "owner_partition": owners,
        "partition_sha256": hashes,
        "references_canonical_sha256": _compact_sha256(refs),
        "aggregates": {
            "reference_count": 2,
            "owner_count": 2,
            "absolute_memory_operand_count": 2,
            "indirect_jump_count": 1,
            "indirect_call_count": 1,
        },
    }
    if data is None:
        return result
    import capstone.x86_const as x

    actual = []
    tot = [0, 0, 0]
    decoder.detail = True
    for owner, f in sorted(_atlas_functions(facts).items()):
        for span in _array(f.get("ranges"), "range"):
            start = _rva(_mapping(span, "range").get("start_rva"), "start")
            size = _mapping(span, "range").get("size")
            ins = _decode_range(data, image, start, size, decoder)
            tot[0] += 1
            tot[1] += size
            tot[2] += len(ins)
            for i in ins:
                for index, op in enumerate(i.operands):
                    value = (
                        (int(op.imm) & 0xFFFFFFFF)
                        if op.type == x.X86_OP_IMM
                        else (
                            int(op.mem.disp) & 0xFFFFFFFF
                            if op.type == x.X86_OP_MEM
                            and op.mem.segment == x.X86_REG_INVALID
                            and op.mem.base == x.X86_REG_INVALID
                            and op.mem.index == x.X86_REG_INVALID
                            else None
                        )
                    )
                    if value == _IAT_VA:
                        actual.append(
                            (
                                i.address - image.image_base,
                                owner,
                                index,
                                bytes(i.bytes),
                                op.access,
                                (
                                    "immediate"
                                    if op.type == x.X86_OP_IMM
                                    else "absolute_memory"
                                ),
                            )
                        )
    if tuple(tot) != (25490, 3735718, 1153814) or actual != [
        (0x371024, 0x371000, 0, bytes.fromhex("ff1570617d00"), 1, "absolute_memory"),
        (_ENTRY, _ENTRY, 0, bytes.fromhex(_RAW), 1, "absolute_memory"),
    ]:
        _bad("complete IAT-slot operand scan differs")
    return result


def _parent_edge(parent: Mapping[str, Any]) -> dict[str, Any]:
    rows = _array(
        _mapping(parent.get("native_calls"), "parent calls").get("direct"),
        "parent direct",
    )
    hits = [
        _mapping(x, "edge")
        for x in rows
        if _mapping(_mapping(x, "edge").get("instruction"), "instruction").get("rva")
        == "0x00378b7d"
    ]
    if len(hits) != 1:
        _bad("parent rejoin edge differs")
    row = hits[0]
    instruction = _mapping(row.get("instruction"), "parent edge instruction")
    edge = _mapping(row.get("ghidra_declared_direct_edge"), "parent declared edge")
    if (
        row.get("source_entry_rva"),
        row.get("source_body_size"),
        row.get("source_body_sha256"),
        row.get("source_atlas_record_sha256"),
        instruction.get("size"),
        instruction.get("sha256"),
        row.get("target_entry_rva"),
        row.get("target_body_size"),
        row.get("target_body_sha256"),
        row.get("target_atlas_record_sha256"),
        edge.get("target_name_sha256"),
    ) != (
        "0x00378b6e",
        25,
        "e4c5374582d34dcaf8ef3cd401b6bcc2e38a1cc1ab6950af7eaf0ce7129c3286",
        "e58ae61360dfe3582ded9e78d44ae9c56e1226ebad653da407ed81b5f39ab4bc",
        5,
        "1bf6aac09857661da870fb8aa4d8b6b3d8f9c750fafdbf2550f03e7da710cc76",
        "0x0039cb98",
        6,
        _BODY,
        _ATLAS,
        "3d859f62aadd9aa78b7bd2d1ca6fa56e5bee6a744dee0f410a74fa1785a97035",
    ):
        _bad("parent rejoin cross-join differs")
    return hits[0]


def _body(
    facts: Mapping[str, Any], ins: list[Any] | None = None, image: Any | None = None
) -> dict[str, Any]:
    f = _atlas_functions(facts).get(_ENTRY)
    if f is None or (
        f.get("body_size"),
        f.get("body_sha256"),
        atlas_record_sha256(f),
        f.get("name"),
        f.get("namespace"),
        f.get("name_source"),
        f.get("thunk"),
    ) != (6, _BODY, _ATLAS, "RtlUnwind", "KERNEL32.DLL", "DEFAULT", True):
        _bad("atlas body differs")
    decoded = _decode() if ins is None else ins
    if image is not None:
        section = next(
            (
                s
                for s in image.sections
                if s.virtual_address <= _ENTRY < s.virtual_address + s.virtual_size
            ),
            None,
        )
        if section is None or (
            section.name,
            section.virtual_address,
            section.virtual_size,
            section.characteristics,
            image.rva_to_file_offset(_ENTRY),
        ) != (".text", 0x1000, 0x3D4B4E, 0x60000020, 0x39BF98):
            _bad("target PE backing differs")
    points = []
    for i in decoded:
        _reads, writes = i.regs_access()
        names = {i.reg_name(r).lower() for r in writes}
        raw = bytes(i.bytes)
        points.append(
            {
                "rva": _hex(i.address - _BASE),
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "writes_ebx": "ebx" in names,
                "writes_esi": "esi" in names,
                "writes_edi": "edi" in names,
                "writes_esp": "esp" in names,
            }
        )
    return {
        "role": "external_import_thunk_opaque_static_boundary",
        "entry_rva": _hex(_ENTRY),
        "atlas_record_sha256": _ATLAS,
        "target_atlas_metadata": {
            "name": "RtlUnwind",
            "namespace": "KERNEL32.DLL",
            "name_source": "DEFAULT",
            "thunk": True,
            "metadata_only": True,
        },
        "target_pe_backing": {
            "section_name": ".text",
            "section_rva": "0x00001000",
            "section_virtual_size": 4016974,
            "section_characteristics": "0x60000020",
            "section_writable": False,
            "file_offset": "0x0039bf98",
            "file_backed": True,
            "contents_or_runtime_behavior_opaque": True,
        },
        "body_size": 6,
        "body_sha256": _BODY,
        "range_start_rva": _hex(_ENTRY),
        "range_size": 6,
        "control_flow_graph_canonical_sha256": _CFG,
        "reviewed_points": points,
        "direct_lua_calls": [],
        "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [],
        "staged_lua_partition_complete": True,
        "call_r32_audit": _audit(),
        "register_call_partition_complete": True,
        "semantic_facts": {
            "relationship_defined_only": True,
            "analysis_labels_opaque": True,
            "source_semantic_names_assigned": False,
            "runtime_or_success_claimed": False,
            "import_metadata_only": True,
        },
    }


_METHOD = {
    "structural_boundary": "The receipt seals one FF25 absolute-memory indirect jump, descriptor ILT IAT hint and name PE bytes, the rejoined parent edge, and complete target and IAT-slot atlas operand traversals.",
    "not_claimed": [
        "analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, exception, throw, or normal return",
        "runtime reachability, invocation, ordering, frequency, state mutation, termination, target resolution, execution, or effect",
        "contents or runtime meaning of the IAT slot or imported target",
        "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
    ],
}


def _summary() -> dict[str, Any]:
    return {
        "reviewed_import_thunk_count": 1,
        "reviewed_import_thunk_bytes": 6,
        "sealed_instruction_count": 1,
        "sealed_control_flow_graph_count": 1,
        "sealed_control_flow_graph_node_count": 1,
        "sealed_control_flow_graph_edge_count": 0,
        "direct_lua_call_count": 0,
        "staged_lua_dispatch_count": 0,
        "call_r32_count": 0,
        "native_direct_edge_count": 0,
        "opaque_indirect_control_count": 1,
        "pe_address_operand_count": 1,
        "target_reference_count": 3,
        "iat_slot_reference_count": 2,
        "schema_violations": 0,
    }


def _evidence(
    parent: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    ins: list[Any] | None = None,
    image: Any | None = None,
    scan: Mapping[str, Any] | None = None,
    iat: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    atlas, p, d = _preflight(parent, direct, facts)
    expected_scan = _scan(facts)
    expected_iat = _iat_scan(facts)
    if scan is not None and not _same(scan, expected_scan):
        _bad("exact target scan differs from pinned scan")
    if iat is not None and not _same(iat, expected_iat):
        _bad("exact IAT scan differs from pinned scan")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(_mapping(facts.get("identity"), "identity")),
        "atlas": atlas,
        "parent_static_boundary": p,
        "direct_call_census": d,
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "sealed_instruction_count": 1,
            "register_call_encoding_audit": [
                {"register": r, "encoding": f"ff{0xd0+i:02x}"}
                for i, r in enumerate(_REGISTER_NAMES)
            ],
        },
        "function_body": _body(facts, ins, image),
        "control_flow_graph": _graph(ins),
        "parent_rejoin_edge": _parent_edge(parent),
        "native_calls": _syntax(facts, image),
        "whole_atlas_reference_scan": expected_scan,
        "whole_atlas_iat_slot_use_scan": expected_iat,
        "method": _METHOD,
        "summary": _summary(),
    }


def _normalize(action):
    try:
        return action()
    except NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
            str(exc)
        ) from exc


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary_structure(
    evidence: Mapping[str, Any],
    parent: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        evidence_object = _mapping(evidence, "evidence")
        parent_object = _mapping(parent, "parent")
        direct_object = _mapping(direct, "direct")
        facts_object = _mapping(facts, "facts")
        for v, l in (
            (evidence_object, "evidence"),
            (parent_object, "parent"),
            (direct_object, "direct"),
            (facts_object, "facts"),
        ):
            _validate_json_tree(v, l)
        receipt = validate_native_lua_direct_call_structure(direct_object, facts_object)
        if (
            receipt.get("status") != "structurally_verified"
            or receipt.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct structural prerequisite differs")
        expected = _evidence(parent_object, direct_object, facts_object)
        if not _same(evidence_object, expected):
            _bad("receipt differs from sealed structure")
        _assert_publication_safe(evidence_object)
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
            "build_identity": dict(evidence_object["build_identity"]),
            "evidence_sha256": _canonical_sha256(evidence_object),
            "summary": dict(evidence_object["summary"]),
        }

    return _normalize(run)


def build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
    executable: Path,
    parent: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        parent_object = _mapping(parent, "parent")
        direct_object = _mapping(direct, "direct")
        facts_object = _mapping(facts, "facts")
        inventory_object = _mapping(inventory, "inventory")
        for v, l in (
            (parent_object, "parent"),
            (direct_object, "direct"),
            (facts_object, "facts"),
            (inventory_object, "inventory"),
        ):
            _validate_json_tree(v, l)
        receipt = validate_native_lua_direct_call_census(
            executable, direct_object, facts_object, inventory=inventory_object
        )
        if (
            receipt.get("status") != "verified"
            or receipt.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct prerequisite differs")
        data, image, digest = _load_executable(executable)
        if digest != _EXE or image.image_base != _BASE:
            _bad("executable differs")
        decoder, _ = _decoder()
        decoder.detail = True
        ins = _decode_range(data, image, _ENTRY, 6, decoder)
        if (
            len(ins) != 1
            or hashlib.sha256(b"".join(bytes(i.bytes) for i in ins)).hexdigest()
            != _BODY
        ):
            _bad("thunk bytes differ")
        out = _evidence(
            parent_object,
            direct_object,
            facts_object,
            ins=ins,
            image=image,
            scan=_scan(facts_object, data, image, decoder),
            iat=_iat_scan(facts_object, data, image, decoder),
        )
        if _load_executable(executable)[2] != digest:
            _bad("executable changed during rebuild")
        _assert_publication_safe(out)
        validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary_structure(
            out, parent_object, direct_object, facts_object
        )
        return out

    return _normalize(run)


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    parent: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        evidence_object = _mapping(evidence, "evidence")
        parent_object = _mapping(parent, "parent")
        direct_object = _mapping(direct, "direct")
        facts_object = _mapping(facts, "facts")
        inventory_object = _mapping(inventory, "inventory")
        _validate_json_tree(evidence_object, "evidence")
        rebuilt = build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
            executable,
            parent_object,
            direct_object,
            facts_object,
            inventory=inventory_object,
        )
        if not _same(evidence_object, rebuilt):
            _bad("receipt differs from exact rebuild")
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": VERIFICATION_KIND,
            "status": "verified",
            "build_identity": dict(rebuilt["build_identity"]),
            "evidence_sha256": _canonical_sha256(rebuilt),
            "summary": dict(rebuilt["summary"]),
        }

    return _normalize(run)


def encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
    value: Mapping[str, Any],
) -> str:
    def run():
        value_object = _mapping(value, "receipt")
        _validate_json_tree(value_object, "receipt")
        return (
            json.dumps(
                value_object,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    return _normalize(run)
