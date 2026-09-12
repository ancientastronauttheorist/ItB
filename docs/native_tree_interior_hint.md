# Native interior lower-bound hinted insertion

This proof covers an absent key strictly between existing keys, with the hint
set to its exact nonminimum lower-bound node. The native owner executes two
key comparisons, predecessor traversal, one of two attachment calls, canonical
rebalancing, normal exception-registration restoration and cookie return.
Arbitrary hints, equality, successor-side dispatch and fallback remain excluded.

## Real caller joins

For owner entry stack `H`, the first comparator enters at `H-80` and returns
to `H-68`, establishing query < candidate. The owner stores the candidate in
its iterator slot `H-28`; predecessor enters at `H-72` without stack arguments.
The sealed predecessor oracle runs on the actual old-node graph and slot,
including every intermediate slot write and its independent inorder check.

Predecessor returns EAX=EDX=`H-28`. The second comparator establishes
predecessor < query. Its EDX upper bytes therefore come from `H-28`, not from
the outer entry value; its low byte is the final left byte. Both comparisons
return ECX=`0xffffffff`, which becomes the unused key argument at `H-76`.

If predecessor.right is nil, the child attaches right to predecessor. Otherwise
the lower-bound candidate has a nil left child and the child attaches there.
The two caller paths have different output-local/parent-push ordering, which
the oracle preserves. Both child entries are `H-92`, with EAX=predecessor.right,
ECX=tree, EBX=predecessor, ESI=output, EDI=head and the second comparator's EDX.
The child returns at `H-68`; the ordinary owner tail finishes at `H+20`.

Final EAX names the result slot, ECX is the cookie, and EDX follows the child's
bypass/recolor/rotation contract. Nonvolatile registers restore; arithmetic
flags are `0x44` under mask `0x8d5`, and DF preserves. Normal registration uses
the explicit synthetic flat-FS contract established by the
[empty hint proof](native_tree_empty_hint.md), without exception delivery.

## Corpus and evidence

The corpus contains 2,016 native cases across four insertion orders, nine tree
sizes from two to 255, selected interior gaps, node/frame/string alignments,
DF, nil markers, cookies and saved registration heads. Keys use fixed-width
hexadecimal strings preserving the independent abstract key order.

Loaded code totals 900 bytes and 333 sites; 308 sites execute. All selected
owner and cookie sites execute. Previously sealed comparator, predecessor and
accepted-balancing bodies are loaded in full, without claiming every generic
leaf branch occurs in this caller. The corpus exercises 1,140 predecessor-right
and 876 candidate-left attachments, up to seven predecessor-slot writes,
three balancing iterations and two rotations. Both mirrored triangles/lines
and all four non-nil transferred-subtree cases occur.

Every ordered access, final register, flag and mapped byte is compared. The
independent canonical insertion model agrees on complete tree/node/output
pages; separate native equations protect the ancestor, both comparators,
iterator slot, key strings, registration and cookie. Corruption controls cover
an unread outer argument, node padding, restored registration and the precise
cookie mismatch frontier. No callee is summarized opaquely.

- [Implementation](../src/observatory/native_tree_interior_hint_conformance.py)
- [CLI](../scripts/itb_native_tree_interior_hint_conformance.py)
- [Tests](../tests/test_itb_native_tree_interior_hint_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_tree_interior_hint_conformance.json)

Canonical SHA-256:
`b4b8859192f3054ab33fbfe9e275e980c48571bb1dc57f88bb3a6aebd1876074`.
Encoded SHA-256:
`bdb2f71c5f0ebf735a0286110d4f35bbc4006be8adba1dbbb8612216bb8a18c1`.

Use `build`, `verify`, or `verify-structure` with `--program-facts`,
`--balancing`, `--comparator`, `--predecessor` and `--cookie-return`.
Exact operations require `--executable`; verification requires `--evidence`.
Enable the gated subprocess replay with `ITB_EXACT_EXE` and private runtime
`PYTHONPATH`. The input executable SHA-256 remains
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Published receipts contain only normalized witnesses and synthetic inputs.

Independent native-contract review: **GO**. The enclosing construction owner,
exceptional behavior and whole-game accounting remain separate work.
