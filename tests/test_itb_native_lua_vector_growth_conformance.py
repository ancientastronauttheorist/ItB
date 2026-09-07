"""Independent arithmetic boundaries and exact bounded growth replay checks."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_lua_vector_growth_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "end,capacity,expected_request",
    [
        (0, 0, 1),
        (8, 8, 2),
        (16, 16, 3),
        (32, 32, 6),
        (0x7FFFFFF8, 0x7FFFFFF8, 0x17FFFFFE),
        (0x7FFFFFFF, 0x80000000, 0x10000000),
        (0x80000000, 0x80000000, 0xF0000001),
        (0xFFFFFFFF, 0, 0),
        (0xFFFFFFF8, 0xFFFFFFF8, 0),
        (0xFFFFFFF0, 0xFFFFFFF0, 0xFFFFFFFF),
    ],
)
def test_explicit_machine_boundary_requests(end, capacity, expected_request):
    result = replay.oracle(dict(begin=0, end=end, capacity=capacity, alignment=0))
    assert result["path"] == "resize_frontier"
    assert result["requested"] == expected_request
    assert result["stack_delta"] == -16


@pytest.mark.parametrize("gap", [0, 1, 7, 8, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF])
def test_free_byte_partition_including_unsigned_negative(gap):
    result = replay.oracle(
        dict(begin=0, end=8, capacity=(8 + gap) & 0xFFFFFFFF, alignment=15)
    )
    assert (result["path"] == "no_growth") == (gap >= 8)
    if gap >= 8:
        assert result["stack_delta"] == -8 and result["requested"] is None


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (0, 0, 0x44),
        (0, 1, 0x95),
        (1, 0, 0),
        (0x80000000, 1, 0x814),
        (0x7FFFFFFF, 0xFFFFFFFF, 0x885),
    ],
)
def test_final_comparison_flags(left, right, expected):
    assert replay._cmp_flags(left, right) == expected


@pytest.mark.parametrize("key", ["begin", "end", "capacity", "alignment"])
@pytest.mark.parametrize("value", [True, -1, 0x100000000, None])
def test_invalid_input_rejected(key, value):
    vector = dict(begin=0, end=0, capacity=0, alignment=0)
    vector[key] = value
    with pytest.raises(replay.ConformanceError):
        replay.oracle(vector)


@pytest.fixture(scope="module")
def receipt():
    paths = {
        k: PROGRAMS / (PREFIX + "native_lua_vector_growth_" + k + ".json")
        for k in ["semantics", "conformance"]
    }
    return paths, {
        k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()
    }


def test_published_receipt(receipt):
    paths, data = receipt
    evidence = data["conformance"]
    assert (
        replay.encode_conformance(evidence).encode()
        == paths["conformance"].read_bytes()
    )
    assert replay._canonical_sha256(evidence) == replay.SEALED_SHA256
    assert (
        replay.validate_structure(evidence, data["semantics"])["status"]
        == "structurally_verified"
    )
    assert evidence["summary"]["cases"] == 3168
    assert evidence["summary"]["executed_calls"] == 0
    assert evidence["summary"]["failure_frontier"] == 0
    assert evidence["summary"]["executed_instruction_sites"] == 33


def test_forged_execution_claim_rejected(receipt):
    _, data = receipt
    evidence = copy.deepcopy(data["conformance"])
    evidence["summary"]["executed_calls"] = 1
    with pytest.raises(replay.ConformanceError):
        replay.validate_structure(evidence, data["semantics"])


def test_exact_replay_binary_cli(receipt):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _ = receipt
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_lua_vector_growth_conformance.py"),
            "build",
            "--executable",
            executable,
            "--semantics",
            str(paths["semantics"]),
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
