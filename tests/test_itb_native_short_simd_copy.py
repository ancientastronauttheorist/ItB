"""Independent boundary checks for short forward and backward MOVDQU slices."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.observatory import native_short_simd_copy_semantics as forward
from src.observatory import native_short_simd_copy_conformance as forward_replay
from src.observatory import native_backward_simd_copy_semantics as backward
from src.observatory import native_backward_simd_copy_conformance as backward_replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
RAW_HASHES = {
    (
        "short",
        "semantics",
    ): "ec5b10bc557e3464c34393976b8215379f4c004ebd0b31d26a97999c052805a5",
    (
        "short",
        "conformance",
    ): "897e2824ca52788bd9814a8b6cee9319e2d9b67b222dd5374a30a5bb26d9bada",
    (
        "backward",
        "semantics",
    ): "1ffcfaf5eb034436c43983f9992b4af4502395d531eb8a2b00a38266e9c0d775",
    (
        "backward",
        "conformance",
    ): "70c89bf0685be4cc62ca4f21d0cbf433b0b982de5235b13bbc35ae46c2842bd8",
}


@pytest.fixture(params=["short", "backward"])
def domain(request):
    name = request.param
    helper, replay, error = (
        (forward, forward_replay, forward.ShortSimdCopyError)
        if name == "short"
        else (backward, backward_replay, backward.BackwardSimdCopyError)
    )
    return name, helper, replay, error


@pytest.mark.parametrize("length", [32, 33, 35, 36, 47, 48, 63, 64, 65, 95, 96, 127])
def test_snapshot_xmm_and_scalar_boundaries(domain, length):
    name, helper, _, _ = domain
    for alignment in (0, 1, 7, 15):
        source = 256 + alignment
        destination = source + (1 if name == "backward" else -3)
        fixture = helper.case_fixture(length, source, destination)
        result = helper.model_case(length, source, destination)
        snapshot = fixture["payload"][source : source + length]
        expected_payload = bytearray(fixture["payload"])
        expected_payload[destination : destination + length] = snapshot
        assert (
            result["payload_after_sha256"]
            == hashlib.sha256(expected_payload).hexdigest()
        )
        expected_xmm = dict(fixture["xmm"])
        if name == "short":
            last = 32 * (length // 32 - 1)
            remaining = length
        else:
            remaining = length - ((destination + length) % 16)
            last = remaining % 32 if remaining >= 32 else None
        if last is not None:
            expected_xmm["xmm0"] = int.from_bytes(snapshot[last : last + 16], "little")
            expected_xmm["xmm1"] = int.from_bytes(
                snapshot[last + 16 : last + 32], "little"
            )
        assert result["xmm"] == expected_xmm
        expected_edx = length if name == "backward" else 0
        if name == "short" and length % 32 >= 4:
            at = length - length % 4 - 4
            expected_edx = int.from_bytes(snapshot[at : at + 4], "little")
        assert result["registers"] == dict(
            fixture["registers"],
            eax=helper.PAYLOAD + destination,
            ecx=0,
            edx=expected_edx,
            esp=fixture["stack"] + 4,
        )
        assert result["arithmetic_flags"] == dict(
            cf=0,
            pf=1,
            af=None if remaining % 4 == 0 else 0,
            zf=1,
            sf=0,
            of=0,
        )
        assert result["df"] == 0
        vector_events = [event for event in result["events"] if event["width"] == 16]
        assert [event["kind"] for event in vector_events] == [
            "read",
            "read",
            "write",
            "write",
        ] * (remaining // 32)
        for event in vector_events:
            start = helper.PAYLOAD + (
                source if event["kind"] == "read" else destination
            )
            assert start <= event["address"] <= start + length - 16


@pytest.mark.parametrize("word", [2, 3, 0x80000002, 0xFFFFFFFF])
def test_only_selected_feature_word_read(domain, word):
    name, helper, _, _ = domain
    destination = 257 if name == "backward" else 128
    result = helper.model_case(64, 256, destination, feature_word=word)
    feature = [event for event in result["events"] if event["address"] == 0x893F30]
    assert feature == [dict(kind="read", address=0x893F30, width=4, value=word)]
    assert not any(event["address"] == 0x8B6E48 for event in result["events"])


@pytest.mark.parametrize("word", [0, 1, 4, True, -1, 0x100000000])
def test_feature_premise_rejects_invalid_or_clear_bit(domain, word):
    name, helper, _, error = domain
    destination = 0x2001 if name == "backward" else 0x1000
    with pytest.raises(error):
        helper.copy_spec(destination, 0x2000, 64, word)


@pytest.mark.parametrize("length", [31, 128, True, -1, 0x100000000])
def test_unproved_lengths_rejected(domain, length):
    name, helper, _, error = domain
    with pytest.raises(error):
        helper.copy_spec(0x2001 if name == "backward" else 0x1000, 0x2000, length)


def test_direction_wrap_and_df_boundaries(domain):
    name, helper, _, error = domain
    with pytest.raises(error):
        helper.copy_spec(0x1000 if name == "backward" else 0x2001, 0x2000, 64)
    with pytest.raises(error):
        helper.copy_spec(0xFFFFFFFF, 0xFFFFFFE0, 64)
    with pytest.raises(error):
        helper.model_case(64, df=1)
    with pytest.raises(error):
        helper.model_case(64, frame_alignment=True)


def test_replay_oracle_is_a_snapshot(domain):
    name, _, replay, _ = domain
    payload = bytes((i * 73 + i // 5) & 255 for i in range(1024))
    vector = dict(
        length=97,
        source_offset=256,
        destination_offset=257 if name == "backward" else 253,
        alignment=7,
        df=0,
        feature_word=2,
    )
    result = replay.oracle(vector, payload)
    expected = bytearray(payload)
    at = vector["destination_offset"]
    expected[at : at + 97] = payload[256:353]
    assert result["payload"] == expected
    assert result["source_snapshot"] == payload[256:353]


def load_receipts(name, helper):
    paths = {
        key: PROGRAMS / (PREFIX + suffix + ".json")
        for key, suffix in {
            "program_facts": "program_facts",
            "scalar_copy_semantics": "native_scalar_copy_semantics",
            "semantics": f"native_{name}_simd_copy_semantics",
            "conformance": f"native_{name}_simd_copy_conformance",
        }.items()
    }
    data = {key: json.loads(path.read_bytes()) for key, path in paths.items()}
    return paths, data, {key: data[key] for key in helper.SOURCE_PINS}


def test_sealed_receipts_and_exact_encoding(domain):
    name, helper, replay, _ = domain
    paths, data, sources = load_receipts(name, helper)
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
        assert hashlib.sha256(raw).hexdigest() == RAW_HASHES[name, kind]
    assert (
        data["conformance"]["executed_rvas"]
        == data["semantics"]["model_evidence"]["instruction_union_rvas"]
    )


@pytest.mark.parametrize("kind", ["semantics", "conformance", "source"])
def test_mutated_receipts_rejected(domain, kind):
    name, helper, replay, error = domain
    _, data, sources = load_receipts(name, helper)
    changed = copy.deepcopy(data["scalar_copy_semantics" if kind == "source" else kind])
    changed["schema_version"] = 99
    with pytest.raises((error, replay.ConformanceError)):
        if kind == "source":
            helper.validate_structure(
                data["semantics"], dict(sources, scalar_copy_semantics=changed)
            )
        elif kind == "semantics":
            helper.validate_structure(changed, sources)
        else:
            replay.validate_structure(changed, data["semantics"])


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_exact_cli_rebuild(domain, kind):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    name, helper, _, _ = domain
    paths, _, sources = load_receipts(name, helper)
    args = [
        sys.executable,
        str(ROOT / "scripts" / f"itb_native_{name}_simd_copy_{kind}.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources if kind == "semantics" else ["semantics"]:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
