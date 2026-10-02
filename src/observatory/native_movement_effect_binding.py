"""Exact named movement-method builder joins and bounded parent source facts.

This is static evidence. Runtime registration, child semantics and actual pawn
movement are not established by these decoded call/field facts.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import capstone as cs
from capstone import x86_const as x

from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory.native_assertion_helper_second_child_callee_frontier import _edge

ANALYSIS_KIND = "pe_native_movement_effect_binding"
SEALED_SHA256 = "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9"
BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    )
}
BODY_PINS = {
    "initializer": (
        0x279880,
        32310,
        "51f3a81b7b832098c11f81beb1c85e1fe488434adce745dd8af5cb5af64200c2",
    ),
    "move_builder": (
        0x28B780,
        147,
        "528764075a6750bf842e27e49aa860a6c4f269db63d85c63c8c259e04e1c2437",
    ),
    "charge_builder": (
        0x28B820,
        147,
        "9aec74f429618a835c82a7d8cc3e188baea828a7cb74d0f8ab026f239e4744c4",
    ),
    "move_parent": (
        0x257340,
        231,
        "910d5418dbd9db30c75adcd8b74077c5c4e99119b2298c6c252045f8c9803d67",
    ),
    "charge_parent": (
        0x2576F0,
        138,
        "b4c477b2c8b460c7697bdb236c50c264cbacb68e55189048fc4b536847a6e90a",
    ),
}
METHODS = (
    dict(
        name="AddMove",
        name_rva=0x438D20,
        target=0x257340,
        start=0x27B758,
        end=0x27B776,
        slot=-20,
        call=0x27B771,
        builder=0x28B780,
        vtable=0x43B710,
    ),
    dict(
        name="AddCharge",
        name_rva=0x438D14,
        target=0x2576F0,
        start=0x27B776,
        end=0x27B794,
        slot=-20,
        call=0x27B78F,
        builder=0x28B820,
        vtable=0x43B704,
    ),
)
EXPECTED_CALLS = {
    "move_builder": ((0x28B7A9, 0x3574DB),),
    "charge_builder": ((0x28B849, 0x3574DB),),
    "move_parent": (
        (0x257392, 0x1999A0),
        (0x2573A2, 0x0C5BB0),
        (0x2573BE, 0x15B9B0),
        (0x2573D0, 0x259F00),
        (0x2573DB, 0x10E2A0),
        (0x2573E8, 0x10E2A0),
        (0x257400, 0x7800),
        (0x25741C, 0x3574CA),
    ),
    "charge_parent": ((0x257733, 0x9A8E0), (0x25773A, 0x257340), (0x257760, 0x7800)),
}


class MovementBindingError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise MovementBindingError(message)


def _normalize(operation):
    try:
        return operation()
    except MovementBindingError:
        raise
    except Exception as exc:
        raise MovementBindingError(str(exc)) from exc


def _hex(value):
    return f"0x{value:08x}"


def _preflight(sources):
    return _normalize(lambda: _preflight_checked(sources))


def _preflight_checked(sources):
    common._validate_json_tree(sources, "sources")
    _require(
        type(sources) is dict and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    identities = {
        name: common._source_identity(sources[name], kind, digest, name)
        for name, (kind, digest) in SOURCE_PINS.items()
    }
    facts = sources["program_facts"]
    _require(
        facts["identity"]["executable_sha256"] == EXE_SHA256, "source build differs"
    )
    indexed = {int(row["entry_rva"], 16): row for row in facts["functions"]}
    _require(len(indexed) == len(facts["functions"]), "duplicate atlas entry")
    for name, (entry, size, digest) in BODY_PINS.items():
        _require(entry in indexed, name + " atlas entry absent")
        row = indexed[entry]
        _require(
            row["body_size"] == size
            and row["body_sha256"] == digest
            and row["ranges"] == [dict(start_rva=_hex(entry), size=size)],
            name + " atlas body differs",
        )
    return identities


def _signature(row):
    operands = []
    for op in row.operands:
        if op.type == x.X86_OP_REG:
            operands.append(("reg", row.reg_name(op.reg)))
        elif op.type == x.X86_OP_IMM:
            operands.append(("imm", op.imm & 0xFFFFFFFF))
        elif op.type == x.X86_OP_MEM:
            m = op.mem
            operands.append(
                (
                    "mem",
                    op.size,
                    row.reg_name(m.segment),
                    row.reg_name(m.base),
                    row.reg_name(m.index),
                    m.scale,
                    m.disp,
                )
            )
        else:
            raise MovementBindingError("unsupported selected operand")
    return row.mnemonic, tuple(operands)


def _r(name):
    return ("reg", name)


def _i(value):
    return ("imm", value & 0xFFFFFFFF)


def _m(base, disp, size=4):
    return ("mem", size, None, base, None, 1, disp)


def _selected_initializer(rows, method):
    selected = [r for r in rows if method["start"] <= r.address - BASE < method["end"]]
    _require(
        selected
        and selected[0].address - BASE == method["start"]
        and selected[-1].address + len(selected[-1].bytes) - BASE == method["end"],
        "initializer fragment alignment differs",
    )
    method_store = ("mov", (_m("ebp", method["slot"]), _i(BASE + method["target"])))
    slot_read = ("push", (_m("ebp", -16),))
    recipe = [
        slot_read,
        method_store,
        slot_read,
        ("push", (_r("ecx"),)),
        ("lea", (_r("ecx"), _m("ebp", method["slot"]))),
        ("push", (_r("ecx"),)),
        ("push", (_i(BASE + method["name_rva"]),)),
        ("mov", (_r("ecx"), _r("eax"))),
        ("call", (_i(BASE + method["builder"]),)),
    ]
    if method["name"] == "AddCharge":
        recipe = [method_store, slot_read, slot_read] + recipe[3:]
    _require(
        [_signature(r) for r in selected] == recipe, "method argument chain differs"
    )
    return [common._point(r) for r in selected]


def _graph(rows):
    starts = {r.address - BASE for r in rows}
    result = []
    for r in rows:
        pc = r.address - BASE
        successors, flow, call = [pc + len(r.bytes)], "fallthrough", None
        if r.group(cs.CS_GRP_RET):
            _require(
                r.id == x.X86_INS_RET
                and len(r.operands) == 1
                and r.operands[0].type == x.X86_OP_IMM,
                "selected return form differs",
            )
            successors, flow = [], "return_syntax"
        elif r.group(cs.CS_GRP_JUMP):
            _require(
                len(r.operands) == 1 and r.operands[0].type == x.X86_OP_IMM,
                "selected jump is not direct",
            )
            target = r.operands[0].imm - BASE
            successors = (
                [target]
                if r.id == x.X86_INS_JMP
                else sorted(set(successors + [target]))
            )
            flow = (
                "direct_jump" if r.id == x.X86_INS_JMP else "direct_conditional_branch"
            )
        elif r.group(cs.CS_GRP_CALL):
            _require(
                len(r.operands) == 1 and r.operands[0].type == x.X86_OP_IMM,
                "selected call is not direct",
            )
            call, flow = (
                _hex(r.operands[0].imm - BASE),
                "opaque_call_possible_fallthrough",
            )
        _require(set(successors) <= starts, "selected CFG leaves body")
        result.append(
            common._point(r)
            | dict(
                flow_kind=flow,
                successor_rvas=[_hex(s) for s in successors],
                direct_target_rva=call,
            )
        )
    return dict(
        nodes=result,
        node_count=len(result),
        edge_count=sum(len(r["successor_rvas"]) for r in result),
    )


def _body_packet(rows, name, facts):
    entry, size, digest = BODY_PINS[name]
    calls = [
        (r.address - BASE, r.operands[0].imm - BASE)
        for r in rows
        if r.group(cs.CS_GRP_CALL)
    ]
    _require(
        tuple(calls) == EXPECTED_CALLS[name], "selected declared call partition differs"
    )
    return dict(
        entry_rva=_hex(entry),
        size=size,
        body_sha256=digest,
        instruction_count=len(rows),
        graph=_graph(rows),
        direct_calls=[_edge(facts, pc, entry, target) for pc, target in calls],
    )


def _check_builder(rows, name):
    entry = BODY_PINS[name][0]
    delta = entry - 0x28B780
    indexed = {r.address - BASE: r for r in rows}
    required = {
        0x28B7A7: ("push", (_i(20),)),
        0x28B7B3: ("mov", (_r("eax"), _m("ebp", 12))),
        0x28B7B9: ("mov", (_r("ecx"), _m("eax", 0))),
        0x28B7BB: ("mov", (_r("eax"), _m("ebp", 8))),
        0x28B7BE: ("mov", (_m("edx", 4), _i(0))),
        0x28B7C5: (
            "mov",
            (
                _m("edx", 0),
                _i(BASE + (0x43B710 if name == "move_builder" else 0x43B704)),
            ),
        ),
        0x28B7CB: ("mov", (_m("edx", 8), _r("eax"))),
        0x28B7CE: ("mov", (_m("edx", 12), _r("ecx"))),
        0x28B7D1: ("mov", (_r("esi"), _m("edi", 4))),
        0x28B7D4: ("mov", (_r("ecx"), _m("esi", 64))),
        0x28B7DB: ("mov", (_m("esi", 64), _r("edx"))),
        0x28B7FB: ("mov", (_m("ecx", 4), _r("edx"))),
        0x28B7FE: ("mov", (_r("eax"), _r("edi"))),
        0x28B810: ("ret", (_i(20),)),
    }
    for pc, signature in required.items():
        _require(
            pc + delta in indexed and _signature(indexed[pc + delta]) == signature,
            "builder selected field or call argument differs",
        )


def _literal(data, image, rva, text):
    wanted = text.encode("ascii") + b"\0"
    offset = image.rva_span_to_file_offset(rva, len(wanted))
    _require(
        offset is not None and data[offset : offset + len(wanted)] == wanted,
        "complete method name differs",
    )
    return dict(
        rva=_hex(rva),
        size=len(wanted),
        sha256=hashlib.sha256(wanted).hexdigest(),
        text=text,
    )


def _parent_relations(decoded):
    required = {
        "move_parent": {
            0x257376: ("mov", (_r("eax"), _m("ebp", 12))),
            0x257379: ("mov", (_r("edx"), _m("ebp", 8))),
            0x25737C: ("sub", (_r("eax"), _r("edx"))),
            0x25737E: ("sar", (_r("eax"), _i(3))),
            0x257381: ("cmp", (_r("eax"), _i(1))),
            0x257384: ("ja", (_i(BASE + 0x25738A),)),
            0x257386: ("xor", (_r("bl"), _r("bl"))),
            0x257388: ("jmp", (_i(BASE + 0x2573F0),)),
            0x2573A7: ("movss", (_r("xmm0"), _m("ebp", 20))),
            0x2573B9: ("movss", (_m("ebp", -124), _r("xmm0"))),
            0x2573E6: ("mov", (_r("bl"), _i(1))),
            0x2573F0: ("test", (_r("edx"), _r("edx"))),
            0x2573F2: ("je", (_i(BASE + 0x257408),)),
            0x2573F4: ("mov", (_r("ecx"), _m("ebp", 16))),
            0x2573F7: ("sub", (_r("ecx"), _r("edx"))),
            0x2573F9: ("push", (_i(8),)),
            0x2573FB: ("sar", (_r("ecx"), _i(3))),
            0x2573FE: ("push", (_r("ecx"),)),
            0x2573FF: ("push", (_r("edx"),)),
            0x257408: ("mov", (_r("al"), _r("bl"))),
            0x257424: ("ret", (_i(16),)),
        },
        "charge_parent": {
            0x25773F: ("test", (_r("al"), _r("al"))),
            0x257741: ("je", (_i(BASE + 0x25774D),)),
            0x257743: ("mov", (_r("eax"), _m("esi", 4))),
            0x257746: ("mov", (_m("eax", -92), _i(2))),
            0x25774D: ("mov", (_r("ecx"), _m("ebp", 8))),
            0x257750: ("test", (_r("ecx"), _r("ecx"))),
            0x257752: ("je", (_i(BASE + 0x257768),)),
            0x257754: ("mov", (_r("eax"), _m("ebp", 16))),
            0x257757: ("sub", (_r("eax"), _r("ecx"))),
            0x257759: ("push", (_i(8),)),
            0x25775B: ("sar", (_r("eax"), _i(3))),
            0x25775E: ("push", (_r("eax"),)),
            0x25775F: ("push", (_r("ecx"),)),
            0x257777: ("ret", (_i(16),)),
        },
    }
    points = {}
    for name, signatures in required.items():
        indexed = {r.address - BASE: r for r in decoded[name]}
        for pc, signature in signatures.items():
            _require(
                pc in indexed and _signature(indexed[pc]) == signature,
                "movement parent selected relation differs",
            )
        points[name] = [common._point(indexed[pc]) for pc in signatures]
    return dict(
        move=dict(
            points=points["move_parent"],
            caller_bytes_consumed=16,
            caller_word_roles=[
                "path_begin",
                "path_end",
                "path_capacity",
                "parameter_bits",
            ],
            selected_count=dict(
                subtract_word_offsets=[8, 4],
                arithmetic_shift=3,
                compare_kind="unsigned_above",
                threshold=1,
            ),
            skip_path_sets_BL=0,
            record_path_sets_BL=1,
            return_copies_BL_to_AL=True,
            parameter_local_frame_offset=-124,
            input_parameter_frame_offset=20,
            free_guard_stride=8,
            free_guard_requires_nonzero_begin=True,
        ),
        charge=dict(
            points=points["charge_parent"],
            caller_bytes_consumed=16,
            called_parent_rva=_hex(0x257340),
            parent_call_rva=_hex(0x25773A),
            conditional_write=dict(
                condition="parent_return_AL_nonzero",
                receiver_word_offset=4,
                destination_delta=-92,
                width=4,
                value=2,
            ),
            separate_original_path_free=True,
            free_guard_stride=8,
        ),
    )


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    facts = sources["program_facts"]
    data, image, digest = common._load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable build differs")
    decoded = {
        name: common._decode_body(data, image, facts, entry)
        for name, (entry, _, _) in BODY_PINS.items()
    }
    for name, (entry, size, digest) in BODY_PINS.items():
        rows = decoded[name]
        _require(
            rows[0].address - BASE == entry
            and sum(len(r.bytes) for r in rows) == size
            and hashlib.sha256(b"".join(bytes(r.bytes) for r in rows)).hexdigest()
            == digest,
            "exact selected body differs",
        )
    bindings = []
    for method in METHODS:
        points = _selected_initializer(decoded["initializer"], method)
        refs = [
            r.address - BASE
            for r in decoded["initializer"]
            if r.id == x.X86_INS_PUSH
            and len(r.operands) == 1
            and r.operands[0].type == x.X86_OP_IMM
            and r.operands[0].imm == BASE + method["name_rva"]
        ]
        _require(
            refs == [method["call"] - 7],
            "selected initializer name-reference partition differs",
        )
        bindings.append(
            dict(
                name=method["name"],
                literal=_literal(data, image, method["name_rva"], method["name"]),
                method_rva=_hex(method["target"]),
                builder_rva=_hex(method["builder"]),
                initializer_points=points,
                initializer_call=_edge(
                    facts, method["call"], 0x279880, method["builder"]
                ),
                caller_argument_roles=[
                    "name_address",
                    "method_slot_address",
                    "unused_word",
                    "unused_word",
                    "unused_word",
                ],
                record_fields=[
                    dict(
                        offset=0,
                        role="selected_vtable",
                        value_rva=_hex(method["vtable"]),
                    ),
                    dict(offset=4, role="next", value=0),
                    dict(offset=8, role="name_address"),
                    dict(offset=12, role="dereferenced_method_slot"),
                ],
                allocation_bytes=20,
                caller_bytes_consumed=20,
                unwritten_offset=16,
                owner_indirection_offset=4,
                owner_list_offset=64,
            )
        )
    for name in ("move_builder", "charge_builder"):
        _check_builder(decoded[name], name)
    packets = {
        name: _body_packet(decoded[name], name, facts)
        for name in BODY_PINS
        if name != "initializer"
    }
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=copy.deepcopy(facts["identity"]),
        source_receipts=identities,
        decoder=dict(name="Capstone", version="5.0.7", mode="x86-32"),
        initializer=dict(
            entry_rva=_hex(0x279880),
            size=32310,
            body_sha256=BODY_PINS["initializer"][2],
            instruction_count=len(decoded["initializer"]),
        ),
        bindings=bindings,
        distinct_bonus_literal=_literal(data, image, 0x439038, "AddMoveBonus"),
        bodies=packets,
        parent_relations=_parent_relations(decoded),
        scope=dict(
            evidence="static_exact_build",
            runtime_registration=False,
            class_namespace=False,
            child_semantics=False,
            pawn_movement=False,
            accounting_promotions=0,
        ),
    )
    common._assert_publication_safe(result)
    return result


def build_binding(executable, sources):
    result = _normalize(lambda: _build_unsealed(executable, sources))
    _require(
        common._canonical_sha256(result) == SEALED_SHA256, "binding receipt differs"
    )
    return result


def validate_structure(evidence, sources):
    def checked():
        _preflight(sources)
        common._validate_json_tree(evidence, "evidence")
        _require(
            type(evidence) is dict
            and evidence.get("analysis_kind") == ANALYSIS_KIND
            and common._canonical_sha256(evidence) == SEALED_SHA256,
            "sealed binding receipt differs",
        )
        _require(
            evidence["source_receipts"] == _preflight(sources),
            "source receipt join differs",
        )
        common._assert_publication_safe(evidence)
        return copy.deepcopy(evidence)

    return _normalize(checked)


def validate_binding(executable, evidence, sources):
    checked = validate_structure(evidence, sources)
    rebuilt = build_binding(executable, sources)
    _require(
        common._canonical_bytes(checked) == common._canonical_bytes(rebuilt),
        "executable rebuilt binding differs",
    )
    return checked


def encode_binding(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
