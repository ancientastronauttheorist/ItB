# Third callback on retained actual factory receiver state

This composition runs three bounded native callback invocations on the actual
factory-produced receiver. It captures the verified second return, retains
current pages and all eight GPRs, then explicitly invokes the callback again.
Each callback and its helpers execute continuously; the invocation boundaries
are supplied host transitions.

The first source constructs three destination nodes. The second source mixes
existing and new keys, leaving an eight-node destination and a full two-record
vector. The third source keeps the second source's exact canonical topology,
keys and IDs, and flips its payload DWORDs. It updates seven existing
destination nodes, preserving omitted key16, all IDs, topology and key
pointers. No third-call tree node is allocated.

Before the third host binding, the captured page digest and GPR packet must
equal the verified second observation. Independent checks reconstruct the
second logical destination and bind all eight physical node addresses, links,
colors, nil bytes, key pointers and payloads. They also check the modeled
full-return registers, all eighteen receiver DWORDs, all sentinel links and
bytes, current two-record vector, original freed record, both original key
storage regions, previous SEH and cookie bytes. Capture is accepted only after
the second callback's native checks and independent routing checks pass.

The host supplies the new invocation frame and changes only named source
payload bytes. It preserves current receiver, sentinel, destination nodes,
key strings, both earlier vector buffers and all unrelated mapped pages.
Generated fixture pages never replace captured pages.

The native growth law is `max(size+1, capacity+capacity/2)`, with integer
division. Full size/capacity two grows to capacity three: request 24 bytes,
copy sixteen actual old bytes, free the old allocation and append `[0,A]`.
The third vector lies at DATA+`0x800+a`; its new mapping contains only DATA
page zero. The old vector lies at DATA+`0x1000+a`, on a disjoint mapped page.
The first freed eight-byte buffer at DATA+`0x2000+a` remains preserved under
the explicit host free-response premise. An unused fresh-node candidate at
DATA+`0x61f` stays separate from the new vector and retained nodes.

Heap dispatch uses the number of tree allocations, since both a tree node
and this vector request 24 bytes. Third tree count is zero. For old size `n`,
capacity `k=max(n+1,n+n/2)`, vector HeapAlloc entry checks all eight GPRs:
EAX/ESI=`8*k`, EBX=`0x1fffffff-n/2`, ECX=U+4, EDX=k, EDI=n and the established
EBP/ESP frame offsets. Defined flags follow `TEST(8*k,8*k)` parity. Free entry
and successful response preserve EBX=n; their other seven registers and
pointer-parity flags retain the sealed free law. Default zero/one-record
behavior is unchanged. Native class/full return, ordered memory events,
complete mapped pages and identity-bound Lua requests remain checked.

The 216 cases cover eighteen producer recipes, three vector alignments, two
first-key profiles and two transfer profiles. Each uses the seven-key second
source and two initial callbacks, followed by the all-existing third source.
There are 648 callback invocations. First/second/third site unions contain
701/864/546 sites; the combined union has 881 of 1,115 selected sites in
2,905 unique bytes. Partition: 76 callback, 707 class-operation, 27 marker,
71 table sites, with 234 excluded. First sites equal the predecessor's
three-node family; second sites remain within its mixed-source proof.

Totals: 143,280 factory, 326,376 first-callback, 710,316 second-callback and
534,816 third-callback instructions; 7,344 factory and 26,568 callback Lua
requests. Allocations: 216 factory, 864 first class, 1,296 second class and
216 third class. There are 648 first nodes, 1,080 second inserted nodes,
432 second existing updates, 1,512 third existing updates and zero third
tree allocations. Final nodes total 1,728. Second/third vector copies total
1,728/3,456 bytes; vector allocations total 3,456/5,184 bytes. The chain
requests 432 frees, 1,296 marker and table calls each, and 648 assignments.
Each callback retains five modeled Lua values and returns zero results.

All 37 controls reject: thirty runtime boundary corruptions, native cookie
failure, two capture identity mutations and four refreshed-digest retained
node/string mutations. Independent synthetic adapter tests additionally
exercise coordinated GPR, receiver, sentinel, vector, FS/cookie and both key
storage mutations before host binding.

Receipt: [sealed JSON](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_callback_third_conformance.json).
Canonical SHA: `2e12f3b7af5475178f0660fbdab0aae7a7478fc684d1ad8f68e8bec7a96a7832`.
File SHA: `f3da47c838db5835c969359dda92143c02bf79179117d98f26330911070e3cbf`.
Deterministic UTF-8 LF size: 348,679 bytes; 33 strictly pinned source receipts.
The CLI supports build, exact verify and PE-free structure verification.
The complete gate passes **380 tests, no skips**: 208 pure-model tests,
91 new conformance tests and 81 mixed-key predecessor tests. New native
build/exact verification and unchanged predecessor rebuild/verification pass.
Independent model, engine and final receipt reviews are **GO**. All thirteen
protected user hashes match their baseline.

The pure destination bound is fourteen, separately from the native eight-node
union. Third source topology, words/references/transfers, invocation frames,
successful allocation/free responses and preserved freed bytes are explicit
premises. New third keys, other recipes, more calls, allocator reuse/failure,
real Lua VM effects, ownership and whole-program accounting remain open.
No accounting promotion is made.
