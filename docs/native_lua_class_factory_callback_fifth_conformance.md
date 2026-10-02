# Fifth callback with retained SIMD machine state

The actual factory receiver passes through five separately invoked native
callbacks on the same retained pages. Each callback executes continuously
through its marker helpers, class operation, Lua request suffix, cookie and
normal return. Host invocation boundaries remain explicit.

The fifth operation starts with four live records and capacity four. It
requests48, copies32 through the retained-feature short MOVDQU path, supplies
successful free of the old32, appends the external [0,A] record and finishes
with five live records and capacity six. The fresh vector is DATA+0x2800+a;
the old fourth vector is DATA+0x3800+a. The earlier8/16/24 records and old32
remain intact under the supplied free-response premise. The new spare8 bytes
retain their actual captured values.

Every producer reads all eight XMM registers, eight GPRs, full EFLAGS and PC
at actual fourth entry and return. The finite predecessor state has zero XMMs
and flags0x246. These are checked observations. Captured pages must match both
the verified fourth observation and an independent complete-page oracle before
host binding. Direct laws separately check U72, P24, eight retained destination
nodes, source nodes and both key regions, old vectors, FS, cookie and feature
page. The [logical fifth model](native_lua_class_factory_callback_fifth_semantics.md)
separately checks all17 inputs, detached predecessor packets, U13/P24, routing,
full48/spare8, stack exclusion and both normal returns.

The binder deep-copies the captured pages and changes exactly36 declared
bytes: eight caller bytes and seven DWORD source payloads. Every patch has
independently checked before/after values; complete replay must equal the new
fixture. One producer profile keeps source payloads unchanged and the other
complements them. Neither changes topology or keys. Seven existing-key routes
update the retained destination, while omitted key16 keeps its payload.
No fifth tree allocation occurs.

An explicit factory-only adapter binds the exact source7/destination8 and
full4/cap4 geometry to the independently checked
[standalone SIMD class join](native_lua_class_simd_vector_return_conformance.md).
It cannot construct a replacement fixture. Optional callback machine transport
checks all eight XMM registers and clear DF at callback/class entries,
growth/resize/copy boundaries, supplied heap and Lua responses, class return,
cookie failure and full return. The copy return independently checks all GPRs
and defined flags. XMM0/1 equal the two captured old32 halves; XMM2..7 survive.
Supplied APIs preserve XMMs as an explicit premise.

Only the four selected MOVDQU sites permit wide hooks, represented as two
ordered eight-byte halves per instruction. Exact read/write address pairs,
direction, values and full ordered memory events remain checked. All final
mapped bytes must agree with the independent oracle. Default receipts omit
the optional SIMD fields, and the builder checks every first-through-fourth
observation hash and executed-site set against the sealed predecessor.

The216 cases cover the fourth corpus's eighteen producer recipes, three
vector alignments, two first-key profiles and two transfer profiles. There
are1,080 callback invocations. First-through-fifth site sets contain
701/864/546/548/553 sites; their union contains900 of1,134 selected sites in
2,973 unique bytes. Partition:76 callback,726 class operation,27 marker,
71 table and234 excluded sites. The actual factory and first four callback
observation hashes remain identical to the pinned fourth receipt.

Fifth totals:532,440 executed instructions,216 allocations of48,216 frees
of old32,1,512 existing-key payload updates,6,912 copied bytes,8,640 final
live bytes,10,368 capacity bytes and1,728 preserved spare bytes. Every fourth
entry and return is machine-captured,216 each. The native SIMD hooks record
864 wide reads and864 wide writes. Across five callbacks there are44,280
Lua requests,864 frees,2,160 marker and table calls each, and1,080 assignment
requests. No opaque native instructions or accounting promotions are used.

All164 controls reject for their intended reasons:39 native callback/heap/
SIMD corruptions, one cookie-failure frontier, two stale capture identities,
28 fourth boundary mutations,84 refreshed-digest retained-byte mutations,
two strict allocation/free type mutations and eight host-patch mutations.
Coordinated digest or page/patch changes cannot authorize changed retained
state. Cookie mismatch stops before failure-handler execution.

Receipt: [sealed JSON](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_callback_fifth_conformance.json).
Canonical SHA: `92dea33a6ca68214a08f9056ef1d6abb0ed7f6450fec789bcb85a2677db70255`.
File SHA: `11b70e8b0ee7e061ed4642d4ea1b20d5b57137f65f05ec8d41a531383c190226`.
Deterministic UTF-8 LF size:392,703 bytes;45 strictly pinned source receipts.
The CLI supports build, exact verification and PE-free structure verification.
The new conformance gate passes197 tests without skips, including twelve
isolated native producer boundaries, capture/host/adapter corruption checks,
all native controls and exact CLI rebuild/verification/structure. The
standalone SIMD class gate passes130 tests unchanged,327 combined without
skips. Fourth callback exact rebuild, verification and structure gates
reproduce its unchanged359,299-byte receipt after the shared plumbing changes.
Independent final source/test and published receipt reviews are GO.

This finite proof excludes a sixth callback, other source/key domains, actual
Lua VM table effects, heap ownership and invalidation, allocator reuse/failure,
exception delivery, hardware execution and whole-program accounting. The full
game remains unfinished.
