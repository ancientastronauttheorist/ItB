"""Independent global record overlay, partial-field and provenance checks."""

from __future__ import annotations
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from src.observatory import native_assertion_helper_failure_stores as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def values(flags=0x246):
    return dict(
        ecx=0x11223344,
        edx=0x22334455,
        ebx=0x33445566,
        esi=0x44556677,
        edi=0x55667788,
        ss=0x1234,
        cs=0x2345,
        ds=0x3456,
        es=0x4567,
        fs=0x5678,
        gs=0x6789,
        flags=flags,
        saved_ebp=0x2003000,
        inherited_return=0x779E5F,
        frame=0x2002CD0,
        current_cookie=0xAABBCCDD,
        current_other=0x98765432,
        dead_local=0xDEADBEEF,
    )


@pytest.mark.parametrize("flags", [0x46, 0x56, 0x246, 0x256, 0x446, 0x204246])
def test_independent_overlay_and_unknown_bytes(flags):
    before = bytes((i * 37 + 0xA5) % 256 for i in range(4096))
    v = values(flags)
    after = helper.overlay_spec(before, v)
    # Independent SDK-compatible field offsets, not copied from implementation.
    context = 0xB78
    fields = [
        (176, 4, 0),
        (172, 4, v["ecx"]),
        (168, 4, v["edx"]),
        (164, 4, v["ebx"]),
        (160, 4, v["esi"]),
        (156, 4, v["edi"]),
        (200, 2, v["ss"]),
        (188, 2, v["cs"]),
        (152, 2, v["ds"]),
        (148, 2, v["es"]),
        (144, 2, v["fs"]),
        (140, 2, v["gs"]),
        (192, 4, flags),
        (180, 4, v["saved_ebp"]),
        (184, 4, v["inherited_return"]),
        (196, 4, v["frame"] + 8),
        (0, 4, 65537),
    ]
    expected = bytearray(before)
    touched = set()
    for offset, width, value in fields:
        at = context + offset
        expected[at : at + width] = value.to_bytes(width, "little")
        touched.update(range(at, at + width))
    for offset, value in [
        (0, 0xC0000409),
        (4, 1),
        (12, v["inherited_return"]),
        (16, 1),
        (20, 2),
    ]:
        at = 0xB28 + offset
        expected[at : at + 4] = value.to_bytes(4, "little")
        touched.update(range(at, at + 4))
    assert after == bytes(expected)
    assert len(touched) == 76
    assert all(after[i] == before[i] for i in range(4096) if i not in touched)
    # Segment fields are DWORD SDK fields, but these are only WORD writes.
    for offset in [200, 188, 152, 148, 144, 140]:
        at = context + offset
        assert after[at + 2 : at + 4] == before[at + 2 : at + 4]
    assert after[0xB28 + 8 : 0xB28 + 12] == before[0xB28 + 8 : 0xB28 + 12]
    assert after[context + 204 : context + 716] == before[context + 204 : context + 716]


@pytest.mark.parametrize(
    "flags", [0, 2, 0x47, 0x42, 0x6, 0xC6, 0x846, 0x10046, 0x20046]
)
def test_incompatible_pushed_flags_rejected(flags):
    with pytest.raises(helper.FailureStoreError):
        helper.overlay_spec(bytes(4096), values(flags))


@pytest.mark.parametrize("key", ["dead_local", "current_cookie", "current_other"])
def test_dead_and_local_only_inputs_do_not_change_global_overlay(key):
    before = bytes([0xAD]) * 4096
    original = values()
    changed = dict(original)
    changed[key] ^= 0xFFFFFFFF
    assert helper.overlay_spec(before, original) == helper.overlay_spec(before, changed)


@pytest.mark.parametrize(
    "key,bad", [("ecx", True), ("frame", -1), ("flags", None), ("edx", 0x100000000)]
)
def test_invalid_input_words_rejected(key, bad):
    v = values()
    v[key] = bad
    with pytest.raises(helper.FailureStoreError):
        helper.overlay_spec(bytes(4096), v)


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "dispatch": "native_assertion_helper_failure_dispatch",
        "frontier": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary",
        "layout": "windows_exception_layout",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_failure_stores",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "cb12a468a04fd3e2b00609fce5a5d2aefe9f2beed8487f0d7cf2af9c6ac431ca"
    )
    assert evidence["summary"] == dict(
        actual_import_executions=0,
        bytes=217,
        cases=256,
        global_writes_per_case=22,
        global_written_bytes=76,
        instructions=42,
        negative_controls=3,
        reads_per_case=10,
        stack_writes_per_case=7,
        stack_written_bytes=12,
    )
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_stores(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


def test_final_stack_words_and_dead_read():
    v = values()
    v["frame"] = helper.STACK + 4096
    before = bytes((i * 17 + 0x55) % 256 for i in range(16384))
    expected = bytearray(before)
    for offset, value in [
        (-808, 0x7F19F8),
        (-8, v["current_cookie"]),
        (-4, v["current_other"]),
    ]:
        at = 4096 + offset
        expected[at : at + 4] = value.to_bytes(4, "little")
    assert helper.stack_overlay_spec(before, v) == bytes(expected)
    transfer = helper.transfer_spec()
    assert transfer["dead_read"]["instruction_rva"] == "0x00357bef"
    assert transfer["dead_read"]["G_offset"] == -804
    assert transfer["final_eax"] == 4 and transfer["final_esp_G_offset"] == -808
    assert transfer["zero_fill_premise"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("raw_bytes", "private"),
        ("scope", {}),
        ("summary", {}),
    ],
)
def test_mutated_receipt_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.FailureStoreError):
        helper.validate_structure(changed, sources)


def test_exact_pe_rebuild(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE to rebuild fallback stores")
    paths, sources, _ = chain
    args = ["verify", "--executable", executable, "--evidence", str(paths["evidence"])]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_failure_stores.py"),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == "" and json.loads(result.stdout)["status"] == "verified"
