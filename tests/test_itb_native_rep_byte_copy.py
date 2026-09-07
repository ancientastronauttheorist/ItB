"""Forward REP byte dispatch and the narrow BT flag contract."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_rep_byte_copy_semantics as helper
from src.observatory import native_rep_byte_copy_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize("length", [128, 129, 255, 512, 1023, 2047, 2048])
def test_snapshot_and_ascending_byte_transfers(length):
    for destination in (2031, 2047, 2048, 4100):
        fixture = helper.case_fixture(length, 2048, destination)
        expected = bytearray(fixture["payload"])
        expected[destination : destination + length] = fixture["payload"][
            2048 : 2048 + length
        ]
        result = helper.model_case(length, 2048, destination)
        assert result["payload_after_sha256"] == hashlib.sha256(expected).hexdigest()
        reads = [
            e
            for e in result["events"]
            if e["kind"] == "read"
            and helper.PAYLOAD <= e["address"] < helper.PAYLOAD + 8192
        ]
        assert [(e["address"] - helper.PAYLOAD, e["width"]) for e in reads] == [
            (2048 + i, 1) for i in range(length)
        ]
        assert result["registers"]["edx"] == length and result["registers"]["ecx"] == 0


@pytest.mark.parametrize("word", [2, 3, 0x80000002, 0xFFFFFFFF])
@pytest.mark.parametrize("length", [128, 129])
def test_only_cf_and_zf_are_claimed_after_bt(word, length):
    result = helper.model_case(length, feature_word=word)
    assert result["arithmetic_flags"] == dict(
        cf=1, zf=int(length == 128), pf=None, af=None, sf=None, of=None
    )


@pytest.mark.parametrize("word", [0, 1, 4, True, -1, 0x100000000])
def test_missing_feature_or_invalid_word_is_not_in_domain(word):
    with pytest.raises(helper.RepByteCopyError):
        helper.copy_spec(0x1000, 0x2000, 128, word)


def test_destructive_forward_overlap_and_df_set_are_excluded():
    with pytest.raises(helper.RepByteCopyError):
        helper.copy_spec(0x2001, 0x2000, 128)
    with pytest.raises(helper.RepByteCopyError):
        helper.model_case(128, df=1)


@pytest.mark.parametrize("length", [127, 2049])
def test_unproved_lengths_rejected(length):
    with pytest.raises(helper.RepByteCopyError):
        helper.copy_spec(0x1000, 0x2000, length)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "scalar_copy_semantics": "native_scalar_copy_semantics",
        "semantics": "native_rep_byte_copy_semantics",
        "conformance": "native_rep_byte_copy_conformance",
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
    assert data["conformance"]["summary"]["cases"] == 1344


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 99
    with pytest.raises((helper.RepByteCopyError, replay.ConformanceError)):
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
        str(ROOT / "scripts" / ("itb_native_rep_byte_copy_" + kind + ".py")),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "semantics" else ["semantics"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
