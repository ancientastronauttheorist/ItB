# Call-free tree successor

The exact Windows executable helper at RVA `0x0006df30` occupies 79 bytes
and 31 decoded nodes. Its independent specification advances a node held in
an iterator slot to its inorder successor. The caller edge is pinned by the
existing class-return helper chain. This is a bounded structural proof;
container identity, key ordering and balancing are not inferred.

ECX supplies the slot pointer. Nodes have left, parent and right pointers at
offsets 0, 4 and 8, and a sentinel byte at offset 13. A sentinel start leaves
the slot unchanged. A non-sentinel right child leads to the leftmost node of
that subtree. Otherwise the helper climbs parents, writing each intermediate
ancestor while climbing from a right child, then writes the first qualifying
ancestor or sentinel. EAX and EDX return the slot pointer; ESP advances four
bytes through RET. EBX, ESI, EDI and EBP remain unchanged.

The specification accepts at most 128 mapped, disjoint node records with one
nonzero sentinel, one root when nonempty, consistent parent/child links and
finite acyclic topology. The iterator slot and return word must be disjoint
from the tree and each other; links remain stable during this call-free helper.
Malformed, aliased, cyclic or concurrently changed structures are outside this
domain. Rejecting a cycle does not prove native termination on that input.

The integer instruction model is compared with an independent inorder oracle
over 672 cases: balanced, left-chain, right-chain, single-node and empty
fixtures; every starting node including the sentinel; all 16 stack alignments;
and sentinel bytes 1 and 255. All 31 sites are covered. Ordered data reads,
intermediate slot writes and the return-word read are checked. The multibyte
NOP performs no data-memory access. A changed ancestor write fails the semantic
check, and a cyclic topology fails domain validation. This tranche does not
execute the helper on hardware or in an emulator.

Producer: `scripts/itb_native_lua_tree_successor_semantics.py`, with `build`,
`verify` and `verify-structure` commands. Supply `--chain` and `--program-facts`
from the pinned Windows program artifacts; build and verify additionally
require `--executable`, and both verification commands require `--evidence`.
The exact executable is read and decoded, never launched.

Published receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_tree_successor_semantics.json`.
Canonical SHA256:
`4d03a8bfc8ef34f5c700e7d5aa8a8a1a81967978a80d284b9342201c961ba7fd`.
Raw UTF-8/LF SHA256:
`552515f52dbbd4ac323e0b896c975ce20bbe2444abeaa3300e92596982ba8592`.

Validation: 19 focused tests passed with `ITB_EXACT_EXE` set, including a
subprocess CLI rebuild that reproduces the published bytes. Independent
semantic review passed. No atlas accounting promotion is made.

Next: compose this iterator with the owner prefix at `0x002eb140`, which still
depends on insertion at `0x002e81f0`. Source/destination aliasing and mutations
during traversal require explicit lifetime and finite-traversal premises.
Real growth at `0x002eb620` and the owner epilogue remain separate open work.
