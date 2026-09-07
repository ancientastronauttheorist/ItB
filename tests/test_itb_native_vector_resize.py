"""Resize pointer publication, frame restoration and conditional child contracts."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_vector_resize_semantics as helper
from src.observatory import native_vector_resize_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "delta", [0, 1, 7, 8, 9, 0x7FFFFFFF, 0x80000000, 0xFFFFFFF9, 0xFFFFFFFF]
)
def test_copy_length_and_published_end_differ_for_unaligned_words(delta):
    b = 0x10001000
    e = (b + delta) & 0xFFFFFFFF
    p = 0x20000000
    result = helper.resize_spec(b, e, e, 0xFFFFFFFF, p)
    expected = replay.oracle(b, e, e, 0xFFFFFFFF, p)
    assert result["copy_arguments"] == expected["copy_arguments"] == [p, b, delta]
    assert result["new_end"] == expected["new_end"] == (p + (delta & ~7)) & 0xFFFFFFFF


@pytest.mark.parametrize("begin", [0, 0x10001000])
@pytest.mark.parametrize("alignment", [0, 1, 7, 15])
def test_native_frame_cleanup_and_metadata_publication(begin, alignment):
    args = (begin, begin + 24, begin + 32, 6, 0x20000000)
    fixture = helper.case_fixture(*args, alignment)
    result = helper.model_case(*args, alignment)
    stack = fixture["stack"]
    assert [c["entry_esp"] for c in result["summaries"]] == [stack - 28, stack - 36] + (
        [stack - 36] if begin else []
    )
    assert result["registers"]["esp"] == stack + 8
    assert result["registers"]["eax"] == 0x20000018
    for reg in ("ebx", "esi", "edi", "ebp"):
        assert result["registers"][reg] == fixture["registers"][reg]
    writes = [
        e
        for e in result["events"]
        if e["kind"] == "write"
        and fixture["object"] <= e["address"] < fixture["object"] + 12
    ]
    assert [e["address"] - fixture["object"] for e in writes] == [8, 4, 0]
    assert [e["value"] for e in writes] == [0x20000030, 0x20000018, 0x20000000]
    assert (result["flags"]["af"] is None) == (begin == 0)


def test_empty_resize_still_calls_copy_without_deallocation():
    result = helper.model_case(0, 0, 0, 0, 0)
    assert [c["role"] for c in result["summaries"]] == ["allocation", "copy"]
    assert result["summaries"][1]["arguments"] == [0, 0, 0]


def test_ordinary_geometry_keeps_all_live_elements():
    result = helper.ordinary_geometry_spec(0x1000, 0x1018, 0x1020, 6, 0x2000)
    assert result["preserved_elements"] == 3 and result["copy_bytes"] == 24
    assert result["new_end"] == 0x2018 and result["new_capacity"] == 0x2030


@pytest.mark.parametrize(
    "args",
    [
        (0x1000, 0x1019, 0x1020, 6, 0x2000),
        (0, 8, 8, 1, 0x2000),
        (0x1000, 0x1018, 0x1020, 2, 0x2000),
        (0x1000, 0x80001000, 0x80001000, 0x10000000, 0x2000),
        (0x1000, 0x1008, 0x1008, 1, 0xFFFFFFF8),
    ],
)
def test_invalid_ordinary_geometry_is_not_promoted(args):
    with pytest.raises(helper.ResizeError):
        helper.ordinary_geometry_spec(*args)


def test_object_cannot_alias_saved_frame():
    with pytest.raises(helper.ResizeError, match="overlaps"):
        helper.model_case(0, 0, 0, 1, 0x2000, object_address=0x30001000)


@pytest.mark.parametrize("bad", [True, -1, 0x100000000, None])
def test_invalid_machine_count_rejected(bad):
    with pytest.raises(helper.ResizeError):
        helper.resize_spec(0, 0, 0, bad, 0)
    with pytest.raises(replay.ConformanceError):
        replay.oracle(0, 0, 0, bad, 0)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "allocation_semantics": "native_lua_vector_allocation_semantics",
        "deallocation_semantics": "native_vector_deallocation_semantics",
        "semantics": "native_vector_resize_semantics",
        "conformance": "native_vector_resize_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_published_receipts_preserve_explicit_child_scope(receipts):
    paths, data, sources = receipts
    assert (
        helper.validate_structure(data["semantics"], sources)["status"]
        == "structurally_verified"
    )
    assert (
        replay.validate_structure(data["conformance"], data["semantics"])["status"]
        == "structurally_verified"
    )
    assert (
        helper.encode_semantics(data["semantics"]).encode()
        == paths["semantics"].read_bytes()
    )
    assert (
        replay.encode_conformance(data["conformance"]).encode()
        == paths["conformance"].read_bytes()
    )
    assert data["semantics"]["summary"]["modeled_sites"] == 46
    assert data["conformance"]["summary"]["cases"] == 1600
    assert data["conformance"]["summary"]["callee_instructions"] == 0


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 99
    with pytest.raises((helper.ResizeError, replay.ConformanceError)):
        (
            helper.validate_structure(changed, sources)
            if kind == "semantics"
            else replay.validate_structure(changed, data["semantics"])
        )


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_exact_cli_rebuild(receipts, kind):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts" / ("itb_native_vector_resize_" + kind + ".py")),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "semantics" else ["semantics"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
