# Native 24-byte tree node factory

Factory RVA `0x0007cd90` now executes initializer `0x0007d060`, allocation
retry and the heap wrapper through one supplied successful HeapAlloc response.
The ordinary domain supplies an independent positive writable 24-byte block.
Tree-head storage, the key pointer chain and the complete ancestor are disjoint.
No vector capacity or alignment wrapper is involved: the request is exactly 24.

For factory entry N, initializer entry is N-8, retry N-24 and the heap API
N-60. Retry returns through this initializer's continuation `0x0047d06b`.
Original ESI remains live until allocation returns. The native thunk and wrapper
write and read their saved frame words in the observed order. All stack events
are compared with a fresh independent runtime success oracle.

Initializer reads the tree head three separate times and writes three DWORD
links at offsets 0, 4 and 8. Factory clears only the WORD at offset 12: **bytes
14 and 15 retain their original allocated contents**. It reads its second
argument, dereferences that pointer twice to obtain the key word, writes the key
at offset 16 and zero at offset 20. First and third arguments are never read.
RET 12 consumes all three arguments, finishing at N+16. Final EAX is the node,
EDX the node plus 16 and ECX the key; nonvolatile registers are restored.
Defined flags come from TEST(node+16), with AF unspecified and DF clear.

Unicorn 2.1.4 matches 2,304 cases across 32 block alignments, four stack
alignments, three head words, three key words and two register seeds. The replay
loads 232 instruction bytes and 96 sites and executes 73 sites, including all
39 factory and initializer sites. One heap API response is supplied per case.
Full allocation, ancestor, tree, key, global and import pages are verified, as
are ordered accesses and registers/flags. Mutations to an unread caller argument
and to preserved padding fail at their intended memory checks. Independent
review passed. Focused tests include exact CLI rebuilding.

Null or wrapping returned pointers, arbitrary aliases, retries/failures, actual
heap effects and insertion/topology changes are outside this successful proof.
No whole-program accounting promotion occurs.

`scripts/itb_native_tree_node_factory_conformance.py` provides `build`, `verify`
and `verify-structure`, taking `--program-facts` and `--allocation-conformance`.
Exact commands require `--executable`; verification requires `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_tree_node_factory_conformance.json`.
Canonical SHA-256:
`8b1c632e4c818a06e1083d82fce3aabdbdc7a10046c9567f0a6bd59de29d339c`.
Raw SHA-256:
`72e067e25176b4e5a22315356e1605903ae220c6f8c9904101e4e1108830e977`.
