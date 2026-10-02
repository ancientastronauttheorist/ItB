# Positive small path assignment semantics

`src/observatory/native_movement_path_small_assign_semantics.py` predicts
assignment into an all-zero destination header for actual source counts one
through 511. Its six keyword-only inputs describe immutable pages, GPRs, XMMs,
return address, ordinary flags and a supplied successful allocation result.
Count derives from the source end minus begin; capacity is unread.
Independent source review is GO. All 659 distinct independent checks validate:
658 passed initially, then seven affected geometry checks passed after fixing
one overlapping test frame. The implementation required no correction.

Mapped source and destination headers and complete eight-byte entry buffers
must be disjoint and nonwrapping. The supplied allocation occupies the ordinary
16 KiB DATA region; the conservative two-page stack window and selected heap
and IAT values are required. Zero count, nonempty destination, capacity reuse,
growth, aligned allocation at count 512, failure and unwind are separate arms.

The complete seven-field allocator and ten-field scalar-copy laws are manually
checked before transporting the allocator's final RET event or adopting child
state. The fifteen-field owner packet contains full ABI, pages, ordered
accesses, trace, flags, DF, endpoint, geometry, seven complete boundary states,
child packets, import and source snapshot. Positive traces contain
`142 + 10*N` instructions and `82 + 4*N` accesses, with one allocation of `8*N`.
Reviewed child instruction semantics remain an explicit trust boundary.

Final EAX identifies the destination header, ECX the last source DWORD and
EDX source end. ESP advances eight bytes; nonvolatile GPRs and all XMMs
preserve. The destination header becomes allocation begin, end and capacity;
all source bytes and unrelated mapped bytes preserve. Stack ADD flags use
`0x8d5`; SAR3 uses `0xc5` and imported TEST uses `0x8c5`, excluding undefined
bits. DF is zero. Typed schemas, all ordinary input flags, geometry, complete
child forgeries, pre-child call ledgers and detachment have independent checks.

Five executable probes at counts one, two, three, seventeen and 511 agree on
all boundary and import states, GPRs, XMMs, pages, ordered accesses, trace,
flags, DF and endpoint. Count two retains exact prior fifteen-field packet
compatibility. This is a semantic checkpoint; broader native corpus sealing,
allocator ownership, Lua consumers and gameplay remain unfinished.
