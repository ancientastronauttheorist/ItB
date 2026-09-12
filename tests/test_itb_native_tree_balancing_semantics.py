"""Independent invariant checks and repair examples for canonical insertion."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory import native_tree_balancing_semantics as m

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_"


def test_empty_and_uint32_extremes():
    assert m.validate_tree(m.from_keys([])) == dict(nodes=0, black_height=1, inorder=[])
    tree = m.from_keys([0xFFFFFFFF, 0, 0x80000000])
    assert tree["root"] == 2
    assert m.validate_tree(tree) == dict(
        nodes=3, black_height=2, inorder=[0, 0x80000000, 0xFFFFFFFF]
    )


@pytest.mark.parametrize(
    "keys,kinds,root",
    [
        ([3, 2, 1], ["left_line"], 1),
        ([3, 1, 2], ["left_triangle", "left_line"], 2),
        ([1, 2, 3], ["right_line"], 1),
        ([1, 3, 2], ["right_triangle", "right_line"], 2),
        ([2, 1, 3, 0], ["red_uncle"], 0),
        ([2, 1, 3, 4], ["red_uncle"], 0),
    ],
)
def test_hand_derived_repairs(keys, kinds, root):
    before = m.from_keys(keys[:-1])
    snapshot = copy.deepcopy(before)
    result = m.insert(before, keys[-1])
    after = result["tree"]
    assert before == snapshot
    assert after is not before and after["nodes"] is not before["nodes"]
    assert all(a is not b for a, b in zip(after["nodes"], before["nodes"]))
    assert [n["key"] for n in after["nodes"]] == keys
    assert after["root"] == root
    assert [s["kind"] for s in result["steps"]] == kinds
    assert m.validate_tree(after)["inorder"] == sorted(keys)
    if len(keys) == 3:
        assert after["nodes"][root]["color"] == 1
        assert sorted(n["color"] for n in after["nodes"]) == [0, 0, 1]
        assert result["steps"][0] == dict(
            kind=kinds[0], current=2, parent=1, grandparent=0, uncle=None
        )
    else:
        assert [n["color"] for n in after["nodes"]] == [1, 1, 1, 0]


def test_repeated_recolor_and_nonempty_rotation_transfer():
    tree = m.from_keys([])
    repeated = False
    rotations = 0
    for key in range(128):
        result = m.insert(tree, key)
        repeated |= sum(s["kind"] == "red_uncle" for s in result["steps"]) >= 2
        rotations += sum(s["kind"].endswith("line") for s in result["steps"])
        tree = result["tree"]
        assert m.validate_tree(tree)["inorder"] == list(range(key + 1))
    assert repeated and rotations > 20
    # The root rotation on inserting 7 transfers node 2 from node 3 to node 1.
    before = m.from_keys(list(range(7)))
    assert before["root"] == 1
    assert before["nodes"][3]["left"] == 2
    after = m.insert(before, 7)["tree"]
    assert after["root"] == 3
    assert after["nodes"][1]["right"] == 2
    assert after["nodes"][2]["parent"] == 1
    assert after["nodes"][3]["left"] == 1


@pytest.mark.parametrize("key", [True, False, -1, 2**32, 1.5, "1", None])
def test_invalid_key_is_rejected_without_mutation(key):
    tree = m.from_keys([10])
    before = copy.deepcopy(tree)
    with pytest.raises(m.BalancingError, match="uint32"):
        m.insert(tree, key)
    assert tree == before


def test_duplicate_and_population_bound():
    tree = m.from_keys(list(range(256)))
    with pytest.raises(m.BalancingError, match="node bound"):
        m.insert(tree, 256)
    with pytest.raises(m.BalancingError, match="duplicate"):
        m.from_keys([1, 1])
    with pytest.raises(m.BalancingError, match="sequence bound"):
        m.from_keys(list(range(257)))
    with pytest.raises(m.BalancingError, match="sequence bound"):
        m.from_keys(iter([1]))


@pytest.mark.parametrize(
    "mutation,pattern",
    [
        ("root_bool", "root ID"),
        ("pointer_bool", "node ID"),
        ("color_bool", "color"),
        ("key_bool", "uint32"),
        ("root_red", "root must be black"),
        ("parent", "parent differs"),
        ("cycle", "cycle or shared child"),
        ("shared", "cycle or shared child"),
        ("red_parent", "red parent violation"),
        ("black_height", "unequal black height"),
        ("order", "strict BST"),
        ("duplicate", "duplicate"),
        ("unreachable", "unreachable"),
        ("unknown", "node ID"),
        ("empty_members", "unreachable"),
        ("extra_field", "tree schema"),
    ],
)
def test_forged_tree_rejected(mutation, pattern):
    tree = m.from_keys([4, 2, 6, 1])
    nodes = tree["nodes"]
    if mutation == "root_bool":
        tree["root"] = False
    elif mutation == "pointer_bool":
        nodes[1]["parent"] = False
    elif mutation == "color_bool":
        nodes[1]["color"] = True
    elif mutation == "key_bool":
        nodes[1]["key"] = True
    elif mutation == "root_red":
        nodes[0]["color"] = 0
    elif mutation == "parent":
        nodes[1]["parent"] = 2
    elif mutation == "cycle":
        nodes[1]["right"] = 0
    elif mutation == "shared":
        nodes[1]["right"] = 3
    elif mutation == "red_parent":
        nodes[1]["color"] = 0
    elif mutation == "black_height":
        nodes[3]["color"] = 1
    elif mutation == "order":
        nodes[3]["key"] = 7
    elif mutation == "duplicate":
        nodes[3]["key"] = 4
    elif mutation == "unreachable":
        nodes.append(dict(left=None, right=None, parent=None, color=1, key=8))
    elif mutation == "unknown":
        nodes[1]["right"] = 99
    elif mutation == "empty_members":
        tree["root"] = None
    else:
        tree["count"] = 4
    with pytest.raises(m.BalancingError, match=pattern):
        m.validate_tree(tree)
    with pytest.raises(m.BalancingError):
        m.insert(tree, 10)


@pytest.fixture(scope="module")
def receipts():
    source_path = Path(str(PREFIX) + "program_facts.json")
    evidence_path = Path(str(PREFIX) + "native_tree_balancing_semantics.json")
    sources = {"program_facts": json.loads(source_path.read_bytes())}
    evidence = json.loads(evidence_path.read_bytes())
    return source_path, evidence_path, sources, evidence


def test_sealed_corpus_replay(receipts):
    _, path, sources, evidence = receipts
    assert m.validate_semantics(evidence, sources)["status"] == "verified"
    assert evidence["summary"]["cases"] == 885
    assert evidence["summary"]["repeated_recolor_insertions"] > 0
    assert all(evidence["summary"]["repair_steps"].values())
    assert evidence["summary"]["max_nodes"] == 256
    assert evidence["summary"]["accounting_promotions"] == 0
    assert path.read_bytes() == m.encode_semantics(evidence).encode()
    assert m._canonical_sha256(evidence) == m.SEALED_SHA256
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "e822c37dd1f589cd7e2082353f8d0d4069a40dfaf95c331ad494cc080ec80983"
    )


@pytest.mark.parametrize("kind", ["evidence", "source", "partition"])
def test_receipt_mutation_rejected(receipts, kind):
    _, _, sources, evidence = receipts
    sources, evidence = copy.deepcopy(sources), copy.deepcopy(evidence)
    if kind == "evidence":
        evidence["summary"]["accounting_promotions"] = 1
    elif kind == "source":
        sources["program_facts"]["schema_version"] = 999
    else:
        sources["unexpected"] = {}
    with pytest.raises(RuntimeError):
        m.validate_structure(evidence, sources)


def test_cli_rebuild_without_executable(receipts):
    source, evidence, _, _ = receipts
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_tree_balancing_semantics.py"),
            "build",
            "--program-facts",
            str(source),
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == evidence.read_bytes()
