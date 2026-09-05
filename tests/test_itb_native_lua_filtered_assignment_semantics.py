"""Independent key filtering, stack induction and finite transcript checks."""

from __future__ import annotations
import copy
import hashlib
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from src.observatory import native_lua_filtered_assignment_semantics as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
TRANSCRIPTS = [
    list(row)
    for n in range(4)
    for row in itertools.product(["init", "finalize", "other"], repeat=n)
]


@pytest.mark.parametrize("keys", TRANSCRIPTS)
def test_independent_finite_request_relation(keys):
    r = helper.assignment_spec(keys)
    assert r["iterations"] == len(keys)
    assert r["assignment_iteration_indices"] == [
        i for i, k in enumerate(keys) if k == "other"
    ]
    assert r["assignment_requests"] == keys.count("other")
    assert r["api_calls"] == 2 + sum(
        {"init": 4, "finalize": 7, "other": 10}[k] for k in keys
    )
    assert r["eax"] == 0 and r["native_esp_delta"] == 4 and r["lua_stack_delta"] == 0


@pytest.mark.parametrize("keys", TRANSCRIPTS)
@pytest.mark.parametrize("alignment,prefix,volatile", [(0, 0, 0), (15, 2, 0xFFFFFFFF)])
def test_independent_model_stack_and_requests(keys, alignment, prefix, volatile):
    r = helper.model_case(alignment, prefix, keys, volatile)
    assert r["outcome"] == helper.assignment_spec(keys)
    assignments = [c for c in r["calls"] if c["api"] == "lua_settable"]
    assert len(assignments) == keys.count("other")
    assert all(c["arguments"][1] == 0xFFFFFFFB for c in assignments)
    assert len(r["calls"]) == 2 + sum(
        {"init": 4, "finalize": 7, "other": 10}[k] for k in keys
    )
    assert r["calls"][-1]["api"] == "lua_next"
    assert r["calls"][-1]["lua_top_after"] == prefix + 2
    assert all(
        c["arguments"][-1] == 0xFFFFFFFE for c in r["calls"] if c["api"] == "lua_next"
    )


def test_larger_symbolic_transcript_preserves_iteration_positions():
    keys = ["other", "init", "finalize"] * 100
    r = helper.assignment_spec(keys)
    assert r["assignment_iteration_indices"] == list(range(0, 300, 3))
    assert r["assignment_requests"] == 100 and r["api_calls"] == 2102


@pytest.mark.parametrize("bad", [None, False, 0, "other", (), ["unknown"], [True]])
def test_bad_transcripts_rejected(bad):
    with pytest.raises(helper.AssignmentError):
        helper.assignment_spec(bad)


def test_induction_suffix_and_destination_indices():
    r = helper.loop_invariant_spec()
    assert (
        r["entry_lua_stack"]
        == r["normal_return"]
        == ["prefix", "destination", "source"]
    )
    assert r["before_next"] == ["prefix", "destination", "source", "iterator_key"]
    assert r["assignment_before_call"] == [
        "prefix",
        "destination",
        "source",
        "iterator_key",
        "duplicate_key",
        "value",
    ]
    assert r["assignment_index"] == -5 and r["source_index_at_next"] == -2


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "chain": "native_lua_class_return_helper_chain",
        "direct_calls": "native_lua_direct_call_census",
        "program_facts": "program_facts",
        "evidence": "native_lua_filtered_assignment_semantics",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "b702b24ca55a586ac3be3acf0e8d357623d3431c707821d46647b2308779fc1b"
    )
    assert evidence["summary"] == dict(
        accounting_promotions=0,
        actual_import_executions=0,
        cases=2560,
        direct_import_sites=8,
        finite_transcripts=40,
        modeled_nodes=71,
        staged_import_sites=6,
        static_bytes=180,
        static_nodes=71,
        unique_imports=8,
    )
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_semantics(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("raw_bytes", "private"),
        ("scope", {}),
        ("summary", {}),
    ],
)
def test_mutated_receipt_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.AssignmentError):
        helper.validate_structure(changed, sources)


def test_exact_pe_binary_build(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE for filtered assignment rebuild")
    paths, sources, _ = chain
    args = ["build", "--executable", executable]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_lua_filtered_assignment_semantics.py"),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert r.stderr == b"" and r.stdout == paths["evidence"].read_bytes()
