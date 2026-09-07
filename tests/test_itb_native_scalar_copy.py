"""Feature-zero REP copy, alignment fallbacks and distinct exit flags."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_scalar_copy_semantics as helper
from src.observatory import native_scalar_copy_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "length", [32, 33, 34, 35, 63, 64, 65, 127, 128, 129, 511, 512, 513, 2047, 2048]
)
def test_snapshot_copy_across_alignment_and_overlap(length):
    for delta in (-17, -1, 0, 1, 17):
        source, destination = 2048, 2048 + delta
        fixture = helper.case_fixture(length, source, destination)
        expected = bytearray(fixture["payload"])
        expected[destination : destination + length] = fixture["payload"][
            source : source + length
        ]
        result = helper.model_case(length, source, destination)
        assert result["payload_after_sha256"] == hashlib.sha256(expected).hexdigest()
        assert (
            result["registers"]["eax"] == helper.PAYLOAD + destination
            and result["registers"]["ecx"] == 0
        )
        assert result["df"] == 0


@pytest.mark.parametrize("length", [32, 33, 34])
@pytest.mark.parametrize("backward", [False, True])
def test_alignment_can_rejoin_short_scalar_path(length, backward):
    destination = 2049 if backward else 2048 - (length - 31)
    relation = helper.copy_spec(
        helper.PAYLOAD + destination, helper.PAYLOAD + 2048, length
    )
    assert relation["remaining"] == 31
    result = helper.model_case(length, 2048, destination)
    table_addresses = {
        helper.BASE + table + 4 * i for table in helper.TABLES for i in range(4)
    }
    assert not any(
        e["kind"] == "read" and e["address"] in table_addresses
        for e in result["events"]
    )


def test_backward_rep_flags_come_from_pointer_subtraction():
    destination = helper.PAYLOAD + 2049
    result = helper.model_case(64, 2048, 2049)
    left = destination + 63
    value = left - 4
    flags = result["arithmetic_flags"]
    assert flags == dict(
        cf=0,
        pf=int((value & 255).bit_count() % 2 == 0),
        af=int((left & 15) < 4),
        zf=0,
        sf=0,
        of=0,
    )


def test_forward_rep_flags_retain_nonzero_remainder():
    result = helper.model_case(65, 2048, 1024)
    assert result["arithmetic_flags"] == dict(cf=0, pf=0, af=None, zf=0, sf=0, of=0)


@pytest.mark.parametrize("length", [31, 2049, True, -1])
def test_unproven_length_domain_rejected(length):
    with pytest.raises(helper.ScalarCopyError):
        helper.copy_spec(0x1000, 0x2000, length)


def test_direction_flag_premise_is_required():
    with pytest.raises(helper.ScalarCopyError):
        helper.model_case(64, df=1)
    with pytest.raises(replay.ConformanceError):
        replay.oracle(
            dict(
                length=64,
                source_offset=2048,
                destination_offset=2049,
                alignment=0,
                df=1,
            )
        )


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "small_copy_semantics": "native_small_copy_semantics",
        "semantics": "native_scalar_copy_semantics",
        "conformance": "native_scalar_copy_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_receipts_and_encoding(receipts):
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
    assert data["conformance"]["summary"]["cases"] == 1620


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 99
    with pytest.raises((helper.ScalarCopyError, replay.ConformanceError)):
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
        str(ROOT / "scripts" / ("itb_native_scalar_copy_" + kind + ".py")),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "semantics" else ["semantics"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
