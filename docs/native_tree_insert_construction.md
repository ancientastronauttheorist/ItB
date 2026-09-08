# Native insertion prefix through node construction

The insertion owner now executes lower-bound search, its existing-key decision,
and successful native node construction. Existing keys return normally; the
construction path stops before insertion-hint CALL `0x002e826b`. The new node
has not yet been linked into or rebalanced within the tree. Only a successful
HeapAlloc response is supplied; allocation retry, heap wrapper, initializer and
factory instructions run natively.

The independently sealed decision state becomes the factory input. Factory
entry N=O-36 reaches heap API O-96 and returns at ESP O-20. The complete factory
stack oracle is explicitly rebased to this owner's stack mapping, and its caller
return event is replaced with `0x006e825f`. Full stack and allocation images must
match after the rebase.

The factory's second argument is the address O-8 of the owner's local query
argument. Reading that local and then its pointee yields the **query pointer**,
which becomes the node's key field at offset 16. It is not the query's first
DWORD. Three head links and the two-byte header are initialized, padding bytes
14–15 remain unchanged, and payload offset 20 is zero. Empty trees now receive
real mapped query-pointer storage because construction needs that key chain.

Before the hint call, four arguments are prepared in ascending stack order:
result slot O-8, candidate, node key-field address and new node. ESP is O-36;
EAX is O-8, ECX the tree and EDX node+16. Final arithmetic flags come from
ADD(node,16), including defined AF, rather than the factory's preceding TEST.
Existing returns retain the decision proof and consume two arguments at O+12.

Unicorn 2.1.4 matches 3,630 cases across two owner frames, three sentinel bytes
and five node alignments. There are 780 existing returns and 2,850 construction
frontiers, each construction supplying one heap response. The replay loads 452
instruction bytes and 198 static sites, executing 175 sites, including all
owner-prefix, lower-bound, factory and initializer sites. Complete ancestor,
allocation, output, tree, key, global and import storage, ordered accesses,
registers and defined flags agree. Corruption controls cover unread ancestor,
tree padding and allocated-node padding. The padding control explicitly selects
an allocation case. Independent review passed. Focused tests include exact CLI
rebuilding.

Actual heap effects, failed allocation, hint execution and tree topology mutations
remain outside this proof. Stable existing returns imply key equality; sorted
inorder keys additionally justify global minimum and absence guarantees. No
whole-program accounting promotion occurs.

`scripts/itb_native_tree_insert_construction_conformance.py` accepts the decision
source flags plus `--decision-conformance` and `--factory-conformance`, with
`build`, `verify` and `verify-structure`. Exact commands need `--executable`;
verification needs `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_tree_insert_construction_conformance.json`.
Canonical SHA-256:
`9b81311ccbef89af7e789b491776f9930e3d7ae23e437db71bdba8d9033ad599`.
Raw SHA-256:
`facf6e0a4e727ee599a4d9d1bc0f45b5d515c2057b5da18090dd1a569f23c5b7`.
