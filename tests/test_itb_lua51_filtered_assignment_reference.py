"""Independent redirected-assignment and protected-error reference checks."""

from __future__ import annotations
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from src.observatory import lua51_filtered_assignment_reference as helper

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT / "data/observatory/programs/lua_5_1_5_x86_filtered_assignment_reference.json"
)


def test_independent_reference_partition():
    rows = helper.expected_rows()
    assert len(rows) == 48 and len({tuple(r[:3]) for r in rows}) == 48
    assert sum(r[3] == 0 for r in rows) == 42
    assert sum(r[3] == 2 for r in rows) == 6
    for (
        mode,
        pattern,
        prefix,
        status,
        requests,
        callbacks,
        before,
        after,
        preserved,
        eqcalls,
        match,
        count,
    ) in rows:
        total = [0, 0, 0, 1, 1, 6][pattern]
        assert before == 2 + 2 * prefix and eqcalls == 0
        if mode == 3 and total:
            assert (
                status == 2
                and requests == callbacks == 1
                and after == -1
                and preserved == 0
                and match == -1
            )
        else:
            assert (
                status == 0
                and requests == count == total
                and after == before
                and preserved == match == 1
            )
            assert callbacks == (total if mode == 2 else 0)


def transcript():
    return "version Lua 5.1.5\npointer 4\n" + "".join(
        "case " + " ".join(map(str, r)) + "\n" for r in helper.expected_rows()
    )


def test_parser_accepts_expected_transcript():
    assert helper.parse_probe(transcript()) == helper.expected_rows()


@pytest.mark.parametrize(
    "which", ["version", "count", "duplicate", "eqhandler", "truth", "error"]
)
def test_parser_rejects_changed_results(which):
    lines = transcript().splitlines()
    if which == "version":
        lines[0] = "version Lua 5.4.0"
    elif which == "count":
        lines.pop()
    elif which == "duplicate":
        lines.append(lines[-1])
    elif which == "eqhandler":
        row = lines[2].split()
        row[10] = "1"
        lines[2] = " ".join(row)
    elif which == "truth":
        row = lines[12].split()
        row[5] = "0"
        lines[12] = " ".join(row)
    else:
        lines[-1] = lines[-1].replace(" 2 1 1 ", " 0 1 1 ")
    with pytest.raises(helper.AssignmentReferenceError):
        helper.parse_probe("\n".join(lines))


@pytest.fixture(scope="module")
def evidence():
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_sealed_reference(evidence):
    assert (
        hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
        == "aa3a701d5b74f4e774727e21db0a4eeaa0953f935bf4fb9e4cd141ea80bb80ee"
    )
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_reference(evidence).encode() == EVIDENCE.read_bytes()
    assert helper.validate_structure(evidence)["status"] == "structurally_verified"


@pytest.mark.parametrize(
    "key,value", [("schema_version", True), ("scope", {}), ("raw_bytes", "private")]
)
def test_mutated_receipt_rejected(evidence, key, value):
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.AssignmentReferenceError):
        helper.validate_structure(changed)


def test_official_source_exact_rebuild():
    archive = os.environ.get("ITB_LUA51_REFERENCE_ARCHIVE")
    if not archive:
        pytest.skip("set ITB_LUA51_REFERENCE_ARCHIVE for compiler probe")
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_lua51_filtered_assignment_reference.py"),
            "build",
            "--archive",
            archive,
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert r.stderr == b"" and r.stdout == EVIDENCE.read_bytes()
