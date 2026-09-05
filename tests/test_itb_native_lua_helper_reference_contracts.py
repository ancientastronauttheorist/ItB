"""Independent finite projection and error-exclusion checks for Lua contracts."""

from __future__ import annotations
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import pytest
from src.observatory import native_lua_helper_reference_contracts as helper
from src.observatory import lua51_marker_reference as marker
from src.observatory import lua51_filtered_assignment_reference as assignment

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def test_marker_projection_partition():
    counts = {"no_metatable": 0, "false_marker": 0, "truthy_marker": 0}
    errors = 0
    for row in marker.expected_rows():
        if row[3]:
            errors += 1
            with pytest.raises(helper.ContractError):
                helper.marker_projection(row)
        else:
            r = helper.marker_projection(row)
            counts[r["path"]] += 1
            assert (
                r["reference_result"]
                == r["native_contract_al"]
                == int(row[0] != 0 and row[1] not in (0, 1))
            )
            assert "eax" not in r and r["lua_stack_delta"] == 0
    assert (
        counts == {"no_metatable": 14, "false_marker": 12, "truthy_marker": 30}
        and errors == 14
    )


def test_assignment_projection_does_not_invent_next_order():
    count = errors = requests = 0
    for row in assignment.expected_rows():
        if row[3]:
            errors += 1
            with pytest.raises(helper.ContractError):
                helper.assignment_projection(row)
        else:
            r = helper.assignment_projection(row)
            count += 1
            requests += r["reference_assignment_requests"]
            assert (
                r["native_contract_assignment_requests"] == [0, 0, 0, 1, 1, 6][row[1]]
            )
            assert not r["reference_next_order_observed"]
            assert not {"assignment_iteration_indices", "eax", "trace_rvas"} & set(r)
    assert (count, errors, requests) == (42, 6, 48)


@pytest.mark.parametrize(
    "kind,index,value",
    [
        ("marker", 4, 1),
        ("marker", 7, 0),
        ("marker", 0, True),
        ("assignment", 4, 1),
        ("assignment", 8, 0),
        ("assignment", 0, True),
    ],
)
def test_changed_compared_observation_rejected(kind, index, value):
    row = list((marker if kind == "marker" else assignment).expected_rows()[0])
    row[index] = value
    with pytest.raises(helper.ContractError):
        (
            helper.marker_projection
            if kind == "marker"
            else helper.assignment_projection
        )(row)


@pytest.fixture(scope="module")
def chain():
    paths = {
        "marker_native": PROGRAMS / (PREFIX + "native_lua_class_marker_semantics.json"),
        "marker_reference": PROGRAMS / "lua_5_1_5_x86_marker_reference.json",
        "assignment_native": PROGRAMS
        / (PREFIX + "native_lua_filtered_assignment_semantics.json"),
        "assignment_reference": PROGRAMS
        / "lua_5_1_5_x86_filtered_assignment_reference.json",
        "chain": PROGRAMS / (PREFIX + "native_lua_class_return_helper_chain.json"),
        "direct_calls": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "program_facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "evidence": PROGRAMS / (PREFIX + "native_lua_helper_reference_contracts.json"),
    }
    loaded = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: loaded[k] for k in helper.SOURCE_PINS}, loaded["evidence"]


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "f309f0703dd1598878d089e780e1c7a69b5fe7eb6d5379b695d5554c01bf36f1"
    )
    assert evidence["summary"] == dict(
        normal_comparisons=98,
        marker_normal_comparisons=56,
        assignment_normal_comparisons=42,
        excluded_protected_errors=20,
        marker_path_counts=dict(no_metatable=14, false_marker=12, truthy_marker=30),
        assignment_request_sum=48,
        new_native_executions=0,
        new_reference_executions=0,
        accounting_promotions=0,
    )
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_contracts(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "key,value", [("schema_version", True), ("scope", {}), ("raw_bytes", "private")]
)
def test_mutated_receipt_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.ContractError):
        helper.validate_structure(changed, sources)


def test_binary_cli_rebuild(chain):
    paths, sources, _ = chain
    args = ["build"]
    for k in sources:
        args += ["--" + k.replace("_", "-"), str(paths[k])]
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_lua_helper_reference_contracts.py"),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert r.stderr == b"" and r.stdout == paths["evidence"].read_bytes()
