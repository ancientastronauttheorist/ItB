"""Independent finite replay domain, overlap oracle and subprocess checks."""

from __future__ import annotations
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from src.observatory import native_lua_class_vector_append_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (PREFIX + "native_lua_class_vector_append_conformance.json")
SEMANTICS = PROGRAMS / (PREFIX + "native_lua_class_vector_append_semantics.json")


def test_independent_replay_partition():
    cases = helper.vectors()
    assert (
        len(cases) == 144 and len({(v["name"], v["alignment"]) for v in cases}) == 144
    )
    assert sum(v["end"] == v["capacity"] for v in cases) == 32
    assert sum(v["post_end"] == 0 for v in cases) == 16


def test_overlap_and_null_oracles():
    initial = bytes((i ^ (i >> 8)) & 255 for i in range(65536))
    overlap = next(v for v in helper.vectors() if v["name"] == "ordered_overlap")
    result = helper.oracle(overlap, initial)
    at = overlap["end"] - helper.DATA
    assert result["memory"][at : at + 8] == initial[at - 4 : at] * 2
    null = next(v for v in helper.vectors() if v["name"] == "null_destination")
    result = helper.oracle(null, initial)
    assert result["memory"] == initial and result["end_after"] == 8


@pytest.fixture(scope="module")
def chain():
    return json.loads(EVIDENCE.read_text()), json.loads(SEMANTICS.read_text())


def test_sealed_receipt(chain):
    evidence, semantics = chain
    assert (
        hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
        == "c3f752ec1862c41021b3e4e4cc2e2ee1488851d96ab8624328837ce1201b7798"
    )
    assert evidence["summary"] == dict(
        cases=144,
        visited_instruction_sites=36,
        executed_noncall_instruction_sites=34,
        summarized_call_sites=2,
        growth_summaries=32,
        actual_growth_helper_executions=0,
        negative_controls=1,
    )
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_conformance(evidence).encode() == EVIDENCE.read_bytes()
    assert (
        helper.validate_structure(evidence, semantics)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("scope", {}),
        ("vectors", []),
        ("raw_bytes", "private"),
    ],
)
def test_mutated_receipt_rejected(chain, key, value):
    evidence, semantics = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.ConformanceError):
        helper.validate_structure(changed, semantics)


def test_exact_replay_subprocess():
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and supply Unicorn 2.1.4 for exact replay")
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_lua_class_vector_append_conformance.py"),
            "build",
            "--executable",
            executable,
            "--semantics",
            str(SEMANTICS),
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert r.stderr == b"" and r.stdout == EVIDENCE.read_bytes()
