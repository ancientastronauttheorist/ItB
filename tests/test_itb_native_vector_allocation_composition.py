"""Fresh ancestor-frame joins and nested allocation contract tests."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_vector_allocation_composition as helper
from src.observatory import native_vector_allocation_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
P = 0x6000100


def candidate(*rows, frontier=False):
    return dict(
        kind="candidate",
        responses=[dict(kind=k, eax=v) for k, v in rows],
        allow_frontier=frontier,
    )


@pytest.mark.parametrize("entry", [48, 0x30001000, 0x3000100F, 0xFFFFFFF7])
def test_fresh_frame_equations(entry):
    result = helper.frame_join(entry)
    offsets = {
        "owner_frame": -4,
        "retry_entry": -12,
        "retry_frame": -16,
        "candidate_entry": -24,
        "heap_frame": -28,
        "heap_callee_entry": -48,
        "after_heap_stdcall12": -32,
        "after_candidate_cdecl": -20,
        "after_retry_cdecl": -8,
        "after_owner_ret4": 8,
    }
    for key, offset in offsets.items():
        assert result[key] == entry + offset
    assert result["heap_argument_slots"] == dict(
        heap=entry - 44, flags=entry - 40, size=entry - 36
    )


@pytest.mark.parametrize("entry", [True, 47, 0xFFFFFFF8, 0x100000000])
def test_invalid_or_wrapping_frame_rejected(entry):
    with pytest.raises(helper.VectorAllocationCompositionError):
        helper.frame_join(entry)


@pytest.mark.parametrize(
    "count,pointer,expected",
    [(1, P, P), (511, P + 1, P + 1), (512, P, P + 32), (513, P + 29, P + 64)],
)
def test_conditional_success_requires_valid_block(count, pointer, expected):
    result = helper.compositional_spec(count, pointer)
    assert result["outcome"] == "conditional_normal_return"
    assert result["result"] == result["ecx"] == expected
    if count >= 512:
        assert result["metadata_write"] == dict(address=expected - 4, value=pointer)
    else:
        assert result["metadata_write"] is None


@pytest.mark.parametrize("count", range(0x1FFFFFF8, 0x1FFFFFFC))
def test_expanded_heap_guard_disallows_positive_candidate(count):
    frontier = helper.compositional_spec(count)
    assert not frontier["positive_candidate_possible_under_normal_stable_protocol"]
    with pytest.raises(helper.VectorAllocationCompositionError):
        helper.compositional_spec(count, P)
    with pytest.raises(helper.VectorAllocationCompositionError):
        helper.nested_protocol_spec(count, 0, [candidate(("heap", P))])


def test_inner_zero_is_not_owner_zero():
    rows = [candidate(("heap", 0), ("error", P + 0x100))]
    result = helper.nested_protocol_spec(512, 0, rows, True)
    assert (
        result["outcome"] == "outer_retry_frontier"
        and result["frontier_kind"] == "handler"
    )
    assert result["owner"] is None
    rows += [dict(kind="handler", eax=1), candidate(("heap", P))]
    result = helper.nested_protocol_spec(512, 0, rows)
    assert (
        result["outcome"] == "conditional_normal_return"
        and result["owner"]["result"] == P + 32
    )


@pytest.mark.parametrize("pointer", [0x30001000, 0x30000FF4, 0x30001001])
def test_error_pointer_cannot_corrupt_ancestor_frame(pointer):
    with pytest.raises(helper.VectorAllocationCompositionError):
        helper.nested_protocol_spec(
            512, 0, [candidate(("heap", 0), ("error", pointer))], True
        )


@pytest.mark.parametrize("pointer", [0, 0x30000FF0, 0xFFFFFFE0])
def test_invalid_or_overlapping_success_block_rejected(pointer):
    with pytest.raises(helper.VectorAllocationCompositionError):
        helper.compositional_spec(512, pointer)


@pytest.mark.parametrize(
    "count,outcome",
    [
        (0, "zero_return"),
        (0x1FFFFFFC, "padding_failure_frontier"),
        (0x20000000, "size_failure_frontier"),
    ],
)
def test_nonretry_paths_do_not_consume_nested_records(count, outcome):
    assert helper.nested_protocol_spec(count, 0, [])["outcome"] == outcome
    with pytest.raises(helper.VectorAllocationCompositionError):
        helper.nested_protocol_spec(count, 0, [candidate(("heap", P))])


def test_integrated_success_oracle_matches_conditional_contract():
    for count in [1, 511, 512, 513, 1024]:
        for offset in range(32):
            expected = replay.successful_oracle(count, P + offset)
            actual = helper.compositional_spec(count, P + offset)
            assert (
                actual["request"] == expected["request"]
                and actual["result"] == expected["result"]
            )


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "allocation": "native_lua_vector_allocation_semantics",
        "returns": "native_lua_vector_allocation_return_semantics",
        "retry": "native_allocation_retry_semantics",
        "heap_protocol": "native_heap_allocation_protocol",
        "handoff": "native_heap_allocation_handoff",
        "composition": "native_vector_allocation_composition",
        "conformance": "native_vector_allocation_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_receipts_keep_projection_and_integrated_execution_distinct(receipts):
    paths, data, sources = receipts
    assert (
        helper.validate_structure(data["composition"], sources)["status"]
        == "structurally_verified"
    )
    assert (
        replay.validate_structure(data["conformance"], data["composition"])["status"]
        == "structurally_verified"
    )
    assert (
        helper.encode_composition(data["composition"]).encode()
        == paths["composition"].read_bytes()
    )
    assert (
        replay.encode_conformance(data["conformance"]).encode()
        == paths["conformance"].read_bytes()
    )
    coverage = helper.coverage_spec(sources)
    assert [g["nodes"] for g in coverage["groups"]] == [19, 11, 2, 2]
    assert data["conformance"]["summary"]["cases"] == 2576
    assert data["conformance"]["summary"]["executed_instruction_sites"] == 66


@pytest.mark.parametrize("kind", ["composition", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 99
    with pytest.raises(
        (helper.VectorAllocationCompositionError, replay.ConformanceError)
    ):
        (
            helper.validate_structure(changed, sources)
            if kind == "composition"
            else replay.validate_structure(changed, data["composition"])
        )


@pytest.mark.parametrize("kind", ["composition", "conformance"])
def test_exact_cli_rebuild(receipts, kind):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _, sources = receipts
    script = "itb_native_vector_allocation_" + kind + ".py"
    args = [
        sys.executable,
        str(ROOT / "scripts" / script),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "composition" else ["composition"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
