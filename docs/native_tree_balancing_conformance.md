# Native accepted tree insertion and rebalancing

The receipt executes the accepted part of owner `0x0007d0a0` through its real
`RET 20`: `[0x0007d0a0,0x0007d294)`, 500 bytes and 181 static instruction sites.
It joins the sealed attachment prefix to red-uncle recoloring, both optional
triangle rotations, both final line rotations and the return tail. No callee,
import or opaque instruction executes in this range. Count-failure handling
at `0x0007d294` remains outside the claim.

## Independent comparisons

A separate [canonical insertion model](native_tree_balancing_semantics.md)
builds each initial tree and predicts the new topology and colors. The native
oracle independently describes ordered memory accesses, register restoration
and the ancestor frame. Exact Unicorn execution must match that event stream,
all general registers, all six arithmetic flags, both DF values and every
byte of every mapped data page. The model separately agrees on the complete
tree, node and output pages; it does not model machine stack effects.

All records are disjoint. Ordinary nodes have zero nil bytes and canonical
red/black colors; the head has black color and a nonzero nil byte. Count,
root, extrema and parent links are consistent, and the selected child is nil.
A fresh disjoint red node supplies the new key token and payload. The fixture
protects the full ancestor, result page, all node padding and all inert key
and payload bytes. Keys are abstract unsigned labels used to choose a valid
insertion position; accepted native balancing never compares or dereferences
those key fields. This is not a proof of the surrounding string comparator.

## Corpus and coverage

The sealed corpus contains 1,329 insertions: all permutations of sizes one
through six, plus selected prefixes of increasing, decreasing, alternating,
bit-reversed and eight deterministic shuffled 256-key sequences. Existing
tree sizes range from zero to 255. Node records, the fresh node and ancestor
frames have varied alignments. Head nil bytes include 1, 128 and 255.

The corpus executes all 175 canonically reachable sites. The six excluded
sites belong to generic triangle relinking arms:

- `0x0007d149`, `0x0007d14c` and mirrored `0x0007d209`, `0x0007d20c`: the
  red triangle pivot cannot also be the canonical black root.
- `0x0007d159` and mirrored `0x0007d21b`: dispatch already established the
  pivot's parent-child orientation, and preceding triangle writes do not
  change that orientation before relinking.

Malformed trees are not introduced merely to hit these sites. The receipt
records 13 distinct branch features, including all four non-nil middle-subtree
transfers, root and both nonroot parent-side line rotations, both triangles,
and red-uncle repair. Observed insertions require up to four loop iterations
and at most two rotations. Non-nil transfers can occur after recoloring has
moved the cursor upward from the fresh leaf.

Each recolor advances the cursor two parent links toward the head without
changing topology. A line rotation, optionally preceded by a triangle,
makes the cursor's parent black and exits. These canonical invariants explain
finite progress; the replay instruction budget is not itself a termination
proof. The sealed experiment remains a finite corpus, not a general theorem
for arbitrary graphs.

## Return and corruption checks

EAX returns the result-slot address. ECX names the final black parent. EDX
preserves its entry value on the initial black-parent bypass, names the last
uncle on a recolor-only exit, or names the old grandparent after a line
rotation. Nonvolatile registers restore; ESP becomes entry plus 24. Canonical
final arithmetic flags are zero under mask `0x8d5`, from the final comparison
of black color 1 with zero; DF is independently preserved.

Three corruption controls must fail their intended checks: an unread
ancestor argument, fresh-node padding, and the saved ESI slot on a two-rotation
path. The ESI control additionally requires ESI to be the sole differing
register with correct arithmetic flags before accepting the intended failure.

## Artifacts and reproduction

- [Implementation](../src/observatory/native_tree_balancing_conformance.py)
- [CLI](../scripts/itb_native_tree_balancing_conformance.py)
- [Tests](../tests/test_itb_native_tree_balancing_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_tree_balancing_conformance.json)

Canonical SHA-256:
`58b41864a6b9f486adf139102e08bdb8d4620660963998bd43675800265b31ce`.
Encoded SHA-256:
`e383bf77f6ec42e23f1bd5c40d07c9170d38bca5dd00ae307c3f9906bfd588d7`.

The CLI accepts `build`, `verify`, or `verify-structure`, with `--program-facts`,
`--attachment` and `--semantics`. Exact operations require `--executable`;
verification requires `--evidence`. Builds emit deterministic UTF-8/LF JSON.
Exact PE SHA-256 is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Capstone 5.0.7 and Unicorn 2.1.4 remain private dependencies. Enable the gated
subprocess replay with `ITB_EXACT_EXE` and private runtime `PYTHONPATH`.

Independent review of native memory equations, ABI, excluded branches,
source pins and corruption controls: **GO**. Size failure, exceptions, hint
dispatch, full class-owner composition and whole-game accounting remain open.

Validation: **36 focused tests passed**, including a byte-identical exact
1,329-case CLI rebuild.
