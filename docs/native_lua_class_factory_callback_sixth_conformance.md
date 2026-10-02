# Sixth callback with retained SIMD state

The actual factory receiver now passes through six explicit host invocations
on retained pages. Each callback executes continuously through its native
helpers, supplied Lua requests and normal return. The sixth operation uses the
fifth allocation: size5/cap6 becomes size6/cap6. It preserves the existing40,
appends the external eight-byte record and fills capacity48 without a heap
request, copy or free.

Every fifth producer captures all eight XMM registers, eight GPRs, full EFLAGS
and PC at entry and return. The entry XMM values are checked against the sealed
predecessor's zero state. Return XMM0/1 are independently derived from the old
four-record bytes; XMM2..7 remain zero. Complete captured pages must equal the
independent fifth oracle. Direct laws also bind U72, P24, source/destination
nodes, keys, old8/16/24/32, current40, spare8, FS, cookie and feature page.
Typed allocation48 and free-old32 packets are checked before reuse.

The binder copies the capture and replays exactly36 declared byte patches:
eight caller bytes and seven source payload DWORDs. Sixth payloads are
complemented for profile zero and unchanged for profile one. Topology, keys,
physical identities and omitted destination key16 remain intact.

A distinct factory spare adapter closes exact25 fixture and20 vector keys.
It constructs no replacement fixture. Independent event laws specify seven
ordered payload writes and the append/end writes, plus the exact19-event
scalar append and cookie-return tail. Earlier tree-prefix reads and callee
scratch remain inherited from the pinned tree/spare oracle. Complete nonstack
pages independently equal the retained baseline with only the permitted writes.
U17/class and U16/normal preservation include the established U13; P24 and
old vector buffers remain intact. The logical model independently supplies
the selected [T-140,T+8) stack exclusion and class EDX=T-60 successor slot.

The separate XMM_SPARE_FACTORY transport preserves all eight captured XMM
values and checks clear DF at parent/class entries, supplied Lua calls, class
return, cookie failure and full return. Supplied API preservation is an
explicit premise. Only scalar memory widths are admitted. Both machine and
receipt guards exclude the complete selected growth/resize/copy bodies; the
receipt also excludes selected allocation/free wrappers from the sixth trace.
Every ordered native access and mapped final byte agrees with the composed
oracle. All first-through-fifth observation hashes/site sets, the factory hash
and prior fourth-boundary hash must match the sealed fifth receipt.

The216 cases produce1,296 callback invocations. First-through-sixth site sets
contain701/864/546/548/553/347 sites. Their union remains900 of1,134 loaded
sites in2,973 unique bytes; partition76 callback,726 class operation,27 marker,
71 table and234 excluded. The sixth executes487,944 instructions,1,512 existing
payload updates,10,368 final live/capacity bytes and8,640 preserved old bytes.
There are216 actual fifth entry and return captures each and216 complete XMM
preservations. Across the six callbacks there are53,136 supplied Lua requests,
2,592 marker/table calls each and1,296 assignment requests. Previous SIMD-wide
read/write totals remain864 each and supplied frees remain864. No sixth heap,
free, tree allocation, copied byte or wide access occurs.

All211 controls reject at their intended reasons:26 native mutations, one
cookie frontier, two stale captures,62 boundary/schema mutations, eight
coordinated GPR mutations, six observation XMM/DF mutations, four capture-schema
mutations,86 refreshed-digest retained-byte mutations, two typed allocator/free
mutations and14 host-patch mutations. Coordinated metadata cannot authorize
changed retained state. Cookie mismatch stops before failure-handler execution.

Receipt: [sealed JSON](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_callback_sixth_conformance.json).
Canonical SHA: `cdd92b83335043ca08b33f04dc4ca9a3643e97f594f8ba8349f40de81f547c18`.
File SHA: `f969840a607bf858ae0dedf52bc7140097567c5edadde42ae373fd5e9aff4aac`.
Deterministic UTF-8 LF size405,953 bytes;46 strictly pinned receipts. The CLI
supports build, exact verification and PE-free structure verification.
The136 conformance checks pass without skips, including103 pure checks,
16 isolated actual native checks, sealed-receipt/source mutations and exact
CLI rebuild, verification and structure verification. Shared fifth transport's
65 focused pure regressions pass,201 tests combined. Independent final
source/test and published-receipt reviews are GO.

The finite proof excludes other keys and source recipes, more than six
callbacks, actual Lua VM table effects, heap ownership/invalidation/reuse,
assertion/exception delivery, hardware execution and whole-program accounting.
The complete game remains unfinished.
