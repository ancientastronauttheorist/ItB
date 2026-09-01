"""Immutable relationship-only receipt for the 0x0039cb92 import thunk.

This module proves a small finite set of static facts about one six-byte x86
import thunk.  In particular, the import name is PE metadata; it is not a
claim about runtime resolution, execution, or behavior.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capstone import CsError

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _decode_range,
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_class_factory_chain import _with_edi_writes
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
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary import (
    ANALYSIS_KIND as PREDECESSOR_KIND,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = (
    "pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_"
    "callee_external_target_import_thunk_static_boundary"
)
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS_SHA256 = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT_SHA256 = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PREDECESSOR_SHA256 = "0d8bb3aecc53090dc5282844885ed327e79541ebaad4b7ca928e0494f86b08a9"
_IMAGE_BASE = 0x00400000

_ROOT_RVA = 0x0039CB92
_ROOT_BYTES = "ff2510607d00"
_ROOT_SIZE = 6
_ROOT_BODY_SHA256 = "247575b8ff280345c05bf6c58c3620b861c076bb718663401c6c729f4542cee7"
_ROOT_ATLAS_SHA256 = "495f4729075f0f38c369905e1cd00f3f3d9b1eb5247caf5ce112fec3e6066f4e"
_CFG_SHA256 = "29e8bc268788c4dad137925a79b4350355d7f7db2dd2666bbc21399dd5bce60c"

_IAT_VA = 0x007D6010
_IAT_RVA = 0x003D6010
_IMPORT_METADATA = {
    "evidence_class": "fact",
    "library": "KERNEL32.dll",
    "name": "IsProcessorFeaturePresent",
    "ordinal": None,
    "hint": 772,
    "iat_rva": "0x003d6010",
}
_RAW_IMPORT_TABLE_BINDING = {
    "pe_bits": 32,
    "import_directory_rva": "0x0048eca4",
    "import_directory_size": 220,
    "import_directory_file_offset": "0x0048dca4",
    "import_directory_sha256": "788f7357cb31ba62895740d67e0d8a0f6bf962c467ec801a29cf9044d522fd65",
    "descriptor_count": 10,
    "import_record_count": 342,
    "named_import_count": 342,
    "ordinal_import_count": 0,
    "kernel32_import_count": 139,
    "matching_name_count": 1,
    "matching_iat_slot_count": 1,
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
    "thunk_index": 4,
    "lookup_thunk_rva": "0x0048ed90",
    "lookup_thunk_file_offset": "0x0048dd90",
    "lookup_thunk_raw_value": "0x00490a02",
    "lookup_thunk_sha256": "4a4a07bfd0b46732c457558065401cc422a188a7e84dfb482d179bd610989a61",
    "iat_slot_rva": "0x003d6010",
    "iat_slot_file_offset": "0x003d5010",
    "iat_slot_raw_value": "0x00490a02",
    "iat_slot_sha256": "4a4a07bfd0b46732c457558065401cc422a188a7e84dfb482d179bd610989a61",
    "import_by_name_rva": "0x00490a02",
    "import_by_name_file_offset": "0x0048fa02",
    "hint_and_name_nul_terminated_size": 28,
    "hint_and_name_nul_terminated_sha256": "bd0a4eda3c3cad901506880438be40e8c7fe64cb99de20e10c67759b071b7f47",
    "hint": 772,
    "name": "IsProcessorFeaturePresent",
    "metadata_only": True,
}

_REFERENCE_SITES = (
    (0x00357B75, 0x00357B6A, "e818500400", "324c7636ddd286b956053bb39fa045719f388d5254e441ce98b33d77d11fb074"),
    (0x00357C7C, 0x00357C71, "e8114f0400", "34cee74141620b8de324a94f04fe3dd885a816a6139131ddee8f43ab5785752e"),
    (0x00358026, 0x0035800D, "e8674b0400", "7e8c41f5d76a4703f1d1ec2c2573a16eaf27022d0082a9c7708e64a4c6e9163c"),
    (0x00358528, 0x0035851B, "e865460400", "62c30753e9ddcec2be947cc7f388687335ff143d7352955ef8ab62556480aa15"),
    (0x00379F21, 0x00379F1F, "e86c2c0200", "697696782a1427361f7866422ee2ca01fb0144a34fcacc55b5bb5f73125d7ae5"),
    (0x003891AC, 0x00389190, "e8e1390100", "0bea8bde88bfd39c21f692d6e7b1c5f426624479d2a400d624dae9c9956bd018"),
)
_SCAN_SCOPE = {
    "atlas_function_count": 25312,
    "atlas_body_range_count": 25490,
    "decoded_bytes": 3735718,
    "decoded_instructions": 1153814,
    "all_declared_ranges_decoded": True,
    "operand_classes": ["absolute_memory", "immediate"],
}
_PARTITION_SHA256 = {
    "owner_partition": "1bbecba81a7d7aa4aeca7f1f710d6f01f560569ffa80408e47615ced30e2abcd",
    "target_owner_partition": "3a8c2764b1ef2d34109ba3afefbceac6055183a06bf28065f29b231f54dd0f8c",
    "target_reference_partition": "4ac37284ab3f41c7661c27432c2e89564f73e16913fa0f183b564f6d2330604e",
}


class NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError(RuntimeError):
    """Raised when the sealed import-thunk receipt cannot be reproduced."""


def _bad(message: str) -> None:
    raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError(message)


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _compact_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _instruction(rva: int, encoded: str) -> dict[str, Any]:
    raw = bytes.fromhex(encoded)
    return {"rva": _hex(rva), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _empty_register_audit() -> list[dict[str, Any]]:
    return [{"register": register, "call_rvas": []} for register in _REGISTER_NAMES]


def _decode_root() -> list[Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    instructions = list(decoder.disasm(bytes.fromhex(_ROOT_BYTES), _IMAGE_BASE + _ROOT_RVA))
    if len(instructions) != 1 or bytes(instructions[0].bytes) != bytes.fromhex(_ROOT_BYTES):
        _bad("sealed import-thunk bytes do not decode")
    return instructions


def _reviewed_points(instructions: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for instruction in instructions:
        _reads, writes = instruction.regs_access()
        names = {instruction.reg_name(register).lower() for register in writes}
        raw = bytes(instruction.bytes)
        result.append({
            "rva": _hex(instruction.address - _IMAGE_BASE),
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "writes_ebx": "ebx" in names,
            "writes_esi": "esi" in names,
            "writes_edi": "edi" in names,
            "writes_esp": "esp" in names,
        })
    return result


def _graph(instructions: list[Any] | None = None) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    decoded = _decode_root() if instructions is None else instructions
    graph = _with_edi_writes(
        _enhanced_cfg(decoded, _IMAGE_BASE, (_ROOT_RVA, _ROOT_SIZE), capstone, x86),
        decoded,
        x86,
    )
    graph["caller_entry_rva"] = _hex(_ROOT_RVA)
    if (
        graph.get("node_count"), graph.get("edge_count"), _canonical_sha256(graph)
    ) != (1, 0, _CFG_SHA256):
        _bad("import-thunk CFG differs")
    node = graph.get("nodes", [None])[0]
    if not isinstance(node, Mapping) or node.get("flow_kind") != "indirect_jump" or node.get("successor_rvas") != []:
        _bad("import-thunk indirect-jump CFG differs")
    return graph


def _raw_import_table_binding(image: Any | None = None) -> dict[str, Any]:
    """Verify the descriptor, ILT, IAT, hint, and name without loader claims."""
    binding = dict(_RAW_IMPORT_TABLE_BINDING)
    if image is None:
        return binding
    if image.bits != 32 or len(image.data_directories) <= 1:
        _bad("import-thunk requires a 32-bit PE import directory")
    directory_rva, directory_size = image.data_directories[1]
    if (directory_rva, directory_size) != (0x0048ECA4, 220):
        _bad("raw PE import directory differs")
    directory_offset = image.rva_span_to_file_offset(directory_rva, directory_size)
    if directory_offset != 0x0048DCA4:
        _bad("raw PE import directory is not at the sealed file span")
    directory_bytes = image.data[directory_offset:directory_offset + directory_size]
    if hashlib.sha256(directory_bytes).hexdigest() != _RAW_IMPORT_TABLE_BINDING["import_directory_sha256"]:
        _bad("raw PE import directory bytes differ")
    descriptors = [
        struct.unpack_from("<IIIII", directory_bytes, index * 20)
        for index in range(directory_size // 20)
    ]
    if len(descriptors) != 11 or any(not any(row) for row in descriptors[:10]) or any(descriptors[10]):
        _bad("raw PE import descriptor partition differs")
    descriptor_rva = directory_rva + 7 * 20
    descriptor_offset = image.rva_span_to_file_offset(descriptor_rva, 20)
    if descriptor_offset != 0x0048DD30:
        _bad("raw PE import descriptor span differs")
    descriptor_bytes = image.data[descriptor_offset:descriptor_offset + 20]
    if hashlib.sha256(descriptor_bytes).hexdigest() != _RAW_IMPORT_TABLE_BINDING["descriptor_sha256"]:
        _bad("raw PE import descriptor bytes differ")
    original_first_thunk, timestamp, forwarder_chain, name_rva, first_thunk = struct.unpack_from(
        "<IIIII", image.data, descriptor_offset
    )
    if (original_first_thunk, timestamp, forwarder_chain, name_rva, first_thunk) != (
        0x0048ED80, 0, 0, 0x004905FE, 0x003D6000
    ):
        _bad("raw PE import descriptor differs")
    name_offset = image.rva_span_to_file_offset(name_rva, 13)
    library_bytes = b"KERNEL32.dll\0"
    if (
        name_offset != 0x0048F5FE
        or image.data[name_offset:name_offset + len(library_bytes)] != library_bytes
        or hashlib.sha256(library_bytes).hexdigest()
        != _RAW_IMPORT_TABLE_BINDING["library_nul_terminated_sha256"]
    ):
        _bad("raw PE import library differs")
    lookup_rva = original_first_thunk + 4 * 4
    lookup_offset = image.rva_span_to_file_offset(lookup_rva, 4)
    iat_offset = image.rva_span_to_file_offset(first_thunk + 4 * 4, 4)
    if (lookup_offset, iat_offset) != (0x0048DD90, 0x003D5010):
        _bad("raw PE thunk spans differ")
    lookup_bytes = image.data[lookup_offset:lookup_offset + 4]
    iat_bytes = image.data[iat_offset:iat_offset + 4]
    if (
        hashlib.sha256(lookup_bytes).hexdigest()
        != _RAW_IMPORT_TABLE_BINDING["lookup_thunk_sha256"]
        or hashlib.sha256(iat_bytes).hexdigest()
        != _RAW_IMPORT_TABLE_BINDING["iat_slot_sha256"]
    ):
        _bad("raw PE ILT/IAT bytes differ")
    (import_by_name_rva,) = struct.unpack_from("<I", image.data, lookup_offset)
    (iat_value,) = struct.unpack_from("<I", image.data, iat_offset)
    if import_by_name_rva != 0x00490A02 or iat_value != import_by_name_rva:
        _bad("raw PE ILT/IAT entry differs")
    import_name_offset = image.rva_span_to_file_offset(import_by_name_rva, 28)
    if import_name_offset != 0x0048FA02:
        _bad("raw PE import-by-name span differs")
    hint_name_bytes = image.data[import_name_offset:import_name_offset + 28]
    if hashlib.sha256(hint_name_bytes).hexdigest() != _RAW_IMPORT_TABLE_BINDING["hint_and_name_nul_terminated_sha256"]:
        _bad("raw PE import hint/name bytes differ")
    (hint,) = struct.unpack_from("<H", image.data, import_name_offset)
    if hint != 772 or hint_name_bytes[2:] != b"IsProcessorFeaturePresent\0":
        _bad("raw PE import hint or name differs")
    imports = image.imports()
    matching_name = [item for item in imports if item.get("name") == "IsProcessorFeaturePresent"]
    matching_iat = [item for item in imports if item.get("iat_rva") == _hex(_IAT_RVA)]
    if (
        len(imports) != 342
        or sum(item.get("name") is not None for item in imports) != 342
        or sum(item.get("ordinal") is not None for item in imports) != 0
        or sum(item.get("library") == "KERNEL32.dll" for item in imports) != 139
        or len(matching_name) != 1
        or len(matching_iat) != 1
        or not _same(matching_name[0], _IMPORT_METADATA)
        or not _same(matching_iat[0], _IMPORT_METADATA)
    ):
        _bad("raw PE IAT metadata uniqueness differs")
    return binding


def _import_binding(image: Any | None = None) -> dict[str, Any]:
    binding = {
        "role": "typed_pe_import_iat_operand",
        "instruction": _instruction(_ROOT_RVA, _ROOT_BYTES),
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
        "pe_import_metadata": dict(_IMPORT_METADATA),
        "raw_pe_import_table_binding": _raw_import_table_binding(image),
        "import_metadata_only": True,
        "contents_or_runtime_behavior_opaque": True,
    }
    if image is not None:
        section = next(
            (item for item in image.sections if item.virtual_address <= _IAT_RVA < item.virtual_address + item.virtual_size),
            None,
        )
        if section is None or (
            section.name,
            section.virtual_address,
            section.characteristics,
            image.rva_to_file_offset(_IAT_RVA) is not None,
        ) != (".rdata", 0x003D6000, 0x40000040, True):
            _bad("IAT section or backing differs")
    return binding


def _native_syntax(image: Any | None = None) -> dict[str, Any]:
    return {
        "outgoing_direct": [],
        "opaque_indirect_controls": [{
            "role": "opaque_absolute_memory_indirect_jump",
            "instruction": _instruction(_ROOT_RVA, _ROOT_BYTES),
            "operand_class": "absolute_memory",
            "operand_index": 0,
            "operand_access": "read",
            "operand_va": _hex(_IAT_VA),
            "operand_rva": _hex(_IAT_RVA),
            "control_encoding": "ff25",
            "runtime_target_opaque": True,
            "runtime_execution_or_behavior_opaque": True,
        }],
        "indirect_control_partition_complete": True,
        "pe_address_operands": [_import_binding(image)],
        "pe_address_operand_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [],
        "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [],
        "opaque_interrupt_partition_complete": True,
        "call_r32_audit": _empty_register_audit(),
        "register_call_partition_complete": True,
    }


def _declared_edges(program_facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw_edge in _array(program_facts.get("ghidra_declared_direct_calls"), "declared direct edges"):
        edge = _mapping(raw_edge, "declared direct edge")
        site = _rva(edge.get("instruction_rva"), "declared direct edge site")
        if site in result:
            _bad("declared direct-edge sites repeat")
        result[site] = edge
    return result


def _reference_rows(program_facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = _atlas_functions(program_facts)
    edges = _declared_edges(program_facts)
    expected_sites = {site for site, _owner, _raw, _atlas in _REFERENCE_SITES}
    observed_sites = {
        site
        for site, edge in edges.items()
        if _rva(edge.get("target_entry_rva"), "declared target") == _ROOT_RVA
    }
    if observed_sites != expected_sites:
        _bad("declared import-thunk frontier differs")
    rows: list[dict[str, Any]] = []
    for site, owner_entry, encoded, owner_atlas in _REFERENCE_SITES:
        edge = edges.get(site)
        owner = functions.get(owner_entry)
        if edge is None or owner is None:
            _bad("import-thunk reference atlas join is absent")
        if (
            _rva(edge.get("source_entry_rva"), "reference source"),
            _rva(edge.get("target_entry_rva"), "reference target entry"),
            _rva(edge.get("target_rva"), "reference target"),
            atlas_record_sha256(owner),
        ) != (owner_entry, _ROOT_RVA, _ROOT_RVA, owner_atlas):
            _bad("import-thunk reference atlas join differs")
        rows.append({
            "instruction_rva": _hex(site),
            "instruction_size": 5,
            "instruction_sha256": hashlib.sha256(bytes.fromhex(encoded)).hexdigest(),
            "owner_entry_rva": _hex(owner_entry),
            "owner_atlas_record_sha256": owner_atlas,
            "target_rva": _hex(_ROOT_RVA),
            "target_atlas_record_sha256": _ROOT_ATLAS_SHA256,
            "target_va": _hex(_IMAGE_BASE + _ROOT_RVA),
            "operand_class": "immediate",
            "operand_index": 0,
            "use_class": "direct_call",
            "call_form": "x86_relative_near_call_e8",
            "ghidra_declared_direct_edge": _normalized_declared_edge(edge),
        })
    return rows


def _reference_scan(program_facts: Mapping[str, Any], data: bytes | None = None, image: Any | None = None, decoder: Any | None = None) -> dict[str, Any]:
    references = _reference_rows(program_facts)
    owners = [
        {
            "owner_entry_rva": row["owner_entry_rva"],
            "owner_atlas_record_sha256": row["owner_atlas_record_sha256"],
            "reference_count": 1,
        }
        for row in references
    ]
    target_owners = [
        {"target_rva": _hex(_ROOT_RVA), **owner}
        for owner in owners
    ]
    target_references = [{
        "target_rva": _hex(_ROOT_RVA),
        "target_atlas_record_sha256": _ROOT_ATLAS_SHA256,
        "reference_count": len(references),
    }]
    partitions = {
        "owner_partition": _compact_sha256(owners),
        "target_owner_partition": _compact_sha256(target_owners),
        "target_reference_partition": _compact_sha256(target_references),
    }
    if partitions != _PARTITION_SHA256:
        _bad("import-thunk reference partition differs")
    result = {
        "scope": dict(_SCAN_SCOPE),
        "references": references,
        "target_partition": [{
            "target_rva": _hex(_ROOT_RVA),
            "target_atlas_record_sha256": _ROOT_ATLAS_SHA256,
            "reference_count": len(references),
            "owner_count": len(owners),
        }],
        "target_reference_partition": target_references,
        "owner_partition": owners,
        "target_owner_partition": target_owners,
        "partition_sha256": partitions,
        "aggregates": {
            "reference_count": len(references),
            "target_count": 1,
            "owner_count": len(owners),
            "target_owner_count": len(target_owners),
            "direct_call_count": len(references),
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }
    if data is None:
        return result

    import capstone.x86_const as x86

    functions = _atlas_functions(program_facts)
    actual: list[tuple[int, int, bytes]] = []
    totals = [0, 0, 0]
    assert image is not None and decoder is not None
    decoder.detail = True
    for owner_entry, function in sorted(functions.items()):
        for raw_range in _array(function.get("ranges"), "atlas range"):
            item = _mapping(raw_range, "atlas range")
            start = _rva(item.get("start_rva"), "atlas range start")
            size = item.get("size")
            instructions = _decode_range(data, image, start, size, decoder)
            totals[0] += 1
            totals[1] += size
            totals[2] += len(instructions)
            for instruction in instructions:
                for index, operand in enumerate(instruction.operands):
                    if operand.type == x86.X86_OP_IMM:
                        value, operand_class = operand.imm & 0xFFFFFFFF, "immediate"
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.segment == x86.X86_REG_INVALID
                        and operand.mem.base == x86.X86_REG_INVALID
                        and operand.mem.index == x86.X86_REG_INVALID
                    ):
                        value, operand_class = operand.mem.disp & 0xFFFFFFFF, "absolute_memory"
                    else:
                        continue
                    if value == _IMAGE_BASE + _ROOT_RVA:
                        actual.append((instruction.address - image.image_base, index, bytes(instruction.bytes), operand_class))
    expected = [(site, 0, bytes.fromhex(encoded), "immediate") for site, _owner, encoded, _atlas in _REFERENCE_SITES]
    if tuple(totals) != (25490, 3735718, 1153814) or actual != expected:
        _bad("exhaustive import-thunk reference scan differs")
    return result


def _iat_slot_use_scan(program_facts: Mapping[str, Any], data: bytes | None = None, image: Any | None = None, decoder: Any | None = None) -> dict[str, Any]:
    """Seal the complete atlas use-set for the IAT-slot VA itself."""
    reference = {
        "instruction_rva": _hex(_ROOT_RVA),
        "instruction_size": _ROOT_SIZE,
        "instruction_sha256": hashlib.sha256(bytes.fromhex(_ROOT_BYTES)).hexdigest(),
        "owner_entry_rva": _hex(_ROOT_RVA),
        "owner_atlas_record_sha256": _ROOT_ATLAS_SHA256,
        "operand_class": "absolute_memory",
        "operand_index": 0,
        "operand_access": "read",
        "operand_va": _hex(_IAT_VA),
        "operand_rva": _hex(_IAT_RVA),
        "control_syntax": "x86_absolute_memory_indirect_jump_ff25",
    }
    result = {
        "scope": dict(_SCAN_SCOPE),
        "scanned_operand_va": _hex(_IAT_VA),
        "scanned_operand_rva": _hex(_IAT_RVA),
        "references": [reference],
        "aggregates": {
            "reference_count": 1,
            "owner_count": 1,
            "absolute_memory_operand_count": 1,
            "indirect_jump_count": 1,
        },
    }
    if data is None:
        return result

    import capstone.x86_const as x86

    functions = _atlas_functions(program_facts)
    actual: list[tuple[int, int, bytes, int, str]] = []
    totals = [0, 0, 0]
    assert image is not None and decoder is not None
    decoder.detail = True
    for _owner_entry, function in sorted(functions.items()):
        for raw_range in _array(function.get("ranges"), "atlas range"):
            item = _mapping(raw_range, "atlas range")
            start = _rva(item.get("start_rva"), "atlas range start")
            size = item.get("size")
            instructions = _decode_range(data, image, start, size, decoder)
            totals[0] += 1
            totals[1] += size
            totals[2] += len(instructions)
            for instruction in instructions:
                for index, operand in enumerate(instruction.operands):
                    if operand.type == x86.X86_OP_IMM:
                        value = operand.imm & 0xFFFFFFFF
                        operand_class = "immediate"
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.segment == x86.X86_REG_INVALID
                        and operand.mem.base == x86.X86_REG_INVALID
                        and operand.mem.index == x86.X86_REG_INVALID
                    ):
                        value = operand.mem.disp & 0xFFFFFFFF
                        operand_class = "absolute_memory"
                    else:
                        continue
                    if value == _IAT_VA:
                        actual.append((
                            instruction.address - image.image_base,
                            index,
                            bytes(instruction.bytes),
                            operand.access,
                            operand_class,
                        ))
    expected = [(_ROOT_RVA, 0, bytes.fromhex(_ROOT_BYTES), 1, "absolute_memory")]
    if tuple(totals) != (25490, 3735718, 1153814) or actual != expected:
        _bad("exhaustive IAT-slot use scan differs")
    return result


def _preflight(predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if identity.get("executable_sha256") != _EXE_SHA256:
        _bad("program facts executable identity differs")
    if not _same(predecessor.get("build_identity"), identity) or not _same(direct.get("build_identity"), identity):
        _bad("prerequisite build identity differs")
    if _canonical_sha256(predecessor) != _PREDECESSOR_SHA256 or predecessor.get("analysis_kind") != PREDECESSOR_KIND:
        _bad("predecessor receipt differs")
    direct_receipt = validate_native_lua_direct_call_structure(direct, facts)
    if direct_receipt.get("status") != "structurally_verified" or direct_receipt.get("evidence_sha256") != _DIRECT_SHA256:
        _bad("direct-call prerequisite differs")
    return {
        "program_facts": _source_identity(facts, "pe_ghidra_program_facts", _FACTS_SHA256, "program facts"),
        "predecessor_static_boundary": _source_identity(predecessor, PREDECESSOR_KIND, _PREDECESSOR_SHA256, "predecessor"),
        "direct_call_census": _source_identity(direct, DIRECT_KIND, _DIRECT_SHA256, "direct calls"),
    }


def _parent_edge(predecessor: Mapping[str, Any]) -> list[dict[str, Any]]:
    calls = _mapping(predecessor.get("native_calls"), "predecessor native calls")
    rows = [dict(_mapping(item, "predecessor outgoing edge")) for item in _array(calls.get("outgoing_direct"), "predecessor outgoing edges")]
    match = [
        row for row in rows
        if _rva(_mapping(row.get("instruction"), "parent instruction").get("rva"), "parent site") == 0x00357B75
        and _rva(row.get("target_entry_rva"), "parent target") == _ROOT_RVA
    ]
    if len(rows) != 2 or len(match) != 1 or match[0].get("control_encoding") != "e8":
        _bad("predecessor parent edge differs")
    if not _same(match[0].get("instruction"), _instruction(0x00357B75, "e818500400")):
        _bad("predecessor parent bytes differ")
    return match


def _summary() -> dict[str, Any]:
    return {
        "reviewed_target_count": 1,
        "reviewed_target_bytes": 6,
        "sealed_instruction_count": 1,
        "sealed_control_flow_graph_count": 1,
        "sealed_control_flow_graph_node_count": 1,
        "sealed_control_flow_graph_edge_count": 0,
        "native_direct_edge_count": 0,
        "direct_lua_call_count": 0,
        "staged_lua_dispatch_count": 0,
        "call_r32_count": 0,
        "opaque_indirect_control_count": 1,
        "pe_address_operand_count": 1,
        "pe_immediate_operand_count": 0,
        "pe_absolute_memory_operand_count": 1,
        "pe_import_metadata_count": 1,
        "segment_qualified_memory_syntax_count": 0,
        "bnd_prefixed_control_syntax_count": 0,
        "opaque_interrupt_syntax_count": 0,
        "predecessor_parent_edge_count": 1,
        "target_reference_count": 6,
        "target_reference_target_count": 1,
        "target_reference_owner_count": 6,
        "target_reference_direct_call_count": 6,
        "target_reference_other_address_count": 0,
        "target_reference_memory_operand_count": 0,
        "schema_violations": 0,
    }


def _evidence(predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, instructions: list[Any] | None = None, image: Any | None = None, scan: Mapping[str, Any] | None = None, iat_scan: Mapping[str, Any] | None = None) -> dict[str, Any]:
    prerequisites = _preflight(predecessor, direct, facts)
    decoded = _decode_root() if instructions is None else instructions
    raw = b"".join(bytes(item.bytes) for item in decoded)
    function = _atlas_functions(facts).get(_ROOT_RVA)
    if raw != bytes.fromhex(_ROOT_BYTES) or hashlib.sha256(raw).hexdigest() != _ROOT_BODY_SHA256:
        _bad("import-thunk body differs")
    if function is None or (function.get("body_size"), function.get("body_sha256"), atlas_record_sha256(function)) != (_ROOT_SIZE, _ROOT_BODY_SHA256, _ROOT_ATLAS_SHA256):
        _bad("import-thunk atlas record differs")
    whole_scan = _reference_scan(facts) if scan is None else dict(scan)
    if not _same(whole_scan, _reference_scan(facts)):
        _bad("import-thunk scan receipt differs")
    slot_scan = _iat_slot_use_scan(facts) if iat_scan is None else dict(iat_scan)
    if not _same(slot_scan, _iat_slot_use_scan(facts)):
        _bad("IAT-slot use scan receipt differs")
    parent = _parent_edge(predecessor)
    if whole_scan["references"][0]["instruction_rva"] != parent[0]["instruction"]["rva"]:
        _bad("predecessor parent does not join import-thunk scan")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(_mapping(facts.get("identity"), "program facts identity")),
        "program_facts": prerequisites["program_facts"],
        "predecessor_static_boundary": prerequisites["predecessor_static_boundary"],
        "direct_call_census": prerequisites["direct_call_census"],
        "decoder": {
            "name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86", "mode_bits": 32, "sealed_instruction_count": 1,
            "register_call_encoding_audit": [
                {"register": register, "encoding": f"ff{0xd0 + index:02x}"}
                for index, register in enumerate(_REGISTER_NAMES)
            ],
        },
        "function_body": {
            "role": "external_import_thunk_opaque_static_boundary",
            "entry_rva": _hex(_ROOT_RVA),
            "atlas_record_sha256": _ROOT_ATLAS_SHA256,
            "body_size": _ROOT_SIZE,
            "body_sha256": _ROOT_BODY_SHA256,
            "range_start_rva": _hex(_ROOT_RVA),
            "range_size": _ROOT_SIZE,
            "control_flow_graph_canonical_sha256": _CFG_SHA256,
            "reviewed_points": _reviewed_points(decoded),
            "direct_lua_calls": [],
            "staged_lua_dispatches": [],
            "call_r32_audit": _empty_register_audit(),
            "register_call_partition_complete": True,
            "semantic_facts": {
                "relationship_defined_only": True,
                "analysis_labels_opaque": True,
                "source_semantic_names_assigned": False,
                "runtime_or_success_claimed": False,
                "import_metadata_only": True,
            },
        },
        "control_flow_graph": _graph(decoded),
        "predecessor_parent_edges": parent,
        "native_calls": _native_syntax(image),
        "whole_atlas_reference_scan": whole_scan,
        "whole_atlas_iat_slot_use_scan": slot_scan,
        "method": {
            "structural_boundary": "The receipt seals one FF25 absolute-memory indirect jump, its PE IAT import metadata, the predecessor parent, and a six-row direct-call atlas frontier.",
            "not_claimed": [
                "analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return",
                "runtime reachability, invocation, ordering, frequency, state mutation, termination, target resolution, execution, or effect",
                "contents or runtime meaning of the IAT slot or imported target",
                "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
            ],
        },
        "summary": _summary(),
    }


def _normalize(action: Any) -> Any:
    try:
        return action()
    except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError:
        raise
    except (
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaClassReturnHelperChainError,
        PEAnchorError,
        CsError,
        struct.error,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError(str(exc)) from exc


def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary_structure(evidence: Mapping[str, Any], predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    """Recreate the finite receipt without opening the executable."""
    def run() -> dict[str, Any]:
        for value, label in ((evidence, "evidence"), (predecessor, "predecessor"), (direct, "direct"), (facts, "program facts")):
            _validate_json_tree(value, label)
        expected = _evidence(predecessor, direct, facts)
        if not _same(evidence, expected):
            _bad("import-thunk receipt differs from sealed structure")
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
            "build_identity": dict(evidence["build_identity"]),
            "evidence_sha256": _canonical_sha256(evidence),
            "summary": dict(evidence["summary"]),
        }
    return _normalize(run)


def build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary(executable: Path, predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Build the sealed receipt with exact PE bytes and a TOCTOU digest recheck."""
    def run() -> dict[str, Any]:
        for value, label in ((predecessor, "predecessor"), (direct, "direct"), (facts, "program facts"), (inventory, "inventory")):
            _validate_json_tree(value, label)
        direct_receipt = validate_native_lua_direct_call_census(executable, direct, facts, inventory=inventory)
        if direct_receipt.get("status") != "verified" or direct_receipt.get("evidence_sha256") != _DIRECT_SHA256:
            _bad("exact direct-call prerequisite differs")
        data, image, digest = _load_executable(executable)
        if digest != _EXE_SHA256 or image.image_base != _IMAGE_BASE:
            _bad("executable identity differs")
        decoder, _ = _decoder()
        decoder.detail = True
        instructions = _decode_range(data, image, _ROOT_RVA, _ROOT_SIZE, decoder)
        result = _evidence(
            predecessor,
            direct,
            facts,
            instructions=instructions,
            image=image,
            scan=_reference_scan(facts, data, image, decoder),
            iat_scan=_iat_slot_use_scan(facts, data, image, decoder),
        )
        if _load_executable(executable)[2] != digest:
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary_structure(result, predecessor, direct, facts)
        return result
    return _normalize(run)


def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary(executable: Path, evidence: Mapping[str, Any], predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary(executable, predecessor, direct, facts, inventory=inventory)
        if not _same(evidence, rebuilt):
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


def encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary(value: Mapping[str, Any]) -> str:
    def run() -> str:
        _validate_json_tree(value, "receipt")
        _mapping(value, "encoded value")
        return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    return _normalize(run)
