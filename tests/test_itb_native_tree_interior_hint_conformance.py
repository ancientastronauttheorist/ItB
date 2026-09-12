"""Interior hint joins comparisons, predecessor slot, and the real child ABI."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory import native_tree_interior_hint_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_"
CANONICAL = "b4b8859192f3054ab33fbfe9e275e980c48571bb1dc57f88bb3a6aebd1876074"
RAW = "bdb2f71c5f0ebf735a0286110d4f35bbc4006be8adba1dbbb8612216bb8a18c1"


def read(pages, address, width=4):
    return sum(
        pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] << (8 * i)
        for i in range(width)
    )


def event(access, address, value, width=4):
    return dict(access=access, address=address, width=width, value=value)


@pytest.fixture(scope="module")
def cases():
    vectors = c.vectors()
    result = []
    for group in range(len(vectors) // 12):
        v = vectors[group * 12 + group % 12]
        f = c._fixture(v)
        result.append((v, f, c._expected(v, f)))
    return result


def neighbors(v, f):
    nodes = f["tree"]["nodes"]
    pred = max(
        (i for i, node in enumerate(nodes) if node["key"] < v["key"]),
        key=lambda i: nodes[i]["key"],
    )
    candidate = min(
        (i for i, node in enumerate(nodes) if node["key"] > v["key"]),
        key=lambda i: nodes[i]["key"],
    )
    return pred, candidate


def byte_events(f, left, right):
    events = []
    for offset, (a, b) in enumerate(zip(f["strings"][left], f["strings"][right])):
        events += [
            event("read", left + offset, a, 1),
            event("read", right + offset, b, 1),
        ]
        if a != b:
            assert a < b
            return events, a
    pytest.fail("expected distinct strict string ordering")


def test_both_ordered_comparisons_and_predecessor_frame(cases):
    for v, f, e in cases:
        h = f["s"]
        pred, candidate = neighbors(v, f)
        query = read(f["pages"], f["node"] + 16)
        candidate_string = read(f["pages"], f["addresses"][candidate] + 16)
        pred_string = read(f["pages"], f["addresses"][pred] + 16)
        assert read(f["pages"], h + 8) == f["addresses"][candidate]
        for left, right, ret in (
            (query, candidate_string, 0x2E83D7),
            (pred_string, query, 0x2E83F2),
        ):
            start = e["events"].index(event("write", h - 80, c.BASE + ret))
            reads, _ = byte_events(f, left, right)
            expected = (
                [
                    event("write", h - 80, c.BASE + ret),
                    event("write", h - 84, h - 4),
                    event("read", h - 72, right),
                    event("read", h - 76, left),
                ]
                + reads
                + [event("read", h - 84, h - 4), event("read", h - 80, c.BASE + ret)]
            )
            assert e["events"][start : start + len(expected)] == expected
        pred_call = e["events"].index(event("write", h - 72, c.BASE + 0x2E83E6))
        assert e["events"][pred_call - 1 : pred_call + 2] == [
            event("write", h - 28, f["addresses"][candidate]),
            event("write", h - 72, c.BASE + 0x2E83E6),
            event("read", h - 28, f["addresses"][candidate]),
        ]
        pred_ret = e["events"].index(event("read", h - 72, c.BASE + 0x2E83E6))
        assert e["events"][pred_ret + 1 : pred_ret + 5] == [
            event("write", h - 72, query),
            event("read", h - 28, f["addresses"][pred]),
            event("read", f["addresses"][pred] + 16, pred_string),
            event("write", h - 76, pred_string),
        ]
        assert h - 72 + 4 == h - 68


def test_predecessor_slot_writes_follow_independent_ancestor_path(cases):
    maximum = 0
    for v, f, e in cases:
        pred, candidate = neighbors(v, f)
        nodes = f["tree"]["nodes"]
        writes = []
        if nodes[candidate]["left"] is not None:
            current = nodes[candidate]["left"]
            while nodes[current]["right"] is not None:
                current = nodes[current]["right"]
            writes.append(current)
        else:
            current = candidate
            parent = nodes[current]["parent"]
            while parent is not None and nodes[parent]["left"] == current:
                writes.append(parent)
                current, parent = parent, nodes[parent]["parent"]
            writes.append(parent)
        assert writes[-1] == pred
        expected = [
            event("write", f["s"] - 28, f["addresses"][i]) for i in [candidate] + writes
        ]
        assert [
            a
            for a in e["events"]
            if a["access"] == "write" and a["address"] == f["s"] - 28
        ] == expected
        assert e["predecessor_writes"] == len(writes)
        maximum = max(maximum, len(writes))
    assert maximum == 7


def test_both_attachment_orders_and_child_register_contract(cases, monkeypatch):
    selected = {e["selected_right"]: (v, f) for v, f, e in cases}
    assert set(selected) == {True, False}
    original = c.balancing._expected
    captured = []

    def inspect_child(vector, fixture):
        captured.append(fixture)
        return original(vector, fixture)

    monkeypatch.setattr(c.balancing, "_expected", inspect_child)
    for right, (v, f) in selected.items():
        e = c._expected(v, f)
        child = captured[-1]
        h, n = f["s"], f["node"]
        pred, candidate = neighbors(v, f)
        pred_address, candidate_address = (
            f["addresses"][pred],
            f["addresses"][candidate],
        )
        pred_right = read(f["pages"], pred_address + 8)
        parent = pred_address if right else candidate_address
        common = [event("read", h - 36, c.attachment.TREE)]
        if right:
            common += [event("read", h - 40, c.OUTPUT), event("write", h - 80, parent)]
        else:
            common += [event("write", h - 80, parent), event("read", h - 40, c.OUTPUT)]
        common += [
            event("write", h - 84, int(not right)),
            event("write", h - 88, c.OUTPUT),
            event("write", h - 92, c.BASE + (0x2E8412 if right else 0x2E8423)),
        ]
        begin = e["events"].index(common[0])
        assert e["events"][begin : begin + len(common)] == common
        assert child["s"] == h - 92 and child["selector"] == int(not right)
        assert child["registers"]["eax"] == pred_right
        assert child["registers"]["ebx"] == pred_address
        assert child["registers"]["esi"] == c.OUTPUT
        assert child["registers"]["ecx"] == c.attachment.TREE
        _, low_byte = byte_events(
            f, read(f["pages"], pred_address + 16), read(f["pages"], n + 16)
        )
        assert child["registers"]["edx"] == ((h - 28) & 0xFFFFFF00) | low_byte
        assert read(child["pages"], h - 80) == parent
        assert read(child["pages"], h - 76) == 0xFFFFFFFF
        assert read(child["pages"], h - 72) == n
        assert read(e["pages"], h - 100) == pred_address


def test_second_comparison_edx_uses_predecessor_slot_upper_bits(cases):
    bypasses = 0
    for v, f, e in cases:
        pred, _ = neighbors(v, f)
        left = read(f["pages"], f["addresses"][pred] + 16)
        query = read(f["pages"], f["node"] + 16)
        _, low_byte = byte_events(f, left, query)
        merged = ((f["s"] - 28) & 0xFFFFFF00) | low_byte
        steps = f["result"]["steps"]
        if not steps:
            bypasses += 1
            assert merged != (f["registers"]["edx"] & 0xFFFFFF00) | low_byte
            edx = merged
        else:
            last = steps[-1]
            identity = (
                last["uncle"] if last["kind"] == "red_uncle" else last["grandparent"]
            )
            edx = c.attachment.HEAD if identity is None else f["addresses"][identity]
        assert e["registers"] == dict(
            f["registers"], eax=c.OUTPUT, ecx=v["cookie"], edx=edx, esp=f["s"] + 20
        )
        assert e["flags"] == 0x44 and e["endpoint"] == read(f["pages"], f["s"])
    assert bypasses > 0


def test_model_node_pages_key_storage_registration_and_ancestor_preserved(cases):
    for v, f, e in cases:
        tree = c.balancing.model.insert(f["tree"], v["key"])["tree"]
        pages = {page: bytearray(payload) for page, payload in f["pages"].items()}
        at = lambda identity: (
            c.attachment.HEAD if identity is None else f["addresses"][identity]
        )

        def put(address, value, width=4):
            for i, byte in enumerate(value.to_bytes(width, "little")):
                pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

        for i, node in enumerate(tree["nodes"]):
            for offset, field in ((0, "left"), (4, "parent"), (8, "right")):
                put(at(i) + offset, at(node[field]))
            put(at(i) + 12, node["color"], 1)
        # An interior insertion preserves both head extrema.
        put(c.attachment.HEAD + 4, at(tree["root"]))
        put(c.attachment.TREE + 4, len(tree["nodes"]))
        put(c.OUTPUT, f["node"])
        for page, payload in pages.items():
            if page not in (c.attachment.STACK, c.attachment.STACK + 0x1000):
                assert bytes(payload) == e["pages"][page]
        for offset in range(0, 24, 4):
            assert read(e["pages"], f["s"] + offset) == read(
                f["pages"], f["s"] + offset
            )
        h = f["s"]
        assert [a for a in e["events"] if a["address"] == 0] == [
            event("read", 0, v["previous_seh"]),
            event("write", 0, h - 16),
            event("write", 0, v["previous_seh"]),
        ]
        assert (
            read(e["pages"], h - 24)
            == read(e["pages"], h - 68)
            == v["cookie"] ^ (h - 4)
        )
        assert read(e["pages"], h - 56) == c.BASE + 0x2E84D8
        assert read(e["pages"], h - 12) == 0x007D0EA0


@pytest.mark.parametrize(
    "changes",
    [
        {"keys": []},
        {"key": 0},
        {"key": 1},
        {"key": 3},
        {"key": 4},
        {"mode": "minimum"},
        {"keys": [1, 1, 3]},
        {"keys": list(range(1, 514, 2))},
        {"string_alignment": True},
        {"string_alignment": 4},
        {"node_alignment": 32},
        {"tree_alignment": 16},
        {"frame_alignment": -1},
        {"df": 2},
        {"nil_marker": 0},
        {"cookie": True},
        {"cookie": 2**32},
        {"previous_seh": -1},
    ],
)
def test_invalid_interior_key_or_fixture_bound_rejected(changes):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], **changes))


@pytest.fixture(scope="module")
def receipts():
    names = dict(
        program_facts="program_facts",
        balancing="native_tree_balancing_conformance",
        comparator="native_tree_key_compare_conformance",
        predecessor="native_tree_predecessor_conformance",
        cookie_return="native_lua_class_vector_return_conformance",
        evidence="native_tree_interior_hint_conformance",
    )
    paths = {key: Path(str(PREFIX) + name + ".json") for key, name in names.items()}
    data = {key: json.loads(path.read_bytes()) for key, path in paths.items()}
    return paths, data, {key: data[key] for key in c.SOURCE_PINS}


def test_sealed_receipt_identity_and_coverage(receipts):
    paths, data, sources = receipts
    evidence = data["evidence"]
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert c.SEALED_SHA256 == c._canonical_sha256(evidence) == CANONICAL
    raw = paths["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == c.encode_conformance(evidence).encode() and b"\r\n" not in raw
    summary = evidence["summary"]
    assert {k: v for k, v in summary.items() if k != "child_features"} == dict(
        cases=2016,
        instruction_bytes=900,
        static_sites=333,
        executed_sites=308,
        normal_returns=2016,
        max_child_iterations=3,
        max_child_rotations=2,
        predecessor_max_writes=7,
        predecessor_right_insertions=1140,
        candidate_left_insertions=876,
        opaque_instructions=0,
        accounting_promotions=0,
    )
    assert evidence["negative_controls"] == [
        dict(kind=kind, rejected=True)
        for kind in ("ancestor", "padding", "seh", "cookie")
    ]


@pytest.mark.parametrize(
    "kind",
    [
        "evidence",
        "program_facts",
        "balancing",
        "comparator",
        "predecessor",
        "cookie_return",
    ],
)
def test_mutated_evidence_or_source_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 999
    with pytest.raises(RuntimeError):
        c.validate_structure(
            changed if kind == "evidence" else data["evidence"],
            sources if kind == "evidence" else dict(sources, **{kind: changed}),
        )


def test_exact_cli_rebuild(receipts):
    exe = os.environ.get("ITB_EXACT_EXE")
    if not exe:
        pytest.skip("requires private exact executable and Unicorn runtime")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_tree_interior_hint_conformance.py"),
        "build",
        "--executable",
        exe,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["evidence"].read_bytes()
