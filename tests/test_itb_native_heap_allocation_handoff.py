"""Named import handoff, size partition and protected-memory tests."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_heap_allocation_handoff as helper
from src.observatory import native_heap_allocation_handoff_conformance as replay
from src.observatory import native_lua_vector_allocation_semantics as allocation

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize("size", [0, 1, 8, 4131, 0xFFFFFFDB, 0xFFFFFFE0])
def test_accepted_argument_order_and_normalization(size):
    result = helper.handoff_spec(size, 0x12345678)
    expected = replay.oracle(size, 0x12345678)
    assert result["outcome"] == expected["outcome"] == "heap_call"
    assert result["arguments"] == expected["arguments"] == [0x12345678, 0, max(size, 1)]
    fixture = helper.case_fixture(size, 0x12345678, 15)
    modeled = helper.model_case(size, 0x12345678, 15)
    assert modeled["registers"]["esp"] == fixture["stack"] - 20
    assert modeled["registers"]["esi"] == max(size, 1)
    assert not any(
        e["kind"] == "read" and e["address"] == helper.IAT_SLOT
        for e in modeled["events"]
    )


@pytest.mark.parametrize("size", range(0xFFFFFFE1, 0x100000000))
def test_every_rejected_size_stops_before_error_call(size):
    result = helper.handoff_spec(size, 0)
    assert result["outcome"] == "error_frontier" and result["arguments"] == []
    expected = replay.oracle(size, 0)
    assert result["stop_rva"] == expected["stop"] == 0x389469


@pytest.mark.parametrize("count", range(0x1FFFFFF8, 0x1FFFFFFC))
def test_downstream_guard_is_narrower_than_padding_guard(count):
    requested = allocation.allocation_spec(count)["requested"]
    assert requested is not None
    assert helper.handoff_spec(requested, 0)["outcome"] == "error_frontier"


def test_largest_upstream_count_reaching_heap_boundary():
    requested = allocation.allocation_spec(0x1FFFFFF7)["requested"]
    assert requested == 0xFFFFFFDB
    assert helper.handoff_spec(requested, 0)["outcome"] == "heap_call"


@pytest.mark.parametrize(
    "size,undefined_af", [(0, False), (1, True), (0xFFFFFFE1, False)]
)
def test_flag_definedness_at_each_boundary(size, undefined_af):
    result = helper.model_case(size, 0)
    assert (result["arithmetic_flags"]["af"] is None) == undefined_af


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("bad", [True, -1, 0x100000000, None])
def test_invalid_words_rejected(index, bad):
    args = [0, 0]
    args[index] = bad
    with pytest.raises(helper.HeapHandoffError):
        helper.handoff_spec(*args)
    with pytest.raises(replay.ConformanceError):
        replay.oracle(*args)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "retry_semantics": "native_allocation_retry_semantics",
        "semantics": "native_heap_allocation_handoff",
        "conformance": "native_heap_allocation_handoff_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_published_receipts_keep_static_import_and_execution_separate(receipts):
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
    assert data["semantics"]["summary"]["cases"] == 1440
    assert data["conformance"]["summary"]["cases"] == 1776
    assert data["conformance"]["summary"]["iat_dereferences"] == 0
    assert data["conformance"]["summary"]["executed_calls"] == 0


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["summary"]["cases"] += 1
    with pytest.raises((helper.HeapHandoffError, replay.ConformanceError)):
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
    script = (
        "itb_native_heap_allocation_handoff"
        + ("_conformance" if kind == "conformance" else "")
        + ".py"
    )
    args = [
        sys.executable,
        str(ROOT / "scripts" / script),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "semantics" else ["semantics"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
