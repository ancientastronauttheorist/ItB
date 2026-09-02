"""Fail-closed structural receipt for direct child ``0x0038edb6``.

This receipt is deliberately relationship-defined.  Ghidra and import names are
retained only as syntax/analysis metadata; it makes no CRT, ABI, behaviour, or
runtime-reachability claim.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter, defaultdict
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
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_assertion_helper_first_callee_direct_callee_pair_static_boundary import (
    ANALYSIS_KIND as PREDECESSOR_KIND,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PREDECESSOR = "e1a04d9e847b1ec61e57e24cb02c03eea6b35aae5a1ad059cdd4339ebb939378"
_BASE, _ENTRY, _SIZE = 0x400000, 0x38EDB6, 133
_RAW = "8bff535657ff1514617d008bf033dba19042890083f8ff740c50e88f2200008bf885ff755168640300006a01e84f9effff8bf8595985ff750953e861a3ffff59eb2b57ff3590428900e8b622000085c0750357ebe56850758b0057e88efdffff53e83aa3ffff83c40c85ff750956ff15dc607d00eb0956ff15dc607d008bdf5f5e8bc35bc3"
_BODY = "891a14212f8009b76d5814e72a7fb528b856bc647f352c46f410153a1479d16e"
_ATLAS = "b5c70c924e8dbcfa802a08fbf2559bd9a8cc3df5d38c614b8cc04a9f3f4bb9b6"
_CFG = "a16958fb83c275642c78d407095bf5468a077b70935a5b199121da5e88c098d8"
_PARENT = (
    0x385BCC,
    0x385BCC,
    "e8e5910000",
    "a8859e2355301186727a01e26a0ba71246f402b520df1907d3949e338b077b42",
)
_OUTGOING = (
    (0x38EDD0, 0x391064, "e88f220000"),
    (0x38EDE2, 0x388C36, "e84f9effff"),
    (0x38EDF0, 0x389156, "e861a3ffff"),
    (0x38EDFF, 0x3910BA, "e8b6220000"),
    (0x38EE11, 0x38EBA4, "e88efdffff"),
    (0x38EE17, 0x389156, "e83aa3ffff"),
)
_INCOMING = (
    (0x379E88, 0x379E77, "e8294f0100"),
    (0x385BB9, 0x385BB9, "e8f8910000"),
    _PARENT[:3],
    (0x38928D, 0x389287, "e8245b0000"),
    (0x38BC6C, 0x38BC5A, "e845310000"),
    (0x38E812, 0x38E7B8, "e89f050000"),
)
_RELOC = (
    0x539000,
    0x35618,
    0x510A00,
    "06630f9047636fb68afba81d89dbc1ef2f21c459b684d57d1d2bcaeb3750dfa3",
)
_SCOPE = {
    "atlas_function_count": 25312,
    "atlas_body_range_count": 25490,
    "decoded_bytes": 3735718,
    "decoded_instructions": 1153814,
    "all_declared_ranges_decoded": True,
    "operand_classes": ["absolute_memory", "immediate"],
}
_SCAN_HASHES = {
    "references": "448a82fb8568ae5eda0eebf7137ab47a0d93b74f1d0470ecde09d0e66ce193d8",
    "target_partition": "d5c09b335b09de70447004c7cc8c6108f7cea5bad56cea6bf04708232783347a",
    "owner_partition": "b283c218df65607de0cca4532c6141056b975e79cb1015caae957fcfe0c712e9",
    "target_owner_partition": "1a175671421e5a917656f74a0e04c1625431d3746278e922eee0a5aa11da33be",
    "target_reference_partition": "5fd484723d694eacb7b09ccec0aa7f43960b306e9c694a4fb8f1fc09921604fe",
}


class NativeAssertionHelperFirstCalleeDirectCalleePairFirstTargetChildStaticBoundaryError(
    RuntimeError
):
    """Raised when the finite child receipt cannot be reconstructed."""


def _bad(message: str) -> None:
    raise NativeAssertionHelperFirstCalleeDirectCalleePairFirstTargetChildStaticBoundaryError(
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
    value = bytes.fromhex(raw)
    return {
        "rva": _hex(rva),
        "size": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }


def _empty_register_calls() -> list[dict[str, Any]]:
    return [{"register": name, "call_rvas": []} for name in _REGISTER_NAMES]


def _edges(facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for value in _array(facts.get("ghidra_declared_direct_calls"), "declared calls"):
        edge = _mapping(value, "declared call")
        site = _rva(edge.get("instruction_rva"), "declared call site")
        if site in result:
            _bad("duplicate declared direct call")
        result[site] = edge
    return result


def _edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    name = edge.get("target_name")
    if type(name) is not str:
        _bad("declared edge lacks analysis name")
    return {
        "instruction_rva": _hex(_rva(edge.get("instruction_rva"), "edge site")),
        "source_entry_rva": _hex(_rva(edge.get("source_entry_rva"), "edge source")),
        "target_entry_rva": _hex(
            _rva(edge.get("target_entry_rva"), "edge target entry")
        ),
        "target_rva": _hex(_rva(edge.get("target_rva"), "edge target")),
        "target_name_sha256": hashlib.sha256(name.encode()).hexdigest(),
    }


def _decode(raw: bytes = bytes.fromhex(_RAW)) -> list[Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    rows = list(decoder.disasm(raw, _BASE + _ENTRY))
    if len(rows) != 53 or b"".join(bytes(row.bytes) for row in rows) != raw:
        _bad("sealed child bytes do not decode exactly")
    return rows


def _points(rows: list[Any]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        _, writes = row.regs_access()
        names = {row.reg_name(reg).lower() for reg in writes}
        raw = bytes(row.bytes)
        result.append(
            {
                "rva": _hex(row.address - _BASE),
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "writes_ebx": "ebx" in names,
                "writes_esi": "esi" in names,
                "writes_edi": "edi" in names,
                "writes_esp": "esp" in names,
            }
        )
    return result


def _graph(rows: list[Any] | None = None) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    decoded = _decode() if rows is None else rows
    value = _with_edi_writes(
        _enhanced_cfg(decoded, _BASE, (_ENTRY, _SIZE), capstone, x86), decoded, x86
    )
    value["caller_entry_rva"] = _hex(_ENTRY)
    if (value.get("node_count"), value.get("edge_count"), _canonical_sha256(value)) != (
        53,
        57,
        _CFG,
    ):
        _bad("sealed child CFG differs")
    return value


def _preflight(
    predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]
) -> dict[str, Any]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if (
        identity.get("executable_sha256") != _EXE
        or not _same(predecessor.get("build_identity"), identity)
        or not _same(direct.get("build_identity"), identity)
    ):
        _bad("prerequisite identity differs")
    if (
        predecessor.get("analysis_kind") != PREDECESSOR_KIND
        or _canonical_sha256(predecessor) != _PREDECESSOR
    ):
        _bad("direct-callee pair predecessor differs")
    summary = _mapping(facts.get("summary"), "program facts summary")
    return {
        "program_facts": {
            **_source_identity(
                facts, "pe_ghidra_program_facts", _FACTS, "program facts"
            ),
            "function_count": summary.get("function_count"),
            "body_range_count": summary.get("body_range_count"),
            "function_body_bytes": summary.get("function_body_bytes"),
        },
        "direct_callee_pair_static_boundary": _source_identity(
            predecessor,
            PREDECESSOR_KIND,
            _PREDECESSOR,
            "direct-callee pair predecessor",
        ),
        "direct_call_census": _source_identity(
            direct, DIRECT_KIND, _DIRECT, "direct-call census"
        ),
    }


def _target(facts: Mapping[str, Any]) -> Mapping[str, Any]:
    function = _atlas_functions(facts).get(_ENTRY)
    expected = (
        _SIZE,
        _BODY,
        _ATLAS,
        "___acrt_getptd_noexit",
        "ANALYSIS",
        "Global",
        False,
    )
    actual = (
        None
        if function is None
        else (
            function.get("body_size"),
            function.get("body_sha256"),
            atlas_record_sha256(function),
            function.get("name"),
            function.get("name_source"),
            function.get("namespace"),
            function.get("thunk"),
        )
    )
    if actual != expected:
        _bad("target atlas record differs")
    return function


def _parent(
    predecessor: Mapping[str, Any], facts: Mapping[str, Any]
) -> list[dict[str, Any]]:
    calls = _mapping(predecessor.get("native_calls"), "predecessor native calls")
    rows = [
        dict(_mapping(value, "predecessor target row"))
        for value in _array(calls.get("targets"), "predecessor targets")
    ]
    match = [
        row
        for row in rows
        if _rva(row.get("entry_rva"), "predecessor target entry") == _PARENT[0]
    ]
    if len(match) != 1:
        _bad("predecessor target child partition differs")
    edges = _array(match[0].get("outgoing_direct"), "predecessor outgoing direct edges")
    if len(edges) != 1:
        _bad("predecessor child edge count differs")
    row = dict(_mapping(edges[0], "predecessor child edge"))
    if (
        _rva(
            _mapping(row.get("instruction"), "parent instruction").get("rva"),
            "parent site",
        ),
        _rva(row.get("source_entry_rva"), "parent source"),
        _rva(row.get("target_entry_rva"), "parent target"),
        row.get("target_atlas_record_sha256"),
    ) != (_PARENT[0], _PARENT[1], _ENTRY, _ATLAS) or not _same(
        row.get("instruction"), _instruction(_PARENT[0], _PARENT[2])
    ):
        _bad("predecessor child edge differs")
    return [row]


def _section(image: Any, rva: int) -> tuple[Any, int | None]:
    section = next(
        (
            row
            for row in image.sections
            if row.virtual_address <= rva < row.virtual_address + row.virtual_size
        ),
        None,
    )
    if (
        section is None
        or section.name != ".data"
        or section.virtual_address != 0x492000
        or section.characteristics != 0xC0000040
        or section.virtual_size != 0x471CC
        or section.raw_size != 0x24800
        or section.raw_offset != 0x490200
    ):
        _bad("PE data section binding differs")
    return section, image.rva_to_file_offset(rva)


def _expected_imports() -> dict[int, dict[str, Any]]:
    shared = {
        "dll_name": "KERNEL32.dll",
        "descriptor_file_offset": "0x0048dd30",
        "descriptor_raw": "80ed48000000000000000000fe05490000603d00",
        "original_first_thunk_rva": "0x0048ed80",
        "first_thunk_rva": "0x003d6000",
        "import_name_metadata_only": True,
    }
    return {
        0x3D6114: {
            **shared,
            "ilt_entry_rva": "0x0048ee94",
            "ilt_entry_file_offset": "0x0048de94",
            "ilt_entry_raw": "a6044900",
            "iat_slot_rva": "0x003d6114",
            "iat_slot_va": "0x007d6114",
            "iat_slot_file_offset": "0x003d5114",
            "iat_slot_raw": "a6044900",
            "import_by_name_rva": "0x004904a6",
            "import_by_name_file_offset": "0x0048f4a6",
            "hint": 514,
            "import_name": "GetLastError",
        },
        0x3D60DC: {
            **shared,
            "ilt_entry_rva": "0x0048ee5c",
            "ilt_entry_file_offset": "0x0048de5c",
            "ilt_entry_raw": "ba054900",
            "iat_slot_rva": "0x003d60dc",
            "iat_slot_va": "0x007d60dc",
            "iat_slot_file_offset": "0x003d50dc",
            "iat_slot_raw": "ba054900",
            "import_by_name_rva": "0x004905ba",
            "import_by_name_file_offset": "0x0048f5ba",
            "hint": 1139,
            "import_name": "SetLastError",
        },
    }


def _imports(image: Any) -> dict[int, dict[str, Any]]:
    if (
        image.bits != 32
        or len(image.data_directories) <= 1
        or image.data_directories[1] != (0x48ECA4, 0xDC)
    ):
        _bad("import directory differs")
    start = image.rva_span_to_file_offset(0x48ECA4, 0xDC)
    if start != 0x48DCA4:
        _bad("import directory is not raw-backed as expected")
    found: dict[int, dict[str, Any]] = {}
    cursor = start
    while cursor < start + 0xDC:
        original, timestamp, forwarder, name_rva, first_thunk = struct.unpack_from(
            "<IIIII", image.data, cursor
        )
        if not any((original, timestamp, forwarder, name_rva, first_thunk)):
            break
        name_offset = image.rva_to_file_offset(name_rva)
        original_offset = image.rva_to_file_offset(original)
        if name_offset is None or original_offset is None:
            _bad("import descriptor is not file-backed")
        dll = image.data[name_offset : image.data.index(b"\0", name_offset)].decode(
            "ascii"
        )
        for index in range(0, 0x10000, 4):
            thunk = struct.unpack_from("<I", image.data, original_offset + index)[0]
            if thunk == 0:
                break
            slot_rva = first_thunk + index
            if slot_rva not in (0x3D6114, 0x3D60DC):
                continue
            hint_offset = image.rva_to_file_offset(thunk & 0x7FFFFFFF)
            if hint_offset is None or thunk & 0x80000000:
                _bad("required import uses unexpected thunk syntax")
            symbol = image.data[
                hint_offset + 2 : image.data.index(b"\0", hint_offset + 2)
            ].decode("ascii")
            iat_offset = image.rva_to_file_offset(slot_rva)
            found[slot_rva] = {
                "dll_name": dll,
                "descriptor_file_offset": _hex(cursor),
                "descriptor_raw": image.data[cursor : cursor + 20].hex(),
                "original_first_thunk_rva": _hex(original),
                "first_thunk_rva": _hex(first_thunk),
                "ilt_entry_rva": _hex(original + index),
                "ilt_entry_file_offset": _hex(original_offset + index),
                "ilt_entry_raw": image.data[
                    original_offset + index : original_offset + index + 4
                ].hex(),
                "iat_slot_rva": _hex(slot_rva),
                "iat_slot_va": _hex(_BASE + slot_rva),
                "iat_slot_file_offset": _hex(iat_offset),
                "iat_slot_raw": image.data[iat_offset : iat_offset + 4].hex(),
                "import_by_name_rva": _hex(thunk),
                "import_by_name_file_offset": _hex(hint_offset),
                "hint": struct.unpack_from("<H", image.data, hint_offset)[0],
                "import_name": symbol,
                "import_name_metadata_only": True,
            }
        cursor += 20
    if found != _expected_imports():
        _bad("required raw import/IAT bindings differ")
    return found


def _relocations(image: Any) -> dict[str, Any]:
    rva, size, offset, digest = _RELOC
    if (
        image.bits != 32
        or len(image.data_directories) <= 5
        or image.data_directories[5] != (rva, size)
        or image.rva_span_to_file_offset(rva, size) != offset
        or hashlib.sha256(image.data[offset : offset + size]).hexdigest() != digest
    ):
        _bad("base relocation directory differs")
    sites: list[tuple[int, int, int, int, str]] = []
    cursor = offset
    while cursor < offset + size:
        page, block_size = struct.unpack_from("<II", image.data, cursor)
        if block_size < 8 or cursor + block_size > offset + size:
            _bad("base relocation block malformed")
        for at in range(cursor + 8, cursor + block_size, 2):
            entry = struct.unpack_from("<H", image.data, at)[0]
            site = page + (entry & 0xFFF)
            if entry >> 12 == 3 and _ENTRY <= site < _ENTRY + _SIZE:
                file_offset = image.rva_span_to_file_offset(site, 4)
                if file_offset is None:
                    _bad("HIGHLOW site is not file-backed")
                sites.append(
                    (
                        site,
                        at,
                        file_offset,
                        struct.unpack_from("<I", image.data, file_offset)[0],
                        image.data[at : at + 2].hex(),
                    )
                )
        cursor += block_size
    expected = [
        (0x38EDBD, 0x53352A, 0x38E1BD, 0x7D6114, "bd3d"),
        (0x38EDC6, 0x53352C, 0x38E1C6, 0x894290, "c63d"),
        (0x38EDFB, 0x53352E, 0x38E1FB, 0x894290, "fb3d"),
        (0x38EE0C, 0x533530, 0x38E20C, 0x8B7550, "0c3e"),
        (0x38EE26, 0x533532, 0x38E226, 0x7D60DC, "263e"),
        (0x38EE2F, 0x533534, 0x38E22F, 0x7D60DC, "2f3e"),
    ]
    if cursor != offset + size or sites != expected:
        _bad("HIGHLOW relocation frontier differs")
    return {
        "directory": {
            "rva": _hex(rva),
            "size": size,
            "file_offset": _hex(offset),
            "sha256": digest,
        },
        "highlow_site_count_inside_target": len(sites),
        "highlow_sites": [
            {
                "site_rva": _hex(site),
                "file_offset": _hex(file_offset),
                "entry_file_offset": _hex(entry_offset),
                "entry_raw": raw,
                "type": "HIGHLOW",
                "value_va": _hex(value),
                "value_rva": _hex(value - _BASE),
            }
            for site, entry_offset, file_offset, value, raw in sites
        ],
    }


def _native_calls(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    _target(facts)
    edges = _edges(facts)
    functions = _atlas_functions(facts)
    outgoing = []
    for site, target, raw in _OUTGOING:
        edge = edges.get(site)
        function = functions.get(target)
        if (
            edge is None
            or function is None
            or (
                _rva(edge.get("source_entry_rva"), "outgoing source"),
                _rva(edge.get("target_entry_rva"), "outgoing target entry"),
                _rva(edge.get("target_rva"), "outgoing target"),
            )
            != (_ENTRY, target, target)
        ):
            _bad("outgoing edge differs")
        outgoing.append(
            {
                "role": "opaque_native_direct_edge",
                "instruction": _instruction(site, raw),
                "source_entry_rva": _hex(_ENTRY),
                "target_entry_rva": _hex(target),
                "target_rva": _hex(target),
                "target_atlas_record_sha256": atlas_record_sha256(function),
                "callee_behavior_opaque": True,
                "ghidra_declared_direct_edge": _edge(edge),
            }
        )
    if {
        site
        for site, edge in edges.items()
        if _rva(edge.get("source_entry_rva"), "outgoing source") == _ENTRY
    } != {site for site, _, _ in _OUTGOING}:
        _bad("outgoing direct census differs")
    controls = []
    bindings = _imports(image) if image is not None else _expected_imports()
    for site, raw, access, va, syntax, meaning in (
        (
            0x38EDBB,
            "ff1514617d00",
            "read",
            0x7D6114,
            "call_absolute_memory",
            "GetLastError import binding",
        ),
        (
            0x38EE24,
            "ff15dc607d00",
            "read",
            0x7D60DC,
            "call_absolute_memory",
            "SetLastError import binding",
        ),
        (
            0x38EE2D,
            "ff15dc607d00",
            "read",
            0x7D60DC,
            "call_absolute_memory",
            "SetLastError import binding",
        ),
    ):
        controls.append(
            {
                "role": "opaque_import_iat_control_syntax",
                "instruction": _instruction(site, raw),
                "control_syntax": syntax,
                "operand_class": "absolute_memory",
                "operand_index": 0,
                "operand_access": access,
                "iat_va": _hex(va),
                "iat_rva": _hex(va - _BASE),
                "import_binding": bindings[va - _BASE],
                "import_meaning_metadata_only": True,
                "contents_or_runtime_behavior_opaque": True,
            }
        )
    addresses = []
    for site, raw, access, va in (
        (0x38EDC5, "a190428900", "read", 0x894290),
        (0x38EDF9, "ff3590428900", "read", 0x894290),
        (0x38EE0B, "6850758b00", "read", 0x8B7550),
    ):
        rva = va - _BASE
        file_offset = (
            (0x492490 if rva == 0x494290 else None)
            if image is None
            else _section(image, rva)[1]
        )
        if image is not None and (
            (rva == 0x494290 and file_offset != 0x492490)
            or (rva == 0x4B7550 and file_offset is not None)
        ):
            _bad("data operand raw backing differs")
        addresses.append(
            {
                "role": "opaque_pe_"
                + ("immediate" if site == 0x38EE0B else "absolute_memory")
                + "_data_address_syntax",
                "instruction": _instruction(site, raw),
                "operand_class": "immediate" if site == 0x38EE0B else "absolute_memory",
                "operand_index": 1 if site == 0x38EDC5 else 0,
                "operand_access": access,
                "operand_va": _hex(va),
                "operand_rva": _hex(rva),
                "section_name": ".data",
                "section_rva": "0x00492000",
                "section_characteristics": "0xc0000040",
                "section_writable": True,
                "section_virtual_size": "0x000471cc",
                "section_raw_size": "0x00024800",
                "section_raw_offset": "0x00490200",
                "file_backed": file_offset is not None,
                "file_offset": None if file_offset is None else _hex(file_offset),
                "contents_or_runtime_behavior_opaque": True,
            }
        )
    return {
        "outgoing_direct": outgoing,
        "outgoing_direct_partition_complete": True,
        "direct_lua_calls": [],
        "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [],
        "staged_lua_dispatch_partition_complete": True,
        "opaque_indirect_controls": [],
        "indirect_control_partition_complete": True,
        "import_and_iat_body_controls": controls,
        "import_and_iat_body_control_partition_complete": True,
        "pe_address_operands": addresses,
        "pe_address_operand_partition_complete": True,
        "non_pe_immediate_literals": [
            {
                "role": "opaque_comparison_literal",
                "instruction": _instruction(0x38EDCA, "83f8ff"),
                "operand_index": 1,
                "value_u32": "0xffffffff",
            },
            {
                "role": "opaque_data_literal",
                "instruction": _instruction(0x38EDDB, "6864030000"),
                "operand_index": 0,
                "value_u32": "0x00000364",
            },
            {
                "role": "opaque_data_literal",
                "instruction": _instruction(0x38EDE0, "6a01"),
                "operand_index": 0,
                "value_u32": "0x00000001",
            },
            {
                "role": "opaque_data_literal",
                "instruction": _instruction(0x38EE1C, "83c40c"),
                "operand_index": 1,
                "value_u32": "0x0000000c",
            },
        ],
        "non_pe_immediate_literal_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [],
        "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [],
        "opaque_interrupt_partition_complete": True,
        "call_r32_audit": _empty_register_calls(),
        "register_call_partition_complete": True,
        "base_relocation_scan": (
            _relocations(image) if image is not None else _relocations_placeholder()
        ),
    }


def _relocations_placeholder() -> dict[str, Any]:
    return {
        "directory": {
            "rva": _hex(_RELOC[0]),
            "size": _RELOC[1],
            "file_offset": _hex(_RELOC[2]),
            "sha256": _RELOC[3],
        },
        "highlow_site_count_inside_target": 6,
        "highlow_sites": [
            {
                "site_rva": _hex(site),
                "file_offset": _hex(file),
                "entry_file_offset": _hex(entry),
                "entry_raw": raw,
                "type": "HIGHLOW",
                "value_va": _hex(value),
                "value_rva": _hex(value - _BASE),
            }
            for site, entry, file, value, raw in [
                (0x38EDBD, 0x53352A, 0x38E1BD, 0x7D6114, "bd3d"),
                (0x38EDC6, 0x53352C, 0x38E1C6, 0x894290, "c63d"),
                (0x38EDFB, 0x53352E, 0x38E1FB, 0x894290, "fb3d"),
                (0x38EE0C, 0x533530, 0x38E20C, 0x8B7550, "0c3e"),
                (0x38EE26, 0x533532, 0x38E226, 0x7D60DC, "263e"),
                (0x38EE2F, 0x533534, 0x38E22F, 0x7D60DC, "2f3e"),
            ]
        ],
    }


def _scan(
    data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]
) -> dict[str, Any]:
    import capstone.x86_const as x86

    functions = _atlas_functions(facts)
    edges = _edges(facts)
    found = []
    totals = [0, 0, 0]
    target_va = image.image_base + _ENTRY
    decoder.detail = True
    for owner, function in sorted(functions.items()):
        for value in _array(function.get("ranges"), "atlas ranges"):
            span = _mapping(value, "atlas range")
            start = _rva(span.get("start_rva"), "atlas range start")
            size = span.get("size")
            if type(size) is not int or size <= 0:
                _bad("invalid atlas range")
            rows = _decode_range(data, image, start, size, decoder)
            totals[0] += 1
            totals[1] += size
            totals[2] += len(rows)
            for row in rows:
                for index, operand in enumerate(row.operands):
                    if operand.type == x86.X86_OP_IMM:
                        kind, target = "immediate", int(operand.imm) & 0xFFFFFFFF
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.segment == x86.X86_REG_INVALID
                        and operand.mem.base == x86.X86_REG_INVALID
                        and operand.mem.index == x86.X86_REG_INVALID
                    ):
                        kind, target = (
                            "absolute_memory",
                            int(operand.mem.disp) & 0xFFFFFFFF,
                        )
                    else:
                        continue
                    if target != target_va:
                        continue
                    raw = bytes(row.bytes)
                    site = row.address - image.image_base
                    if (
                        kind != "immediate"
                        or index != 0
                        or row.id != x86.X86_INS_CALL
                        or len(raw) != 5
                        or raw[0] != 0xE8
                    ):
                        _bad("unreviewed target-reference syntax")
                    edge = edges.get(site)
                    if edge is None or (
                        _rva(edge.get("source_entry_rva"), "reference source"),
                        _rva(edge.get("target_entry_rva"), "reference target"),
                        _rva(edge.get("target_rva"), "reference target"),
                    ) != (owner, _ENTRY, _ENTRY):
                        _bad("target reference does not match declared E8 frontier")
                    found.append(
                        {
                            "instruction_rva": _hex(site),
                            "instruction_size": len(raw),
                            "instruction_sha256": hashlib.sha256(raw).hexdigest(),
                            "owner_entry_rva": _hex(owner),
                            "owner_atlas_record_sha256": atlas_record_sha256(function),
                            "target_rva": _hex(_ENTRY),
                            "target_atlas_record_sha256": _ATLAS,
                            "target_va": _hex(target_va),
                            "operand_class": kind,
                            "operand_index": index,
                            "use_class": "direct_call",
                            "call_form": "x86_relative_near_call_e8",
                            "ghidra_declared_direct_edge": _edge(edge),
                        }
                    )
    if tuple(totals) != (25490, 3735718, 1153814):
        _bad("all-atlas scan scope differs")
    expected_sites = [site for site, _, _ in _INCOMING]
    if [int(row["instruction_rva"], 16) for row in found] != expected_sites:
        _bad("all-operand scan survivor frontier differs")
    owners = Counter(row["owner_entry_rva"] for row in found)
    owner_atlas = {
        row["owner_entry_rva"]: row["owner_atlas_record_sha256"] for row in found
    }
    target_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": len(found),
            "owner_count": len(owners),
        }
    ]
    owner_partition = [
        {
            "owner_entry_rva": owner,
            "owner_atlas_record_sha256": owner_atlas[owner],
            "reference_count": count,
        }
        for owner, count in sorted(owners.items())
    ]
    target_owner_partition = [
        {"target_rva": _hex(_ENTRY), **row} for row in owner_partition
    ]
    target_reference_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": len(found),
        }
    ]
    hashes = {
        "references": _compact(found),
        "target_partition": _compact(target_partition),
        "owner_partition": _compact(owner_partition),
        "target_owner_partition": _compact(target_owner_partition),
        "target_reference_partition": _compact(target_reference_partition),
    }
    return {
        "target_rvas": [_hex(_ENTRY)],
        "target_vas": [_hex(target_va)],
        "scope": dict(_SCOPE),
        "references": found,
        "target_partition": target_partition,
        "owner_partition": owner_partition,
        "target_owner_partition": target_owner_partition,
        "target_reference_partition": target_reference_partition,
        "partition_sha256": hashes,
        "references_canonical_sha256": hashes["references"],
        "aggregates": {
            "reference_count": len(found),
            "target_count": 1,
            "owner_count": len(owners),
            "target_owner_count": len(target_owner_partition),
            "direct_call_count": len(found),
            "comparison_count": 0,
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    edges = _edges(facts)
    functions = _atlas_functions(facts)
    rows = []
    for site, owner, raw in _INCOMING:
        edge, function = edges.get(site), functions.get(owner)
        if edge is None or function is None:
            _bad("declared incoming edge or owner missing")
        rows.append(
            {
                "instruction_rva": _hex(site),
                "instruction_size": 5,
                "instruction_sha256": hashlib.sha256(bytes.fromhex(raw)).hexdigest(),
                "owner_entry_rva": _hex(owner),
                "owner_atlas_record_sha256": atlas_record_sha256(function),
                "target_rva": _hex(_ENTRY),
                "target_atlas_record_sha256": _ATLAS,
                "target_va": _hex(_BASE + _ENTRY),
                "operand_class": "immediate",
                "operand_index": 0,
                "use_class": "direct_call",
                "call_form": "x86_relative_near_call_e8",
                "ghidra_declared_direct_edge": _edge(edge),
            }
        )
    owners = [
        {
            "owner_entry_rva": row["owner_entry_rva"],
            "owner_atlas_record_sha256": row["owner_atlas_record_sha256"],
            "reference_count": 1,
        }
        for row in rows
    ]
    target = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 6,
            "owner_count": 6,
        }
    ]
    target_owner = [{"target_rva": _hex(_ENTRY), **row} for row in owners]
    target_ref = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 6,
        }
    ]
    hashes = {
        "references": _compact(rows),
        "target_partition": _compact(target),
        "owner_partition": _compact(owners),
        "target_owner_partition": _compact(target_owner),
        "target_reference_partition": _compact(target_ref),
    }
    if hashes != _SCAN_HASHES:
        _bad("sealed all-operand reference partition hashes differ")
    return {
        "target_rvas": [_hex(_ENTRY)],
        "target_vas": [_hex(_BASE + _ENTRY)],
        "scope": dict(_SCOPE),
        "references": rows,
        "target_partition": target,
        "owner_partition": owners,
        "target_owner_partition": target_owner,
        "target_reference_partition": target_ref,
        "partition_sha256": hashes,
        "references_canonical_sha256": hashes["references"],
        "aggregates": {
            "reference_count": 6,
            "target_count": 1,
            "owner_count": 6,
            "target_owner_count": 6,
            "direct_call_count": 6,
            "comparison_count": 0,
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }


def _evidence(
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    rows: list[Any] | None = None,
    image: Any | None = None,
    scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    decoded = _decode() if rows is None else rows
    raw = b"".join(bytes(row.bytes) for row in decoded)
    if raw != bytes.fromhex(_RAW) or hashlib.sha256(raw).hexdigest() != _BODY:
        _bad("child body differs")
    _target(facts)
    expected_scan = _expected_scan(facts)
    received_scan = expected_scan if scan is None else dict(scan)
    if not _same(received_scan, expected_scan):
        _bad("target-reference receipt differs")
    parent = _parent(predecessor, facts)
    if parent[0]["instruction"]["rva"] not in {
        row["instruction_rva"] for row in received_scan["references"]
    }:
        _bad("predecessor edge does not join scan")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(
            _mapping(facts.get("identity"), "program facts identity")
        ),
        **_preflight(predecessor, direct, facts),
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "sealed_instruction_count": 53,
            "register_call_encoding_audit": [
                {"register": name, "encoding": f"ff{0xD0 + index:02x}"}
                for index, name in enumerate(_REGISTER_NAMES)
            ],
        },
        "function_body": {
            "role": "relationship_defined_direct_callee_pair_first_target_child_static_boundary",
            "entry_rva": _hex(_ENTRY),
            "atlas_record_sha256": _ATLAS,
            "body_size": _SIZE,
            "body_sha256": _BODY,
            "range_start_rva": _hex(_ENTRY),
            "range_size": _SIZE,
            "control_flow_graph_canonical_sha256": _CFG,
            "reviewed_points": _points(decoded),
            "direct_lua_calls": [],
            "staged_lua_dispatches": [],
            "call_r32_audit": _empty_register_calls(),
            "register_call_partition_complete": True,
            "ghidra_analysis_metadata": {
                "name": "___acrt_getptd_noexit",
                "namespace": "Global",
                "name_source": "ANALYSIS",
                "thunk": False,
                "metadata_only": True,
            },
            "semantic_facts": {
                "relationship_defined_only": True,
                "analysis_labels_opaque": True,
                "source_semantic_names_assigned": False,
                "runtime_or_success_claimed": False,
            },
        },
        "control_flow_graph": _graph(decoded),
        "predecessor_parent_edges": parent,
        "native_calls": _native_calls(facts, image),
        "whole_atlas_reference_scan": received_scan,
        "method": {
            "structural_boundary": "The receipt seals 133 decoded PE bytes, six opaque direct child edges, three IAT controls, three PE data-address operands, six HIGHLOW sites, one declared predecessor edge, and an exhaustive all-operand atlas frontier.",
            "not_claimed": [
                "CRT semantics, analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return",
                "runtime reachability, invocation, ordering, frequency, or effects",
                "contents or runtime meaning of PE-address or IAT operands",
                "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
                "external IAT consumer closure",
            ],
        },
        "summary": {
            "reviewed_target_count": 1,
            "reviewed_target_bytes": 133,
            "sealed_instruction_count": 53,
            "sealed_control_flow_graph_count": 1,
            "sealed_control_flow_graph_node_count": 53,
            "sealed_control_flow_graph_edge_count": 57,
            "native_direct_edge_count": 6,
            "direct_lua_call_count": 0,
            "staged_lua_dispatch_count": 0,
            "call_r32_count": 0,
            "opaque_indirect_control_count": 0,
            "import_and_iat_body_control_count": 3,
            "highlow_relocation_site_count": 6,
            "bnd_prefixed_control_syntax_count": 0,
            "segment_qualified_memory_syntax_count": 0,
            "opaque_interrupt_syntax_count": 0,
            "non_pe_immediate_literal_count": 4,
            "pe_address_operand_count": 3,
            "target_reference_count": 6,
            "target_reference_owner_count": 6,
            "target_reference_direct_call_count": 6,
            "target_reference_memory_operand_count": 0,
            "target_reference_other_address_count": 0,
            "schema_violations": 0,
        },
    }


def _normalize(operation: Any) -> Any:
    try:
        return operation()
    except NativeAssertionHelperFirstCalleeDirectCalleePairFirstTargetChildStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeAssertionHelperFirstCalleeDirectCalleePairFirstTargetChildStaticBoundaryError(
            str(exc)
        ) from exc


def build_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
    executable: Path,
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        for value, label in (
            (predecessor, "predecessor"),
            (direct, "direct"),
            (facts, "facts"),
            (inventory, "inventory"),
        ):
            _validate_json_tree(value, label)
        prerequisite = validate_native_lua_direct_call_census(
            executable, direct, facts, inventory=inventory
        )
        if (
            prerequisite.get("status") != "verified"
            or prerequisite.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call exact prerequisite failed")
        data, image, digest = _load_executable(executable)
        if digest != _EXE or image.image_base != _BASE:
            _bad("executable identity or image base differs")
        offset = image.rva_to_file_offset(_ENTRY)
        if offset is None or data[offset : offset + _SIZE] != bytes.fromhex(_RAW):
            _bad("executable child bytes differ")
        decoder, _ = _decoder()
        result = _evidence(
            predecessor,
            direct,
            facts,
            rows=_decode(data[offset : offset + _SIZE]),
            image=image,
            scan=_scan(data, image, decoder, facts),
        )
        replay, replay_image, replay_digest = _load_executable(executable)
        if (
            replay_digest != digest
            or replay != data
            or replay_image.image_base != _BASE
        ):
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary_structure(
            result, predecessor, direct, facts
        )
        return result

    return _normalize(run)


def encode_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
    value: Mapping[str, Any],
) -> str:
    return _normalize(
        lambda: json.dumps(
            _mapping(value, "encoded evidence"),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def validate_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary_structure(
    evidence: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        prerequisite = validate_native_lua_direct_call_structure(direct, facts)
        if (
            prerequisite.get("status") != "structurally_verified"
            or prerequisite.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call structural prerequisite failed")
        if not _same(evidence, _evidence(predecessor, direct, facts)):
            _bad("evidence structure differs")
        _assert_publication_safe(evidence)
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
            "build_identity": dict(evidence["build_identity"]),
            "evidence_sha256": _canonical_sha256(evidence),
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def validate_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
            executable, predecessor, direct, facts, inventory=inventory
        )
        if not _same(evidence, rebuilt):
            _bad("evidence differs from exact rebuild")
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": VERIFICATION_KIND,
            "status": "verified",
            "build_identity": dict(rebuilt["build_identity"]),
            "evidence_sha256": _canonical_sha256(rebuilt),
            "summary": dict(rebuilt["summary"]),
        }

    return _normalize(run)
