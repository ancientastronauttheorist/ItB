# Native insertion decision through lower-bound search

The insertion owner prefix at RVA `0x002e81f0` now executes the native lower-bound
leaf and its own candidate comparison. It either writes an existing-node result
and returns, or prepares the three arguments for node construction and stops
before CALL `0x002e825a`. No allocation or tree mutation is executed here.

For owner entry O, lower-bound enters at O-28 and saves as deep as O-44. Its
initial EBX is the tree pointer, EDI the output pointer, EBP O-4 and ESI the
owner's original ESI. The independently sealed lower-bound oracle is rebased
with those registers and real continuation `0x006e8204`.

A head candidate selects construction immediately. Otherwise the owner compares
query bytes with candidate-key bytes, opposite to the lower-bound leaf's order.
A smaller query selects construction; equality returns the candidate. Stable
lower-bound traversal only selects candidates whose keys are at least the query,
even on unordered trees. Thus **every existing return implies key equality**.
Sorted inorder keys are needed for global minimum and absence guarantees: an
unordered traversal can miss an existing key and reach construction.

Existing return writes a candidate DWORD and a false byte at output offsets zero
and four, restores nonvolatile registers and finishes RET 8 at O+12. Construction
preparation stores the query-argument address in local O-8, pushes its address
between two dummy ECX words and stops at ESP O-32. ECX again names the tree;
EAX names O-8. A future factory CALL would enter O-36 and reach heap API O-96,
but those effects remain outside this checkpoint.

Flags distinguish the two construction routes: head equality leaves all six
CMP flags defined, while a smaller query leaves TEST(-1) with AF unspecified.
Existing equality leaves TEST(0), also with AF unspecified. DL tracks the final
query byte after the inline comparison, and the candidate key cursor remains
in ECX on existing return. Full ancestor, tree, strings and output pages, ordered
accesses, registers, defined flags and clear DF are checked.

Unicorn 2.1.4 matches 1,452 cases, covering all 94 sites and 203 instruction
bytes across prefix and leaf. There are 1,140 construction frontiers and 312
existing returns. No existing return has a greater query than candidate.
Both unread ancestor and tree-padding mutation controls fail at their intended
full-memory checks. Independent review passed. Focused tests cover unordered
absence limitations and include exact CLI rebuilding.

`scripts/itb_native_tree_insert_decision_conformance.py` accepts `--program-facts`,
`--lower-bound-semantics` and `--lower-bound-conformance`, with `build`, `verify`
and `verify-structure`. Exact commands need `--executable`; verification needs
`--evidence`. No whole-program accounting promotion occurs.

Published receipt:
`windows_build_13725832_31fe35265598_native_tree_insert_decision_conformance.json`.
Canonical SHA-256:
`01dc9252982cac47b67691b2b20e41ea24b41876d07ef05cbbf91625ee6aaeb0`.
Raw SHA-256:
`ffa01d553edfea5070bc34617fb8d7875094abb88a8a92dd8154e858bcefac72`.
