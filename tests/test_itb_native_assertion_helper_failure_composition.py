"""Independent failure-body partition and conditional interface checks."""

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
from src.observatory import native_assertion_helper_failure_composition as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "query,last,outer",
    itertools.product([0, 1, 2, 0x80000000, 0xFFFFFFFF], [0, 1, 0xFFFFFFFF], range(2)),
)
def test_independent_conditional_interface(query, last, outer):
    ebp = [0x12345678, 0x87654321][outer]
    target = [0x11223344, 0xAABBCCDD][outer]
    r = helper.failure_contract(query, last, ebp, target)
    assert r["eax"] == (last if query == 0 else query)
    assert r["esp_F_offset"] == (8 if query == 0 else -816 - 804)
    assert r["esp_G_offset"] == (824 if query == 0 else -804)
    assert r["instruction_pointer"] == (target if query == 0 else 0x757B81)
    assert r["ebp_value"] == (ebp if query == 0 else None)
    assert r["ecx_value"] == (None if query == 0 else 2)
    assert r["wrapper_normal_returns_assumed"] == (4 if query == 0 else 0)
    assert not any(
        r[k]
        for k in [
            "interrupt_executed",
            "termination_guaranteed",
            "original_owner_words_guaranteed",
        ]
    )


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("bad", [True, -1, 0x100000000, None, 0.0, "0"])
def test_invalid_relation_words_rejected(index, bad):
    args = [0, 0, 0, 0]
    args[index] = bad
    with pytest.raises(helper.FailureCompositionError):
        helper.failure_contract(*args)


def test_frame_joins_and_additional_memory_premises():
    s = helper.interface_spec()
    assert s["frames"] == dict(G_F_offset=-816, H_G_offset=-816, F_G_offset=816)
    assert s["dispatch_to_stores"]["esp_G_offset"] == -804
    assert s["stores_to_returns"]["esp_G_offset"] == -808
    assert not s["stores_to_returns"]["runtime_pair_contents_proved"]
    assert not s["new_return_memory_premises"]["earlier_query_protects_outer_words"]
    assert not s["concrete_upstream_vectors_concatenated"]
    assert not s["global_preservation_across_wrapper_claimed"]


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "dispatch": "native_assertion_helper_failure_dispatch",
        "stores": "native_assertion_helper_failure_stores",
        "returns": "native_assertion_helper_failure_return",
        "owner": "native_assertion_helper_owner_composition",
        "frontier": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_failure_composition",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


def test_disjoint_complete_frontier_and_external_continuations(chain):
    _, sources, _ = chain
    segments = [
        sources["dispatch"]["static_prefix"]["instruction_points"],
        sources["stores"]["slice"]["points"],
        sources["returns"]["parent_tail"]["points"],
    ]
    assert [len(p) for p in segments] == [10, 42, 4]
    assert [sum(x["size"] for x in p) for p in segments] == [25, 217, 9]
    points = sum(segments, [])
    expected = [
        {k: p[k] for k in ("rva", "size", "sha256")}
        for p in sources["frontier"]["function_body"]["reviewed_points"]
    ]
    assert points == expected and len({p["rva"] for p in points}) == 56
    assert sum(p["size"] for p in points) == 251
    for a, b in zip(points, points[1:]):
        assert int(a["rva"], 16) + a["size"] == int(b["rva"], 16)
    assert int(points[-1]["rva"], 16) + points[-1]["size"] == 0x357C65
    assert len(sources["returns"]["wrapper"]["points"]) == 12
    assert len(sources["returns"]["owner_continuation"]["points"]) == 3
    assert not {p["rva"] for p in sources["returns"]["wrapper"]["points"]} & {
        p["rva"] for p in points
    }


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "07e9da2406545ed4ee1ae7f917d010cfbcb436622a9cd3b515c4bc3f5d1440ac"
    )
    assert evidence["summary"]["new_model_executions"] == 0
    assert evidence["summary"]["accounting_promotions"] == 0
    assert evidence["summary"]["frontier_static_bytes"] == 251
    assert evidence["summary"]["frontier_static_nodes"] == 56
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert (
        helper.encode_composition(evidence).encode() == paths["evidence"].read_bytes()
    )
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
    with pytest.raises(helper.FailureCompositionError):
        helper.validate_structure(changed, sources)


def test_exact_pe_binary_cli_build(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE for failure composition rebuild")
    paths, sources, _ = chain
    args = ["build", "--executable", executable]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_failure_composition.py"),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["evidence"].read_bytes()
