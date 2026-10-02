"""Independent selected-static movement binding checks; no child behavior oracle.

Handwritten instruction recipes are decoded only when the primary runs pytest.
Exact PE extraction runs in isolated quiet workers, never a game process.
"""

import copy
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from collections import UserDict

import capstone
import pytest

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import native_movement_effect_binding as c

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
FACTS_PATH = PROGRAMS / (PREFIX + "program_facts.json")
EVIDENCE_PATH = PROGRAMS / (PREFIX + "native_movement_effect_binding.json")
BASE = 0x00400000
FACTS_SHA = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
EXE_SHA = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
BODY = {
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
CALLS = {
    "move_builder": [(0x28B7A9, 0x3574DB)],
    "charge_builder": [(0x28B849, 0x3574DB)],
    "move_parent": [
        (0x257392, 0x1999A0),
        (0x2573A2, 0x0C5BB0),
        (0x2573BE, 0x15B9B0),
        (0x2573D0, 0x259F00),
        (0x2573DB, 0x10E2A0),
        (0x2573E8, 0x10E2A0),
        (0x257400, 0x7800),
        (0x25741C, 0x3574CA),
    ],
    "charge_parent": [(0x257733, 0x9A8E0), (0x25773A, 0x257340), (0x257760, 0x7800)],
}
BRANCHES = {
    "move_builder": {
        0x28B7D9: (0x28B7DB, 0x28B7E0),
        0x28B7DE: (0x28B7FE,),
        0x28B7E7: (0x28B7E9, 0x28B7FB),
        0x28B7F9: (0x28B7F0, 0x28B7FB),
    },
    "charge_builder": {
        0x28B879: (0x28B87B, 0x28B880),
        0x28B87E: (0x28B89E,),
        0x28B887: (0x28B889, 0x28B89B),
        0x28B899: (0x28B890, 0x28B89B),
    },
    "move_parent": {
        0x257384: (0x257386, 0x25738A),
        0x257388: (0x2573F0,),
        0x2573F2: (0x2573F4, 0x257408),
    },
    "charge_parent": {0x257741: (0x257743, 0x25774D), 0x257752: (0x257754, 0x257768)},
}
RETURNS = {
    "move_builder": (0x28B810, 20),
    "charge_builder": (0x28B8B0, 20),
    "move_parent": (0x257424, 16),
    "charge_parent": (0x257777, 16),
}


def canonical(value):
    return (
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def hx(value):
    return f"0x{value:08x}"


def point(pc, data):
    return dict(rva=hx(pc), size=len(data), sha256=hashlib.sha256(data).hexdigest())


def decoded(pc, data):
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    rows = list(decoder.disasm(data, BASE + pc))
    assert sum(row.size for row in rows) == len(data)
    return rows


def instruction_map(table):
    rows = []
    for pc, hexadecimal in table.items():
        one = decoded(pc, bytes.fromhex(hexadecimal))
        assert len(one) == 1
        rows.extend(one)
    return rows


def initializer_recipe(method):
    slot_store = b"\xc7\x45\xec" + struct.pack("<I", BASE + method["target"])
    pushed_unused = b"\xff\x75\xf0"
    chunks = (
        [pushed_unused, slot_store, pushed_unused]
        if method["name"] == "AddMove"
        else [slot_store, pushed_unused, pushed_unused]
    )
    chunks += [
        b"\x51",
        b"\x8d\x4d\xec",
        b"\x51",
        b"\x68" + struct.pack("<I", BASE + method["name_rva"]),
        b"\x8b\xc8",
        b"\xe8" + struct.pack("<i", method["builder"] - method["call"] - 5),
    ]
    return chunks


BUILDER_BYTES = {
    0x28B7A7: "6a14",
    0x28B7B3: "8b450c",
    0x28B7B9: "8b08",
    0x28B7BB: "8b4508",
    0x28B7BE: "c7420400000000",
    0x28B7C5: "c70210b78300",
    0x28B7CB: "894208",
    0x28B7CE: "894a0c",
    0x28B7D1: "8b7704",
    0x28B7D4: "8b4e40",
    0x28B7DB: "895640",
    0x28B7FB: "895104",
    0x28B7FE: "8bc7",
    0x28B810: "c21400",
}
PARENT_BYTES = {
    "move_parent": {
        0x257376: "8b450c",
        0x257379: "8b5508",
        0x25737C: "2bc2",
        0x25737E: "c1f803",
        0x257381: "83f801",
        0x257384: "7704",
        0x257386: "32db",
        0x257388: "eb66",
        0x2573A7: "f30f104514",
        0x2573B9: "f30f114584",
        0x2573E6: "b301",
        0x2573F0: "85d2",
        0x2573F2: "7414",
        0x2573F4: "8b4d10",
        0x2573F7: "2bca",
        0x2573F9: "6a08",
        0x2573FB: "c1f903",
        0x2573FE: "51",
        0x2573FF: "52",
        0x257408: "8ac3",
        0x257424: "c21000",
    },
    "charge_parent": {
        0x25773F: "84c0",
        0x257741: "740a",
        0x257743: "8b4604",
        0x257746: "c740a402000000",
        0x25774D: "8b4d08",
        0x257750: "85c9",
        0x257752: "7414",
        0x257754: "8b4510",
        0x257757: "2bc1",
        0x257759: "6a08",
        0x25775B: "c1f803",
        0x25775E: "50",
        0x25775F: "51",
        0x257777: "c21000",
    },
}


@pytest.fixture(scope="module")
def receipts():
    return json.loads(EVIDENCE_PATH.read_bytes()), dict(
        program_facts=json.loads(FACTS_PATH.read_bytes())
    )


@pytest.mark.parametrize("method", METHODS, ids=lambda m: m["name"])
def test_handwritten_initializer_stack_recipe(method):
    chunks = initializer_recipe(method)
    rows = decoded(method["start"], b"".join(chunks))
    expected = []
    pc = method["start"]
    for chunk in chunks:
        expected.append(point(pc, chunk))
        pc += len(chunk)
    assert pc == method["end"]
    assert c._selected_initializer(rows, method) == expected
    assert len(expected) == 9
    # The method-slot contents and its address are separate arguments.
    assert b"\xc7\x45\xec" in b"".join(chunks)
    assert chunks[4] == b"\x8d\x4d\xec"


@pytest.mark.parametrize("index", range(9))
@pytest.mark.parametrize("method", METHODS, ids=lambda m: m["name"])
def test_every_initializer_argument_or_order_is_bound(method, index):
    chunks = initializer_recipe(method)
    replacement = [
        bytes.fromhex("ff75f4"),
        b"\xc7\x45\xe8" + struct.pack("<I", BASE + method["target"]),
        bytes.fromhex("ff75f4"),
        b"\x52",
        bytes.fromhex("8d4de8"),
        b"\x52",
        b"\x68" + struct.pack("<I", BASE + method["name_rva"] + 1),
        b"\x8b\xd0",
        b"\xe8" + struct.pack("<i", method["builder"] + 1 - method["call"] - 5),
    ]
    if method["name"] == "AddCharge":
        replacement[0], replacement[1] = replacement[1], replacement[0]
    chunks[index] = replacement[index]
    with pytest.raises(c.MovementBindingError):
        c._selected_initializer(decoded(method["start"], b"".join(chunks)), method)


@pytest.mark.parametrize("kind", ("missing", "shifted", "reordered"))
def test_initializer_recipe_requires_complete_selected_instruction_extent(kind):
    method = METHODS[0]
    rows = decoded(method["start"], b"".join(initializer_recipe(method)))
    if kind == "missing":
        rows.pop(2)
    elif kind == "shifted":
        rows = decoded(method["start"] + 1, b"".join(initializer_recipe(method)))
    else:
        rows[0], rows[1] = rows[1], rows[0]
    with pytest.raises(c.MovementBindingError):
        c._selected_initializer(rows, method)


@pytest.mark.parametrize(
    "kind", ("method_word", "bonus_name", "method_value_as_argument", "other_builder")
)
def test_initializer_binds_slot_contents_name_and_dereferenced_method_transport(kind):
    method = METHODS[0]
    chunks = initializer_recipe(method)
    if kind == "method_word":
        chunks[1] = b"\xc7\x45\xec" + struct.pack("<I", BASE + 0x2576F0)
    elif kind == "bonus_name":
        chunks[6] = b"\x68" + struct.pack("<I", BASE + 0x439038)
    elif kind == "method_value_as_argument":
        chunks[4] = bytes.fromhex("8b4dec")
    else:
        chunks[8] = b"\xe8" + struct.pack("<i", 0x28B820 - method["call"] - 5)
    with pytest.raises(c.MovementBindingError):
        c._selected_initializer(decoded(method["start"], b"".join(chunks)), method)


@pytest.mark.parametrize("name", ("move_builder", "charge_builder"))
def test_handwritten_builder_record_fields_and_owner_list(name):
    delta = 0 if name == "move_builder" else 0xA0
    table = {pc + delta: data for pc, data in BUILDER_BYTES.items()}
    if delta:
        table[0x28B7C5 + delta] = "c70204b78300"
    c._check_builder(instruction_map(table), name)


@pytest.mark.parametrize("pc", tuple(BUILDER_BYTES))
def test_each_selected_builder_field_or_argument_is_required(pc):
    rows = instruction_map(BUILDER_BYTES)
    rows = [row for row in rows if row.address != BASE + pc]
    with pytest.raises(c.MovementBindingError):
        c._check_builder(rows, "move_builder")


@pytest.mark.parametrize(
    "pc,wrong",
    (
        (0x28B7A7, "6a10"),
        (0x28B7B9, "8b4804"),
        (0x28B7BE, "c7420401000000"),
        (0x28B7C5, "c70204b78300"),
        (0x28B7CB, "894210"),
        (0x28B7CE, "894a10"),
        (0x28B7D1, "8b7708"),
        (0x28B7D4, "8b4e44"),
        (0x28B7DB, "895644"),
        (0x28B7FB, "895108"),
        (0x28B810, "c21000"),
    ),
)
def test_builder_semantic_mutations_are_independent_of_receipt_hash(pc, wrong):
    table = dict(BUILDER_BYTES)
    table[pc] = wrong
    with pytest.raises(c.MovementBindingError):
        c._check_builder(instruction_map(table), "move_builder")


def expected_relations():
    return dict(
        move=dict(
            points=[
                point(pc, bytes.fromhex(data))
                for pc, data in PARENT_BYTES["move_parent"].items()
            ],
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
            points=[
                point(pc, bytes.fromhex(data))
                for pc, data in PARENT_BYTES["charge_parent"].items()
            ],
            caller_bytes_consumed=16,
            called_parent_rva=hx(0x257340),
            parent_call_rva=hx(0x25773A),
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


def test_handwritten_parent_count_parameter_free_and_charge_relations():
    rows = {name: instruction_map(table) for name, table in PARENT_BYTES.items()}
    assert c._parent_relations(rows) == expected_relations()


@pytest.mark.parametrize(
    "name,pc,wrong",
    (
        ("move_parent", 0x25737E, "c1e803"),
        ("move_parent", 0x257381, "83f802"),
        ("move_parent", 0x257384, "7f04"),
        ("move_parent", 0x257386, "b301"),
        ("move_parent", 0x2573A7, "f30f104510"),
        ("move_parent", 0x2573B9, "f30f114588"),
        ("move_parent", 0x2573E6, "b300"),
        ("move_parent", 0x2573F0, "85c0"),
        ("move_parent", 0x2573F9, "6a04"),
        ("move_parent", 0x2573FB, "c1e903"),
        ("move_parent", 0x257408, "8ac7"),
        ("move_parent", 0x257424, "c21400"),
        ("charge_parent", 0x25773F, "85c0"),
        ("charge_parent", 0x257741, "750a"),
        ("charge_parent", 0x257743, "8b4608"),
        ("charge_parent", 0x257746, "c740a801000000"),
        ("charge_parent", 0x257759, "6a04"),
        ("charge_parent", 0x25775B, "c1e803"),
        ("charge_parent", 0x257777, "c21400"),
    ),
)
def test_parent_source_relations_reject_signed_branch_layout_and_field_changes(
    name, pc, wrong
):
    tables = copy.deepcopy(PARENT_BYTES)
    tables[name][pc] = wrong
    rows = {key: instruction_map(table) for key, table in tables.items()}
    with pytest.raises(c.MovementBindingError):
        c._parent_relations(rows)


class LiteralImage:
    def __init__(self, rva, length):
        self.rva, self.length = rva, length

    def rva_span_to_file_offset(self, rva, length):
        return 0 if rva == self.rva and length <= self.length else None


@pytest.mark.parametrize(
    "name,rva",
    (("AddMove", 0x438D20), ("AddCharge", 0x438D14), ("AddMoveBonus", 0x439038)),
)
def test_names_require_complete_nul_terminated_literals(name, rva):
    data = name.encode("ascii") + bytes([0])
    assert c._literal(data, LiteralImage(rva, len(data)), rva, name) == dict(
        rva=hx(rva), size=len(data), text=name, sha256=hashlib.sha256(data).hexdigest()
    )
    for wrong in (data[:-1], data[:-1] + b"X", b"add" + data[3:], b"AddMoveBonus\0"):
        if wrong == data:
            continue
        with pytest.raises(c.MovementBindingError):
            c._literal(wrong, LiteralImage(rva, len(wrong)), rva, name)
    with pytest.raises(c.MovementBindingError):
        c._literal(data, LiteralImage(rva + 1, len(data)), rva, name)


def test_graph_is_syntactic_closed_flow_and_opaque_call_fallthrough():
    # NOP; JZ RET; direct CALL outside body; RET 16. No callee return is asserted.
    rows = decoded(0x1000, bytes.fromhex("907405e800100000c21000"))
    graph = c._graph(rows)
    assert graph["node_count"] == 4 and graph["edge_count"] == 4
    nodes = graph["nodes"]
    assert nodes[1]["successor_rvas"] == [hx(0x1003), hx(0x1008)]
    assert nodes[2]["flow_kind"] == "opaque_call_possible_fallthrough"
    assert nodes[2]["direct_target_rva"] == hx(0x2008)
    assert nodes[3]["flow_kind"] == "return_syntax" and nodes[3]["successor_rvas"] == []


@pytest.mark.parametrize("hexadecimal", ("ffe0", "ffd0c21000", "eb01c21000", "c3"))
def test_graph_rejects_indirect_call_jump_outside_body_and_wrong_return_form(
    hexadecimal,
):
    with pytest.raises(c.MovementBindingError):
        c._graph(decoded(0x1000, bytes.fromhex(hexadecimal)))


def test_sealed_static_receipt_has_exact_names_recipes_and_unpromoted_scope(receipts):
    evidence, sources = receipts
    assert digest(evidence) == c.SEALED_SHA256 and c.SEALED_SHA256 != "PENDING"
    assert (
        EVIDENCE_PATH.read_bytes()
        == encoded(evidence)
        == c.encode_binding(evidence).encode("utf-8")
    )
    assert b"\r" not in EVIDENCE_PATH.read_bytes()
    assert set(evidence) == {
        "schema_version",
        "analysis_kind",
        "build_identity",
        "source_receipts",
        "decoder",
        "initializer",
        "bindings",
        "distinct_bonus_literal",
        "bodies",
        "parent_relations",
        "scope",
    }
    assert evidence["schema_version"] == 1 and type(evidence["schema_version"]) is int
    assert evidence["analysis_kind"] == "pe_native_movement_effect_binding"
    assert evidence["decoder"] == dict(name="Capstone", version="5.0.7", mode="x86-32")
    assert evidence["build_identity"] == sources["program_facts"]["identity"]
    assert evidence["build_identity"]["executable_sha256"] == EXE_SHA
    assert evidence["source_receipts"] == dict(
        program_facts=dict(
            analysis_kind="pe_ghidra_program_facts", canonical_sha256=FACTS_SHA
        )
    )
    assert c.SOURCE_PINS == dict(program_facts=("pe_ghidra_program_facts", FACTS_SHA))
    entry, size, sha = BODY["initializer"]
    assert evidence["initializer"] == dict(
        entry_rva=hx(entry), size=size, body_sha256=sha, instruction_count=9348
    )
    assert evidence["scope"] == dict(
        evidence="static_exact_build",
        runtime_registration=False,
        class_namespace=False,
        child_semantics=False,
        pawn_movement=False,
        accounting_promotions=0,
    )
    assert [row["name"] for row in evidence["bindings"]] == ["AddMove", "AddCharge"]
    for row, method in zip(evidence["bindings"], METHODS):
        data = method["name"].encode("ascii") + bytes([0])
        assert row["literal"] == dict(
            rva=hx(method["name_rva"]),
            size=len(data),
            text=method["name"],
            sha256=hashlib.sha256(data).hexdigest(),
        )
        assert row["method_rva"] == hx(method["target"]) and row["builder_rva"] == hx(
            method["builder"]
        )
        assert row["record_fields"] == [
            dict(offset=0, role="selected_vtable", value_rva=hx(method["vtable"])),
            dict(offset=4, role="next", value=0),
            dict(offset=8, role="name_address"),
            dict(offset=12, role="dereferenced_method_slot"),
        ]
        assert row["caller_argument_roles"] == [
            "name_address",
            "method_slot_address",
            "unused_word",
            "unused_word",
            "unused_word",
        ]
        assert (
            row["allocation_bytes"],
            row["caller_bytes_consumed"],
            row["unwritten_offset"],
            row["owner_indirection_offset"],
            row["owner_list_offset"],
        ) == (20, 20, 16, 4, 64)
        chunks, pc, wanted = initializer_recipe(method), method["start"], []
        for chunk in chunks:
            wanted.append(point(pc, chunk))
            pc += len(chunk)
        assert row["initializer_points"] == wanted
        call = row["initializer_call"]
        assert (
            call["instruction_rva"],
            call["source_entry_rva"],
            call["target_entry_rva"],
            call["target_rva"],
        ) == (
            hx(method["call"]),
            hx(0x279880),
            hx(method["builder"]),
            hx(method["builder"]),
        )
    bonus = b"AddMoveBonus\0"
    assert evidence["distinct_bonus_literal"] == dict(
        rva=hx(0x439038),
        size=13,
        text="AddMoveBonus",
        sha256=hashlib.sha256(bonus).hexdigest(),
    )


def test_all_four_graphs_have_full_byte_extent_and_handwritten_call_branch_relations(
    receipts,
):
    evidence, sources = receipts
    facts = sources["program_facts"]
    counts = {
        "move_builder": (51, 53),
        "charge_builder": (51, 53),
        "move_parent": (72, 73),
        "charge_parent": (46, 47),
    }
    declared = facts["ghidra_declared_direct_calls"]
    assert set(evidence["bodies"]) == set(counts)
    for name, body in evidence["bodies"].items():
        entry, size, sha = BODY[name]
        assert (body["entry_rva"], body["size"], body["body_sha256"]) == (
            hx(entry),
            size,
            sha,
        )
        graph = body["graph"]
        assert (graph["node_count"], graph["edge_count"]) == counts[name]
        nodes = graph["nodes"]
        assert body["instruction_count"] == len(nodes) == counts[name][0]
        pc = entry
        for node in nodes:
            assert (
                node["rva"] == hx(pc) and type(node["size"]) is int and node["size"] > 0
            )
            assert set(node) == {
                "rva",
                "size",
                "sha256",
                "flow_kind",
                "successor_rvas",
                "direct_target_rva",
            }
            assert len(node["sha256"]) == 64
            pc += node["size"]
        assert pc == entry + size
        call_map = dict(CALLS[name])
        ret_pc, ret_arg = RETURNS[name]
        for node in nodes:
            pc = int(node["rva"], 16)
            if pc in BRANCHES[name]:
                successors = [hx(target) for target in BRANCHES[name][pc]]
                flow = (
                    "direct_jump"
                    if len(successors) == 1
                    else "direct_conditional_branch"
                )
                target = None
            elif pc == ret_pc:
                successors, flow, target = [], "return_syntax", None
                assert (
                    node["sha256"]
                    == hashlib.sha256(bytes([0xC2, ret_arg, 0])).hexdigest()
                )
            else:
                successors = [hx(pc + node["size"])]
                flow = (
                    "opaque_call_possible_fallthrough"
                    if pc in call_map
                    else "fallthrough"
                )
                target = hx(call_map[pc]) if pc in call_map else None
            assert (
                node["successor_rvas"],
                node["flow_kind"],
                node["direct_target_rva"],
            ) == (successors, flow, target)
        assert graph["edge_count"] == sum(len(n["successor_rvas"]) for n in nodes)
        expected_edges = []
        for pc, target in CALLS[name]:
            matching = [r for r in declared if int(r["instruction_rva"], 16) == pc]
            assert len(matching) == 1
            source = matching[0]
            assert (
                int(source["source_entry_rva"], 16),
                int(source["target_entry_rva"], 16),
                int(source["target_rva"], 16),
            ) == (entry, target, target)
            expected_edges.append(
                dict(
                    instruction_rva=hx(pc),
                    source_entry_rva=hx(entry),
                    target_entry_rva=hx(target),
                    target_rva=hx(target),
                    target_name_sha256=hashlib.sha256(
                        source["target_name"].encode("utf-8")
                    ).hexdigest(),
                )
            )
        assert body["direct_calls"] == expected_edges
    assert sum(b["graph"]["node_count"] for b in evidence["bodies"].values()) == 220
    assert sum(b["graph"]["edge_count"] for b in evidence["bodies"].values()) == 226
    for key, name in (("move", "move_parent"), ("charge", "charge_parent")):
        relation = copy.deepcopy(evidence["parent_relations"][key])
        expected = expected_relations()[key]
        selected = relation.pop("points")
        expected.pop("points")
        assert relation == expected
        indexed = {p["rva"]: p for p in evidence["bodies"][name]["graph"]["nodes"]}
        assert [p["rva"] for p in selected] == [hx(pc) for pc in PARENT_BYTES[name]]
        assert all(
            p == {k: indexed[p["rva"]][k] for k in ("rva", "size", "sha256")}
            for p in selected
        )


def test_source_pin_exact_atlas_body_partition_and_output_detachment(receipts):
    evidence, sources = receipts
    assert digest(sources["program_facts"]) == FACTS_SHA
    indexed = {
        int(r["entry_rva"], 16): r for r in sources["program_facts"]["functions"]
    }
    for entry, size, sha in BODY.values():
        assert indexed[entry]["ranges"] == [dict(start_rva=hx(entry), size=size)]
        assert (indexed[entry]["body_size"], indexed[entry]["body_sha256"]) == (
            size,
            sha,
        )
    before = copy.deepcopy((evidence, sources))
    checked = c.validate_structure(evidence, sources)
    checked["bindings"][0]["literal"]["text"] = "changed"
    checked["bodies"]["move_parent"]["graph"]["nodes"].clear()
    assert (evidence, sources) == before


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "outer_facade",
        "nested_facade",
        "kind",
        "exe",
        "size",
        "sha",
        "range",
        "duplicate",
        "edge",
        "float",
        "nontext",
        "bool",
    ),
)
def test_direct_preflight_normalizes_strict_source_and_pinned_atlas_errors(
    receipts, kind
):
    _, original = receipts
    sources = copy.deepcopy(original)
    facts = sources["program_facts"]
    function = next(r for r in facts["functions"] if r["entry_rva"] == hx(0x257340))
    if kind == "missing":
        sources.clear()
    elif kind == "extra":
        sources["other"] = facts
    elif kind == "outer_facade":
        sources = UserDict(sources)
    elif kind == "nested_facade":
        sources["program_facts"] = UserDict(facts)
    elif kind == "kind":
        facts["analysis_kind"] = "pe_native_movement_effect_binding"
    elif kind == "exe":
        facts["identity"]["executable_sha256"] = "0" * 64
    elif kind == "size":
        function["body_size"] += 1
    elif kind == "sha":
        function["body_sha256"] = "0" * 64
    elif kind == "range":
        function["ranges"][0]["start_rva"] = hx(0x257341)
    elif kind == "duplicate":
        facts["functions"].append(copy.deepcopy(function))
    elif kind == "edge":
        edge = next(
            r
            for r in facts["ghidra_declared_direct_calls"]
            if r["instruction_rva"] == hx(0x25773A)
        )
        edge["target_rva"] = hx(0x257341)
    elif kind == "float":
        function["body_size"] = 231.0
    elif kind == "nontext":
        facts[1] = "bad"
    else:
        facts["schema_version"] = True
    with pytest.raises(c.MovementBindingError):
        c._preflight(sources)


@pytest.mark.parametrize(
    "kind",
    (
        "name",
        "bonus",
        "slot",
        "method",
        "builder",
        "field16",
        "size",
        "point",
        "branch",
        "call",
        "parameter",
        "signed",
        "BL",
        "charge",
        "scope",
        "schema",
        "pin",
        "decoder",
        "extra",
    ),
)
def test_receipt_mutations_cannot_reseal_by_changing_local_labels(receipts, kind):
    original, sources = receipts
    evidence = copy.deepcopy(original)
    if kind == "name":
        evidence["bindings"][0]["literal"]["text"] = "AddMoveBonus"
    elif kind == "bonus":
        evidence["distinct_bonus_literal"]["rva"] = hx(0x438D20)
    elif kind == "slot":
        evidence["bindings"][0]["caller_argument_roles"][1] = "method_value"
    elif kind == "method":
        evidence["bindings"][0]["method_rva"] = hx(0x2576F0)
    elif kind == "builder":
        evidence["bindings"][0]["builder_rva"] = hx(0x28B820)
    elif kind == "field16":
        evidence["bindings"][0]["record_fields"].append(
            dict(offset=16, role="invented")
        )
    elif kind == "size":
        evidence["bindings"][0]["allocation_bytes"] = 16
    elif kind == "point":
        evidence["bindings"][0]["initializer_points"][0]["sha256"] = "0" * 64
    elif kind == "branch":
        evidence["bodies"]["move_parent"]["graph"]["nodes"][0]["successor_rvas"] = []
    elif kind == "call":
        evidence["bodies"]["charge_parent"]["direct_calls"][1]["target_entry_rva"] = hx(
            0x257341
        )
    elif kind == "parameter":
        evidence["parent_relations"]["move"]["input_parameter_frame_offset"] = 16
    elif kind == "signed":
        evidence["parent_relations"]["move"]["selected_count"][
            "compare_kind"
        ] = "signed_above"
    elif kind == "BL":
        evidence["parent_relations"]["move"]["record_path_sets_BL"] = 0
    elif kind == "charge":
        evidence["parent_relations"]["charge"]["conditional_write"][
            "destination_delta"
        ] = -88
    elif kind == "scope":
        evidence["scope"]["child_semantics"] = True
    elif kind == "schema":
        evidence["schema_version"] = True
    elif kind == "pin":
        evidence["source_receipts"]["program_facts"]["canonical_sha256"] = "0" * 64
    elif kind == "decoder":
        evidence["decoder"]["version"] = "other"
    else:
        evidence["invented"] = 0
    assert digest(evidence) != c.SEALED_SHA256
    with pytest.raises(c.MovementBindingError):
        c.validate_structure(evidence, sources)


def test_encoding_preserves_unicode_lf_and_rejects_nan():
    sample = dict(name="é", value=[None, True, 0xFFFFFFFF])
    assert c.encode_binding(sample).encode("utf-8") == encoded(sample)
    with pytest.raises(ValueError):
        c.encode_binding(dict(value=float("nan")))


def quiet_environment():
    environment = dict(os.environ)
    environment.pop("PYTHONFAULTHANDLER", None)
    return environment


def isolated(action):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE for the exact selected-static source gate")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action],
        cwd=ROOT,
        capture_output=True,
        env=quiet_environment(),
        timeout=600,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout == b"" and result.stderr == b""


def test_exact_source_builder_and_verifier_in_one_isolated_worker():
    isolated("selected_static")


def test_exact_source_mutations_are_rejected_without_rebuilding_the_atlas():
    isolated("source_tamper")


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_cli_returns_the_exact_deterministically_encoded_sealed_receipt(
    receipts, command
):
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE for the selected-static source gate")
    arguments = [
        sys.executable,
        str(ROOT / "scripts/itb_native_movement_effect_binding.py"),
        command,
        "--program-facts",
        str(FACTS_PATH),
    ]
    if command != "build":
        arguments += ["--evidence", str(EVIDENCE_PATH)]
    if command != "verify-structure":
        arguments += ["--executable", str(Path(executable))]
    result = subprocess.run(
        arguments, cwd=ROOT, capture_output=True, env=quiet_environment(), timeout=600
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stderr == b"" and result.stdout == EVIDENCE_PATH.read_bytes()


@pytest.mark.parametrize(
    "kind", ("crlf", "compact", "bom", "duplicate_key", "source", "receipt")
)
def test_structure_cli_rejects_encoding_source_and_receipt_tampering(
    receipts, tmp_path, kind
):
    evidence, sources = receipts
    raw = encoded(evidence)
    if kind == "crlf":
        raw = raw.replace(b"\n", b"\r\n")
    elif kind == "compact":
        raw = canonical(evidence)
    elif kind == "bom":
        raw = bytes([0xEF, 0xBB, 0xBF]) + raw
    elif kind == "duplicate_key":
        raw = raw.replace(b"{\n", b'{\n  "schema_version": 1,\n', 1)
    elif kind == "source":
        sources = copy.deepcopy(sources)
        sources["program_facts"]["schema_version"] = 99
    else:
        evidence = copy.deepcopy(evidence)
        evidence["scope"]["pawn_movement"] = True
        raw = encoded(evidence)
    evidence_path, facts_path = tmp_path / "receipt.json", tmp_path / "facts.json"
    evidence_path.write_bytes(raw)
    facts_path.write_bytes(encoded(sources["program_facts"]))
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_movement_effect_binding.py"),
            "verify-structure",
            "--program-facts",
            str(facts_path),
            "--evidence",
            str(evidence_path),
        ],
        cwd=ROOT,
        capture_output=True,
        env=quiet_environment(),
        timeout=600,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert result.stderr.startswith(b"error:")


def worker_selected_static():
    evidence = json.loads(EVIDENCE_PATH.read_bytes())
    sources = dict(program_facts=json.loads(FACTS_PATH.read_bytes()))
    before = copy.deepcopy(sources)
    built = c.build_binding(Path(os.environ["ITB_EXACT_EXE"]), sources)
    assert encoded(built) == EVIDENCE_PATH.read_bytes()
    assert (
        c.validate_binding(Path(os.environ["ITB_EXACT_EXE"]), evidence, sources)
        == evidence
    )
    assert sources == before


def worker_source_tamper():
    import tempfile

    sources = dict(program_facts=json.loads(FACTS_PATH.read_bytes()))
    executable = Path(os.environ["ITB_EXACT_EXE"])
    data, image, sha = c.common._load_executable(executable)
    assert sha == EXE_SHA
    # Selected bodies, argument slot, complete names and bonus, never the whole atlas.
    locations = [
        0x279880,
        0x28B780,
        0x28B820,
        0x257340,
        0x2576F0,
        0x27B75B,
        0x27B76A,
        0x27B77F,
        0x438D20,
        0x438D27,
        0x438D14,
        0x439038,
    ]
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "changed.exe"
        for rva in locations:
            offset = image.rva_span_to_file_offset(rva, 1)
            assert offset is not None
            changed = bytearray(data)
            changed[offset] ^= 1
            target.write_bytes(changed)
            try:
                c.build_binding(target, sources)
            except c.MovementBindingError:
                pass
            else:
                raise AssertionError(f"changed selected source accepted: {rva:x}")


if __name__ == "__main__":
    faulthandler.disable()
    if sys.argv[1] == "selected_static":
        worker_selected_static()
    elif sys.argv[1] == "source_tamper":
        worker_source_tamper()
    else:
        raise SystemExit("unknown worker")
