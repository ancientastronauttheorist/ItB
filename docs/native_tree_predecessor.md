# Call-free tree iterator predecessor

The leaf at RVA `0x00071850` contains 94 bytes and 38 instructions, with
no calls. It reads the node through an iterator slot and writes the previous
node back to that slot. A sentinel entry selects the sentinel's right link.
An ordinary node with a left subtree selects that subtree's rightmost node;
otherwise it climbs parents, writing each intermediate ancestor to the slot.
The minimum node reaches the sentinel as a machine-level result; this does
not assert that decrementing a C++ begin iterator is valid.

The domain requires one nonzero-byte sentinel, finite acyclic consistent
parent/child links, stable mapped node records, and a disjoint iterator slot
and return word. Sentinel bytes 1, 128 and 255 are checked. The structural
relation also covers noncanonical sentinel right links. Interpreting a
sentinel-entry result as the inorder maximum additionally requires its right
link to name that maximum, or itself for an empty tree. No key-ordering,
balancing, container-ownership or insertion claim follows.

EAX and EDX return the iterator-slot address; ESP advances four. ECX stays
at the slot on sentinel entry, otherwise it is the final descent node or
climb parent. EBX, EBP, ESI and EDI preserve. All six arithmetic flags come
from the final byte comparison with zero; DF preserves either entry value.
The multibyte NOP makes no data-memory access.

## Evidence and reproduction

The semantic graph checks 14,400 cases, including 13,824 inorder-corollary
cases. Exact Unicorn 2.1.4 replay checks 4,416 cases, including 4,230 with
that corollary. Both cover all 38 sites and 94 bytes, with independent review GO. Eight tree fixtures
include balanced, empty, single, left/right chains and a deeper zigzag.
Semantic cases use all sixteen frame alignments; native replay uses all
sixteen for balanced, single and empty shapes and three representative
alignments for the others. Both DF values and canonical/noncanonical head
metadata are exercised.

The native oracle independently reconstructs every byte/DWORD read and
iterator-slot write, and separately computes a recursive inorder list.
All general registers, defined flags, DF and complete mapped data pages
including padding are checked. A changed ancestor-store source must fail
the ordered-event oracle; a changed return register fails the GPR oracle.
The exact body is verified against program facts and the pinned executable.
The successor receipt provides reviewed topology conventions, without an
invented caller-composition claim.

`scripts/itb_native_tree_predecessor_semantics.py` takes `--program-facts`
and `--successor-semantics`; the conformance script takes `--semantics`.
Both support `build`, `verify` and `verify-structure`, with deterministic
UTF-8/LF JSON through binary stdout. Exact commands require `--executable`;
verification requires `--evidence`.

`tests/test_itb_native_tree_predecessor.py` covers independent inorder
results, intermediate ancestor writes, high sentinel flags, malformed
links, noncanonical heads, receipt integrity and gated exact CLI rebuilds.
All 47 tests passed, including both exact CLI rebuilds.
Set `ITB_EXACT_EXE` and the private `.local_decompile/fill_runtime` on
`PYTHONPATH` for exact checks. Hardware/game execution, malformed or
concurrent storage, insertion composition and global accounting promotion
remain excluded.

Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_tree_predecessor_semantics.json`: canonical
  `52861d984526abd8a5108075fd25d07bf8043ba61de69aa53139e3c70d97b37f`;
  raw `641f99378def5e6f885d99e6a96b362134ae1a818651c11b57b89df046d7558d`.
- `native_tree_predecessor_conformance.json`: canonical
  `be9b0a94dc4cb000ba2e7b87c5167e93b97ba83ca05c5ffe96f246ec7a493694`;
  raw `ea89dc8bfc2f5c89a2efe4b58ae18b3309e2f5387b4159ac1ea11b25722a661a`.
