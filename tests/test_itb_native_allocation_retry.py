"""Finite retry protocol, stack effects and exact wrapper replay checks."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_allocation_retry_semantics as helper
from src.observatory import native_allocation_retry_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def responses(*rows):
    return [dict(kind=k, eax=v) for k, v in rows]


@pytest.mark.parametrize("requested", [0, 8, 4131, 0xFFFFFFFB, 0xFFFFFFFF])
def test_full_protocol_and_failure_selection(requested):
    failure = "minus_one_failure" if requested == 0xFFFFFFFF else "failure"
    rows = responses(
        ("candidate", 0), ("handler", 0), (failure, 123), ("candidate", 0x80000000)
    )
    result = helper.retry_spec(requested, rows)
    assert result["outcome"] == "returned" and result["result"] == 0x80000000
    expected = replay.protocol_oracle(requested, rows)
    assert expected["returned"] and expected["result"] == result["result"]
    fixture = helper.case_fixture(requested, 15)
    modeled = helper.model_case(requested, rows, frame_alignment=15)
    assert modeled["registers"]["esp"] == fixture["stack"] + 4
    assert modeled["registers"]["ecx"] == requested
    assert modeled["arithmetic_flags"]["af"] is None


@pytest.mark.parametrize(
    "rows,kind",
    [
        ([], "candidate"),
        (responses(("candidate", 0)), "handler"),
        (responses(("candidate", 0), ("handler", 0)), "failure"),
        (responses(("candidate", 0), ("handler", 1)), "candidate"),
        (responses(("candidate", 0), ("handler", 0), ("failure", 77)), "candidate"),
    ],
)
def test_incomplete_transcript_requires_explicit_frontier(rows, kind):
    with pytest.raises(helper.AllocationRetryError):
        helper.retry_spec(8, rows)
    result = helper.retry_spec(8, rows, True)
    assert result["outcome"] == "frontier" and result["frontier_kind"] == kind
    assert not helper.model_case(8, rows, True)["returned"]


def test_failure_call_has_distinct_continuation_slot():
    rows = responses(("candidate", 0), ("handler", 0), ("failure", 77))
    fixture = helper.case_fixture(8)
    result = helper.model_case(8, rows, True)
    writes = [
        (e["address"], e["value"]) for e in result["events"] if e["kind"] == "write"
    ]
    s = fixture["stack"]
    assert (s - 12, helper.BASE + 0x357507) in writes
    assert (s - 12, helper.BASE + 0x3574E8) in writes
    assert (s - 8, helper.BASE + 0x3574FF) in writes
    assert writes[-1] == (s - 8, 8)


@pytest.mark.parametrize(
    "rows",
    [
        responses(("handler", 1)),
        responses(("candidate", 1), ("candidate", 1)),
        responses(("candidate", 0), ("handler", 0), ("minus_one_failure", 0)),
        [{"kind": "candidate", "eax": True}],
        [{"kind": "candidate", "eax": -1}],
        [{"kind": "candidate", "eax": 1, "extra": 0}],
    ],
)
def test_invalid_or_unused_responses_rejected(rows):
    with pytest.raises(helper.AllocationRetryError):
        helper.retry_spec(8, rows, True)
    with pytest.raises(replay.ConformanceError):
        replay.protocol_oracle(8, rows)


@pytest.mark.parametrize(
    "count,byte_request,modulo",
    [(1, 8, 0), (511, 4088, 0), (512, 4131, 3), (0x1FFFFFFB, 0xFFFFFFFB, 3)],
)
def test_upstream_request_corollary_is_conditional(count, byte_request, modulo):
    r = helper.upstream_request_spec(count)
    assert r["request"] == byte_request and r["request_modulo_eight"] == modulo
    assert r["minus_one_failure_excluded_under_stable_request"]


@pytest.mark.parametrize("count", [0, 0x1FFFFFFC, 0x20000000])
def test_nonrequest_paths_have_no_request_corollary(count):
    with pytest.raises(helper.AllocationRetryError):
        helper.upstream_request_spec(count)


def test_all_independent_finite_vectors_agree_with_graph():
    for v in replay.vectors()[::16]:
        expected = replay.protocol_oracle(v["request"], v["responses"])
        result = helper.model_case(v["request"], v["responses"], True, 15)
        assert result["returned"] == expected["returned"]
        assert result["protocol"]["result"] == expected["result"]
        assert result["protocol"]["frontier_kind"] == expected["next_kind"]


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "allocation_semantics": "native_lua_vector_allocation_semantics",
        "semantics": "native_allocation_retry_semantics",
        "conformance": "native_allocation_retry_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_receipts_distinguish_wrapper_and_callee_execution(receipts):
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
    assert data["conformance"]["summary"]["native_call_instructions"] == 1600
    assert data["conformance"]["summary"]["callee_instruction_executions"] == 0


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["summary"]["cases"] += 1
    with pytest.raises((helper.AllocationRetryError, replay.ConformanceError)):
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
        str(ROOT / ("scripts/itb_native_allocation_retry_" + kind + ".py")),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "semantics" else ["semantics"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
