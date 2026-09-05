"""Tree successor boundary, mutation, publication and exact rebuild checks."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_tree_successor_semantics as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
ARTIFACT = PROGRAMS / (PREFIX + "native_lua_tree_successor_semantics.json")
NIL = 0x10000000


@pytest.mark.parametrize(
    "shape,count",
    [
        ("balanced", 7),
        ("left_chain", 4),
        ("right_chain", 4),
        ("single", 1),
        ("empty", 0),
    ],
)
@pytest.mark.parametrize("flag", [1, 255])
def test_every_successor_matches_explicit_fixture_order(shape, count, flag):
    nodes = helper.tree_fixture(shape, flag)
    expected_order = [NIL + 64 * i for i in range(1, count + 1)]
    for index, start in enumerate(expected_order):
        result = helper.successor_spec(nodes, start)
        assert result["successor"] == (
            expected_order[index + 1] if index + 1 < count else NIL
        )
        assert result["native_esp_delta"] == 4
        for alignment in [0, 15]:
            helper.model_case(shape, start, alignment, flag)
    sentinel = helper.successor_spec(nodes, NIL)
    assert sentinel["successor"] == NIL
    assert sentinel["slot_write_nodes"] == []
    assert sentinel["path"] == "sentinel_unchanged"


def test_parent_climb_records_intermediate_writes():
    nodes = helper.tree_fixture("right_chain")
    result = helper.successor_spec(nodes, NIL + 256)
    assert result["slot_write_nodes"] == [NIL + 192, NIL + 128, NIL + 64, NIL]


@pytest.mark.parametrize(
    "mutation", ["cycle", "unmapped", "second_sentinel", "bad_parent", "bool_flag"]
)
def test_invalid_topology_is_outside_domain(mutation):
    nodes = helper.tree_fixture("balanced")
    node = nodes[NIL + 64]
    if mutation == "cycle":
        node["left"] = NIL + 64
    elif mutation == "unmapped":
        node["right"] = 0x12345678
    elif mutation == "second_sentinel":
        node["sentinel"] = 1
    elif mutation == "bad_parent":
        node["parent"] = NIL
    else:
        node["sentinel"] = False
    with pytest.raises(helper.SuccessorError):
        helper.successor_spec(nodes, NIL + 64)


def test_wrong_intermediate_write_is_detected():
    actions = dict(helper.OPS)
    actions[0x6DF6F] = ("mov", helper.M("edx"), helper.R("edx"))
    with pytest.raises(helper.SuccessorError):
        helper.model_case("right_chain", NIL + 256, 0, actions=actions)


def sources():
    return {
        key: json.loads((PROGRAMS / (PREFIX + suffix + ".json")).read_text())
        for key, suffix in {
            "chain": "native_lua_class_return_helper_chain",
            "program_facts": "program_facts",
        }.items()
    }


def test_published_receipt_and_tamper_rejection():
    payload = ARTIFACT.read_bytes()
    assert (
        hashlib.sha256(payload).hexdigest()
        == "552515f52dbbd4ac323e0b896c975ce20bbe2444abeaa3300e92596982ba8592"
    )
    evidence = json.loads(payload)
    result = helper.validate_structure(evidence, sources())
    assert result["summary"]["cases"] == 672
    assert result["summary"]["modeled_nodes"] == 31
    assert result["summary"]["actual_native_executions"] == 0
    altered = copy.deepcopy(evidence)
    altered["summary"]["actual_native_executions"] = 1
    with pytest.raises(helper.SuccessorError):
        helper.validate_structure(altered, sources())


@pytest.mark.skipif(
    not os.environ.get("ITB_EXACT_EXE"), reason="exact executable required"
)
def test_exact_cli_rebuild_is_byte_identical():
    command = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_tree_successor_semantics.py"),
        "build",
        "--executable",
        os.environ["ITB_EXACT_EXE"],
        "--chain",
        str(PROGRAMS / (PREFIX + "native_lua_class_return_helper_chain.json")),
        "--program-facts",
        str(PROGRAMS / (PREFIX + "program_facts.json")),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.stdout == ARTIFACT.read_bytes()
