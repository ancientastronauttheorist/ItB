"""Division boundaries, metadata guard inverse, and exact isolated replay."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.observatory import native_vector_deallocation_semantics as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
P = 0x10000020


@pytest.mark.parametrize("count", [0, 1, 0xFFFFFFFF])
def test_zero_stride_stops_before_division_operand_read(count):
    fixture = helper.case_fixture(P, count, 0)
    result = helper.model_case(P, count, 0)
    assert result["specification"]["outcome"] == "division_frontier"
    assert result["stop_rva"] == "0x0000780b"
    assert not any(
        e["kind"] == "read" and e["address"] == fixture["stack"] + 12
        for e in result["events"]
    )
    assert result["registers"]["eax"] == 0xFFFFFFFF
    assert result["registers"]["edx"] == 0


@pytest.mark.parametrize("stride", [2, 7, 8, 16, 4096, 0x80000000, 0xFFFFFFFF])
def test_count_overflow_is_guarded_before_multiplication(stride):
    quotient, remainder = divmod(0xFFFFFFFF, stride)
    result = helper.model_case(P, quotient + 1, stride)
    assert result["specification"]["reason"] == "count_overflow"
    assert result["registers"]["eax"] == quotient
    assert result["registers"]["edx"] == remainder
    assert "0x00007816" not in result["trace_rvas"]


@pytest.mark.parametrize("pointer", [0, 1, P, 0xFFFFFFFF])
def test_small_payload_passes_pointer_without_metadata_access(pointer):
    result = helper.model_case(pointer, 511, 8)
    assert result["specification"]["free_argument"] == pointer
    assert not result["specification"]["metadata_read"]
    assert result["stop_rva"] == "0x00007851"


@pytest.mark.parametrize(
    "delta,reason",
    [
        (0, "metadata_not_below_pointer"),
        (1, "metadata_distance_below_four"),
        (3, "metadata_distance_below_four"),
        (4, None),
        (31, None),
        (32, None),
        (35, None),
        (36, "metadata_distance_above_thirty_five"),
    ],
)
def test_large_metadata_distance_endpoints(delta, reason):
    result = helper.model_case(P, 512, 8, P - delta)
    spec = result["specification"]
    assert spec["metadata_read"] and spec["reason"] == reason
    assert spec["outcome"] == ("guard_failure" if reason else "free_frontier")
    if reason is None:
        assert spec["free_argument"] == P - delta


def test_alignment_test_uses_low_byte_flags():
    result = helper.model_case(0x80000001, 512, 8)
    assert result["specification"]["reason"] == "misaligned_pointer"
    assert result["arithmetic_flags"]["sf"] == 0
    assert result["arithmetic_flags"]["af"] is None
    assert not result["specification"]["metadata_read"]


@pytest.mark.parametrize("offset", range(32))
def test_allocation_alignment_metadata_recovers_original_block(offset):
    raw = 0x10000100 + offset
    result = helper.inverse_storage_spec(raw, 4096)
    assert result["aligned_pointer"] % 32 == 0
    assert result["free_argument"] == raw
    assert 4 <= result["leading_bytes"] <= 35
    assert result["metadata_address"] == result["aligned_pointer"] - 4


def test_metadata_cannot_overlap_protected_frame():
    with pytest.raises(helper.DeallocationError, match="overlaps"):
        helper.model_case(0x30001000, 512, 8, 0x30000FE0)


@pytest.mark.parametrize("bad", [True, -1, 0x100000000, None])
def test_invalid_stride_rejected(bad):
    with pytest.raises(helper.DeallocationError):
        helper.deallocation_spec(P, 0, bad)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "allocation_semantics": "native_lua_vector_allocation_semantics",
        "return_semantics": "native_lua_vector_allocation_return_semantics",
        "semantics": "native_vector_deallocation_semantics",
        "conformance": "native_vector_deallocation_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_published_receipts_and_exact_encoding(receipts):
    from src.observatory import native_vector_deallocation_conformance as replay

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


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    from src.observatory import native_vector_deallocation_conformance as replay

    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 99
    with pytest.raises((helper.DeallocationError, replay.ConformanceError)):
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
        str(ROOT / "scripts" / ("itb_native_vector_deallocation_" + kind + ".py")),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "semantics" else ["semantics"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
