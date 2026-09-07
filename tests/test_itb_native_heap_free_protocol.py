"""Null return, explicit API responses, error storage and call-frame checks."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_heap_free_protocol as helper
from src.observatory import native_heap_free_protocol_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CELL = 0x10000101


def responses(*items):
    return [{"kind": k, "eax": v} for k, v in items]


@pytest.mark.parametrize("seed", [0, 1, 0xFFFFFFFF])
def test_null_pointer_returns_entry_eax_without_api_calls(seed):
    fixture = helper.case_fixture(0, 0, [], seed=seed)
    result = helper.model_case(0, 0, [], seed=seed)
    assert result["returned"] and result["calls"] == []
    assert result["registers"]["eax"] == fixture["registers"]["eax"]
    assert result["registers"]["esp"] == fixture["stack"] + 4
    assert result["arithmetic_flags"]["af"] == 0


@pytest.mark.parametrize("value", [1, 2, 0x80000000, 0xFFFFFFFF])
def test_nonzero_heap_response_returns_unchanged(value):
    seq = responses(("heap_free", value))
    result = helper.model_case(0x5000, 0x1234, seq)
    assert result["protocol"]["outcome"] == "heap_success_return"
    assert result["registers"]["eax"] == value
    assert result["calls"][0]["callee_argument_cleanup"] == 12
    assert result["arithmetic_flags"]["af"] is None
    assert replay.protocol_oracle(0x5000, seq)["result"] == value


@pytest.mark.parametrize("last", [0, 5, 0xFFFFFFFF])
@pytest.mark.parametrize("mapped", [0, 12, 0xFFFFFFFF])
def test_error_path_maps_last_error_and_stores_result(last, mapped):
    seq = responses(
        ("heap_free", 0),
        ("error", CELL),
        ("get_last_error", last),
        ("map_error", mapped),
    )
    fixture = helper.case_fixture(0x5000, 0x1234, seq)
    result = helper.model_case(0x5000, 0x1234, seq)
    assert result["protocol"]["outcome"] == "mapped_error_return"
    assert result["registers"]["eax"] == mapped and result["registers"]["ecx"] == last
    assert {e["address"]: e["value"] for e in result["memory"]}[CELL] == mapped
    assert result["registers"]["esi"] == fixture["registers"]["esi"]
    assert [c["callee_entry_esp"] for c in result["calls"]] == [
        fixture["stack"] - 20,
        fixture["stack"] - 12,
        fixture["stack"] - 12,
        fixture["stack"] - 16,
    ]
    assert (
        result["arithmetic_flags"]
        == helper.summary_outputs(seq[-1], 3, 1)["arithmetic_flags"]
    )


@pytest.mark.parametrize(
    "count,frontier",
    [(0, "heap_free"), (1, "error"), (2, "get_last_error"), (3, "map_error")],
)
def test_finite_prefix_stops_before_next_call(count, frontier):
    seq = responses(("heap_free", 0), ("error", CELL), ("get_last_error", 5))[:count]
    result = helper.model_case(0x5000, 0x1234, seq, allow_frontier=True)
    assert result["protocol"]["frontier_kind"] == frontier
    assert not result["returned"] and len(result["calls"]) == count
    with pytest.raises(helper.HeapFreeError):
        helper.free_protocol_spec(0x5000, seq)


@pytest.mark.parametrize(
    "pointer,seq",
    [
        (0, responses(("heap_free", 1))),
        (1, responses(("error", CELL))),
        (1, responses(("heap_free", 1), ("error", CELL))),
    ],
)
def test_unused_or_mismatched_responses_rejected(pointer, seq):
    with pytest.raises(helper.HeapFreeError):
        helper.free_protocol_spec(pointer, seq, True)
    with pytest.raises(replay.ConformanceError):
        replay.protocol_oracle(pointer, seq)


@pytest.mark.parametrize(
    "cell",
    [
        0x30001000,
        0x30000FFF,
        helper.FREE_IAT - 1,
        helper.LAST_IAT,
        helper.HEAP_WORD,
        0xFFFFFFFF,
        helper.BASE + helper.START,
    ],
)
def test_error_cell_cannot_corrupt_frame_imports_globals_or_code(cell):
    seq = responses(
        ("heap_free", 0), ("error", cell), ("get_last_error", 5), ("map_error", 12)
    )
    with pytest.raises(helper.HeapFreeError):
        helper.model_case(0x5000, 0x1234, seq)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "deallocation_semantics": "native_vector_deallocation_semantics",
        "semantics": "native_heap_free_protocol",
        "conformance": "native_heap_free_protocol_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_published_receipts_and_encoding(receipts):
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
    assert data["semantics"]["summary"]["modeled_nodes"] == 24
    assert data["conformance"]["summary"]["cases"] == 1472


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 99
    with pytest.raises((helper.HeapFreeError, replay.ConformanceError)):
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
        "itb_native_heap_free_protocol"
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
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
