"""Actual caller query, result and heterogeneous destination record mappings."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_tree_insert_return_conformance as c


def read(pages, a, width=4):
    return sum(pages[(a + j) & ~4095][(a + j) & 4095] << (8 * j) for j in range(width))


def mapped_fixture(mode="interior"):
    vector = next(v for v in c.vectors() if v["mode"] == mode and len(v["keys"]) == 2)
    fixture = c._fixture(vector)
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}

    def put(a, value, width=4):
        for j, b in enumerate(value.to_bytes(width, "little")):
            pages.setdefault((a + j) & ~4095, bytearray(b"\x91" * 4096))[
                (a + j) & 4095
            ] = b

    addresses = [c.construction.DATA + 0x2081, c.leaf.NODES + 0x183]
    keys = [0x13000103, 0x14000107]
    old_addresses = fixture["addresses"]
    at = lambda i: c.leaf.HEAD if i is None else addresses[i]
    strings = {}
    for i, node in enumerate(fixture["tree"]["nodes"]):
        for offset in range(24):
            put(
                addresses[i] + offset,
                read(fixture["pages"], old_addresses[i] + offset, 1),
                1,
            )
        for off, name in ((0, "left"), (4, "parent"), (8, "right")):
            put(addresses[i] + off, at(node[name]))
        put(addresses[i] + 16, keys[i])
        payload = f'{node["key"]:08x}'.encode() + b"\0"
        strings[keys[i]] = payload
        for j, b in enumerate(payload):
            put(keys[i] + j, b, 1)
    root = fixture["tree"]["root"]
    put(c.leaf.HEAD + 4, at(root))
    put(
        c.leaf.HEAD,
        addresses[min(range(2), key=lambda i: fixture["tree"]["nodes"][i]["key"])],
    )
    put(
        c.leaf.HEAD + 8,
        addresses[max(range(2), key=lambda i: fixture["tree"]["nodes"][i]["key"])],
    )
    query_argument, query_pointer = 0x16000310, 0x15000205
    payload = f'{vector["key"]:08x}'.encode() + b"\0"
    strings[query_pointer] = payload
    for j, b in enumerate(payload):
        put(query_pointer + j, b, 1)
    put(query_argument, query_pointer)
    output = fixture["stack"] + 24
    put(fixture["stack"] + 4, output)
    put(fixture["stack"] + 8, query_argument)
    for j in range(8):
        put(output + j, 0xCC, 1)
    parent = at(old_addresses.index(fixture["parent"]))
    fixture.update(
        pages={p: bytes(v) for p, v in pages.items()},
        addresses=addresses + [fixture["node"]],
        parent=parent,
        key_pointers=keys,
        query_argument=query_argument,
        query_pointer=query_pointer,
        output=output,
        strings=strings,
    )
    return vector, fixture


@pytest.mark.parametrize("mode", ["minimum", "end", "interior", "existing"])
def test_relocated_caller_pair_and_pointer_retention(mode):
    v, f = mapped_fixture(mode)
    before = copy.deepcopy(f)
    result = c._expected(v, f)
    assert f == before
    inserted = mode != "existing"
    wanted = f["node"] if inserted else f["addresses"][v["keys"].index(v["key"])]
    assert read(result["pages"], f["output"]) == wanted
    assert read(result["pages"], f["output"] + 4, 1) == int(inserted)
    assert result["registers"]["eax"] == f["output"]
    assert (
        bytes(read(result["pages"], f["output"] + i, 1) for i in (5, 6, 7))
        == b"\xcc" * 3
    )
    if inserted:
        assert read(result["pages"], f["node"] + 16) == f["query_pointer"]
        assert read(result["pages"], f["node"] + 16) != f["query_argument"]
    for i, pointer in enumerate(f["key_pointers"]):
        assert read(result["pages"], f["addresses"][i] + 16) == pointer
    for pointer, payload in f["strings"].items():
        assert (
            bytes(read(result["pages"], pointer + j, 1) for j in range(len(payload)))
            == payload
        )
    read_addresses = {e["address"] for e in result["events"] if e["access"] == "read"}
    assert (
        f["query_argument"] in read_addresses and f["query_pointer"] in read_addresses
    )
    assert c.leaf.ARG not in read_addresses and c.leaf.QUERY not in read_addresses


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("query_pointer", True, "invalid caller pointer"),
        ("query_argument", 0xFFFFFFFE, "invalid caller pointer"),
        ("query_pointer", 0xDEAD0000, "unmapped caller storage"),
        ("key_pointers", [1], "invalid caller key mapping"),
        ("addresses", [0x10000100, 0x10002000], "overlapping caller node mapping"),
        ("output", 0xFFFFFFFE, "invalid caller output"),
        ("output", 0xDEAD0000, "unmapped caller output"),
    ],
)
def test_invalid_caller_maps_rejected(field, value, message):
    v, f = mapped_fixture()
    f[field] = value
    with pytest.raises(RuntimeError, match=message):
        c._expected(v, f)


def test_output_cannot_alias_live_owner_or_query_field():
    v, f = mapped_fixture()
    for output in (
        f["stack"] - 8,
        f["query_argument"],
        f["query_pointer"],
        f["key_pointers"][0],
        f["node"],
        f["addresses"][0],
    ):
        changed = dict(f, output=output)
        with pytest.raises(RuntimeError, match="caller output overlaps live storage"):
            c._expected(v, changed)


@pytest.mark.parametrize(
    "bad_node", [True, 0, 0xFFFFFFFF, c.construction.DATA + 0x4000 - 23]
)
def test_fresh_allocation_requires_supplied_storage(bad_node):
    v, f = mapped_fixture()
    f["node"] = bad_node
    with pytest.raises(
        RuntimeError, match="fresh allocation outside supplied data storage"
    ):
        c._expected(v, f)


def test_fresh_allocation_disjoint_from_existing_nodes_and_source_strings():
    v, f = mapped_fixture()
    with pytest.raises(
        RuntimeError, match="fresh allocation overlaps protected caller storage"
    ):
        c._expected(v, dict(f, node=f["addresses"][0]))
    changed = dict(f, key_pointers=[f["node"], f["key_pointers"][1]])
    with pytest.raises(
        RuntimeError, match="fresh allocation overlaps protected caller storage"
    ):
        c._expected(v, changed)


def test_allocated_source_key_pointer_can_be_existing_destination_key():
    v, f = mapped_fixture()
    first = c._expected(v, f)
    tree = f["result"]["tree"]
    duplicate = dict(v, keys=[n["key"] for n in tree["nodes"]], mode="existing")
    cv = dict(
        f["construction_vector"],
        nodes=[
            dict(key=list(f'{n["key"]:08x}'.encode()), left=n["left"], right=n["right"])
            for n in tree["nodes"]
        ],
        root=tree["root"],
    )
    pages = {p: bytearray(b) for p, b in first["pages"].items()}
    for a, value in (
        (f["stack"] + 4, f["output"]),
        (f["stack"] + 8, f["query_argument"]),
    ):
        for j, b in enumerate(value.to_bytes(4, "little")):
            pages[(a + j) & ~4095][(a + j) & 4095] = b
    second_fixture = dict(
        f,
        pages={p: bytes(b) for p, b in pages.items()},
        tree=tree,
        result=None,
        construction_vector=cv,
        addresses=f["addresses"] + [c.construction.DATA + 0x301],
        key_pointers=f["key_pointers"] + [f["query_pointer"]],
        node=c.construction.DATA + 0x301,
    )
    second = c._expected(duplicate, second_fixture)
    assert not second["allocate"]
    assert read(second["pages"], f["output"]) == f["node"]
    assert read(second["pages"], f["output"] + 4, 1) == 0
    assert read(second["pages"], f["node"] + 16) == f["query_pointer"]


def load_sources():
    root = Path(__file__).resolve().parents[1] / "data/observatory/programs"
    sources = {}
    for name, (kind, digest) in c.SOURCE_PINS.items():
        candidates = list(
            root.glob(
                "*"
                + (
                    "program_facts"
                    if name == "program_facts"
                    else kind.removeprefix("pe_")
                )
                + ".json"
            )
        )
        values = [json.loads(path.read_text()) for path in candidates]
        sources[name] = next(
            value for value in values if c._canonical_sha256(value) == digest
        )
    return sources


def native_relocated_replay(executable):
    data, image, _ = c._load_executable(Path(executable))
    codes, points, _ = c._load_code(data, image, load_sources())
    for mode in ("minimum", "end", "interior", "existing"):
        v, f = mapped_fixture(mode)
        result = c._run_case(codes, points, v, fixture=f)
        assert result["registers"]["eax"] == f["output"]


def test_exact_native_relocated_caller_maps():
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE for private native replay")
    script = (
        "import runpy; scope=runpy.run_path("
        + repr(str(Path(__file__).resolve()))
        + ");"
        "scope['native_relocated_replay']("
        + repr(executable)
        + ");print('native caller maps passed')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "native caller maps passed"
