"""Short overlapping copy, zero-length access, flags and discontiguous witnesses."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_small_copy_semantics as helper
from src.observatory import native_small_copy_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize("length", range(32))
def test_every_short_length_matches_original_source_snapshot(length):
    for delta in (-40, -3, -1, 0, 1, 3, 40):
        source, destination = 64, 64 + delta
        fixture = helper.case_fixture(length, source, destination)
        expected = bytearray(fixture["payload"])
        expected[destination : destination + length] = fixture["payload"][
            source : source + length
        ]
        result = helper.model_case(length, source, destination)
        assert result["payload_after_sha256"] == hashlib.sha256(expected).hexdigest()
        assert result["direction"] == ("backward" if 0 < delta < length else "forward")
        assert result["registers"]["eax"] == helper.PAYLOAD + destination
        assert result["registers"]["ecx"] == 0
        assert (result["arithmetic_flags"]["af"] is None) == (length % 4 == 0)


def test_zero_length_does_not_access_payload():
    result = helper.model_case(0)
    assert not any(
        helper.PAYLOAD <= e["address"] < helper.PAYLOAD + 256 for e in result["events"]
    )


@pytest.mark.parametrize("df", [0, 1])
@pytest.mark.parametrize("destination", [63, 65])
def test_scalar_copy_preserves_direction_flag_and_nonvolatile_registers(
    df, destination
):
    fixture = helper.case_fixture(31, 64, destination, 15, 0xFFFFFFFF, df)
    result = helper.model_case(31, 64, destination, 15, 0xFFFFFFFF, df)
    assert result["df"] == df
    for reg in ("ebx", "esi", "edi", "ebp"):
        assert result["registers"][reg] == fixture["registers"][reg]
    assert result["registers"]["esp"] == fixture["stack"] + 4


@pytest.mark.parametrize(
    "destination,source,length",
    [
        (0x1000, 0x2000, 32),
        (0xFFFFFFE1, 0x1000, 31),
        (0x1000, 0xFFFFFFE1, 31),
        (0x1000, 0x2000, True),
    ],
)
def test_larger_or_wrapping_inputs_remain_outside_proof(destination, source, length):
    with pytest.raises(helper.SmallCopyError):
        helper.copy_spec(destination, source, length)


def test_word_read_order_differs_for_destructive_overlap():
    result = helper.model_case(7, 64, 65)
    reads = [
        (e["address"] - helper.PAYLOAD - 64, e["width"])
        for e in result["events"]
        if e["kind"] == "read" and helper.PAYLOAD <= e["address"] < helper.PAYLOAD + 256
    ]
    assert reads == [(3, 4), (2, 1), (1, 1), (0, 1)]


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "resize_semantics": "native_vector_resize_semantics",
        "semantics": "native_small_copy_semantics",
        "conformance": "native_small_copy_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_receipts_keep_small_execution_distinct_from_full_body(receipts):
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
    assert data["conformance"]["summary"]["cases"] == 28672


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 99
    with pytest.raises((helper.SmallCopyError, replay.ConformanceError)):
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
        str(ROOT / "scripts" / ("itb_native_small_copy_" + kind + ".py")),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "semantics" else ["semantics"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
