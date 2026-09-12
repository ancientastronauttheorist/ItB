# Native successor traversal and return

The call-free successor at RVA `0x0006df30` now has native replay against its
previously sealed structural specification. All 79 instruction bytes and 31
sites execute across 972 cases, including sentinel no-op, right-subtree descent,
and parent ascent. The new address-generic oracle accepts an actual node graph,
byte map, iterator slot, return frame and entry registers for caller composition.

Native traversal may write the iterator slot repeatedly while climbing right
children. Its final result agrees with an independent structural inorder walk,
and every intermediate slot write agrees with the sealed specification.
Sentinel entry leaves the slot unchanged. Final EAX and EDX name the slot;
ECX follows the actual descent/ascent cursor, nonvolatile registers preserve,
and ESP advances four. Final arithmetic flags come from a byte comparison with
zero or the last 32-bit child/parent-right comparison, as the actual path requires.
Both DF states preserve.

The domain requires a finite consistent tree with one nonzero sentinel byte,
disjoint node records, separate iterator/return words, mapped reads and a
nonwrapping return frame. Node byte descriptions must agree with the supplied
memory. The oracle rejects cyclic, inconsistent, aliased or unmapped inputs.
No key ordering or red-black balancing is inferred from structural traversal.

The corpus varies six shapes, every node including the sentinel, three node/slot
alignments, three stack alignments, register seeds, two sentinel bytes and both
DF values. An added shape exercises repeated left descent inside a right subtree.
Complete mapped pages, ordered accesses, registers and flags agree. Three
corruption controls protect unread ancestor bytes, node padding and the final
iterator value. No opaque instruction or callee response is supplied.

Independent native-contract review: **GO**. Focused tests: **29 passed**,
including exact CLI reproduction. The generic oracle is ready for the
class mutation loop's successor call at `0x002eb1ab`; that caller composition is
separate work. No whole-program accounting promotion occurs.

- [Implementation](../src/observatory/native_lua_tree_successor_conformance.py)
- [CLI](../scripts/itb_native_lua_tree_successor_conformance.py)
- [Tests](../tests/test_itb_native_lua_tree_successor_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_tree_successor_conformance.json)

Canonical SHA-256:
`f1429d740a09a4c46d0cec2f4049bb684f44d358ad24dd5ac51774a0ac554422`.
Encoded SHA-256:
`7a8ecba10be74eb20c53e133478e717095a0eda63ee1a26e133ed4468376c40d`.

Use `build`, `verify`, or `verify-structure` with `--semantics`. Exact operations
require `--executable`; verification requires `--evidence`. The exact CLI test
uses `ITB_EXACT_EXE` and the private Capstone/Unicorn runtime via `PYTHONPATH`.
Hardware execution, arbitrary malformed graphs and the enclosing Lua/game
behavior remain outside this receipt.
