"""Native marker helper cdecl contracts, boolean AL and protected storage."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_table_transfer_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "c592340aaef40157af3330b0bdf096441ff7a3f25fa12902ce7f023e81772063"
RAW = "747ba7fda8b4ebf813f5af3f8aba7d1ae20c17e4d05cb0cb356a03280896d2fe"


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


def test_independent_filter_and_stack_requests(cases):
    for vector, fixture, expected in cases:
        kinds = vector["kinds"]
        relation = expected["relation"]
        assert relation["assignments"] == [
            i for i, k in enumerate(kinds) if k == "other"
        ]
        assert relation["skipped"] == [i for i, k in enumerate(kinds) if k != "other"]
        assert relation["initial"] == relation["final"]
        assert relation["api_count"] == 2 + sum(
            {"init": 4, "finalize": 7, "other": 10}[k] for k in kinds
        )
        assert [r["api"] for r in expected["calls"]] == [
            r["api"] for r in relation["calls"]
        ]
        assert sum(
            r["api"] == "lua_settable" for r in expected["calls"]
        ) == kinds.count("other")


def test_exact_cdecl_frames_and_staged_import_targets(cases):
    for vector, fixture, expected in cases:
        frames = [-12, -20]
        for kind in vector["kinds"]:
            frames.extend([-24, -36])
            if kind == "init":
                frames.append(-24)
            else:
                frames.extend([-24, -32, -44])
                frames.extend([-24] if kind == "finalize" else [-24, -32, -40, -48])
            frames.append(-24)
        assert [r["entry_esp"] - fixture["entry"] for r in expected["calls"]] == frames
        for call, logical in zip(expected["calls"], expected["relation"]["calls"]):
            assert call["arguments"][0] == fixture["registers"]["ecx"]
            translated = [
                (
                    next(a for a, p in c.LITERALS.items() if p[:-1].decode() == arg)
                    if type(arg) is str
                    else arg & 0xFFFFFFFF
                )
                for arg in logical["arguments"]
            ]
            assert call["arguments"][1:] == translated
            pc = int(call["site_rva"], 16)
            staged = c.CALLS[pc][1]
            assert call["continuation"] == c.BASE + pc + (2 if staged else 6)
            if staged:
                assert call["entry_registers"][staged] == call["target"]
            assert call["entry_registers"]["esi"] == fixture["registers"]["ecx"]
        events = expected["events"]
        for api in ("lua_pushstring", "lua_settop"):
            reads = [
                e
                for e in events
                if e["access"] == "read" and e["address"] == c.BASE + c.SLOTS[api]
            ]
            assert len(reads) == int(bool(vector["kinds"]))


def test_exact_native_return_and_all_protected_storage(cases):
    for vector, fixture, expected in cases:
        regs = expected["registers"]
        assert (
            regs["eax"] == 0
            and expected["flags"] == 0x44
            and expected["flag_mask"] == 0x8C5
        )
        assert (
            regs["esp"] == fixture["entry"] + 4
            and expected["endpoint"] == fixture["endpoint"]
        )
        for r in ("ebx", "esi", "edi", "ebp"):
            assert regs[r] == fixture["registers"][r]
        for r in ("ecx", "edx"):
            assert regs[r] == expected["calls"][-1]["response"][r]
        pages = fixture["pages"]
        for e in expected["events"]:
            if e["access"] == "write":
                assert c.STACK <= e["address"] < c.STACK + 16384
                pages = change(pages, e["address"], e["value"])
        assert pages == expected["pages"]
        entry = fixture["entry"]
        assert read(pages, entry) == fixture["endpoint"]
        assert read(pages, entry - 4) == fixture["registers"]["esi"]
        if vector["kinds"]:
            assert read(pages, entry - 8) == fixture["registers"]["ebx"]
            assert read(pages, entry - 12) == fixture["registers"]["edi"]
        for literal, payload in c.LITERALS.items():
            assert (
                bytes(read(pages, literal + i, 1) for i in range(len(payload)))
                == payload
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("alignment", True),
        ("alignment", 2),
        ("alignment", -1),
        ("prefix_length", 1),
        ("prefix_length", True),
        ("kinds", ()),
        ("kinds", ["other"] * 4),
        ("kinds", ["bad"]),
        ("kinds", [True]),
    ],
)
def test_invalid_fixture_domain(field, value):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], **{field: value}))


def test_oracle_preserves_fixture(cases):
    vector, fixture, expected = cases[-1]
    snapshot = copy.deepcopy(fixture)
    assert c._expected(vector, fixture) == expected
    assert fixture == snapshot


@pytest.fixture(scope="module")
def receipts():
    evidence_path = PROGRAMS / (PREFIX + "native_lua_table_transfer_conformance.json")
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
        cases=320,
        instruction_bytes=180,
        call_sites=14,
        imported_functions=8,
        supplied_api_returns=6352,
        assignment_requests=272,
        iterations=816,
        max_iterations=3,
        native_lua_api_instructions=0,
        accounting_promotions=0,
    ).items():
        assert summary[key] == value
    assert (
        summary["static_sites"]
        == summary["executed_sites"]
        == len(evidence["body"]["points"])
    )
    assert evidence["executed_rvas"] == [p["rva"] for p in evidence["body"]["points"]]
    assert {v["kind"] for v in evidence["negative_controls"]} == {
        "ancestor",
        "saved_esi",
        "saved_ebx",
        "argument",
        "return",
        "result",
        "literal_padding",
        "iat_padding",
        "staged_ebx",
        "staged_edi",
    }
    assert all(v["rejected"] for v in evidence["negative_controls"])
    assert "Actual Lua DLL" in " ".join(evidence["scope"]["not_claimed"])
    assert evidence["model_contract"]["sha256"] == c._canonical_sha256(
        c._model_contract()
    )


def test_modified_receipt_and_source_rejected(receipts):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    changed["summary"]["cases"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)
    changed_sources = copy.deepcopy(sources)
    changed_sources["class_chain"]["schema_version"] += 1
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed_sources)


def test_exact_cli_rebuild(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    path, _, paths, _ = receipts
    command = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_table_transfer_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key, source in paths.items():
        command += ["--" + key.replace("_", "-"), str(source)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
