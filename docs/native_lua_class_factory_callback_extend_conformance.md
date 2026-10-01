# Actual factory receiver with mixed second-source keys

This composition retains the actual factory output and verified first callback
return, then supplies a second source with existing and new keys. The native
callback and its class, tree, vector, marker and table helpers run continuously
within each invocation. The host boundary remains explicit.

The first source has three nodes, inserted into the actual empty destination.
Its keys are either `0,1,16` or `1,16,255`; source insertion order is reversed.
The positive profile changes only the supplied first-source key bytes by a
monotonic mapping, before executing the first callback. It keeps source node
IDs, topology and payloads. Actual factory names and receiver storage survive.

The second source has one, three, five or seven nodes depending on its recipe.
Its recipes exercise interior insertion, a new minimum, insertion beyond the
maximum, existing payload updates and omitted existing key 16. Native final
unions contain at most eight nodes. The independent pure model supports two
sources of up to seven nodes each and a destination union of fourteen; that
larger logical bound is not a native coverage claim.

Before rebinding, all eight captured GPRs and the page digest must match the
verified first observation. A separate check derives the first destination
from the pure model and checks actual retained links, colors, nil flags, key
pointers and payloads, plus every original key string. It also checks captured
GPRs against the first modeled return, all receiver words, sentinel links and
marker/padding bytes, and the old record. Coordinated capture
mutations with refreshed page digests must still fail this independent check.
Capture is accepted only after the first callback's full native checks pass.

The host patches named source head/node bytes and query strings. It preserves
all current receiver, sentinel, old vector, destination node and original key
bytes. Original destination key pointers still refer to storage at
`0x1c000fff + 32*i + 3`; every second query uses separate storage at
`0x1d000fff + 32*i + 3`. Generated fixture pages never replace captured pages.
Source object/head and node storage remain at `0x14000000`, `0x14000100` and
`0x14001000 + 64*i + 31`.

First destination nodes are native allocations at DATA+`0x11f`, with 32-byte
spacing. New second-call nodes start at DATA+`0x41f`; the sixteen-byte vector
starts at DATA+`0x1000+a`. Both ranges are disjoint from retained destination
nodes and the old eight-byte vector at DATA+`0x2000+a`. The shared prefix now
uses its existing fixture node base plus allocation ordinal; the default
address schedule is unchanged and collision/extent checks precede insertion.

Native insertion preserves existing logical IDs and appends new IDs in sorted
source visitation order. Independent checks compare each copy's source ID,
key, destination address, insertion mode and payload. They also check retained
key pointers, omitted payloads, final sentinel links, U+56 union count,
thirteen preserved receiver DWORDs and sentinel bytes 12 through 23. New tree
allocations request 24 bytes; vector growth requests 16 bytes, copies the
actual retained record, frees the old allocation and appends `[0,A]` again.
Heap entry/response GPRs and defined flags, normal class/full ABI, complete
mapped pages, ordered memory events and identity-bound Lua requests are
checked against their independent models.

The native matrix contains 864 cases: 18 producer recipes, three
vector alignments, two first-key profiles, four second-source recipes and two
table-transfer profiles. Source node alignment is fixed at 31. The first
callback must retain the predecessor's three-node family's 701-site union.
Both callbacks use the actual retained cookie and previous SEH bytes.

Source-word, registry references, transfer contents and invocation frames are
explicit host premises. Successful allocations, free response and retained
freed bytes are conditional host responses. Real Lua VM/metamethod effects,
allocator failure/reuse, ownership invalidation, more than two callbacks,
other source recipes and whole-program accounting remain open. No accounting
promotion is made.

The independent model's **317 tests pass** and its read-only review is **GO**.
The native build passes all 864 cases and 40 controls. Its 1,115 selected
sites contain 881 executed sites in 2,905 unique bytes: 76 callback,
707 class-operation, 27 marker and 71 table sites, with 234 excluded.
First callbacks execute the predecessor three-node family's 701-site union;
second callbacks execute 864 sites.

Totals: 573,120 factory, 1,305,504 first-callback and 1,599,804 second-callback
instructions; 29,376 factory and 70,848 callback Lua requests; 864 factory,
3,456 first-class and 2,916 second-class allocations. There are 2,592 first
inserted nodes, 2,052 second inserted nodes, 756 existing payload updates,
2,808 second source copies and 4,644 final nodes across the matrix. Vector
growth copies 6,912 old bytes, allocates 13,824 new bytes and frees 864 old
allocations. Marker/table calls total 3,456 each; assignment requests total
1,728. Each callback retains five modeled Lua values and returns zero results.

Forty controls include 33 runtime boundary corruptions, native cookie failure,
two capture identity mutations and four retained-node/string mutations with
refreshed capture digests. The latter reject before second host binding.

Receipt: [sealed JSON](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_callback_extend_conformance.json).
Canonical SHA: `c0cc89b3af1cecb03d752cf7e17fde6c621631bcbb43046475124609bd589797`.
File SHA: `c1997e061f2f161538ec5dc953a185a251585b6affff078115e3c1a701c447e8`.
Deterministic UTF-8 LF size: 590,914 bytes; 32 strictly pinned source receipts.
The CLI supports build, exact verify and PE-free structure verification.
The complete gate passes **453 tests, no skips**: 317 extension model,
81 new conformance and 55 predecessor repeat conformance. New native build
and exact verification, and predecessor repeat build/verification, are
byte-identical to their sealed receipts. Independent review: **GO**. All
thirteen protected user files retain their baseline hashes.
