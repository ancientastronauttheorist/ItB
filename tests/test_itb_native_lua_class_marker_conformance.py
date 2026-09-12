"""Native marker helper cdecl contracts, boolean AL and protected storage."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_marker_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "d8f146cc7b6666a53348465065e7f6f7768f3d803fb6e4ea38bc9d72662515b9"
RAW = "fbfae24cfe5e3ed9affd8ada5add7f04fba3a74ef2d072202e291459734a551e"


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


def test_native_return_lowbyte_upperbits_and_nonvolatile_registers(cases):
    for vector, fixture, expected in cases:
        present = vector["has_metatable"]
        truth = vector["value_kind"] not in ("nil", "false")
        eax = (vector["final_void_eax"] & 0xFFFFFF00) | int(truth) if present else 0
        regs = expected["registers"]
        assert regs["eax"] == eax
        assert regs["eax"] & 255 == int(present and truth)
        assert regs["esp"] == fixture["entry"] + 4
        for name in ("ebx", "esi", "edi", "ebp"):
            assert regs[name] == fixture["registers"][name]
        assert expected["endpoint"] == fixture["endpoint"]
        assert regs["ecx"] == expected["calls"][-1]["response"]["ecx"]
        assert regs["edx"] == expected["calls"][-1]["response"]["edx"]
        if not present or not truth:
            assert expected["flags"] == 0x44 and expected["flag_mask"] == 0x8C5
        else:
            assert expected["flag_mask"] == 0x8D5
            assert expected["flags"] == c._add_flags(fixture["entry"] - 12, 8)


def test_actual_cdecl_arguments_frames_and_lua_prefix(cases):
    for vector, fixture, expected in cases:
        calls = expected["calls"]
        assert [r["api"] for r in calls] == list(
            c.APIS if vector["has_metatable"] else c.APIS[:1]
        )
        assert [r["entry_esp"] - fixture["entry"] for r in calls] == (
            [-16, -16, -24, -32, -16] if vector["has_metatable"] else [-16]
        )
        arguments = [
            fixture["registers"]["edx"],
            c.LITERAL,
            0xFFFFFFFE,
            0xFFFFFFFF,
            0xFFFFFFFD,
        ]
        for call, arg in zip(calls, arguments):
            assert call["arguments"] == [fixture["registers"]["ecx"], arg]
            assert call["entry_registers"]["esi"] == fixture["registers"]["ecx"]
            assert call["entry_registers"]["esp"] == call["entry_esp"]
            assert call["continuation"] == c.BASE + int(call["site_rva"], 16) + 6
            assert (
                dict(
                    access="write",
                    address=call["entry_esp"],
                    width=4,
                    value=call["continuation"],
                )
                in expected["events"]
            )
        length = vector["prefix_length"]
        assert (
            calls[0]["lua_top_before"] == length
            and calls[-1]["lua_top_after"] == length
        )
        if vector["has_metatable"]:
            assert [(r["lua_top_before"], r["lua_top_after"]) for r in calls] == [
                (length, length + 1),
                (length + 1, length + 2),
                (length + 2, length + 2),
                (length + 2, length + 2),
                (length + 2, length),
            ]


def test_independent_final_stack_cells_and_all_other_memory(cases):
    for vector, fixture, expected in cases:
        entry = fixture["entry"]
        cells = {
            -4: fixture["registers"]["esi"],
            -8: fixture["registers"]["edx"],
            -12: fixture["registers"]["ecx"],
            -16: c.BASE + 0x2EB56B,
        }
        if vector["has_metatable"]:
            cells.update(
                {
                    -8: 0xFFFFFFFD,
                    -16: c.BASE
                    + (
                        0x2EB5AD
                        if vector["value_kind"] in ("nil", "false")
                        else 0x2EB5A0
                    ),
                    -20: fixture["registers"]["ecx"],
                    -24: 0xFFFFFFFF,
                    -28: fixture["registers"]["ecx"],
                    -32: c.BASE + 0x2EB590,
                }
            )
        wanted = fixture["pages"]
        for offset, value in cells.items():
            wanted = change(wanted, entry + offset, value)
        assert expected["pages"] == wanted == c._stack_model(vector, fixture)
        assert read(expected["pages"], entry) == fixture["endpoint"]
        assert (
            bytes(
                read(expected["pages"], c.LITERAL + i, 1)
                for i in range(len(c.LITERAL_BYTES))
            )
            == c.LITERAL_BYTES
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("alignment", True),
        ("alignment", -1),
        ("alignment", 16),
        ("prefix_length", 2),
        ("has_metatable", 1),
        ("value_kind", "unknown"),
        ("final_void_eax", True),
        ("final_void_eax", -1),
        ("final_void_eax", 2**32),
    ],
)
def test_invalid_fixture_domain(field, value):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], **{field: value}))


def test_oracle_preserves_input(cases):
    vector, fixture, expected = cases[-1]
    before = copy.deepcopy(fixture)
    assert c._expected(vector, fixture) == expected
    assert fixture == before


@pytest.fixture(scope="module")
def receipts():
    evidence_path = PROGRAMS / (PREFIX + "native_lua_class_marker_conformance.json")
    if not evidence_path.exists() or c.SEALED_SHA256 == "PENDING":
        pytest.skip("awaiting reviewed marker seal")
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
        cases=576,
        instruction_bytes=84,
        static_sites=32,
        executed_sites=32,
        call_sites=6,
        imported_functions=5,
        supplied_api_returns=2496,
        native_lua_api_instructions=0,
        accounting_promotions=0,
    ).items():
        assert summary[key] == value
    assert summary["paths"] == dict(
        no_metatable=96, false_marker=192, truthy_marker=288
    )
    assert evidence["executed_rvas"] == [p["rva"] for p in evidence["body"]["points"]]
    assert {v["kind"] for v in evidence["negative_controls"]} == {
        "ancestor",
        "saved_esi",
        "argument",
        "return",
        "al_upper",
        "literal_padding",
        "iat_padding",
    }
    assert all(v["rejected"] for v in evidence["negative_controls"])
    assert "No actual Lua DLL" in " ".join(evidence["scope"]["premises"])


def test_modified_receipt_and_source_rejected(receipts):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    changed["summary"]["cases"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)
    changed_sources = copy.deepcopy(sources)
    changed_sources["marker_semantics"]["schema_version"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed_sources)


def test_exact_cli_rebuild(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    path, _, paths, _ = receipts
    command = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_class_marker_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key, source in paths.items():
        command += ["--" + key.replace("_", "-"), str(source)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
