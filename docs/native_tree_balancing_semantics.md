# Independent canonical tree insertion semantics

`src/observatory/native_tree_balancing_semantics.py` is a mathematical red-black
tree insertion model. It does not interpret native instructions or translate a
native event oracle. Its source receipt identifies owner RVA `0x0007d0a0`, size
525, SHA-256 `b2e5011fd5c0877474cbc5614da469511eb434d63a4c6e38299bb3ec8a305042`,
through the sealed exact-build program facts. That identity does not establish
equivalence to the owner's machine behavior.

## API and representation

- `validate_tree(tree)` returns `nodes`, `black_height`, and key `inorder`.
- `insert(tree, key)` returns a fresh `{tree, steps}` without mutating the input.
- `from_keys(sequence)` builds a tree from a finite list or tuple.

A tree is exactly `{root, nodes}`. Each node is exactly
`{left, right, parent, color, key}`. IDs are list indices in insertion order.
`None` represents every black nil leaf; nil contributes one to black height.
Color is integer zero (red) or one (black). Keys are distinct unsigned 32-bit
integers. Boolean values are rejected for keys, colors, and IDs. At most 256
nodes are admitted, and insertion into a 256-node tree is rejected.

Validation checks all nodes, strict BST ordering, root color, parent links,
unique reachability, red adjacency, and equal black height. Rotations change
links and colors while preserving stable IDs and all existing keys. Each repair
step records `kind`, `current`, `parent`, `grandparent`, and `uncle` at that
logical step. Kinds are `red_uncle`, `left_triangle`, `left_line`,
`right_triangle`, and `right_line`. Triangle labels refer to which side of the
grandparent contains the red parent. Triangle and following line steps are
separate records; the line record reflects the topology after the triangle.

## Sealed finite corpus

The receipt contains 885 synthetic sequences: all 874 permutations of sizes
zero through six, then increasing, decreasing, alternating, and eight LCG
shuffles of 256 distinct keys spanning zero through `0xffffffff`. Every
insertion is validated. Digests bind the resulting trees and ordered logical
repair steps. Coverage includes both mirrored triangles and lines, red-uncle
repair, and multiple recolor ascents within one insertion.

The receipt contains synthetic vectors, digests, summaries, and source identity;
no PE bytes or private game payloads. It establishes neither a general theorem
over all trees nor native register, flag, memory-event, or hardware behavior.
It makes zero accounting promotions. A separate native conformance experiment
must compare independently observed native outcomes to this model.

Build or replay without an executable:

```powershell
python scripts/itb_native_tree_balancing_semantics.py build --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json
python scripts/itb_native_tree_balancing_semantics.py verify --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_tree_balancing_semantics.json
```

Validation: **37 tests passed**. Two strengthened test assertions were then
rerun successfully; their counts overlap the full run. Independent primary
review of the model and invariants found no blockers.
