# Tree lower-bound leaf

The call-free leaf at RVA `0x002e8290` has 97 bytes and 44 instructions.
Its static lineage is pinned from the existing helper-chain receipt through
`0x002eb19a → 0x002e81f0`, then independently verified at the insertion
owner's call site `0x002e81ff → 0x002e8290`. This records static reachability;
it does not compose or prove the insertion owner's behavior.

The leaf compares NUL-terminated node keys with a query as unsigned bytes.
If a node key is below the query, it follows the right child. Otherwise it
records the node as candidate and follows the left child. It stops at a
node whose sentinel byte is nonzero, returning the candidate or head.

The bounded structural contract permits finite rooted binary trees of at
most 31 nodes, with no sharing or cycles, and readable stable keys of at
most 64 bytes before their terminators. Node, key, query and protected frame
storage are disjoint. The minimum-lower-bound interpretation additionally
requires nondecreasing inorder keys. Under that premise the result is the
first inorder node with key at least the query, including duplicate keys.
Unordered fixtures retain only the structural traversal claim.

## Register and access details

EAX returns the candidate address or head. EBX, EBP, ESI and EDI restore;
`RET 4` advances entry ESP by eight. For a nonempty tree, ECX is the final
node-key comparison cursor and DL is the last compared node byte, with
EDX's upper 24 bits preserved. The two-byte comparison advances both
cursors before testing an equal NUL in the second position, but does not
advance after an equal NUL in the first position.

An empty root reads neither the query argument nor the query string, saves
no EBX, and preserves entry ECX and EDX. The memory-shaped NOP reads no data.
Final arithmetic flags come from comparing the terminal nonzero sentinel
byte with zero: CF/OF/AF/ZF are zero; SF and PF reflect that byte's sign and
parity. The native replay also starts with DF set and checks it unchanged.

## Evidence and limits

The normalized graph model checks 2,904 cases: 2,544 ordered and 360
unordered. Exact Unicorn 2.1.4 replay checks 5,808 cases: 5,088 ordered and
720 unordered. Both cover all 44 sites, and both independent reviews passed.
The corpus includes empty/single trees, balanced and skewed trees, duplicates,
unsigned high bytes, odd/even NUL positions, long common prefixes and a
31-node chain with 64-byte keys. Replay covers all 16 frame alignments and
sentinel bytes 1, 128 and 255.

The independent replay oracle uses byte-string ordering and a separate
inorder minimum check. It checks all general registers, defined arithmetic
flags, ordered node/query/stack accesses, and complete mapped pages including
padding. Three semantic mutations are rejected; replay separately rejects
an unsigned-comparison carry mutation and an upper-EDX clobber. Query storage
is left unmapped for empty trees. No allocator, callback, balancing function
or parent instruction executes. This is not a whole-tree-library proof or
global accounting promotion.

## Reproduction

`scripts/itb_native_tree_lower_bound_semantics.py` takes `--chain` and
`--program-facts`; its conformance counterpart takes `--semantics`. Both
support `build`, `verify` and `verify-structure`. Exact commands require
`--executable`; verification requires `--evidence`. Output is deterministic
UTF-8/LF JSON written through binary stdout on Windows.

`tests/test_itb_native_tree_lower_bound.py` checks independent minimum,
duplicate, unsigned-byte, cursor, empty-tree and invalid-premise cases,
receipt integrity and gated exact CLI rebuilds. All 47 tests passed, including
both exact CLI rebuilds. Set `ITB_EXACT_EXE` and
the private `.local_decompile/fill_runtime` on `PYTHONPATH` for exact checks.

Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_tree_lower_bound_semantics.json`: canonical
  `6ea805600da016000532aa0a0da90ec08d598bc53e1778fe241beeed6afeeca9`;
  raw `06e62158b0beec225c2256eaf70eac4a4a8ce37425149af5d2ce250cf4079915`.
- `native_tree_lower_bound_conformance.json`: canonical
  `e45e0ce4ccc42f13ddb3464be09fa3c2146deacfb0c4b738b557e34bc0a9e731`;
  raw `8a9fb9eb800671ca1935dcf848f6631f01fc8d64beecc9dcbe9124fdec0fa691`.
