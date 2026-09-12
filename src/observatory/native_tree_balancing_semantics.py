"""Independent finite canonical red-black insertion model and synthetic corpus.

This module models mathematical trees, not instruction dispatch or native memory.
Node IDs are insertion-order list indices; None is a black nil leaf.
"""

from __future__ import annotations

import copy
import itertools
import json

from src.observatory.native_assertion_helper_fill_conformance import (
    _assert_publication_safe,
    _canonical_sha256,
    _source_identity,
    _validate_json_tree,
)

ANALYSIS_KIND = "pe_native_tree_balancing_semantics"
SEALED_SHA256 = "1e58923b87126afb5c400ab14f7780a7beeb3a85edac2912f0284e3cb00c0881"
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    )
}
OWNER_RVA = "0x0007d0a0"
OWNER_SHA256 = "b2e5011fd5c0877474cbc5614da469511eb434d63a4c6e38299bb3ec8a305042"
MAX_NODES = 256
STEP_KINDS = ("red_uncle", "left_triangle", "left_line", "right_triangle", "right_line")


class BalancingError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise BalancingError(message)


def _key(value):
    _require(type(value) is int and 0 <= value < 2**32, "key must be uint32")


def validate_tree(tree):
    """Check the entire canonical colored BST, including unreachable members."""
    _require(
        type(tree) is dict and set(tree) == {"root", "nodes"}, "tree schema differs"
    )
    nodes = tree["nodes"]
    _require(
        type(nodes) is list and len(nodes) <= MAX_NODES, "node bound or list differs"
    )

    def pointer(value):
        return value is None or (type(value) is int and 0 <= value < len(nodes))

    _require(pointer(tree["root"]), "root ID differs")
    keys = set()
    for node in nodes:
        _require(
            type(node) is dict
            and set(node) == {"left", "right", "parent", "color", "key"},
            "node schema differs",
        )
        _key(node["key"])
        _require(node["key"] not in keys, "duplicate key")
        keys.add(node["key"])
        _require(
            type(node["color"]) is int and node["color"] in (0, 1), "color differs"
        )
        _require(
            all(pointer(node[k]) for k in ("left", "right", "parent")),
            "node ID differs",
        )
    root = tree["root"]
    if root is None:
        _require(not nodes, "unreachable nodes")
        return dict(nodes=0, black_height=1, inorder=[])
    _require(nodes[root]["color"] == 1, "root must be black")
    seen, inorder = set(), []

    def visit(current, parent, lower, upper):
        if current is None:
            return 1
        _require(current not in seen, "cycle or shared child")
        seen.add(current)
        node = nodes[current]
        _require(node["parent"] == parent, "parent differs")
        _require(lower < node["key"] < upper, "strict BST order differs")
        if node["color"] == 0:
            _require(
                all(
                    child is None or nodes[child]["color"] == 1
                    for child in (node["left"], node["right"])
                ),
                "red parent violation",
            )
        left_height = visit(node["left"], current, lower, node["key"])
        inorder.append(node["key"])
        right_height = visit(node["right"], current, node["key"], upper)
        _require(left_height == right_height, "unequal black height")
        return left_height + node["color"]

    height = visit(root, None, -1, 2**32)
    _require(len(seen) == len(nodes), "unreachable nodes")
    return dict(nodes=len(nodes), black_height=height, inorder=inorder)


def insert(tree, key):
    """Return a fresh tree and logical repair steps without modifying the input."""
    validate_tree(tree)
    _key(key)
    _require(len(tree["nodes"]) < MAX_NODES, "insertion exceeds node bound")
    _require(all(n["key"] != key for n in tree["nodes"]), "duplicate key")
    result = copy.deepcopy(tree)
    nodes = result["nodes"]
    current = result["root"]
    parent = None
    while current is not None:
        parent = current
        current = nodes[current]["left" if key < nodes[current]["key"] else "right"]
    current = len(nodes)
    nodes.append(dict(left=None, right=None, parent=parent, color=0, key=key))
    if parent is None:
        result["root"] = current
    else:
        nodes[parent]["left" if key < nodes[parent]["key"] else "right"] = current
    steps = []

    def rotate(pivot, direction):
        # Promote the opposite child and transfer its inner subtree to pivot.
        outer, inner = ("right", "left") if direction == "left" else ("left", "right")
        promoted = nodes[pivot][outer]
        _require(promoted is not None, "rotation child missing")
        transferred = nodes[promoted][inner]
        nodes[pivot][outer] = transferred
        if transferred is not None:
            nodes[transferred]["parent"] = pivot
        old_parent = nodes[pivot]["parent"]
        nodes[promoted]["parent"] = old_parent
        if old_parent is None:
            result["root"] = promoted
        else:
            side = "left" if nodes[old_parent]["left"] == pivot else "right"
            nodes[old_parent][side] = promoted
        nodes[promoted][inner] = pivot
        nodes[pivot]["parent"] = promoted

    while nodes[current]["parent"] is not None:
        parent = nodes[current]["parent"]
        if nodes[parent]["color"] == 1:
            break
        grandparent = nodes[parent]["parent"]
        _require(grandparent is not None, "red root during repair")
        side = "left" if nodes[grandparent]["left"] == parent else "right"
        opposite = "right" if side == "left" else "left"
        uncle = nodes[grandparent][opposite]

        def record(kind):
            steps.append(
                dict(
                    kind=kind,
                    current=current,
                    parent=parent,
                    grandparent=grandparent,
                    uncle=uncle,
                )
            )

        if uncle is not None and nodes[uncle]["color"] == 0:
            record("red_uncle")
            nodes[parent]["color"] = nodes[uncle]["color"] = 1
            nodes[grandparent]["color"] = 0
            current = grandparent
            continue
        if nodes[parent][opposite] == current:
            record(side + "_triangle")
            current = parent
            rotate(current, side)
            parent = nodes[current]["parent"]
            grandparent = nodes[parent]["parent"]
        record(side + "_line")
        nodes[parent]["color"] = 1
        nodes[grandparent]["color"] = 0
        rotate(grandparent, opposite)
    nodes[result["root"]]["color"] = 1
    validate_tree(result)
    _require(
        [n["key"] for n in nodes] == [n["key"] for n in tree["nodes"]] + [key],
        "stable keys differ",
    )
    return dict(tree=result, steps=steps)


def from_keys(sequence):
    """Build from a bounded finite list or tuple of distinct uint32 keys."""
    _require(
        type(sequence) in (list, tuple) and len(sequence) <= MAX_NODES,
        "sequence bound or type differs",
    )
    tree = dict(root=None, nodes=[])
    for key in sequence:
        tree = insert(tree, key)["tree"]
    return tree


def vectors():
    """All size 0..6 permutations plus eleven reproducible 256-key sequences."""
    result = [
        dict(profile=f"permutation_{size}", keys=list(p))
        for size in range(7)
        for p in itertools.permutations(range(size))
    ]
    ascending = [i * 0x01010101 for i in range(MAX_NODES)]
    alternating = [
        ascending[i // 2 if i % 2 == 0 else MAX_NODES - 1 - i // 2]
        for i in range(MAX_NODES)
    ]
    for name, keys in (
        ("increasing", ascending),
        ("decreasing", ascending[::-1]),
        ("alternating", alternating),
    ):
        result.append(dict(profile=name, keys=keys))
    for seed in range(8):
        keys = list(ascending)
        state = seed + 1
        for index in range(len(keys) - 1, 0, -1):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            swap = state % (index + 1)
            keys[index], keys[swap] = keys[swap], keys[index]
        result.append(dict(profile=f"lcg_shuffle_{seed}", keys=keys))
    return result


def _preflight(sources):
    _require(
        type(sources) is dict and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    identities = {
        k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()
    }
    owners = [
        f for f in sources["program_facts"]["functions"] if f["entry_rva"] == OWNER_RVA
    ]
    _require(
        len(owners) == 1
        and owners[0]["body_sha256"] == OWNER_SHA256
        and owners[0]["body_size"] == 525,
        "exact owner identity differs",
    )
    return identities


def _build_unsealed(sources):
    identities = _preflight(sources)
    corpus = vectors()
    observations = []
    coverage = dict.fromkeys(STEP_KINDS, 0)
    insertions = repeated = maximum_steps = 0
    for vector in corpus:
        tree = dict(root=None, nodes=[])
        outcomes = []
        for key in vector["keys"]:
            outcome = insert(tree, key)
            tree = outcome["tree"]
            steps = outcome["steps"]
            insertions += 1
            maximum_steps = max(maximum_steps, len(steps))
            repeated += int(sum(step["kind"] == "red_uncle" for step in steps) >= 2)
            for step in steps:
                coverage[step["kind"]] += 1
            outcomes.append(dict(tree_sha256=_canonical_sha256(tree), steps=steps))
        observations.append(
            dict(
                outcomes_sha256=_canonical_sha256(outcomes),
                final_tree_sha256=_canonical_sha256(tree),
                summary=validate_tree(tree),
            )
        )
    _require(
        all(coverage.values()) and repeated > 0, "synthetic repair coverage differs"
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        owner=dict(entry_rva=OWNER_RVA, body_sha256=OWNER_SHA256, body_size=525),
        vectors=corpus,
        observations_sha256=_canonical_sha256(observations),
        summary=dict(
            cases=len(corpus),
            insertions=insertions,
            max_nodes=MAX_NODES,
            repair_steps=coverage,
            repeated_recolor_insertions=repeated,
            max_steps_per_insertion=maximum_steps,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Independent canonical red-black insertion model checked on a sealed finite synthetic corpus",
            representation="Stable insertion-order IDs, uint32 distinct keys, None black nil, red zero and black one",
            corpus="All permutations of sizes zero through six; eleven 256-key increasing, decreasing, alternating and LCG-shuffled sequences",
            validation="Every insertion checks strict BST order, parent consistency, finite unique membership, black root, no red adjacency and equal black height",
            not_claimed=[
                "Native instruction, memory-event, ABI or flag equivalence",
                "General balancing-loop theorem or exhaustive trees beyond this corpus",
                "Accounting promotion or actual hardware execution",
            ],
        ),
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256,
        "sealed balancing semantics differs",
    )
    _require(
        evidence["source_receipts"] == identities and evidence["vectors"] == vectors(),
        "semantics sources or vectors differ",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_semantics(sources):
    result = _build_unsealed(sources)
    validate_structure(result, sources)
    return result


def validate_semantics(evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_sha256(build_semantics(sources)) == _canonical_sha256(evidence),
        "synthetic replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_semantics(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
