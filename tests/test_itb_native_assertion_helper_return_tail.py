"""Independent return predicates, preserved slots and mismatch transfers."""

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
from src.observatory import native_assertion_helper_return_tail as helper
from scripts import itb_native_assertion_helper_return_tail as cli

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "pair": "native_assertion_helper_descendant_pair",
        "program_facts": "program_facts",
        "arguments": "native_assertion_helper_import_arguments",
        "handoff": "native_assertion_helper_import_handoff",
        "leaves": "native_assertion_helper_leaf_callees",
        "reused_check": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary",
        "evidence": "native_assertion_helper_return_tail",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


@pytest.mark.parametrize(
    "first,third,selector,equal",
    itertools.product(
        [0, 1, 0xFFFFFFFF, 0x80000000],
        [0, 1, 0xFFFFFFFF, 0x80000000],
        [0, 1, 0xFFFFFFFF, 0x80000000],
        [False, True],
    ),
)
def test_independent_u32_path_predicate(first, third, selector, equal):
    out = helper.tail_spec(first, third, selector, equal)
    assert out == {
        "small_helper_called": first == third == 0 and selector != 0xFFFFFFFF,
        "terminal": "caller_return" if equal else "external_checker_transfer",
        "eax": third,
        "edi_source": "entry_saved_edi",
        "ecx_source": "protected_slot_xor_frame",
        "esp_frame_offset": 8 if equal else -812,
        "ebp_source": "entry_saved_ebp" if equal else "established_frame",
        "instruction_target": "incoming_return_word" if equal else "0x00357b6a",
    }


@pytest.mark.parametrize(
    "index,bad", itertools.product(range(3), [True, -1, 0x100000000, 1.0, "1"])
)
def test_tail_rejects_non_u32(index, bad):
    inputs = [0, 0, 0]
    inputs[index] = bad
    with pytest.raises(helper.TailError):
        helper.tail_spec(*inputs)


@pytest.mark.parametrize("bad", [0, 1, None, "true"])
def test_equality_premise_requires_boolean(bad):
    with pytest.raises(helper.TailError):
        helper.tail_spec(0, 0, 0, bad)


def test_complete_partition_and_matrix_model():
    partitions = helper.branch_partition_spec()
    assert len(partitions) == 16
    assert {
        tuple(
            r[k]
            for k in [
                "first_is_zero",
                "third_is_zero",
                "selector_is_marker",
                "compare_equal",
            ]
        )
        for r in partitions
    } == set(itertools.product([False, True], repeat=4))
    for row in partitions:
        assert row["outcome"]["eax_source"] == "third_return"
        assert "eax" not in row["outcome"]
    expected = list(
        itertools.product(
            range(16),
            [0, 1, 0xFFFFFFFF],
            [0, 1, 0xFFFFFFFF],
            [0, 1, 0xFFFFFFFF],
            [0, 0x6B8B4567],
            [0, 1],
        )
    )
    assert helper.cases() == expected and len(expected) == 1728
    for vector in expected:
        a, first, third, selector, seed, equal = vector
        model = helper.model_case(vector)
        out = model["outcome"]
        assert out["small_helper_called"] == (
            first == third == 0 and selector != 0xFFFFFFFF
        )
        assert out["eax"] == third and out["esp_frame_offset"] == (8 if equal else -812)
        assert model["recovered_word"] == seed
        trace = model["trace_rvas"]
        assert ("0x003586b6" in trace) == out["small_helper_called"]
        assert ("0x003574d5" in trace) == (not equal)
        assert ("0x00379e62" in trace) == bool(equal)
        assert model["record_contents"] == "unspecified after abstract import"


def test_import_does_not_require_record_preservation():
    contract = helper.call_summary_spec()
    assert {(r["frame_offset"], r["width"]) for r in contract["protected_words"]} == {
        (-812, 4),
        (-4, 4),
        (0, 4),
        (4, 4),
        (8, 4),
    }
    assert "Unspecified" in contract["record_memory_effects"]
    checker = helper.checker_spec()
    assert checker["global_equality_is_independent_premise"] is True
    assert checker["writes_memory"] is False


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert (
        helper.SEALED_SHA256
        == "fd5c3c19346955ad9a667cdf1f53757fa98f29948f6a26216f431d8e267ec703"
    )
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "b4d31821692dbc968d50e5ad4c6e7c445d5e6b96de19eed747abbb76ff93669e"
    )
    assert helper.encode_tail(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("scope", {}),
        ("raw_bytes", "private"),
        ("predicate_partitions", []),
        ("checker", {}),
        ("matrix", {}),
    ],
)
def test_receipt_mutation_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.TailError):
        helper.validate_structure(changed, sources)


def arguments(chain, command):
    paths, sources, _ = chain
    result = [command, "--evidence", str(paths["evidence"])]
    for key in sources:
        result += ["--" + key.replace("_", "-"), str(paths[key])]
    return result


def test_cli_structure_without_pe(chain, monkeypatch, capsys):
    def forbidden(*a):
        raise AssertionError("PE-free check attempted executable access")

    monkeypatch.setattr(helper, "_load_executable", forbidden)
    assert cli.main(arguments(chain, "verify-structure")) == 0
    result = capsys.readouterr()
    assert (
        result.err == "" and json.loads(result.out)["status"] == "structurally_verified"
    )


def test_exact_pe_rebuild(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE to rebuild exact tail analysis")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_return_tail.py"),
            *arguments(chain, "verify"),
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
