"""Finite heap protocol, real flag getter and protected error-cell checks."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_heap_allocation_protocol as helper
from src.observatory import native_heap_allocation_protocol_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CELL = 0x6000100


def responses(*rows):
    return [dict(kind=k, eax=v) for k, v in rows]


@pytest.mark.parametrize(
    "size,flag,rows,value",
    [
        (0, 0, responses(("heap", 123)), 123),
        (8, 0, responses(("heap", 0), ("error", CELL)), 0),
        (
            8,
            1,
            responses(("heap", 0), ("handler", 1), ("heap", 0x80000000)),
            0x80000000,
        ),
        (8, 1, responses(("heap", 0), ("handler", 0), ("error", CELL)), 0),
        (0xFFFFFFE1, 1, responses(("error", CELL)), 0),
    ],
)
def test_finite_return_protocol(size, flag, rows, value):
    expected = replay.protocol_oracle(size, flag, rows)
    result = helper.heap_protocol_spec(size, flag, rows)
    assert expected["returned"] and result["outcome"] == "returned"
    assert result["result"] == expected["result"] == value
    fixture = helper.case_fixture(size, 0x12345678, flag, rows, 15)
    modeled = helper.model_case(size, 0x12345678, flag, rows, frame_alignment=15)
    assert modeled["registers"]["esp"] == fixture["stack"] + 4
    assert modeled["registers"]["esi"] == fixture["registers"]["esi"]
    assert modeled["registers"]["ebp"] == fixture["registers"]["ebp"]


@pytest.mark.parametrize(
    "flag,next_kind", [(0, "error"), (1, "handler"), (0xFFFFFFFF, "handler")]
)
def test_failed_heap_executes_flag_getter_before_next_frontier(flag, next_kind):
    rows = responses(("heap", 0))
    result = helper.model_case(8, 0, flag, rows, True)
    assert result["protocol"]["frontier_kind"] == next_kind
    assert result["registers"]["eax"] == flag
    assert (
        sum(
            e["kind"] == "read" and e["address"] == helper.RETRY_WORD
            for e in result["events"]
        )
        == 1
    )
    assert (
        sum(
            e["kind"] == "read" and e["address"] == helper.IAT_SLOT
            for e in result["events"]
        )
        == 1
    )


def test_error_response_writes_twelve_and_returns_zero():
    rows = responses(("error", CELL))
    result = helper.model_case(0xFFFFFFFF, 0, 0, rows)
    memory = {m["address"]: m["value"] for m in result["memory"]}
    assert memory[CELL] == 12
    assert result["registers"]["eax"] == 0 and result["arithmetic_flags"]["af"] is None


@pytest.mark.parametrize("pointer", [0x30001000, 0x30001001, 0xFFFFFFFF])
def test_error_cell_must_not_alias_frame_or_wrap(pointer):
    with pytest.raises(helper.HeapProtocolError):
        helper.model_case(0xFFFFFFFF, 0, 0, responses(("error", pointer)))


@pytest.mark.parametrize(
    "rows", [[], responses(("heap", 0)), responses(("heap", 0), ("handler", 1))]
)
def test_incomplete_transcript_needs_frontier_permission(rows):
    with pytest.raises(helper.HeapProtocolError):
        helper.heap_protocol_spec(8, 1, rows)
    assert helper.heap_protocol_spec(8, 1, rows, True)["outcome"] == "frontier"


@pytest.mark.parametrize(
    "rows",
    [
        responses(("error", CELL)),
        responses(("heap", 1), ("heap", 1)),
        responses(("heap", 0), ("heap", 1)),
        [{"kind": "heap", "eax": True}],
        [{"kind": "heap", "eax": 0x100000000}],
    ],
)
def test_invalid_or_unused_responses_rejected(rows):
    with pytest.raises(helper.HeapProtocolError):
        helper.heap_protocol_spec(8, 1, rows, True)
    with pytest.raises(replay.ConformanceError):
        replay.protocol_oracle(8, 1, rows)


def test_independent_sampled_protocols_match_graph():
    for vector in replay.vectors()[::32]:
        expected = replay.protocol_oracle(
            vector["size"], vector["flag"], vector["responses"]
        )
        actual = helper.model_case(
            vector["size"],
            vector["heap"],
            vector["flag"],
            vector["responses"],
            True,
            15,
        )
        assert actual["returned"] == expected["returned"]
        assert actual["protocol"]["result"] == expected["result"]
        assert actual["protocol"]["frontier_kind"] == expected["next_kind"]


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "handoff": "native_heap_allocation_handoff",
        "semantics": "native_heap_allocation_protocol",
        "conformance": "native_heap_allocation_protocol_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_published_receipts(receipts):
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
    assert data["semantics"]["summary"]["cases"] == 1792
    assert data["conformance"]["summary"]["cases"] == 1280
    assert data["conformance"]["summary"]["opaque_callee_instructions"] == 0


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["summary"]["cases"] += 1
    with pytest.raises((helper.HeapProtocolError, replay.ConformanceError)):
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
        "itb_native_heap_allocation_protocol"
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
