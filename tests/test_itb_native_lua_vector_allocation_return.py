"""Independent alignment geometry, metadata and post-call return checks."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_lua_vector_allocation_return_semantics as helper
from src.observatory import native_lua_vector_allocation_return_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "pointer,aligned,metadata",
    [
        (0, 32, 28),
        (28, 32, 28),
        (29, 64, 60),
        (31, 64, 60),
        (0xFFFFFFDC, 0xFFFFFFE0, 0xFFFFFFDC),
        (0xFFFFFFDD, 0, 0xFFFFFFFC),
        (0xFFFFFFE0, 0, 0xFFFFFFFC),
        (0xFFFFFFFC, 0, 0xFFFFFFFC),
        (0xFFFFFFFF, 32, 28),
    ],
)
def test_explicit_wrapped_pointer_relation(pointer, aligned, metadata):
    result = helper.pointer_spec(pointer)
    expected = replay.pointer_oracle(pointer)
    assert result["aligned_pointer"] == expected["aligned"] == aligned
    assert result["metadata_address"] == expected["metadata"] == metadata


@pytest.mark.parametrize("offset", range(32))
def test_existing_nonwrapping_block_has_room_for_metadata_and_payload(offset):
    p = 0x50001000 + offset
    for size in [1, 8, 4096]:
        result = helper.storage_layout_spec(p, size)
        q = result["aligned_pointer"]
        assert q % 32 == 0 and 4 <= q - p <= 35
        assert p <= q - 4 and q + size <= p + size + 35
        assert helper.pointer_spec(p)["aligned_pointer"] == q


@pytest.mark.parametrize(
    "pointer,size", [(0, 0), (0xFFFFFFE0, 1), (0x50001000, 0xFFFFFFFF)]
)
def test_storage_relation_rejects_missing_or_wrapping_capacity(pointer, size):
    with pytest.raises(helper.AllocationReturnError):
        helper.storage_layout_spec(pointer, size)


@pytest.mark.parametrize("path", ["small", "large"])
def test_postcall_preservation_and_order(path):
    fixture = helper.case_fixture(path, 0x5000101D, 15, 0xFFFFFFFF)
    result = helper.model_case(path, 0x5000101D, 15, 0xFFFFFFFF)
    for reg in ["ebx", "edx", "esi", "edi"]:
        assert result["registers"][reg] == fixture["registers"][reg]
    assert result["registers"]["esp"] == fixture["frame"] + 12
    assert result["registers"]["ebp"] == fixture["saved_ebp"]
    assert result["return_address"] == fixture["return_address"]
    assert [e["kind"] for e in result["events"]] == (
        ["write", "read", "read"] if path == "large" else ["read", "read"]
    )
    assert (result["arithmetic_flags"]["af"] is None) == (path == "large")


def test_metadata_alias_with_saved_frame_is_rejected():
    # P just below F makes the preceding metadata word overlap protected stack.
    with pytest.raises(helper.AllocationReturnError):
        helper.model_case("large", 0x30000FFC)


@pytest.mark.parametrize("bad", [True, -1, 0x100000000, None])
def test_invalid_pointer_rejected(bad):
    with pytest.raises(helper.AllocationReturnError):
        helper.pointer_spec(bad)
    with pytest.raises(replay.ConformanceError):
        replay.pointer_oracle(bad)


@pytest.fixture(scope="module")
def receipts():
    suffixes = {
        "program_facts": "program_facts",
        "allocation_semantics": "native_lua_vector_allocation_semantics",
        "semantics": "native_lua_vector_allocation_return_semantics",
        "conformance": "native_lua_vector_allocation_return_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_receipts(receipts):
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
    assert data["semantics"]["summary"]["cases"] == 16384
    assert data["conformance"]["summary"]["cases"] == 792


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_summary_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["summary"]["cases"] += 1
    with pytest.raises((helper.AllocationReturnError, replay.ConformanceError)):
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
        str(ROOT / ("scripts/itb_native_lua_vector_allocation_return_" + kind + ".py")),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "semantics" else ["semantics"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
