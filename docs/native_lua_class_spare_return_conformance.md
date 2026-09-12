# Native class operation with external spare-capacity append

The bounded class operation now runs from owner entry `0x002eb140` through
native tree copying, an external-argument vector append with spare capacity,
the cookie epilogue and the real caller return. All insertion, comparison,
predecessor, balancing and successor calls execute natively. The only supplied
responses are successful HeapAlloc results for new tree nodes.

The tree phase retains its independently verified key/payload union. The vector
phase appends the unchanged two-word argument record, then advances the end
pointer by eight. The corpus places the external argument both below and above
the vector, checking the different ordered reads used to classify it. Existing
vector bytes, spare neighbors, source trees and strings, destination padding,
globals and the complete ancestor remain protected.

## Return contract

For owner entry `O`, frame `F=O-4` and loop/suffix ESP `F-32`, the append reads
receiver+8, checks capacity, reads the destination end again, copies argument
words in order and performs the end-pointer read/modify/write. It does not call
vector growth. The return oracle uses the actual stack base and caller address.

Final EAX is the second argument word (the source object), ECX is the cookie,
and EDX retains the tree-prefix result. EDI, ESI, EBX and EBP restore their entry
values. Native RET4 finishes at ESP `O+8`; arithmetic flags are `0x44` and DF is
clear. Every nested hint registration has already restored its incoming FS state.

A separate negative control changes the cookie only at the final class CALL
`0x002eb222`, after all nested hint checks. It verifies the exact mismatch frontier
`0x003574d5`, ESP `F-24`, mismatch flags, register state, ordered access prefix and
all protected memory. It stops before the failure implementation.

## Evidence

1,152 cases combine the 192 tree-prefix cases with two external buffer placements
and old vector sizes zero, one and three. Capacity contains at least one spare
record. The cases perform 3,024 tree iterations, with 1,584 allocations and
1,440 existing-key overwrites. Maximum loop length is seven.

The replay loads 1,747 bytes and 679 sites, executing 607. All 26 newly selected
spare-append/return sites (62 bytes) execute. This does not claim internal-argument,
vector-growth or assertion branches. The independent model checks the entire
tree result plus appended record and final end pointer. Six controls cover the
ancestor, source, destination payload, vector, iterator and cookie boundary.
Independent reviews: **GO**. Focused tests: **21 passed**, including exact
CLI reproduction.

- [Implementation](../src/observatory/native_lua_class_spare_return_conformance.py)
- [CLI](../scripts/itb_native_lua_class_spare_return_conformance.py)
- [Tests](../tests/test_itb_native_lua_class_spare_return_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_spare_return_conformance.json)

Canonical SHA-256:
`9b6b20f247d5327476bc4b79caf7a5849248c6d07a332d80ff20c34f1127c8c7`.
Encoded SHA-256:
`6819e7b2a667354e7ea677d52c97137e3dd1c94bc383b9a1f1ac3dde6e724241`.

The CLI takes `--program-facts`, `--prefix`, `--append-semantics` and
`--class-return`; it supports `build`, `verify` and `verify-structure`.
Exact operations additionally take `--executable`, and verification takes
`--evidence`. Exact CLI tests use the private runtime and `ITB_EXACT_EXE`.

Vector growth, internal argument reuse, assertion failure, allocation failure,
actual heap implementation, aliased source/destination trees, arbitrary strings
and Windows exception delivery remain outside this normal-return corpus.
Whole-program accounting promotions remain zero.
