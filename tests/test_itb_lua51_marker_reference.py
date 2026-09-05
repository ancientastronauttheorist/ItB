"""Independent reference-runtime truth classes and protected-error checks."""

from __future__ import annotations
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from src.observatory import lua51_marker_reference as helper

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/observatory/programs/lua_5_1_5_x86_marker_reference.json"


def test_independent_expected_partition():
    rows = helper.expected_rows()
    assert len(rows) == 70 and len({tuple(r[:3]) for r in rows}) == 70
    assert sum(r[3] == 0 for r in rows) == 56
    assert sum(r[3] == 2 for r in rows) == 14
    assert sum(r[8] for r in rows) == 28
    for mode, kind, negative, status, result, before, after, prefix, calls, top in rows:
        assert negative in (0, 1) and before == 3 and top == 1
        if mode == 4:
            assert (
                status == 2
                and result == -1
                and after == -1
                and prefix == 0
                and calls == 1
            )
        else:
            assert status == 0 and after == 3 and prefix == 1
            assert result == int(mode != 0 and kind not in (0, 1))
            assert calls == int(mode == 3)


def transcript():
    return "version Lua 5.1.5\npointer 4\n" + "".join(
        "case " + " ".join(map(str, row)) + "\n" for row in helper.expected_rows()
    )


def test_parser_accepts_reference_transcript():
    assert helper.parse_probe(transcript()) == helper.expected_rows()


@pytest.mark.parametrize(
    "mutation",
    ["version", "pointer", "missing", "duplicate", "truth", "error", "column"],
)
def test_parser_rejects_drift(mutation):
    lines = transcript().splitlines()
    if mutation == "version":
        lines[0] = "version Lua 5.4.0"
    elif mutation == "pointer":
        lines[1] = "pointer 8"
    elif mutation == "missing":
        lines.pop()
    elif mutation == "duplicate":
        lines.append(lines[-1])
    elif mutation == "truth":
        lines[2 + 14 + 6] = "case 1 3 0 0 0 3 3 1 0 1"
    elif mutation == "error":
        lines[-1] = lines[-1].replace(" 2 -1 ", " 0 0 ")
    else:
        lines[-1] += " 0"
    with pytest.raises(helper.ReferenceError):
        helper.parse_probe("\n".join(lines))


@pytest.fixture(scope="module")
def evidence():
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_sealed_reference(evidence):
    assert (
        hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
        == "56a5956cf5f69e6f74f962681b53969775c2b5615da6b301cfece85f35285f08"
    )
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_reference(evidence).encode() == EVIDENCE.read_bytes()
    assert helper.validate_structure(evidence)["status"] == "structurally_verified"
    assert evidence["configuration"]["game_dll_loaded"] is False


@pytest.mark.parametrize(
    "key,value",
    [("schema_version", True), ("source", {}), ("scope", {}), ("raw_bytes", "private")],
)
def test_mutated_receipt_rejected(evidence, key, value):
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.ReferenceError):
        helper.validate_structure(changed)


def test_official_source_exact_rebuild():
    archive = os.environ.get("ITB_LUA51_REFERENCE_ARCHIVE")
    if not archive:
        pytest.skip("set ITB_LUA51_REFERENCE_ARCHIVE for compiler probe")
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_lua51_marker_reference.py"),
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
