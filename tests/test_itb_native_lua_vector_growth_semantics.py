"""Growth geometry, machine-word edge cases and provenance validation."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_lua_vector_growth_semantics as helper
from src.observatory import native_lua_vector_growth_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 511, 512, 0x0FFFFFFF])
def test_full_ordinary_geometry(count):
    expected = max(count + 1, count + count // 2)
    result = helper.aligned_geometry_spec(0, 8 * count, 8 * count)
    assert result == dict(
        size=count, capacity=count, requested=expected, outcome="resize_request"
    )
    assert helper.growth_spec(0, 8 * count, 8 * count)["requested"] == expected


@pytest.mark.parametrize(
    "begin,end,capacity", [(0, 0, 8), (9, 17, 33), (0xFFFFFF00, 0xFFFFFF00, 0xFFFFFFF8)]
)
def test_spare_aligned_geometry(begin, end, capacity):
    assert helper.aligned_geometry_spec(begin, end, capacity)["requested"] is None
    assert helper.growth_spec(begin, end, capacity)["outcome"] == "no_growth"


@pytest.mark.parametrize(
    "values", [(0, 0, 1), (8, 0, 8), (0, 16, 8), (0, 0x80000000, 0x80000000)]
)
def test_reject_machine_states_as_ordinary_geometry(values):
    with pytest.raises(helper.GrowthError):
        helper.aligned_geometry_spec(*values)


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("bad", [True, -1, 0x100000000, None])
def test_strict_u32_inputs(index, bad):
    values = [0, 0, 0]
    values[index] = bad
    with pytest.raises(helper.GrowthError):
        helper.growth_spec(*values)


def test_independent_simplified_oracle_matches_graph_boundaries():
    for vector in replay.vectors()[::16]:
        b, e, c = (vector[k] for k in ["begin", "end", "capacity"])
        expected = replay.oracle(vector)
        result = helper.model_case(b, e, c, 15, 0xFFFFFFFF)
        assert result["specification"]["requested"] == expected["requested"]
        assert result["stop_rva"] == f"0x{expected['stop']:08x}"
        assert result["registers"]["eax"] == expected["eax"]
        assert result["registers"]["edx"] == expected["edx"]
        assert result["registers"]["edi"] == expected["edi"]


def test_logical_shift_mutation_detected():
    ops = dict(helper.OPS)
    ops[0x2EB640] = ("shr", helper.R("edx"), helper.I(3))
    with pytest.raises(helper.GrowthError):
        helper.model_case(0, 0x80000000, 0x80000000, ops=ops)


@pytest.fixture(scope="module")
def receipt():
    suffix = {
        "chain": "native_lua_class_return_helper_chain",
        "program_facts": "program_facts",
        "append_semantics": "native_lua_class_vector_append_semantics",
        "evidence": "native_lua_vector_growth_semantics",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


def test_receipt_proves_unreachable_frontier_without_executing_it(receipt):
    paths, sources, evidence = receipt
    assert helper.encode_semantics(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )
    assert evidence["summary"]["static_nodes"] == 40
    assert evidence["summary"]["modeled_nodes"] == 33
    assert evidence["summary"]["failure_frontiers"] == 0
    assert evidence["failure_unreachability"]["sar3_unsigned_image"] == [
        [0, 0x0FFFFFFF],
        [0xF0000000, 0xFFFFFFFF],
    ]


@pytest.mark.parametrize(
    "key", ["summary", "failure_unreachability", "source_receipts"]
)
def test_changed_receipt_rejected(receipt, key):
    _, sources, evidence = receipt
    altered = copy.deepcopy(evidence)
    altered[key] = {}
    with pytest.raises(helper.GrowthError):
        helper.validate_structure(altered, sources)


def test_exact_pe_cli_build(receipt):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE")
    paths, sources, _ = receipt
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_vector_growth_semantics.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["evidence"].read_bytes()
