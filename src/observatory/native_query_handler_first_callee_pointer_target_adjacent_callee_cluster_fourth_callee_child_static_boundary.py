"""Fail-closed static receipt for the three-byte ``call eax; ret`` child.

Names, the register value at call time, and runtime effects intentionally remain
opaque.  This receipt proves only the bounded PE, atlas, caller, and operand
relationships reproduced below.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _decode_range,
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_class_return_helper_chain import (
    _REGISTER_NAMES,
    _canonical_bytes,
    _canonical_sha256,
    _enhanced_cfg,
    _source_identity,
    _with_edi_writes,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary import (
    ANALYSIS_KIND as FOURTH_KIND,
)
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary import (
    ANALYSIS_KIND as SECOND_KIND,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_FOURTH = "1faeeefe0ee5d9bc9a85ad673133dc7936a02cfea50beb5cd70d72fc36bcb9c5"
_SECOND = "ec66ae66eb932cb59f52ca3ad9095c31bb887723ed7647aef4eeeb0aaa64389d"
_BASE, _ENTRY, _SIZE = 0x400000, 0x378A34, 3
_RAW = "ffd0c3"
_BODY = "94abb6fadbcdb595e2ba8c9a673e591fec8944a2eb04edee55a9ecc56b893047"
_ATLAS = "28e6f200d780328c2667ced90607e5aa26165fa2b59903ba8ae560419766abd1"
_CFG = "a67693cd807e1cc1cf1bb9ee18751f6bdcb1e96d6f9d7595f8370fffe682cc92"
_SCOPE = {
    "atlas_function_count": 25312,
    "atlas_body_range_count": 25490,
    "decoded_bytes": 3735718,
    "decoded_instructions": 1153814,
    "all_declared_ranges_decoded": True,
    "operand_classes": ["absolute_memory", "immediate"],
}
_INCOMING = (
    (
        0x3789D0,
        0x378965,
        "e85f000000",
        "0a78954b488836ef11c4da3d936c0b1092ab9512612c03eabf47f90f9846a7fd",
    ),
    (
        0x378ABB,
        0x378A40,
        "e874ffffff",
        "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
    ),
)
_PARTITION_HASHES = {
    "owner_partition": "d3e73d4ab6f5d6899fe855138d487f697a3c5cce0bdd8aa43875ab6255d92d94",
    "target_partition": "f69834aa6a98745f4c321165f74ead6aee9f8f98770f312fb237fd9efe200a3e",
    "target_owner_partition": "7e02ea8028c10f6798ac00c9963513b52bfd94cee32d93f911a30cb8dfdb8076",
    "target_reference_partition": "ab8617cfd98eedf55d4469c51c3f20e05ce813119a42ccbf3bdb0b150bd93ba5",
}
_REFERENCE_HASH = "2a9c27df8de63d55d3499216cecc2b786fdab5c0145fd47cbada0c27adbeeaf0"
_CALLERS = (
    {
        "owner": 0x378965,
        "size": 132,
        "body": "3a4f91c8543fc061384448e7b6514d862236c568383e896590e467844ddc109a",
        "atlas": "0a78954b488836ef11c4da3d936c0b1092ab9512612c03eabf47f90f9846a7fd",
        "name": "__local_unwind2",
        "name_source": "ANALYSIS",
        "cfg": "eee9f69df3ba913a0ff01962b6f66c5055517839477392a58693281022eff113",
        "loader_site": 0x3789CC,
        "loader_raw": "8b44b308",
        "base_register": "ebx",
        "index_register": "esi",
        "scale": 4,
        "displacement": 8,
        "call_site": 0x3789D0,
        "call_raw": "e85f000000",
        "loader_call_raw": "8b44b308e85f000000",
        "loader_call_sha256": "d29e69be696f680277f8af2c0360387edae6a53d3bb10be208e4f36558419332",
        "paired_start": 0x3789C3,
        "paired_raw": "8b44b308e8490000008b44b308e85f000000",
        "paired_sha256": "b97780aac2c289359da9e75e3a18f65874633668091090f781aa7d0f40d457ad",
        "prior_call_site": 0x3789C7,
        "prior_call_raw": "e849000000",
    },
    {
        "owner": 0x378A40,
        "size": 144,
        "body": "c75af58d5bf56eae591044575adab9c6c3a2861576a9524fa38e4854960c99da",
        "atlas": "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
        "name": "__local_unwind4",
        "name_source": "ANALYSIS",
        "cfg": "3dbfa70a1195e11c64f0856fb189dd662b8740f445e2b2a00d3fd36c5044e9e1",
        "loader_site": 0x378AB8,
        "loader_raw": "8b4308",
        "base_register": "ebx",
        "index_register": None,
        "scale": 1,
        "displacement": 8,
        "call_site": 0x378ABB,
        "call_raw": "e874ffffff",
        "loader_call_raw": "8b4308e874ffffff",
        "loader_call_sha256": "8360eb94c15b023c39811dc84341ffde5af939280ef7adca3f48f7ede00f7edf",
        "paired_start": 0x378AAB,
        "paired_raw": "8b4308e862ffffffb9010000008b4308e874ffffff",
        "paired_sha256": "e218f75f0a9bc7b33729b20a96965c03ee4bef81a5a1741f5d553a7fe7297584",
        "prior_call_site": 0x378AAE,
        "prior_call_raw": "e862ffffff",
    },
)


class NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeChildStaticBoundaryError(
    RuntimeError
):
    """Raised whenever this deliberately narrow static proof no longer holds."""


def _bad(message: str) -> None:
    raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeChildStaticBoundaryError(
        message
    )


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _compact(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _instruction(rva: int, raw: str) -> dict[str, Any]:
    data = bytes.fromhex(raw)
    return {
        "rva": _hex(rva),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _edges(facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw in _array(
        facts.get("ghidra_declared_direct_calls"), "declared direct calls"
    ):
        edge = _mapping(raw, "declared direct call")
        site = _rva(edge.get("instruction_rva"), "direct site")
        if site in result:
            _bad("duplicate declared direct-call site")
        result[site] = edge
    return result


def _normalized_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    name = edge.get("target_name")
    if type(name) is not str:
        _bad("direct edge lacks a label")
    return {
        "instruction_rva": _hex(_rva(edge.get("instruction_rva"), "edge site")),
        "source_entry_rva": _hex(_rva(edge.get("source_entry_rva"), "edge source")),
        "target_entry_rva": _hex(_rva(edge.get("target_entry_rva"), "edge target")),
        "target_rva": _hex(_rva(edge.get("target_rva"), "edge target")),
        "target_name_sha256": hashlib.sha256(name.encode()).hexdigest(),
    }


def _decode(raw: bytes = bytes.fromhex(_RAW)) -> list[Any]:
    if raw != bytes.fromhex(_RAW):
        _bad("sealed child raw bytes differ")
    decoder, _ = _decoder()
    decoder.detail = True
    rows = list(decoder.disasm(raw, _BASE + _ENTRY))
    if len(rows) != 2 or b"".join(bytes(row.bytes) for row in rows) != raw:
        _bad("sealed child bytes do not decode exactly")
    return rows


def _graph(rows: list[Any] | None = None) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    decoded = _decode() if rows is None else rows
    graph = _with_edi_writes(
        _enhanced_cfg(decoded, _BASE, (_ENTRY, _SIZE), capstone, x86), decoded, x86
    )
    graph["caller_entry_rva"] = _hex(_ENTRY)
    if (graph.get("node_count"), graph.get("edge_count")) != (
        2,
        1,
    ) or _canonical_sha256(graph) != _CFG:
        _bad("sealed child control-flow graph differs")
    return graph


def _preflight(
    fourth: Mapping[str, Any],
    second: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    for value, label in (
        (fourth, "fourth-callee receipt"),
        (second, "second-callee receipt"),
        (direct, "direct-call census"),
        (facts, "program facts"),
    ):
        if not isinstance(value, Mapping):
            _bad(f"{label} must be an object")
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if identity.get("executable_sha256") != _EXE or not all(
        _same(value.get("build_identity"), identity)
        for value in (fourth, second, direct)
    ):
        _bad("prerequisite build identity differs")
    if (
        fourth.get("analysis_kind") != FOURTH_KIND
        or _canonical_sha256(fourth) != _FOURTH
    ):
        _bad("fourth-callee receipt differs")
    if (
        second.get("analysis_kind") != SECOND_KIND
        or _canonical_sha256(second) != _SECOND
    ):
        _bad("second-callee receipt differs")
    return {
        "program_facts": _source_identity(
            facts, "pe_ghidra_program_facts", _FACTS, "program facts"
        ),
        "fourth_callee_static_boundary": _source_identity(
            fourth, FOURTH_KIND, _FOURTH, "fourth callee"
        ),
        "second_callee_static_boundary": _source_identity(
            second, SECOND_KIND, _SECOND, "second callee"
        ),
        "direct_call_census": _source_identity(
            direct, DIRECT_KIND, _DIRECT, "direct-call census"
        ),
    }


def _target(facts: Mapping[str, Any]) -> Mapping[str, Any]:
    target = _atlas_functions(facts).get(_ENTRY)
    if target is None or (
        target.get("body_size"),
        target.get("body_sha256"),
        atlas_record_sha256(target),
        target.get("name"),
        target.get("namespace"),
        target.get("name_source"),
        target.get("thunk"),
    ) != (_SIZE, _BODY, _ATLAS, "FUN_00778a34", "Global", "DEFAULT", False):
        _bad("child atlas record differs")
    if not _same(target.get("ranges"), [{"start_rva": _hex(_ENTRY), "size": _SIZE}]):
        _bad("child atlas range differs")
    return target


def _boundaries(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    functions = _atlas_functions(facts)
    expected = (
        (
            "left_neighbor",
            0x378A15,
            31,
            "bfc32dca1a2879c053683385362acc34071b244f56f0724b2ec96d15f6660f29",
            "6bf2ee0e68ff7a0c12250248e928bae616b939421135f8b679081c4903dedb81",
            "__NLG_Notify",
            "ANALYSIS",
        ),
        (
            "right_neighbor",
            0x378A40,
            144,
            "c75af58d5bf56eae591044575adab9c6c3a2861576a9524fa38e4854960c99da",
            "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
            "__local_unwind4",
            "ANALYSIS",
        ),
    )
    result: dict[str, Any] = {
        "layout_only": True,
        "semantic_kinship_claimed": False,
        "left_neighbor_ends_at_target": True,
        "target_ends_at_right_gap": True,
        "right_gap_ends_at_right_neighbor": True,
    }
    for role, entry, size, body, atlas, name, source in expected:
        row = functions.get(entry)
        if row is None or (
            row.get("body_size"),
            row.get("body_sha256"),
            atlas_record_sha256(row),
            row.get("name"),
            row.get("namespace"),
            row.get("name_source"),
            row.get("thunk"),
        ) != (size, body, atlas, name, "Global", source, False):
            _bad("adjacent atlas boundary differs")
        if not _same(row.get("ranges"), [{"start_rva": _hex(entry), "size": size}]):
            _bad("adjacent atlas range differs")
        result[role] = {
            "entry_rva": _hex(entry),
            "body_size": size,
            "body_sha256": body,
            "atlas_record_sha256": atlas,
            "range_start_rva": _hex(entry),
            "range_end_rva_exclusive": _hex(entry + size),
            "ghidra_analysis_metadata": {
                "name": name,
                "namespace": "Global",
                "name_source": source,
                "thunk": False,
                "metadata_only": True,
            },
        }
    ranges = []
    for owner, function in functions.items():
        for raw_range in _array(function.get("ranges"), "atlas range"):
            span = _mapping(raw_range, "atlas range")
            start = _rva(span.get("start_rva"), "range start")
            size = span.get("size")
            if type(size) is not int or size <= 0:
                _bad("invalid atlas range")
            ranges.append((start, start + size, owner))
    overlaps = [row for row in ranges if row[0] < _ENTRY + _SIZE and _ENTRY < row[1]]
    predecessors = [row for row in ranges if row[1] <= _ENTRY]
    successors = [row for row in ranges if row[0] >= _ENTRY + _SIZE]
    if (
        overlaps != [(_ENTRY, _ENTRY + _SIZE, _ENTRY)]
        or max(predecessors, key=lambda row: (row[1], row[0]))
        != (0x378A15, 0x378A34, 0x378A15)
        or min(successors, key=lambda row: (row[0], row[1]))
        != (0x378A40, 0x378AD0, 0x378A40)
    ):
        _bad("nearest atlas boundary partition differs")
    gap = bytes.fromhex("cccccccccccccccccc")
    result["right_un_atlased_gap"] = {
        "start_rva": "0x00378a37",
        "end_rva_exclusive": "0x00378a40",
        "size": 9,
        "section_name": ".text",
        "file_offset": "0x00377e37",
        "bytes_sha256": hashlib.sha256(gap).hexdigest(),
        "atlas_owned": False,
        "contents_or_runtime_behavior_opaque": True,
    }
    if image is not None:
        section = next(
            (
                row
                for row in image.sections
                if row.virtual_address
                <= _ENTRY
                < row.virtual_address + row.virtual_size
            ),
            None,
        )
        if section is None or (
            section.name,
            section.virtual_address,
            section.virtual_size,
            section.raw_size,
            section.raw_offset,
            section.characteristics,
        ) != (".text", 0x1000, 0x3D4B4E, 0x3D4C00, 0x400, 0x60000020):
            _bad("boundary PE section differs")
        offset = image.rva_span_to_file_offset(0x378A37, len(gap))
        if offset != 0x377E37 or image.data[offset : offset + len(gap)] != gap:
            _bad("right gap backing differs")
        for entry, size, body, label in (
            (
                0x378A15,
                31,
                "bfc32dca1a2879c053683385362acc34071b244f56f0724b2ec96d15f6660f29",
                "left neighbor",
            ),
            (
                0x378A40,
                144,
                "c75af58d5bf56eae591044575adab9c6c3a2861576a9524fa38e4854960c99da",
                "right neighbor",
            ),
        ):
            neighbor_offset = image.rva_span_to_file_offset(entry, size)
            if (
                hashlib.sha256(
                    image.data[neighbor_offset : neighbor_offset + size]
                ).hexdigest()
                != body
            ):
                _bad(f"{label} PE backing differs")
    return result


def _target_pe_backing(image: Any | None = None) -> dict[str, Any]:
    result = {
        "section_name": ".text",
        "section_rva": "0x00001000",
        "section_virtual_size": "0x003d4b4e",
        "section_raw_size": "0x003d4c00",
        "section_raw_offset": "0x00000400",
        "section_characteristics": "0x60000020",
        "section_writable": False,
        "file_backed": True,
        "file_offset": "0x00377e34",
    }
    if image is not None:
        section = next(
            (
                row
                for row in image.sections
                if row.virtual_address
                <= _ENTRY
                < row.virtual_address + row.virtual_size
            ),
            None,
        )
        offset = image.rva_span_to_file_offset(_ENTRY, _SIZE)
        if (
            section is None
            or (
                section.name,
                section.virtual_address,
                section.virtual_size,
                section.raw_size,
                section.raw_offset,
                section.characteristics,
                offset,
            )
            != (".text", 0x1000, 0x3D4B4E, 0x3D4C00, 0x400, 0x60000020, 0x377E34)
            or image.data[offset : offset + _SIZE] != bytes.fromhex(_RAW)
        ):
            _bad("child PE backing differs")
    return result


def _expected_incoming(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    sites = {
        site
        for site, edge in edges.items()
        if _rva(edge.get("target_entry_rva"), "incoming target") == _ENTRY
    }
    if sites != {row[0] for row in _INCOMING}:
        _bad("incoming direct-edge frontier differs")
    records = []
    for site, owner, raw, owner_atlas in _INCOMING:
        edge, owner_row = edges.get(site), functions.get(owner)
        if (
            edge is None
            or owner_row is None
            or (
                _rva(edge.get("source_entry_rva"), "incoming source"),
                _rva(edge.get("target_entry_rva"), "incoming target"),
                _rva(edge.get("target_rva"), "incoming target"),
                atlas_record_sha256(owner_row),
            )
            != (owner, _ENTRY, _ENTRY, owner_atlas)
        ):
            _bad("incoming direct-edge cross-join differs")
        records.append(
            {
                "instruction_rva": _hex(site),
                "instruction_size": 5,
                "instruction_sha256": hashlib.sha256(bytes.fromhex(raw)).hexdigest(),
                "owner_entry_rva": _hex(owner),
                "owner_atlas_record_sha256": owner_atlas,
                "target_rva": _hex(_ENTRY),
                "target_atlas_record_sha256": _ATLAS,
                "target_va": _hex(_BASE + _ENTRY),
                "operand_class": "immediate",
                "operand_index": 0,
                "use_class": "direct_call",
                "call_form": "x86_relative_near_call_e8",
                "ghidra_declared_direct_edge": _normalized_edge(edge),
            }
        )
    return records


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    records = _expected_incoming(facts)
    owner_partition = [
        {
            "owner_entry_rva": row["owner_entry_rva"],
            "owner_atlas_record_sha256": row["owner_atlas_record_sha256"],
            "reference_count": 1,
        }
        for row in records
    ]
    target_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 2,
            "owner_count": 2,
        }
    ]
    target_owner_partition = [
        {"target_rva": _hex(_ENTRY), **row} for row in owner_partition
    ]
    target_reference_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 2,
        }
    ]
    hashes = {
        "owner_partition": _compact(owner_partition),
        "target_partition": _compact(target_partition),
        "target_owner_partition": _compact(target_owner_partition),
        "target_reference_partition": _compact(target_reference_partition),
    }
    if hashes != _PARTITION_HASHES or _compact(records) != _REFERENCE_HASH:
        _bad("target-reference hash differs")
    return {
        "target_rvas": [_hex(_ENTRY)],
        "target_vas": [_hex(_BASE + _ENTRY)],
        "scope": dict(_SCOPE),
        "references": records,
        "target_partition": target_partition,
        "owner_partition": owner_partition,
        "target_owner_partition": target_owner_partition,
        "target_reference_partition": target_reference_partition,
        "partition_sha256": hashes,
        "references_canonical_sha256": _REFERENCE_HASH,
        "aggregates": {
            "reference_count": 2,
            "target_count": 1,
            "owner_count": 2,
            "target_owner_count": 2,
            "direct_call_count": 2,
            "comparison_count": 0,
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }


def _caller_provenance(
    facts: Mapping[str, Any],
    image: Any | None = None,
    data: bytes | None = None,
    decoder: Any | None = None,
) -> list[dict[str, Any]]:
    import capstone
    import capstone.x86_const as x86

    functions = _atlas_functions(facts)
    records: list[dict[str, Any]] = []
    for spec in _CALLERS:
        owner, size = spec["owner"], spec["size"]
        row = functions.get(owner)
        if row is None or (
            row.get("body_size"),
            row.get("body_sha256"),
            atlas_record_sha256(row),
            row.get("name"),
            row.get("namespace"),
            row.get("name_source"),
            row.get("thunk"),
        ) != (
            size,
            spec["body"],
            spec["atlas"],
            spec["name"],
            "Global",
            spec["name_source"],
            False,
        ):
            _bad("caller atlas provenance differs")
        if not _same(row.get("ranges"), [{"start_rva": _hex(owner), "size": size}]):
            _bad("caller atlas range differs")

        graph_record = {
            "canonical_sha256": spec["cfg"],
            "node_count": 42 if owner == 0x378965 else 48,
            "edge_count": 45 if owner == 0x378965 else 51,
        }
        loader_reads = [spec["base_register"]]
        if spec["index_register"] is not None:
            loader_reads.append(spec["index_register"])
        if image is not None:
            if data is None or decoder is None:
                _bad("caller PE validation needs decoder and bytes")
            decoder.detail = True
            decoded = _decode_range(data, image, owner, size, decoder)
            by_rva = {item.address - image.image_base: item for item in decoded}
            if len(by_rva) != len(decoded):
                _bad("caller decoder emitted duplicate instruction sites")
            offset = image.rva_span_to_file_offset(owner, size)
            caller_raw = data[offset : offset + size]
            if (
                len(caller_raw) != size
                or hashlib.sha256(caller_raw).hexdigest() != spec["body"]
                or b"".join(bytes(item.bytes) for item in decoded) != caller_raw
            ):
                _bad("caller PE body differs")

            graph = _with_edi_writes(
                _enhanced_cfg(
                    decoded,
                    image.image_base,
                    (owner, size),
                    capstone,
                    x86,
                ),
                decoded,
                x86,
            )
            graph["caller_entry_rva"] = _hex(owner)
            if (graph.get("node_count"), graph.get("edge_count")) != (
                graph_record["node_count"],
                graph_record["edge_count"],
            ) or _canonical_sha256(graph) != spec["cfg"]:
                _bad("caller control-flow graph differs")

            loader = by_rva.get(spec["loader_site"])
            call = by_rva.get(spec["call_site"])
            prior = by_rva.get(spec["prior_call_site"])
            if (
                loader is None
                or call is None
                or prior is None
                or bytes(loader.bytes) != bytes.fromhex(spec["loader_raw"])
                or bytes(call.bytes) != bytes.fromhex(spec["call_raw"])
                or bytes(prior.bytes) != bytes.fromhex(spec["prior_call_raw"])
            ):
                _bad("caller loader or direct-call bytes differ")

            if (
                loader.id != x86.X86_INS_MOV
                or len(loader.operands) != 2
                or loader.operands[0].type != x86.X86_OP_REG
                or loader.operands[0].reg != x86.X86_REG_EAX
                or loader.operands[1].type != x86.X86_OP_MEM
            ):
                _bad("caller EAX loader semantics differ")
            memory = loader.operands[1].mem
            expected_base = getattr(x86, "X86_REG_" + spec["base_register"].upper())
            expected_index = (
                x86.X86_REG_INVALID
                if spec["index_register"] is None
                else getattr(x86, "X86_REG_" + spec["index_register"].upper())
            )
            if (
                memory.segment != x86.X86_REG_INVALID
                or memory.base != expected_base
                or memory.index != expected_index
                or memory.scale != spec["scale"]
                or memory.disp != spec["displacement"]
            ):
                _bad("caller EAX loader address expression differs")
            try:
                reads, writes = loader.regs_access()
            except Exception as exc:  # pragma: no cover - decoder contract failure
                _bad(f"caller loader register access failed: {exc}")
            if sorted(loader.reg_name(register) for register in reads) != sorted(
                loader_reads
            ) or sorted(loader.reg_name(register) for register in writes) != ["eax"]:
                _bad("caller EAX loader register access differs")

            for instruction, target, label in (
                (call, _ENTRY, "child call"),
                (prior, 0x378A15, "prior call"),
            ):
                if (
                    instruction.id != x86.X86_INS_CALL
                    or len(instruction.operands) != 1
                    or instruction.operands[0].type != x86.X86_OP_IMM
                    or (int(instruction.operands[0].imm) & 0xFFFFFFFF)
                    != image.image_base + target
                ):
                    _bad(f"caller {label} semantics differ")

            nodes = {
                _rva(node.get("rva"), "caller CFG node"): node
                for node in _array(graph.get("nodes"), "caller CFG nodes")
            }
            predecessors: dict[int, list[int]] = {site: [] for site in nodes}
            for source, node in nodes.items():
                for successor in _array(
                    node.get("successor_rvas"), "caller CFG successors"
                ):
                    target = _rva(successor, "caller CFG successor")
                    if target in predecessors:
                        predecessors[target].append(source)
            if (
                spec["loader_site"] + len(bytes(loader.bytes)) != spec["call_site"]
                or predecessors.get(spec["call_site"]) != [spec["loader_site"]]
                or nodes[spec["loader_site"]].get("successor_rvas")
                != [_hex(spec["call_site"])]
            ):
                _bad("caller loader is not the unique child-call predecessor")

            for start_key, raw_key, hash_key, label in (
                (
                    "loader_site",
                    "loader_call_raw",
                    "loader_call_sha256",
                    "loader-call window",
                ),
                (
                    "paired_start",
                    "paired_raw",
                    "paired_sha256",
                    "paired-call window",
                ),
            ):
                raw = bytes.fromhex(spec[raw_key])
                window_offset = image.rva_span_to_file_offset(spec[start_key], len(raw))
                observed = data[window_offset : window_offset + len(raw)]
                if (
                    observed != raw
                    or hashlib.sha256(observed).hexdigest() != spec[hash_key]
                ):
                    _bad(f"caller {label} differs")

        records.append(
            {
                "owner_entry_rva": _hex(owner),
                "owner_body_size": size,
                "owner_body_sha256": spec["body"],
                "owner_atlas_record_sha256": spec["atlas"],
                "caller_metadata": {
                    "name": spec["name"],
                    "namespace": "Global",
                    "name_source": spec["name_source"],
                    "thunk": False,
                    "metadata_only": True,
                },
                "caller_control_flow_graph": graph_record,
                "prior_call_instruction": _instruction(
                    spec["prior_call_site"], spec["prior_call_raw"]
                ),
                "prior_call_target_entry_rva": "0x00378a15",
                "loader_instruction": _instruction(
                    spec["loader_site"], spec["loader_raw"]
                ),
                "loader_destination_register": "eax",
                "loader_memory_expression": {
                    "segment_register": None,
                    "base_register": spec["base_register"],
                    "index_register": spec["index_register"],
                    "scale": spec["scale"],
                    "displacement": spec["displacement"],
                },
                "loader_registers_read": sorted(loader_reads),
                "loader_registers_written": ["eax"],
                "loader_origin_class": "computed_memory",
                "loader_call_window": {
                    "start_rva": _hex(spec["loader_site"]),
                    "size": len(bytes.fromhex(spec["loader_call_raw"])),
                    "sha256": spec["loader_call_sha256"],
                },
                "paired_call_window": {
                    "start_rva": _hex(spec["paired_start"]),
                    "size": len(bytes.fromhex(spec["paired_raw"])),
                    "sha256": spec["paired_sha256"],
                },
                "call_instruction": _instruction(spec["call_site"], spec["call_raw"]),
                "call_target_entry_rva": _hex(_ENTRY),
                "loader_is_unique_cfg_predecessor": True,
                "eax_reloaded_after_prior_call": True,
                "constant_or_relocation_origin_proved": False,
                "pe_address_origin_proved": False,
                "import_table_origin_proved": False,
                "static_target_proved": False,
                "register_value_and_runtime_effect_opaque": True,
            }
        )
    return records


def _native_controls(rows: list[Any] | None = None) -> dict[str, Any]:
    import capstone.x86_const as x86

    decoded = _decode() if rows is None else rows
    if len(decoded) != 2:
        _bad("child control instruction count differs")
    call, ret = decoded
    if (
        call.address - _BASE != _ENTRY
        or bytes(call.bytes) != bytes.fromhex("ffd0")
        or call.id != x86.X86_INS_CALL
        or len(call.operands) != 1
        or call.operands[0].type != x86.X86_OP_REG
        or call.operands[0].reg != x86.X86_REG_EAX
        or ret.address - _BASE != _ENTRY + 2
        or bytes(ret.bytes) != bytes.fromhex("c3")
        or ret.id != x86.X86_INS_RET
        or ret.operands
    ):
        _bad("child CALL EAX or RET semantics differ")
    try:
        call_reads, call_writes = call.regs_access()
        ret_reads, ret_writes = ret.regs_access()
    except Exception as exc:  # pragma: no cover - decoder contract failure
        _bad(f"child register access failed: {exc}")
    access = {
        "call_instruction": {
            **_instruction(_ENTRY, "ffd0"),
            "mnemonic": "call",
            "operand_class": "register",
            "operand_index": 0,
            "operand_access": "read",
            "register": "eax",
            "registers_read": sorted(call.reg_name(value) for value in call_reads),
            "registers_written": sorted(call.reg_name(value) for value in call_writes),
        },
        "return_instruction": {
            **_instruction(_ENTRY + 2, "c3"),
            "mnemonic": "ret",
            "explicit_operand_count": 0,
            "registers_read": sorted(ret.reg_name(value) for value in ret_reads),
            "registers_written": sorted(ret.reg_name(value) for value in ret_writes),
        },
    }
    if (
        access["call_instruction"]["registers_read"] != ["eax", "esp"]
        or access["call_instruction"]["registers_written"] != ["esp"]
        or access["return_instruction"]["registers_read"] != ["esp"]
        or access["return_instruction"]["registers_written"] != ["esp"]
    ):
        _bad("child decoded register-access frontier differs")
    audit = [
        {
            "register": name,
            "call_rvas": (["0x00378a34"] if name.lower() == "eax" else []),
        }
        for name in _REGISTER_NAMES
    ]
    return {
        "outgoing_direct": [],
        "outgoing_direct_partition_complete": True,
        "direct_lua_calls": [],
        "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [],
        "staged_lua_partition_complete": True,
        "opaque_indirect_controls": [
            {
                "instruction": _instruction(_ENTRY, "ffd0"),
                "control_kind": "x86_call_r32",
                "register": "eax",
                "static_target_proved": False,
                "target_and_runtime_effect_opaque": True,
            }
        ],
        "indirect_control_partition_complete": True,
        "pe_address_operands": [],
        "pe_address_operand_partition_complete": True,
        "non_pe_immediate_literals": [],
        "non_pe_immediate_literal_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [],
        "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [],
        "opaque_interrupt_partition_complete": True,
        "explicit_ret_immediates": [],
        "explicit_ret_immediate_partition_complete": True,
        "call_r32_audit": audit,
        "register_call_partition_complete": True,
        "decoded_access": access,
    }


def _whole_atlas_reference_scan(
    data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]
) -> dict[str, Any]:
    import capstone.x86_const as x86

    found: list[tuple[int, int, int, bytes, str]] = []
    totals = [0, 0, 0]
    target_va = image.image_base + _ENTRY
    decoder.detail = True
    for owner, function in sorted(_atlas_functions(facts).items()):
        for raw_range in _array(function.get("ranges"), "atlas range"):
            span = _mapping(raw_range, "atlas range")
            start, size = _rva(span.get("start_rva"), "range start"), span.get("size")
            if type(size) is not int or size <= 0:
                _bad("invalid atlas range")
            rows = _decode_range(data, image, start, size, decoder)
            totals[0] += 1
            totals[1] += size
            totals[2] += len(rows)
            for row in rows:
                for index, operand in enumerate(row.operands):
                    if (
                        operand.type == x86.X86_OP_IMM
                        and (int(operand.imm) & 0xFFFFFFFF) == target_va
                    ):
                        found.append(
                            (
                                row.address - image.image_base,
                                owner,
                                index,
                                bytes(row.bytes),
                                "immediate",
                            )
                        )
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.segment == x86.X86_REG_INVALID
                        and operand.mem.base == x86.X86_REG_INVALID
                        and operand.mem.index == x86.X86_REG_INVALID
                        and (int(operand.mem.disp) & 0xFFFFFFFF) == target_va
                    ):
                        found.append(
                            (
                                row.address - image.image_base,
                                owner,
                                index,
                                bytes(row.bytes),
                                "absolute_memory",
                            )
                        )
    expected = [
        (site, owner, 0, bytes.fromhex(raw), "immediate")
        for site, owner, raw, _ in _INCOMING
    ]
    if (
        len(_atlas_functions(facts)) != _SCOPE["atlas_function_count"]
        or tuple(totals)
        != (
            _SCOPE["atlas_body_range_count"],
            _SCOPE["decoded_bytes"],
            _SCOPE["decoded_instructions"],
        )
        or found != expected
    ):
        _bad("all-operand target traversal differs")
    return _expected_scan(facts)


def _dependent_rejoins(
    fourth: Mapping[str, Any],
    second: Mapping[str, Any],
    incoming: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
) -> dict[str, Any]:
    fourth_calls = _array(
        _mapping(fourth.get("native_calls"), "fourth native calls").get(
            "outgoing_direct"
        ),
        "fourth outgoing direct calls",
    )
    fourth_edge = next(
        (
            _mapping(item, "fourth outgoing direct call")
            for item in fourth_calls
            if _mapping(item, "fourth outgoing direct call")
            .get("instruction", {})
            .get("rva")
            == "0x00378abb"
        ),
        None,
    )
    child_reference = next(
        item for item in incoming if item["instruction_rva"] == "0x00378abb"
    )
    if fourth_edge is None or (
        fourth_edge.get("source_entry_rva"),
        fourth_edge.get("target_entry_rva"),
        _mapping(fourth_edge.get("instruction"), "fourth child instruction").get(
            "sha256"
        ),
        fourth_edge.get("source_atlas_record_sha256"),
        fourth_edge.get("target_atlas_record_sha256"),
        fourth_edge.get("ghidra_declared_direct_edge"),
    ) != (
        "0x00378a40",
        _hex(_ENTRY),
        child_reference["instruction_sha256"],
        child_reference["owner_atlas_record_sha256"],
        child_reference["target_atlas_record_sha256"],
        child_reference["ghidra_declared_direct_edge"],
    ):
        _bad("fourth-callee child edge does not rejoin incoming scan")

    fourth_left = _mapping(
        _mapping(
            _mapping(fourth.get("function_body"), "fourth function body").get(
                "adjacent_atlas_boundaries"
            ),
            "fourth adjacent boundaries",
        ).get("left_neighbor"),
        "fourth left neighbor",
    )
    second_right = _mapping(
        _mapping(
            _mapping(second.get("function_body"), "second function body").get(
                "adjacent_atlas_boundaries"
            ),
            "second adjacent boundaries",
        ).get("right_neighbor"),
        "second right neighbor",
    )
    boundary_identity = {
        "entry_rva": _hex(_ENTRY),
        "body_size": _SIZE,
        "body_sha256": _BODY,
        "atlas_record_sha256": _ATLAS,
        "range_start_rva": _hex(_ENTRY),
        "range_end_rva_exclusive": _hex(_ENTRY + _SIZE),
    }
    for neighbor in (fourth_left, second_right):
        if any(neighbor.get(key) != value for key, value in boundary_identity.items()):
            _bad("dependent adjacent boundary does not rejoin child")

    second_references = _array(
        _mapping(second.get("whole_atlas_reference_scan"), "second reference scan").get(
            "references"
        ),
        "second references",
    )
    prior_rejoins = []
    for caller in provenance:
        prior = _mapping(caller.get("prior_call_instruction"), "prior call")
        match = next(
            (
                _mapping(item, "second reference")
                for item in second_references
                if _mapping(item, "second reference").get("instruction_rva")
                == prior.get("rva")
            ),
            None,
        )
        if match is None or (
            match.get("instruction_sha256"),
            match.get("owner_entry_rva"),
            match.get("owner_atlas_record_sha256"),
            match.get("target_rva"),
        ) != (
            prior.get("sha256"),
            caller["owner_entry_rva"],
            caller["owner_atlas_record_sha256"],
            "0x00378a15",
        ):
            _bad("second-callee prior call does not rejoin caller provenance")
        prior_rejoins.append(
            {
                "instruction_rva": prior["rva"],
                "instruction_sha256": prior["sha256"],
                "owner_entry_rva": caller["owner_entry_rva"],
                "target_entry_rva": "0x00378a15",
            }
        )

    return {
        "fourth_callee_declared_edge": {
            "instruction_rva": child_reference["instruction_rva"],
            "instruction_sha256": child_reference["instruction_sha256"],
            "source_entry_rva": child_reference["owner_entry_rva"],
            "target_entry_rva": child_reference["target_rva"],
            "ghidra_declared_direct_edge": child_reference[
                "ghidra_declared_direct_edge"
            ],
        },
        "fourth_callee_left_neighbor_matches_child": True,
        "second_callee_right_neighbor_matches_child": True,
        "child_boundary_identity": boundary_identity,
        "second_callee_prior_call_rejoins": prior_rejoins,
    }


def _evidence(
    fourth: Mapping[str, Any],
    second: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    rows: list[Any] | None = None,
    image: Any | None = None,
    data: bytes | None = None,
    decoder: Any | None = None,
    scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prerequisite = _preflight(fourth, second, direct, facts)
    decoded = _decode() if image is None else rows
    if decoded is None:
        _bad("exact child reconstruction lacks decoded rows")
    body = b"".join(bytes(row.bytes) for row in decoded)
    if body != bytes.fromhex(_RAW) or hashlib.sha256(body).hexdigest() != _BODY:
        _bad("child body differs")
    target = _target(facts)
    incoming = _expected_incoming(facts)
    expected_scan = _expected_scan(facts)
    receipt = expected_scan if scan is None else dict(_mapping(scan, "target scan"))
    if not _same(receipt, expected_scan):
        _bad("whole-atlas reference receipt differs")
    provenance = _caller_provenance(facts, image, data, decoder)
    rejoins = _dependent_rejoins(fourth, second, incoming, provenance)
    controls = _native_controls(decoded)
    graph = _graph(decoded)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(
            _mapping(facts.get("identity"), "program facts identity")
        ),
        **prerequisite,
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "sealed_instruction_count": 2,
            "register_call_encoding_audit": [
                {"register": name, "encoding": f"ff{0xd0 + index:02x}"}
                for index, name in enumerate(_REGISTER_NAMES)
            ],
        },
        "function_body": {
            "role": "opaque_indirect_call_child_static_boundary",
            "entry_rva": _hex(_ENTRY),
            "entry_va": _hex(_BASE + _ENTRY),
            "body_size": _SIZE,
            "body_sha256": _BODY,
            "atlas_record_sha256": _ATLAS,
            "range_start_rva": _hex(_ENTRY),
            "range_size": _SIZE,
            "raw_bytes_sha256": _BODY,
            "target_pe_backing": _target_pe_backing(image),
            "adjacent_atlas_boundaries": _boundaries(facts, image),
            "control_flow_graph_canonical_sha256": _CFG,
            "reviewed_points": [
                {
                    "role": "opaque_indirect_call",
                    "instruction": _instruction(_ENTRY, "ffd0"),
                    "control_kind": "x86_call_r32",
                    "register": "eax",
                },
                {
                    "role": "return",
                    "instruction": _instruction(_ENTRY + 2, "c3"),
                    "explicit_immediate": None,
                },
            ],
            "ghidra_analysis_metadata": {
                "name": target["name"],
                "namespace": target["namespace"],
                "name_source": target["name_source"],
                "thunk": target["thunk"],
                "metadata_only": True,
            },
            "semantic_facts": {
                "relationship_defined_only": True,
                "analysis_label_opaque": True,
                "source_semantic_name_assigned": False,
                "runtime_or_success_claimed": False,
            },
        },
        "control_flow_graph": graph,
        "incoming_declared_direct_edges": incoming,
        "native_controls": controls,
        "caller_provenance_slices": provenance,
        "whole_atlas_reference_scan": receipt,
        "dependent_receipt_rejoins": rejoins,
        "method": {
            "static_only": True,
            "semantic_decoding_claimed": False,
            "structural_boundary": "The receipt seals the three child bytes, two decoded instructions, exact atlas and PE geometry, exhaustive atlas-owned references, two caller CFG slices and their adjacent EAX loaders, and joins back to both prerequisite callee receipts.",
            "not_claimed": [
                "the runtime value held in EAX or the address reached by CALL EAX",
                "analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return",
                "runtime reachability, invocation, ordering, frequency, state continuity, or effects",
                "the contents or runtime meaning of either computed-memory loader expression",
                "computed, indirect, data-originated, un-atlased, dynamic, or Lua-side references outside the sealed partitions",
            ],
        },
        "nonclaims": [
            "The EAX target and its runtime effect are not statically proved.",
            "No runtime behavior, function-name meaning, calling convention, or data semantics is claimed.",
            "The caller loads prove only input-dependent memory origins and do not identify a constant, relocation, PE address, import slot, or concrete call target.",
            "The nine-byte gap is layout evidence only; its contents and runtime behavior remain opaque.",
        ],
        "summary": {
            "reviewed_target_count": 1,
            "reviewed_target_bytes": _SIZE,
            "sealed_instruction_count": 2,
            "sealed_control_flow_graph_count": 1,
            "sealed_control_flow_graph_node_count": graph["node_count"],
            "sealed_control_flow_graph_edge_count": graph["edge_count"],
            "sealed_adjacent_boundary_count": 2,
            "sealed_gap_count": 1,
            "direct_incoming_reference_count": 2,
            "direct_incoming_owner_count": 2,
            "caller_provenance_slice_count": 2,
            "computed_memory_loader_count": 2,
            "static_indirect_target_count": 0,
            "opaque_call_r32_count": 1,
            "opaque_indirect_control_count": 1,
            "direct_outgoing_edge_count": 0,
            "direct_lua_call_count": 0,
            "staged_lua_dispatch_count": 0,
            "pe_address_operand_count": 0,
            "non_pe_immediate_literal_count": 0,
            "segment_qualified_memory_count": 0,
            "bnd_prefixed_control_count": 0,
            "opaque_interrupt_count": 0,
            "explicit_ret_immediate_count": 0,
            "sealed_un_atlased_gap_bytes": 9,
            "target_reference_count": receipt["aggregates"]["reference_count"],
            "target_reference_target_count": receipt["aggregates"]["target_count"],
            "target_reference_owner_count": receipt["aggregates"]["owner_count"],
            "schema_violations": 0,
        },
    }


def _normalize(operation):
    try:
        return operation()
    except NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeChildStaticBoundaryError:
        raise
    except Exception as exc:  # upstream parsers expose several domain errors
        _bad(str(exc))


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary_structure(
    evidence: Mapping[str, Any],
    fourth: Mapping[str, Any],
    second: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        evidence_object = _mapping(evidence, "evidence")
        fourth_object = _mapping(fourth, "fourth-callee boundary")
        second_object = _mapping(second, "second-callee boundary")
        direct_object = _mapping(direct, "direct calls")
        facts_object = _mapping(facts, "program facts")
        for value, label in (
            (evidence_object, "evidence"),
            (fourth_object, "fourth-callee boundary"),
            (second_object, "second-callee boundary"),
            (direct_object, "direct calls"),
            (facts_object, "program facts"),
        ):
            _validate_json_tree(value, label)
        prerequisite = validate_native_lua_direct_call_structure(
            direct_object, facts_object
        )
        if (
            prerequisite.get("status") != "structurally_verified"
            or prerequisite.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call structural prerequisite differs")
        observed = _evidence(fourth_object, second_object, direct_object, facts_object)
        if not _same(evidence_object, observed):
            _bad("evidence structure differs from reconstructed receipt")
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


def build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
    executable: str | Path,
    fourth: Mapping[str, Any],
    second: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        fourth_object = _mapping(fourth, "fourth-callee boundary")
        second_object = _mapping(second, "second-callee boundary")
        direct_object = _mapping(direct, "direct calls")
        facts_object = _mapping(facts, "program facts")
        inventory_object = _mapping(inventory, "inventory")
        for value, label in (
            (fourth_object, "fourth-callee boundary"),
            (second_object, "second-callee boundary"),
            (direct_object, "direct calls"),
            (facts_object, "program facts"),
            (inventory_object, "inventory"),
        ):
            _validate_json_tree(value, label)
        executable_path = Path(executable)
        prerequisite = validate_native_lua_direct_call_census(
            executable_path,
            direct_object,
            facts_object,
            inventory=inventory_object,
        )
        if (
            prerequisite.get("status") != "verified"
            or prerequisite.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call exact prerequisite differs")
        data, image, digest = _load_executable(executable_path)
        if digest != _EXE or image.image_base != _BASE:
            _bad("exact executable identity differs")
        decoder, _version = _decoder()
        decoder.detail = True
        rows = _decode_range(data, image, _ENTRY, _SIZE, decoder)
        scan = _whole_atlas_reference_scan(data, image, decoder, facts_object)
        result = _evidence(
            fourth_object,
            second_object,
            direct_object,
            facts_object,
            rows=rows,
            image=image,
            data=data,
            decoder=decoder,
            scan=scan,
        )
        replay, replay_image, replay_digest = _load_executable(executable_path)
        if (
            replay_digest != digest
            or replay != data
            or replay_image.image_base != _BASE
        ):
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary_structure(
            result, fourth_object, second_object, direct_object, facts_object
        )
        return result

    return _normalize(run)


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
    executable: str | Path,
    evidence: Mapping[str, Any],
    fourth: Mapping[str, Any],
    second: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        evidence_object = _mapping(evidence, "evidence")
        fourth_object = _mapping(fourth, "fourth-callee boundary")
        second_object = _mapping(second, "second-callee boundary")
        direct_object = _mapping(direct, "direct calls")
        facts_object = _mapping(facts, "program facts")
        inventory_object = _mapping(inventory, "inventory")
        _validate_json_tree(evidence_object, "evidence")
        rebuilt = build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
            executable,
            fourth_object,
            second_object,
            direct_object,
            facts_object,
            inventory=inventory_object,
        )
        if not _same(evidence_object, rebuilt):
            _bad("exact executable reconstruction differs")
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": VERIFICATION_KIND,
            "status": "verified",
            "build_identity": dict(rebuilt["build_identity"]),
            "evidence_sha256": _canonical_sha256(rebuilt),
            "summary": dict(rebuilt["summary"]),
        }

    return _normalize(run)


def encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
    value: Mapping[str, Any],
) -> str:
    def run() -> str:
        value_object = _mapping(value, "encoded value")
        _validate_json_tree(value_object, "encoded value")
        return (
            json.dumps(
                value_object,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )

    return _normalize(run)
