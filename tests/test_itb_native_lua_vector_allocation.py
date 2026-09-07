"""Threshold, defined-flag, stack and exact evidence checks for allocation decisions."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_lua_vector_allocation_semantics as helper
from src.observatory import native_lua_vector_allocation_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "count,path,expected_request",
    [
        (0, "zero_return", None),
        (1, "small_request", 8),
        (511, "small_request", 4088),
        (512, "large_request", 4131),
        (513, "large_request", 4139),
        (0x1FFFFFFB, "large_request", 0xFFFFFFFB),
        (0x1FFFFFFC, "padding_failure", None),
        (0x1FFFFFFD, "padding_failure", None),
        (0x1FFFFFFE, "padding_failure", None),
        (0x1FFFFFFF, "padding_failure", None),
        (0x20000000, "size_failure", None),
        (0xFFFFFFFF, "size_failure", None),
    ],
)
def test_independent_threshold_table(count, path, expected_request):
    result = helper.allocation_spec(count)
    expected = replay.oracle(count)
    assert result["outcome"] == expected["path"] == path
    assert result["requested"] == expected["requested"] == expected_request
    for alignment in [0, 15]:
        modeled = helper.model_case(count, alignment)
        assert modeled["returned"] == (count == 0)
        assert modeled["registers"]["eax"] == expected["eax"]


def test_zero_return_cleans_argument_and_excludes_undefined_flag():
    fixture = helper.case_fixture(0, 15)
    result = helper.model_case(0, 15)
    assert result["registers"]["esp"] == fixture["stack"] + 8
    assert result["registers"]["ebp"] == fixture["registers"]["ebp"]
    assert result["registers"]["eax"] == result["registers"]["ecx"] == 0
    assert result["arithmetic_flags"]["af"] is None
    assert replay.oracle(0)["flag_mask"] == 0x8C5
    assert [e["kind"] for e in result["events"]] == ["write", "read", "read", "read"]


@pytest.mark.parametrize(
    "count,padded",
    [(0x1FFFFFFC, 3), (0x1FFFFFFD, 11), (0x1FFFFFFE, 19), (0x1FFFFFFF, 27)],
)
def test_wrapping_padding_records_word_without_request(count, padded):
    result = helper.model_case(count)
    assert result["registers"]["ecx"] == padded
    assert result["specification"]["requested"] is None
    assert result["stop_rva"] == "0x0008a976"


@pytest.mark.parametrize("bad", [True, False, -1, 0x100000000, None, "512"])
def test_invalid_count_rejected(bad):
    with pytest.raises(helper.AllocationError):
        helper.allocation_spec(bad)
    with pytest.raises(replay.ConformanceError):
        replay.oracle(bad)


@pytest.fixture(scope="module")
def receipts():
    suffixes = {
        "chain": "native_lua_class_return_helper_chain",
        "program_facts": "program_facts",
        "growth_semantics": "native_lua_vector_growth_semantics",
        "semantics": "native_lua_vector_allocation_semantics",
        "conformance": "native_lua_vector_allocation_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_receipts_and_distinct_evidence_classes(receipts):
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
    assert data["semantics"]["summary"]["cases"] == 19744
    assert data["conformance"]["summary"]["cases"] == 672
    assert data["conformance"]["summary"]["executed_calls"] == 0


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_claim_rejected(receipts, kind):
    _, data, sources = receipts
    altered = copy.deepcopy(data[kind])
    altered["summary"]["cases"] += 1
    with pytest.raises((helper.AllocationError, replay.ConformanceError)):
        (
            helper.validate_structure(altered, sources)
            if kind == "semantics"
            else replay.validate_structure(altered, data["semantics"])
        )


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_exact_binary_cli_rebuild(receipts, kind):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / ("scripts/itb_native_lua_vector_allocation_" + kind + ".py")),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "semantics" else ["semantics"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
