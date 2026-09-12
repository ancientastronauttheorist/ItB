"""Class tree prefix: independent union, payload transfer and actual call frames."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_tree_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "0e03dd20ee8451eafd6aa848c8a405e924c38dd6abde121c7c06fdba9ea8358d"
RAW = "d52faecaea3de5ca3a6f2bcb1bb416b4a0a02ab909b7f041375f3237cecfa462"


def read(pages, address, width=4):
    return sum(
        pages[(address + i) & ~4095][(address + i) & 4095] << (8 * i)
        for i in range(width)
    )


def change(pages, address, value, width=4):
    result = dict(pages)
    for i, byte in enumerate(value.to_bytes(width, "little")):
        page = (address + i) & ~4095
        payload = bytearray(result[page])
        payload[(address + i) & 4095] = byte
        result[page] = bytes(payload)
    return result


@pytest.fixture(scope="module")
def cases():
    return [(v, f, c._expected(v, f)) for v in c.vectors() for f in [c._fixture(v)]]


def test_independent_key_payload_union_and_immutable_source(cases):
    for vector, fixture, expected in cases:
        before = {
            node["key"]: fixture["destination_state"]["payloads"][i]
            for i, node in enumerate(fixture["destination_state"]["tree"]["nodes"])
        }
        source = {
            node["key"]: fixture["source_state"]["payloads"][i]
            for i, node in enumerate(fixture["source_state"]["tree"]["nodes"])
        }
        wanted = dict(before)
        wanted.update(source)
        pages = expected["pages"]
        actual = {}
        for address in expected["destination_addresses"]:
            pointer = read(pages, address + 16)
            key = int(bytes(read(pages, pointer + i, 1) for i in range(8)), 16)
            actual[key] = read(pages, address + 20)
        assert actual == wanted
        assert read(pages, c.leaf.TREE + 4) == len(wanted)
        assert (
            expected["destination_addresses"][: len(fixture["destination_addresses"])]
            == fixture["destination_addresses"]
        )
        assert [row["key"] for row in expected["insertions"]] == sorted(source)
        assert [row["inserted"] for row in expected["insertions"]] == [
            key not in before for key in sorted(source)
        ]
        for page in (c.SOURCE_OBJECT, c.SOURCE_NODES, c.SOURCE_KEYS):
            if page in fixture["pages"]:
                assert pages[page] == fixture["pages"][page]
        for pointer, payload in fixture["strings"].items():
            assert (
                bytes(read(pages, pointer + i, 1) for i in range(len(payload)))
                == payload
            )


def test_every_iteration_overwrites_payload_even_for_existing_key(cases):
    existing = allocated = 0
    for vector, fixture, expected in cases:
        events = expected["events"]
        for row in expected["insertions"]:
            source = fixture["source_addresses"][row["source"]]
            pair = [
                dict(access="read", address=source + 20, width=4, value=row["payload"]),
                dict(
                    access="write",
                    address=row["destination_address"] + 20,
                    width=4,
                    value=row["payload"],
                ),
            ]
            assert any(events[i : i + 2] == pair for i in range(len(events) - 1))
            if row["inserted"]:
                allocated += 1
                assert read(expected["pages"], row["destination_address"] + 16) == read(
                    fixture["pages"], source + 16
                )
            else:
                existing += 1
                index = fixture["destination_addresses"].index(
                    row["destination_address"]
                )
                assert row["payload"] != fixture["destination_state"]["payloads"][index]
    assert existing == 240 and allocated == 264


def test_real_insertion_successor_and_result_frames(cases):
    for vector, fixture, expected in cases:
        frame = fixture["stack"] - 4
        events = expected["events"]
        calls = [
            i
            for i, e in enumerate(events)
            if e
            == dict(
                access="write", address=frame - 44, width=4, value=c.BASE + 0x2EB19F
            )
        ]
        successor_calls = [
            e
            for e in events
            if e
            == dict(
                access="write", address=frame - 36, width=4, value=c.BASE + 0x2EB1B0
            )
        ]
        assert len(calls) == len(successor_calls) == len(expected["insertions"])
        for index, row in zip(calls, expected["insertions"]):
            assert events[index - 2 : index] == [
                dict(
                    access="write",
                    address=frame - 36,
                    width=4,
                    value=fixture["source_addresses"][row["source"]] + 16,
                ),
                dict(access="write", address=frame - 40, width=4, value=frame - 20),
            ]
        assert not any(
            e["access"] == "read" and e["address"] == frame - 16 for e in events
        )
        if expected["insertions"]:
            last = expected["insertions"][-1]
            assert read(expected["pages"], frame - 20) == last["destination_address"]
            assert read(expected["pages"], frame - 16, 1) == int(last["inserted"])
        else:
            assert bytes(
                read(expected["pages"], frame - 20 + i, 1) for i in range(8)
            ) == bytes(read(fixture["pages"], frame - 20 + i, 1) for i in range(8))
        assert read(expected["pages"], frame - 8) == c.SOURCE_HEAD


def test_prefix_endpoint_abi_and_saved_context(cases):
    for vector, fixture, expected in cases:
        frame = fixture["stack"] - 4
        regs, pages = expected["registers"], expected["pages"]
        assert expected["endpoint"] == c.BASE + c.STOP and expected["flags"] == 0x44
        assert regs["esp"] == frame - 32 and regs["ebp"] == frame
        assert (
            regs["ebx"] == c.SOURCE_OBJECT
            and regs["esi"] == c.SOURCE_HEAD
            and regs["edi"] == c.ARGUMENT
        )
        assert read(pages, frame - 4) == vector["cookie"] ^ frame
        assert read(pages, frame - 12) == c.RECEIVER
        assert read(pages, frame) == fixture["registers"]["ebp"]
        for offset, reg in ((-24, "ebx"), (-28, "esi"), (-32, "edi")):
            assert read(pages, frame + offset) == fixture["registers"][reg]
        assert read(pages, 0) == vector["previous_seh"]
        assert read(pages, c.insertion.empty.COOKIE) == vector["cookie"]
        if expected["insertions"]:
            assert regs["eax"] == regs["edx"] == frame - 8
        else:
            assert regs["eax"] == c.SOURCE_HEAD
            assert regs["edx"] == fixture["registers"]["edx"]
            assert regs["ecx"] == c.RECEIVER


@pytest.mark.parametrize("kind", ["payload", "iterator", "pair", "inserted_byte"])
def test_independent_model_rejects_forged_memory_after_ancestor_copy(cases, kind):
    _, fixture, expected = next(case for case in cases if case[2]["insertions"])
    frame = fixture["stack"] - 4
    last = expected["insertions"][-1]
    address, width = {
        "payload": (last["destination_address"] + 20, 4),
        "iterator": (frame - 8, 4),
        "pair": (frame - 20, 4),
        "inserted_byte": (frame - 16, 1),
    }[kind]
    forged = dict(
        expected,
        pages=change(
            expected["pages"],
            address,
            read(expected["pages"], address, width) ^ 1,
            width,
        ),
    )
    independently_rebuilt = c._model_pages(fixture, forged)
    assert independently_rebuilt != forged["pages"]
    assert read(independently_rebuilt, address, width) == read(
        expected["pages"], address, width
    )


def test_independent_identity_mapping_rejects_rebound_node(cases):
    _, fixture, expected = next(case for case in cases if case[2]["heap_nodes"])
    changed = copy.deepcopy(expected)
    changed["destination_addresses"][-1] ^= 1
    with pytest.raises(
        c.ConformanceError, match="destination identity mapping differs"
    ):
        c._model_pages(fixture, changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_keys", [1] * 8),
        ("destination_keys", [1] * 8),
        ("source_keys", (1, 2)),
        ("source_keys", [True]),
        ("destination_keys", [-1]),
        ("destination_keys", [2**32]),
        ("payload_seed", True),
        ("payload_seed", 2**32),
        ("node_alignment", 32),
        ("frame_alignment", 16),
        ("nil_flag", 0),
        ("cookie", True),
        ("previous_seh", -1),
    ],
)
def test_invalid_fixture_bounds(field, value):
    vector = dict(c.vectors()[0], **{field: value})
    with pytest.raises(RuntimeError):
        c._fixture(vector)


def test_expected_oracle_preserves_fixture(cases):
    vector, fixture, expected = cases[-1]
    before = copy.deepcopy(fixture)
    assert c._expected(vector, fixture) == expected
    assert fixture == before


@pytest.fixture(scope="module")
def receipts():
    evidence_path = PROGRAMS / (PREFIX + "native_lua_class_tree_conformance.json")
    if not evidence_path.exists() or c.SEALED_SHA256 == "PENDING":
        pytest.skip("awaiting reviewed class prefix seal")
    evidence = json.loads(evidence_path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        candidates = [
            (p, json.loads(p.read_text()))
            for p in PROGRAMS.glob("*" + suffix + ".json")
        ]
        path, value = next(
            (p, v) for p, v in candidates if c._canonical_sha256(v) == digest
        )
        paths[key], sources[key] = path, value
    return evidence_path, evidence, paths, sources


def test_seal_encoding_scope_and_coverage(receipts):
    path, evidence, _, sources = receipts
    assert c._canonical_sha256(evidence) == CANONICAL == c.SEALED_SHA256
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode() == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    summary = evidence["summary"]
    for key, value in dict(
        cases=192,
        iterations=504,
        allocated_insertions=264,
        existing_insertions=240,
        max_iterations=7,
        prefix_bytes=123,
        prefix_sites=42,
        normal_prefix_sites=36,
        instruction_bytes=1685,
        static_sites=653,
        executed_sites=581,
        accounting_promotions=0,
    ).items():
        assert summary[key] == value
    assert {row["kind"] for row in evidence["negative_controls"]} == {
        "ancestor",
        "source",
        "payload",
        "iterator",
    }
    assert not any(
        0x2EB15F <= int(pc, 16) < 0x2EB179 for pc in evidence["executed_rvas"]
    )
    assert "vector append" in " ".join(evidence["scope"]["not_claimed"])


def test_modified_receipt_and_source_rejected(receipts):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    changed["summary"]["iterations"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)
    changed_sources = copy.deepcopy(sources)
    changed_sources["successor"]["schema_version"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed_sources)


def test_exact_cli_rebuild(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    path, _, paths, _ = receipts
    command = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_class_tree_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key, source in paths.items():
        command += ["--" + key.replace("_", "-"), str(source)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
