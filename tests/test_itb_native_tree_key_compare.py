"""Relocated append arguments and complete native ancestor-frame contract."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_tree_key_compare_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "left,right,less,signed,last",
    [
        (b"\0", b"\0", 0, 0, 0),
        (b"a\0", b"b\0", 1, -1, 97),
        (b"b\0", b"a\0", 0, 1, 98),
        (b"a\0ignored", b"a\0different", 0, 0, 0),
        (b"a\x80\0", b"a\x7f\0", 0, 1, 128),
        (b"a" * 64 + b"\0", b"a" * 64 + b"b\0", 1, -1, 0),
    ],
)
def test_unsigned_nul_order_and_last_compared_byte(left, right, less, signed, last):
    r = helper.compare_spec(left, right)
    assert (r["less"], r["signed"], r["last_left"]) == (less, signed, last)
    assert r["ecx"] == signed & 0xFFFFFFFF
    assert r["flag_mask"] & 0x10 == 0


@pytest.mark.parametrize("n", [0, 1, 2, 3, 31, 32, 63, 64])
def test_equal_termination_reads_exactly_through_first_nul(n):
    r = helper.compare_spec(b"a" * n + b"\0unused", b"a" * n + b"\0tail")
    assert r["reads"] == [
        dict(side=side, offset=i, value=97 if i < n else 0)
        for i in range(n + 1)
        for side in ("left", "right")
    ]
    assert r["flags"] == 0x44


@pytest.mark.parametrize(
    "left,right",
    [
        (b"missing", b"\0"),
        (b"\0", b"missing"),
        (b"a" * 256 + b"\0", b"\0"),
        (bytearray(b"\0"), b"\0"),
        (None, b"\0"),
    ],
)
def test_unbounded_or_nonbyte_storage_rejected(left, right):
    with pytest.raises(helper.ConformanceError):
        helper.compare_spec(left, right)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "conformance": "native_tree_key_compare_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_comparator_receipt(receipts):
    paths, data, sources = receipts
    evidence = data["conformance"]
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )
    assert (
        helper.encode_conformance(evidence).encode()
        == paths["conformance"].read_bytes()
    )
    assert (
        evidence["summary"]["executed_sites"] == 30
        and evidence["summary"]["opaque_instructions"] == 0
    )


def test_changed_receipt_rejected(receipts):
    _, data, sources = receipts
    changed = copy.deepcopy(data["conformance"])
    changed["schema_version"] = 99
    with pytest.raises(helper.ConformanceError):
        helper.validate_structure(changed, sources)


def test_exact_cli_rebuild(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_tree_key_compare_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
