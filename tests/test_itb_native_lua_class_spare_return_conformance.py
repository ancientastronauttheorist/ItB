"""Class transfer, external spare append, and actual caller return."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_spare_return_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "9b6b20f247d5327476bc4b79caf7a5849248c6d07a332d80ff20c34f1127c8c7"
RAW = "6819e7b2a667354e7ea677d52c97137e3dd1c94bc383b9a1f1ac3dde6e724241"


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
    # Cover each shape and frame with both external placements and all old sizes.
    return [(v, f, c._expected(v, f)) for v in c.vectors() for f in [c._fixture(v)]]


def test_independent_record_append_and_unchanged_old_storage(cases):
    for vector, fixture, expected in cases:
        before = c.prefix._expected(vector, fixture)
        wanted = change(
            before["pages"],
            fixture["vector_end"],
            read(fixture["pages"], c.ARGUMENT, 8),
            8,
        )
        wanted = change(wanted, c.RECEIVER + 8, fixture["vector_end"] + 8)
        for page, payload in wanted.items():
            if page not in (c.construction.STACK, c.construction.STACK + 4096):
                assert expected["pages"][page] == payload
        assert read(expected["pages"], c.RECEIVER + 4) == fixture["vector_begin"]
        assert read(expected["pages"], c.RECEIVER + 12) == fixture["vector_capacity"]
        assert expected["insertions"] == before["insertions"]


def test_exact_ordered_append_accesses(cases):
    for vector, fixture, expected in cases:
        before = c.prefix._expected(vector, fixture)
        frame, end = fixture["stack"] - 4, fixture["vector_end"]

        def event(access, address, value):
            return dict(access=access, address=address, width=4, value=value)

        suffix = [
            event("read", frame - 12, c.RECEIVER),
            event("read", c.RECEIVER + 8, end),
        ]
        if c.ARGUMENT < end:
            suffix.append(event("read", c.RECEIVER + 4, fixture["vector_begin"]))
        suffix += [
            event("read", c.RECEIVER + 12, fixture["vector_capacity"]),
            event("read", c.RECEIVER + 8, end),
            event("read", c.ARGUMENT, read(fixture["pages"], c.ARGUMENT)),
            event("write", end, read(fixture["pages"], c.ARGUMENT)),
            event("read", c.ARGUMENT + 4, c.prefix.SOURCE_OBJECT),
            event("write", end + 4, c.prefix.SOURCE_OBJECT),
            event("read", c.RECEIVER + 8, end),
            event("write", c.RECEIVER + 8, end + 8),
        ]
        assert expected["events"][: len(before["events"])] == before["events"]
        assert expected["events"][len(before["events"]) :][: len(suffix)] == suffix


def test_actual_ret4_abi_and_final_cookie_stack(cases):
    for vector, fixture, expected in cases:
        frame = fixture["stack"] - 4
        regs, pages = expected["registers"], expected["pages"]
        assert expected["endpoint"] == fixture["return_address"]
        assert regs["esp"] == fixture["stack"] + 8
        assert regs["eax"] == c.prefix.SOURCE_OBJECT
        assert regs["ecx"] == vector["cookie"] and expected["flags"] == 0x44
        assert regs["edx"] == (
            frame - 8 if vector["source_keys"] else fixture["registers"]["edx"]
        )
        for register in ("ebx", "esi", "edi", "ebp"):
            assert regs[register] == fixture["registers"][register]
        assert read(pages, frame - 24) == c.BASE + 0x2EB227
        assert read(pages, frame - 4) == vector["cookie"] ^ frame
        assert read(pages, frame + 4) == fixture["return_address"]
        assert read(pages, 0) == vector["previous_seh"]
        assert read(pages, c.returned.COOKIE) == vector["cookie"]


@pytest.mark.parametrize(
    "kind", ["record", "end", "payload", "iterator", "pair", "inserted_byte"]
)
def test_independent_model_rejects_forged_memory(cases, kind):
    _, fixture, expected = next(case for case in cases if case[2]["insertions"])
    frame = fixture["stack"] - 4
    address, width = {
        "record": (fixture["vector_end"], 8),
        "end": (c.RECEIVER + 8, 4),
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


@pytest.mark.parametrize(
    "field,value",
    [
        ("buffer_address", True),
        ("buffer_address", c.ARGUMENT),
        ("old_size", True),
        ("old_size", -1),
        ("old_size", 8),
        ("spare_records", True),
        ("spare_records", 0),
        ("spare_records", 9),
    ],
)
def test_invalid_spare_fixture_bounds(field, value):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], **{field: value}))


def test_expected_preserves_fixture(cases):
    vector, fixture, expected = cases[-1]
    before = copy.deepcopy(fixture)
    assert c._expected(vector, fixture) == expected
    assert fixture == before


@pytest.fixture(scope="module")
def receipts():
    evidence_path = PROGRAMS / (
        PREFIX + "native_lua_class_spare_return_conformance.json"
    )
    if not evidence_path.exists() or c.SEALED_SHA256 == "PENDING":
        pytest.skip("awaiting reviewed class spare return seal")
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
        cases=1152,
        iterations=3024,
        allocated_insertions=1584,
        existing_insertions=1440,
        max_iterations=7,
        instruction_bytes=1747,
        static_sites=679,
        executed_sites=607,
        spare_return_bytes=62,
        spare_return_sites=26,
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
    }
    assert all(row["rejected"] for row in controls.values())
    assert controls["cookie"]["endpoint"] == "0x003574d5"
    executed = set(evidence["executed_rvas"])
    assert {p["rva"] for p in evidence["body"]["spare_return_points"]} <= executed
    assert not any(
        a <= int(pc, 16) < b
        for pc in executed
        for a, b in ((0x2EB15F, 0x2EB179), (0x2EB1CC, 0x2EB1F7), (0x2EB1FC, 0x2EB205))
    )
    assert "failure frontier" in " ".join(evidence["scope"]["not_claimed"])


def test_modified_receipt_and_source_rejected(receipts):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    changed["summary"]["iterations"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)
    changed_sources = copy.deepcopy(sources)
    changed_sources["prefix"]["schema_version"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed_sources)


def test_exact_cli_rebuild(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    path, _, paths, _ = receipts
    command = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_class_spare_return_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key, source in paths.items():
        command += ["--" + key.replace("_", "-"), str(source)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
