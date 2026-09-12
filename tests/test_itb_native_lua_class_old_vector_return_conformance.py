"""Class transfer, old vector copy and free, append, and actual caller return."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_old_vector_return_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "ebdd6a4cfe4ce14ce5606b183ddea87fd4babafa13adf12e6e6980050c62945a"
RAW = "1e21ff2b002f6c56f291289bfb5b2472bd5664672023a0216911b7bd1000424f"


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
    # Cover each tree shape and frame, old size, and allocation alignment.
    return [(v, f, c._expected(v, f)) for v in c.vectors() for f in [c._fixture(v)]]


def test_independent_old_record_copy_append_and_preserved_storage(cases):
    for vector, fixture, expected in cases:
        before = c.prefix._expected(vector, fixture)
        wanted = change(
            before["pages"],
            fixture["vector_end"],
            read(fixture["pages"], c.ARGUMENT, 8),
            8,
        )
        for i in range(vector["old_size"] * 8):
            wanted = change(
                wanted,
                fixture["vector_begin"] + i,
                read(fixture["pages"], fixture["old_begin"] + i, 1),
                1,
            )
        for offset, value in (
            (4, fixture["vector_begin"]),
            (8, fixture["vector_end"] + 8),
            (12, fixture["vector_capacity"]),
        ):
            assert read(fixture["pages"], c.RECEIVER + offset) == fixture[
                "old_begin"
            ] + (0 if offset == 4 else vector["old_size"] * 8)
            wanted = change(wanted, c.RECEIVER + offset, value)
        for page, payload in wanted.items():
            if page not in (c.construction.STACK, c.construction.STACK + 4096):
                assert expected["pages"][page] == payload
        assert expected["insertions"] == before["insertions"]
        assert expected["heap_nodes"] == before["heap_nodes"] + [
            fixture["vector_begin"]
        ]
        assert expected["tree_heap_count"] == len(before["heap_nodes"])
        assert all(
            abs(node - fixture["vector_begin"]) >= 24 for node in before["heap_nodes"]
        )


def test_actual_growth_resize_allocation_copy_and_free_frames(cases):
    for vector, fixture, expected in cases:
        before = c.prefix._expected(vector, fixture)
        frame = fixture["stack"] - 4
        events = expected["events"][len(before["events"]) :]

        def event(access, address, value):
            return dict(access=access, address=address, width=4, value=value)

        assert events[:5] == [
            event("read", frame - 12, c.RECEIVER),
            event(
                "read", c.RECEIVER + 8, fixture["old_begin"] + 8 * vector["old_size"]
            ),
            event(
                "read", c.RECEIVER + 12, fixture["old_begin"] + 8 * vector["old_size"]
            ),
            event("write", frame - 36, before["registers"]["ecx"]),
            event("write", frame - 40, c.BASE + 0x2EB205),
        ]
        for offset, continuation in (
            (-60, 0x2EB66E),
            (-88, 0x2EB695),
            (-136, 0x389463),
            (-96, 0x2EB6A6),
        ):
            assert event("write", frame + offset, c.BASE + continuation) in events
        heap_call = events.index(event("write", frame - 136, c.BASE + 0x389463))
        assert events[heap_call - 1] == event(
            "read", c.growth.ALLOC_IAT, c.construction.IMPORT
        )
        assert event("write", frame - 124, 8 * (vector["old_size"] + 1)) in events
        assert event("write", frame - 128, 0) in events
        assert not any(e["access"] == "read" and e["address"] == 0 for e in events)
        assert (
            sum(
                e["access"] == "read" and e["address"] == c.growth.FREE_IAT
                for e in events
            )
            == 1
        )
        assert event("write", frame - 96, c.BASE + 0x2EB6C8) in events
        assert event("write", frame - 108, c.BASE + 0x7856) in events
        assert event("write", frame - 128, c.BASE + 0x389172) in events
        assert event("write", frame - 124, c.construction.HEAP) in events
        assert event("write", frame - 120, 0) in events
        assert event("write", frame - 116, fixture["old_begin"]) in events
        for i in range(0, 8 * vector["old_size"], 4):
            pair_copy = [
                event(
                    "read",
                    fixture["old_begin"] + i,
                    read(fixture["pages"], fixture["old_begin"] + i),
                ),
                event(
                    "write",
                    fixture["vector_begin"] + i,
                    read(fixture["pages"], fixture["old_begin"] + i),
                ),
            ]
            assert any(events[j : j + 2] == pair_copy for j in range(len(events) - 1))
        end = fixture["vector_end"]
        pair = [
            event("read", c.ARGUMENT, read(fixture["pages"], c.ARGUMENT)),
            event("write", end, read(fixture["pages"], c.ARGUMENT)),
            event("read", c.ARGUMENT + 4, c.prefix.SOURCE_OBJECT),
            event("write", end + 4, c.prefix.SOURCE_OBJECT),
        ]
        assert any(events[i : i + 4] == pair for i in range(len(events) - 3))


def test_actual_ret4_abi_and_final_cookie_stack(cases):
    for vector, fixture, expected in cases:
        frame = fixture["stack"] - 4
        regs, pages = expected["registers"], expected["pages"]
        assert expected["endpoint"] == fixture["return_address"]
        assert regs["esp"] == fixture["stack"] + 8
        assert regs["eax"] == c.prefix.SOURCE_OBJECT
        assert regs["ecx"] == vector["cookie"] and expected["flags"] == 0x44
        assert regs["edx"] == 0xB0000001
        for register in ("ebx", "esi", "edi", "ebp"):
            assert regs[register] == fixture["registers"][register]
        assert read(pages, frame - 24) == c.BASE + 0x2EB227
        assert read(pages, frame - 4) == vector["cookie"] ^ frame
        assert read(pages, frame + 4) == fixture["return_address"]
        assert read(pages, 0) == vector["previous_seh"]
        assert read(pages, c.returned.COOKIE) == vector["cookie"]


@pytest.mark.parametrize(
    "kind",
    [
        "record",
        "begin",
        "end",
        "capacity",
        "payload",
        "iterator",
        "pair",
        "inserted_byte",
    ],
)
def test_independent_model_rejects_forged_memory(cases, kind):
    _, fixture, expected = next(case for case in cases if case[2]["insertions"])
    frame = fixture["stack"] - 4
    address, width = {
        "record": (fixture["vector_end"], 8),
        "end": (c.RECEIVER + 8, 4),
        "begin": (c.RECEIVER + 4, 4),
        "capacity": (c.RECEIVER + 12, 4),
        "payload": (expected["insertions"][-1]["destination_address"] + 20, 4),
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
    rebuilt = c._model_pages(fixture, forged)
    assert rebuilt != forged["pages"]
    assert read(rebuilt, address, width) == read(expected["pages"], address, width)


@pytest.mark.parametrize("value", [True, -1, 32, 2**32])
def test_invalid_vector_alignment(value):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], vector_alignment=value))


def test_expected_preserves_fixture(cases):
    vector, fixture, expected = cases[-1]
    before = copy.deepcopy(fixture)
    assert c._expected(vector, fixture) == expected
    assert fixture == before


@pytest.fixture(scope="module")
def receipts():
    evidence_path = PROGRAMS / (
        PREFIX + "native_lua_class_old_vector_return_conformance.json"
    )
    if not evidence_path.exists() or c.SEALED_SHA256 == "PENDING":
        pytest.skip("awaiting reviewed class old vector return seal")
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
        cases=1536,
        iterations=4032,
        allocated_insertions=2112,
        existing_insertions=1920,
        max_iterations=7,
        instruction_bytes=2372,
        static_sites=920,
        executed_sites=769,
        allocation_requests=1536,
        free_requests=1536,
        grown_vector_records=3840,
        accounting_promotions=0,
    ).items():
        assert summary[key] == value
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert set(controls) == {
        "ancestor",
        "source",
        "payload",
        "vector",
        "iterator",
        "cookie",
        "heap_request",
        "heap_response",
        "old",
        "heap_free_request",
    }
    assert all(row["rejected"] for row in controls.values())
    assert controls["cookie"]["endpoint"] == "0x003574d5"
    executed = set(evidence["executed_rvas"])
    assert {
        "0x002eb1fc",
        "0x002eb1fd",
        "0x002eb200",
        "0x002eb620",
        "0x002eb680",
    } <= executed
    assert not any(
        a <= int(pc, 16) < b
        for pc in executed
        for a, b in ((0x2EB15F, 0x2EB179), (0x2EB1CC, 0x2EB1F7), (0x2EB1C5, 0x2EB1CC))
    )
    assert "failure frontier" in " ".join(evidence["scope"]["not_claimed"])


def test_modified_receipt_and_source_rejected(receipts):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    changed["summary"]["iterations"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)
    changed_sources = copy.deepcopy(sources)
    changed_sources["empty_vector_return"]["schema_version"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed_sources)


def test_exact_cli_rebuild(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    path, _, paths, _ = receipts
    command = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_class_old_vector_return_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key, source in paths.items():
        command += ["--" + key.replace("_", "-"), str(source)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()


@pytest.mark.parametrize(
    "field,value",
    [
        ("old_size", True),
        ("old_size", -1),
        ("old_size", 4),
        ("old_alignment", True),
        ("old_alignment", -1),
        ("old_alignment", 32),
    ],
)
def test_invalid_old_vector_geometry(field, value):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], **{field: value}))


def test_independent_model_rejects_copied_live_record(cases):
    _, fixture, expected = next(case for case in cases if case[0]["old_size"] == 3)
    address = fixture["vector_begin"] + 8
    forged = dict(
        expected,
        pages=change(expected["pages"], address, read(expected["pages"], address) ^ 1),
    )
    assert c._model_pages(fixture, forged) != forged["pages"]
