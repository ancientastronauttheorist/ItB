"""Snapshot and all-XMM boundary checks for the larger backward SIMD slice."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from src.observatory import native_large_backward_simd_copy_semantics as helper
from src.observatory import native_large_backward_simd_copy_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
RAW_HASHES = {
    "semantics": "d3c8b5ac44f59ff52cc9d1b71db36c2f72b74ae9a2d6b0ec0413ab37538da473",
    "conformance": "51dd42926ed664503e87c0812d0ed3bca7e655ebb489fd1fd59c57fe706772d4",
}


@pytest.mark.parametrize(
    "length",
    [
        128,
        129,
        142,
        143,
        144,
        145,
        159,
        160,
        255,
        256,
        257,
        511,
        512,
        513,
        1023,
        1024,
        2047,
        2048,
    ],
)
def test_original_snapshot_and_all_xmm_last_updates(length):
    for alignment in (0, 1, 7, 15):
        source = 2052 + alignment
        destination = source + 1
        fixture = helper.case_fixture(length, source, destination)
        result = helper.model_case(length, source, destination)
        snapshot = fixture["payload"][source : source + length]
        expected = bytearray(fixture["payload"])
        expected[destination : destination + length] = snapshot
        assert result["payload_after_sha256"] == hashlib.sha256(expected).hexdigest()
        remaining = length - (destination + length) % 16
        wanted_xmm = dict(fixture["xmm"])
        if remaining >= 128:
            last128 = remaining % 128
            for i in range(8):
                at = last128 + 16 * i
                wanted_xmm[f"xmm{i}"] = int.from_bytes(snapshot[at : at + 16], "little")
        if remaining % 128 >= 32:
            last32 = remaining % 32
            wanted_xmm["xmm0"] = int.from_bytes(
                snapshot[last32 : last32 + 16], "little"
            )
            wanted_xmm["xmm1"] = int.from_bytes(
                snapshot[last32 + 16 : last32 + 32], "little"
            )
        assert result["xmm"] == wanted_xmm
        assert result["registers"] == dict(
            fixture["registers"],
            eax=helper.PAYLOAD + destination,
            ecx=0,
            edx=length,
            esp=fixture["stack"] + 4,
        )
        assert result["arithmetic_flags"] == dict(
            cf=0, pf=1, af=None if remaining % 4 == 0 else 0, zf=1, sf=0, of=0
        )
        assert result["df"] == 0
        vectors = [e for e in result["events"] if e["width"] == 16]
        assert [e["kind"] for e in vectors] == (["read"] * 8 + ["write"] * 8) * (
            remaining // 128
        ) + ["read", "read", "write", "write"] * ((remaining % 128) // 32)
        for event in vectors:
            start = helper.PAYLOAD + (
                source if event["kind"] == "read" else destination
            )
            assert start <= event["address"] <= start + length - 16


def test_alignment_can_skip_128_loop_and_preserve_upper_xmm():
    fixture = helper.case_fixture(128, 256, 257)
    result = helper.model_case(128, 256, 257)
    assert all(
        result["xmm"][f"xmm{i}"] == fixture["xmm"][f"xmm{i}"] for i in range(2, 8)
    )
    assert "0x0036e910" not in result["trace_rvas"]
    assert "0x0036e977" in result["trace_rvas"]


@pytest.mark.parametrize("word", [2, 3, 0x80000002, 0xFFFFFFFF])
def test_feature_bit_and_same_count_relation(word):
    result = helper.model_case(512, feature_word=word)
    assert [e for e in result["events"] if e["address"] == 0x893F30] == [
        dict(kind="read", address=0x893F30, width=4, value=word)
    ]
    assert result["registers"]["edx"] == 512


@pytest.mark.parametrize("word", [0, 1, 4, True, -1, 0x100000000])
def test_invalid_feature_words_rejected(word):
    with pytest.raises(helper.LargeBackwardSimdCopyError):
        helper.copy_spec(0x2001, 0x2000, 128, word)


@pytest.mark.parametrize("length", [127, 2049, True, -1, 0x100000000])
def test_lengths_outside_domain_rejected(length):
    with pytest.raises(helper.LargeBackwardSimdCopyError):
        helper.copy_spec(0x2001, 0x2000, length)


def test_direction_wrap_df_and_frame_rejected():
    for destination in (0x1000, 0x2000, 0x2080):
        with pytest.raises(helper.LargeBackwardSimdCopyError):
            helper.copy_spec(destination, 0x2000, 128)
    with pytest.raises(helper.LargeBackwardSimdCopyError):
        helper.copy_spec(0xFFFFFFF1, 0xFFFFFFF0, 128)
    with pytest.raises(helper.LargeBackwardSimdCopyError):
        helper.model_case(128, df=1)
    with pytest.raises(helper.LargeBackwardSimdCopyError):
        helper.model_case(128, frame_alignment=True)


def test_replay_snapshot_crosses_payload_page():
    payload = bytes((i * 17 + i // 7) & 255 for i in range(8192))
    vector = dict(
        length=2048,
        source_offset=0xF01,
        destination_offset=0xF12,
        alignment=15,
        df=0,
        feature_word=2,
    )
    result = replay.oracle(vector, payload)
    expected = bytearray(payload)
    expected[0xF12 : 0xF12 + 2048] = payload[0xF01 : 0xF01 + 2048]
    assert result["payload"] == expected
    assert result["source_snapshot"] == payload[0xF01 : 0xF01 + 2048]


@pytest.fixture(scope="module")
def receipts():
    paths = {
        key: PROGRAMS / (PREFIX + suffix + ".json")
        for key, suffix in {
            "program_facts": "program_facts",
            "backward_simd_copy_semantics": "native_backward_simd_copy_semantics",
            "semantics": "native_large_backward_simd_copy_semantics",
            "conformance": "native_large_backward_simd_copy_conformance",
        }.items()
    }
    data = {key: json.loads(path.read_bytes()) for key, path in paths.items()}
    return paths, data, {key: data[key] for key in helper.SOURCE_PINS}


def test_receipt_hashes_encoding_and_structure(receipts):
    paths, data, sources = receipts
    assert (
        helper.validate_structure(data["semantics"], sources)["status"]
        == "structurally_verified"
    )
    assert (
        replay.validate_structure(data["conformance"], data["semantics"])["status"]
        == "structurally_verified"
    )
    for kind, encode in (
        ("semantics", helper.encode_semantics),
        ("conformance", replay.encode_conformance),
    ):
        raw = paths[kind].read_bytes()
        assert raw == encode(data[kind]).encode() and b"\r\n" not in raw
        assert hashlib.sha256(raw).hexdigest() == RAW_HASHES[kind]
    assert (
        data["semantics"]["model_evidence"]["instruction_union_rvas"]
        == data["conformance"]["executed_rvas"]
    )


@pytest.mark.parametrize("kind", ["semantics", "conformance", "source"])
def test_mutated_receipts_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(
        data["backward_simd_copy_semantics" if kind == "source" else kind]
    )
    changed["schema_version"] = 99
    with pytest.raises((helper.LargeBackwardSimdCopyError, replay.ConformanceError)):
        if kind == "source":
            helper.validate_structure(
                data["semantics"], dict(sources, backward_simd_copy_semantics=changed)
            )
        elif kind == "semantics":
            helper.validate_structure(changed, sources)
        else:
            replay.validate_structure(changed, data["semantics"])


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_exact_cli_rebuild(receipts, kind):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts" / f"itb_native_large_backward_simd_copy_{kind}.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources if kind == "semantics" else ["semantics"]:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
