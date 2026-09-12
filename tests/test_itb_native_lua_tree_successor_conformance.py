"""Native successor events, final arithmetic flags and address-generic joining."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory import native_lua_tree_successor_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_"


def case(shape, index, marker=1, alignment=0):
    vector = dict(
        shape=shape,
        start=0x10000000 + 64 * index + alignment,
        node_alignment=alignment,
        alignment=15,
        sentinel_byte=marker,
        df=1,
        seed=2,
    )
    fixture = c.case_fixture(**vector)
    return vector, fixture, c.oracle(vector, fixture)


def read(memory, address, width=4):
    return sum(memory[address + i] << (8 * i) for i in range(width))


def put(memory, address, value, width=4):
    for i, byte in enumerate(value.to_bytes(width, "little")):
        memory[address + i] = byte


@pytest.mark.parametrize("marker", [1, 255])
def test_maximum_right_chain_preserves_every_ancestor_write(marker):
    v, f, e = case("right_chain", 4, marker, 7)
    base = 0x10000007
    assert [a["value"] for a in e["events"] if a["access"] == "write"] == [
        base + 64 * i for i in (3, 2, 1, 0)
    ]
    assert e["result"] == base
    assert e["registers"] == dict(
        f["registers"], eax=f["slot"], edx=f["slot"], ecx=base + 128, esp=f["stack"] + 4
    )
    assert e["flags"] == (0 if marker == 1 else 0x84)
    assert read(e["memory"], f["slot"]) == base
    assert e["events"][-1] == dict(
        access="read", address=f["stack"], width=4, value=e["endpoint"]
    )


def test_deep_right_subtree_descent_reads_but_only_writes_final_node():
    _, f, e = case("deep_right_subtree", 1)
    assert e["result"] == 0x10000080
    assert [a for a in e["events"] if a["access"] == "write"] == [
        dict(access="write", address=f["slot"], width=4, value=0x10000080)
    ]
    descent = [
        a["address"]
        for a in e["events"]
        if a["access"] == "read"
        and a["width"] == 4
        and a["address"] in (0x10000140, 0x10000100, 0x100000C0, 0x10000080)
    ]
    assert descent == [0x10000140, 0x10000100, 0x100000C0, 0x10000080]
    assert e["registers"]["ecx"] == e["result"]
    assert e["flags"] == 0


@pytest.mark.parametrize("shape", c.SHAPES)
@pytest.mark.parametrize("marker", [1, 255])
def test_head_start_returns_slot_without_dereferencing_head_links(shape, marker):
    _, f, e = case(shape, 0, marker)
    assert e["memory"] == f["memory"]
    assert e["events"] == [
        dict(access="read", address=f["slot"], width=4, value=0x10000000),
        dict(access="read", address=0x1000000D, width=1, value=marker),
        dict(access="read", address=f["stack"], width=4, value=e["endpoint"]),
    ]
    assert e["registers"] == dict(
        f["registers"], eax=f["slot"], edx=f["slot"], esp=f["stack"] + 4
    )


def test_parent_break_flags_come_from_pointer_comparison():
    _, f, e = case("balanced", 1)
    # Node 1 is node 2's left child, so final CMP is 0x10000040-0x100000c0.
    # Result -128: CF=1, SF=1, PF=0, AF=0, ZF=0, OF=0.
    assert e["result"] == 0x10000080
    assert e["flags"] == 0x81
    assert e["registers"]["ecx"] == 0x10000040


def test_oracle_rebases_to_arbitrary_caller_slot_stack_and_node_addresses():
    v, f, original = case("right_chain", 4, 255, 15)
    shift = 0x01000000
    memory = {address + shift: value for address, value in f["memory"].items()}
    nodes = {
        address
        + shift: {
            key: value if key == "sentinel" else value + shift
            for key, value in node.items()
        }
        for address, node in f["nodes"].items()
    }
    for address, node in nodes.items():
        for offset, field in ((0, "left"), (4, "parent"), (8, "right")):
            put(memory, address + offset, node[field])
    slot, stack = f["slot"] + shift, f["stack"] + shift
    put(memory, slot, v["start"] + shift)
    put(memory, stack, 0x55443322)
    rebased = dict(
        memory=memory,
        nodes=nodes,
        slot=slot,
        stack=stack,
        registers=dict(f["registers"], ecx=slot, esp=stack),
    )
    before = copy.deepcopy(rebased)
    e = c.oracle(dict(start=v["start"] + shift), rebased)
    assert rebased == before
    assert e["result"] == original["result"] + shift
    assert e["endpoint"] == 0x55443322
    assert e["registers"]["eax"] == e["registers"]["edx"] == slot
    assert e["registers"]["esp"] == stack + 4
    assert all(
        e["memory"][a] == value
        for a, value in memory.items()
        if not slot <= a < slot + 4
    )


def test_return_stack_must_not_wrap_32_bit_address_space():
    v, f, _ = case("single", 1)
    f["stack"] = 0xFFFFFFFC
    f["registers"]["esp"] = f["stack"]
    put(f["memory"], f["stack"], 0x44556677)
    with pytest.raises(RuntimeError, match="invalid slot or return frame"):
        c.oracle(v, f)


@pytest.mark.parametrize(
    "corruption",
    [
        "parent_cycle",
        "slot_alias",
        "return_alias",
        "unmapped_return",
        "memory_link",
        "start_mismatch",
        "register_bool",
    ],
)
def test_invalid_generic_fixture_is_rejected(corruption):
    v, f, _ = case("single", 1)
    if corruption == "parent_cycle":
        f["nodes"][v["start"]]["parent"] = v["start"]
    elif corruption == "slot_alias":
        f["slot"] = v["start"]
        f["registers"]["ecx"] = f["slot"]
    elif corruption == "return_alias":
        f["stack"] = f["slot"]
        f["registers"]["esp"] = f["slot"]
    elif corruption == "unmapped_return":
        del f["memory"][f["stack"] + 3]
    elif corruption == "memory_link":
        f["memory"][v["start"]] ^= 1
    elif corruption == "start_mismatch":
        put(f["memory"], f["slot"], 0x10000000)
    else:
        f["registers"]["eax"] = True
    with pytest.raises(RuntimeError):
        c.oracle(v, f)


@pytest.fixture(scope="module")
def receipts():
    paths = {
        "semantics": Path(str(PREFIX) + "native_lua_tree_successor_semantics.json"),
        "evidence": Path(str(PREFIX) + "native_lua_tree_successor_conformance.json"),
    }
    data = {k: json.loads(p.read_bytes()) for k, p in paths.items()}
    return paths, data, {"semantics": data["semantics"]}


def test_sealed_receipt_structure_and_complete_body(receipts):
    paths, data, sources = receipts
    evidence = data["evidence"]
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert (
        c._canonical_sha256(evidence)
        == c.SEALED_SHA256
        == ("f1429d740a09a4c46d0cec2f4049bb684f44d358ad24dd5ac51774a0ac554422")
    )
    assert hashlib.sha256(paths["evidence"].read_bytes()).hexdigest() == (
        "7a8ecba10be74eb20c53e133478e717095a0eda63ee1a26e133ed4468376c40d"
    )
    assert paths["evidence"].read_bytes() == c.encode_conformance(evidence).encode()
    assert evidence["summary"]["cases"] == 972
    assert evidence["summary"]["executed_sites"] == 31
    assert evidence["executed_rvas"] == [p["rva"] for p in evidence["body"]["points"]]
    assert evidence["negative_controls"] == [
        dict(kind=k, rejected=True) for k in ("ancestor", "node_padding", "slot")
    ]


@pytest.mark.parametrize("kind", ["evidence", "semantics"])
def test_mutated_receipts_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 999
    with pytest.raises(RuntimeError):
        c.validate_structure(
            changed if kind == "evidence" else data["evidence"],
            sources if kind == "evidence" else {"semantics": changed},
        )


def test_exact_cli_rebuild(receipts):
    exe = os.environ.get("ITB_EXACT_EXE")
    if not exe:
        pytest.skip("requires private exact executable and Unicorn runtime")
    paths, _, _ = receipts
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_lua_tree_successor_conformance.py"),
            "build",
            "--executable",
            exe,
            "--semantics",
            str(paths["semantics"]),
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["evidence"].read_bytes()
