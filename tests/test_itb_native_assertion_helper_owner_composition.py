"""Whole-body partitions and independently checked conditional owner relations."""

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
from src.observatory import native_assertion_helper_owner_composition as helper
from scripts import itb_native_assertion_helper_owner_composition as cli

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "pair": "native_assertion_helper_descendant_pair",
        "program_facts": "program_facts",
        "caller": "native_assertion_helper_caller_fill",
        "handoff": "native_assertion_helper_import_handoff",
        "arguments": "native_assertion_helper_import_arguments",
        "tail": "native_assertion_helper_return_tail",
        "failure_frontier": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary",
        "evidence": "native_assertion_helper_owner_composition",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


@pytest.mark.parametrize(
    "first,third,selector,equal",
    itertools.product(
        [0, 1, 0xFFFFFFFF], [0, 1, 0x80000000], [0, 1, 0xFFFFFFFF], [False, True]
    ),
)
def test_independent_owner_relation(first, third, selector, equal):
    relation = helper.owner_contract(first, third, selector, equal)
    pre = selector != 0xFFFFFFFF
    post = pre and first == third == 0
    assert relation["prefix_selector_sampled"] == (selector in [0, 0xFFFFFFFF])
    assert relation["pre_helper_called"] == pre
    assert relation["post_helper_called"] == post
    assert relation["helper_call_count"] == int(pre) + int(post)
    assert relation["eax"] == third
    assert relation["esp_owner_entry_delta"] == (4 if equal else -816)
    assert relation["modeled_boundary"] == (
        "direct_caller_return" if equal else "open_external_transfer"
    )
    assert relation["ebp_source"] == (
        "owner_entry_ebp" if equal else "established_frame"
    )
    for reg in ["ebx", "esi", "edi"]:
        assert relation[reg + "_source"] == "owner_entry_" + reg
    assert relation["global_clear_word_at_modeled_boundary"] == (0 if post else None)
    assert relation["record_contents_after_third_import"] == "unspecified"


def test_pre_helper_does_not_imply_global_survives_imports():
    result = helper.owner_contract(1, 1, 0)
    assert result["pre_helper_called"] and not result["post_helper_called"]
    assert result["global_clear_word_at_modeled_boundary"] is None


@pytest.mark.parametrize("selector", [False, -1, 0x100000000, 1.0])
def test_invalid_relation_input_rejected(selector):
    with pytest.raises(helper.OwnerError):
        helper.owner_contract(0, 0, selector)


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert (
        helper.SEALED_SHA256
        == "62844b54a1fdbc5b3c466bf9a20e87a1ec91c6f18c0cf5e1f26379fd8fe01dbe"
    )
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "bff4fd11aceaf941d7ea7d79b25da8b23f45e11e2a93a9168475abce4cbbd129"
    )


def test_disjoint_complete_body_partition(chain):
    paths, sources, evidence = chain
    rows = (
        sources["handoff"]["prefix"]["points"]
        + sources["arguments"]["slice"]["points"]
        + sources["tail"]["tail"]["points"]
    )
    assert rows == sources["pair"]["bodies"][0]["points"]
    assert len(rows) == 78 and sum(p["size"] for p in rows) == 315
    addresses = [int(p["rva"], 16) for p in rows]
    assert len(set(addresses)) == 78 and addresses[0] == 0x379D28
    for left, right in zip(rows, rows[1:]):
        assert int(left["rva"], 16) + left["size"] == int(right["rva"], 16)
    assert addresses[-1] + rows[-1]["size"] == 0x379E63
    coverage = evidence["coverage"]
    assert [(r["bytes"], r["instructions"]) for r in coverage["segments"]] == [
        (248, 55),
        (23, 6),
        (44, 17),
    ]
    assert evidence["summary"]["accounting_promotions"] == 0
    assert evidence["summary"]["new_dynamic_executions"] == 0
    assert evidence["summary"]["transitive_matrices_rerun"] == 0
    assert helper.encode_owner(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "source",
    [
        "pair",
        "program_facts",
        "caller",
        "handoff",
        "arguments",
        "tail",
        "failure_frontier",
    ],
)
def test_source_mutation_rejected(chain, source):
    _, sources, evidence = chain
    changed = dict(sources)
    changed[source] = dict(sources[source], unexpected=True)
    with pytest.raises(helper.OwnerError):
        helper.validate_structure(evidence, changed)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("scope", {}),
        ("raw_bytes", "private"),
        ("coverage", {}),
        ("summary", {}),
    ],
)
def test_receipt_mutation_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.OwnerError):
        helper.validate_structure(changed, sources)


def args(chain, command):
    paths, sources, _ = chain
    result = [command, "--evidence", str(paths["evidence"])]
    for key in sources:
        result += ["--" + key.replace("_", "-"), str(paths[key])]
    return result


def test_exact_pe_rebuild(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE to rebuild owner composition")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_owner_composition.py"),
            *args(chain, "verify"),
            "--executable",
            executable,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == "" and json.loads(result.stdout)["status"] == "verified"
