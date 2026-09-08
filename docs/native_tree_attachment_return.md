# Native attachment with black-parent return

The bounded path executes attachment at `0x0007d0a0`, the parent-color check
at `0x0007d0f5`, and return tail `0x0007d280` through `0x0007d294`.
The latter two ranges contribute 35 bytes and 13 sites to the sealed
85-byte/35-site attachment prefix. All 48 loaded sites and 120 bytes execute
across the selected corpus. No callee or opaque instruction executes.

Only empty-tree insertion and left/right attachment to a single root are
selected, with parent color 1 or 255. Color 1 is the ordinary black encoding;
255 is a numeric nonzero-branch case, not a claim of a valid red-black tree.
Both DF values, three node alignments and two frame alignments produce 72
cases. Red-parent balancing, rotations, count failure and general red-black
invariants remain outside this proof.

The independently sealed attachment oracle supplies the prefix state. Fresh
ordered tail equations read the new node's parent and its color, read the
head and current root, force that root's color byte to one, then write the
new node through the result pointer at entry stack plus four. For an empty
tree the new node is the root. Every byte of the complete ancestor, topology,
node and result pages, including padding, is checked. Result storage is
explicitly mapped and disjoint; unused consumed arguments remain protected.

EAX returns the result-slot address, ECX names the parent, EDX and ESI preserve,
and the other nonvolatile registers restore. RET 20 finishes with ESP equal
to entry plus 24. Final arithmetic flags come from CMP8 of the nonzero parent
color with zero; DF preserves. Ancestor and node-padding corruption controls
must fail their intended full-memory checks.

The conformance CLI accepts `--program-facts` and `--attachment` with `build`,
`verify` and `verify-structure`. Exact commands also require `--executable`;
verification requires `--evidence`. Output is deterministic UTF-8/LF JSON.
The focused test file is `tests/test_itb_native_tree_attachment_return.py`;
set `ITB_EXACT_EXE` and private `.local_decompile/fill_runtime` on `PYTHONPATH`
to enable the exact CLI rebuild. All 15 focused tests passed, including that
rebuild; the exact verification command also passed. Independent read-only
review passed. No game, hardware or global-accounting
completion is claimed.

Published receipt:
`windows_build_13725832_31fe35265598_native_tree_attachment_return_conformance.json`.
Canonical SHA-256:
`83b9768de14bc2b8d4e79a63e229f50fb1089d34a294867feea18543c20f7f1d`.
Raw SHA-256:
`87c2507184204304c6a9cd9e01c0edf0670b3c9089f78dfb38a6c3ad031abc36`.
