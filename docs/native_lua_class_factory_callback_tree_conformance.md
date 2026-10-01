# Actual factory receiver through nonempty-source callback return

The actual aligned factory output now accepts a supplied nonempty source tree
and reaches the returned callback's normal return. Both native marker helpers,
tree insertion and balancing, successor traversal, first-null vector growth,
two filtered table transfers and the callback epilogue run continuously in one
x86 machine. The factory runs first; closure invocation and source construction
remain explicit host premises.

Implementation: [native conformance](../src/observatory/native_lua_class_factory_callback_tree_conformance.py)
and [independent model](../src/observatory/native_lua_class_factory_callback_tree_semantics.py).
This extends the [empty-source full return](native_lua_class_factory_callback_return_conformance.md).

## Source adapter and preserved producer state

The finite matrix combines eighteen aligned producer profiles, three vector
alignments (0, 7, 31), source populations 0, 1, 3 and 7, three node alignments
(0, 7, 31), and two table-transfer recipes. The destination begins with the
factory's actual empty sentinel P=`0x10000100`; U=`0x0fffffcc`, U+52 points to
P, and U+4/8/12 are initially zero. No replacement destination is installed.

Source keys are prefixes of `[0,1,16,255,0x80000000,0xfffffffe,0xffffffff]`,
inserted into the supplied source in reverse order. Native traversal visits
unsigned keys in ascending order. Source insertion IDs differ from destination
insertion IDs: the independent model checks each copied payload's routing,
new node address, tree count and final sentinel links. The first destination
insertion uses the empty-tree path; subsequent ones use the end-insertion path.
This does not cover arbitrary destination insertion orders or every balancing arm.

Source object/head remain `0x14000000` and `0x14000100`; source nodes start at
`0x14001000` with a 64-byte stride plus the selected node alignment. Key bytes
are eight lowercase hexadecimal ASCII digits and NUL, relocated to
`0x1c000fff + 32*i + (node_alignment % 4)`. The first zero-alignment key crosses
a page boundary. This storage is disjoint from the retained factory name page.
Named source-link, node and key patches are written onto captured producer
pages; missing pages are added with explicit synthetic fill. Generated source
fixture pages never replace actual producer or running-parent pages.

The adapter obtains the security cookie and previous FS registration from
actual retained producer bytes. In particular, profile one's FS value is not
the older fixture's default. The actual receiver's 72 bytes and sentinel's
24 bytes remain unchanged at host entry. All unmentioned producer bytes survive
that boundary; subsequent native scratch writes are checked independently.

## Native and logical boundaries

The class helper copies source entries into newly allocated 24-byte nodes,
updates U+56 and P's root/leftmost/rightmost pointers, then allocates an
eight-byte vector and appends the original pair `[0,A]`. The callback copies
A's first word into U+0 and performs both table-transfer request streams.
Final mutable receiver offsets are 0, 4, 8, 12 and 56. The thirteen other
receiver DWORDs and P bytes 12 through 23 retain captured producer values.
Source bytes, keys, names, references, context, global/FS pages, callback
ancestors and the original pair are also checked through complete page equality.

The runtime compares actual ordered memory events and all mapped pages with a
physical composition, then compares sentinel links, source/destination IDs,
payloads and allocation partition with the independent model. Each case has
one 24-byte allocation per copied node followed by one eight-byte allocation.
Tree heap entry checks the exact request, EAX insertion-result pointer T-104,
ESI=24, EBP=T-172, ESP=T-192 and defined TEST flags. Vector heap entry retains
the predecessor's checks of all eight GPRs and its T-188 frame. Allocation
response identities are checked at the native continuation.

Lua requests retain the actual produced userdata and supplied source identities.
The twelve-request prefix and both table streams have independent token-stack
checks. The two recipes use empty streams or both filtered category orders;
`init`/`finalize` are skipped and `other` requests assignment. Five modeled Lua
values remain before zero-result return. This establishes conditional requests,
not real VM table or metamethod effects.

Normal return preserves incoming EBX/ESI/EDI/EBP, sets EAX=0, restores the
captured cookie to ECX, uses the supplied final-table EDX response law, and
returns to the supplied host endpoint with ESP=T+4 and defined flags `0x44`
under mask `0xcd5`. The class helper's zero-length old-vector copy leaves EDX=0
at its own return. Source-independent suffix contract checks reject coordinated
request/stack corruptions even when two composed packets would agree.

## Evidence and limits

The seal contains 1,296 cases, 1,062 selected sites in 2,746 unique bytes,
and 713 executed sites: 76 callback, 539 class-operation, 27 marker and 71 table
sites. The remaining 349 sites are excluded. Source-size families execute
368, 572, 701 and 713 sites respectively. Totals are 859,680 factory and
1,866,564 callback/helper instructions; 44,064 factory and 53,136 callback Lua
requests; 1,296 factory allocations, 3,564 tree allocations totaling 85,536 bytes,
and 1,296 eight-byte vector allocations. There are 2,592 marker and 2,592 table
helper calls, 1,296 assignment requests and no frees. All 29 controls pass.
The empty-source coverage union must equal the sealed predecessor's
368 executed sites; additional sites belong to the nonempty class operation.
Parent assertion/error paths remain excluded. Tree-request, tree-register and
tree-flags controls extend the predecessor controls; native cookie failure
still stops before its handler executes.

The source tree, word and registry references remain supplied host state.
Real Lua invocation/registry/metamethod behavior, allocation failure, arbitrary
pointer domains, heap ownership, handler delivery and whole-program accounting
remain open. No accounting promotion is made.

Receipt: [sealed JSON](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_callback_tree_conformance.json).
Canonical SHA: `a924cb10e338afa823ced7bf0fb3de20e8b8bb4b1e962fdcc299fec2f2b77614`.
File SHA: `0d73e76a3be7e1a3b51d4be8662936a1e310d65f5c7924e0fb7eaac0cc5f0555`.
Deterministic UTF-8 LF size: 692,724 bytes; 26 strictly pinned source receipts.
The CLI supports build, exact verify and PE-free structure verification.
Validation: **366 passed, no skips**: 262 independent model, 63 new
conformance and 41 predecessor full-return tests. The new native build and
exact verify are byte-identical to the seal; the older 324-case factory callback
return also rebuilds and verifies unchanged. PE-free structure checks pass.
Independent semantic review: **GO**. All thirteen protected hashes matched.
The broader seven-node pure model is conditional logic, not additional native
coverage beyond the frozen matrix.
