# External inline string assignment semantics

`src/observatory/native_movement_inline_string_assign_semantics.py` predicts
external assignment of zero through fifteen bytes into a 24-byte inline string
with capacity fifteen. Five keyword-only inputs describe actual pages, GPRs,
XMMs, return and ordinary flags; caller words provide source and count.
Independent source review is GO. All 2,306 independent checks pass without
skips in 28.72 seconds. All 210 full-state executable cases agree.

Positive source bytes are mapped, disjoint from the complete destination
object and protected stack, and nonwrapping. The destination's previous length
may be zero through fifteen. Zero source pointers are unread and may be null
or unmapped, but must select the actual external branch: null, below destination
or at/above the destination's logical end. Alias handling, heap strings,
capacity growth and length failures remain separate arms.

The complete thirteen-field packet contains geometry, full ABI, pages,
ordered accesses, trace, defined flags, DF, endpoint, source snapshot, complete
memcpy packet and two full prefix-inclusive child states for positive count.
Zero has no child packet or child states. A handwritten complete eleven-field
scalar-copy prediction is compared before adoption, including trace, all
bytes/accesses, ABI, flags and endpoint. A separate direct page law checks
all caller stack writes, destination bytes and preserved source.

The destination receives exactly count bytes, a NUL at that count and the new
length; capacity and unwritten padding preserve. Final EAX is destination,
ESP entry plus twelve, and nonvolatile GPRs/all XMMs preserve. Positive ECX is
zero, with EDX the final copied DWORD or count. Zero's prefix matters: null
source preserves ECX as destination, other sources leave ECX fifteen; EDX
preserves unless the source is at/above destination, which leaves destination
in EDX. Final flags are `0x85` under `0x8d5`; DF is zero.

Zero branches have 26/32/39 instructions and 15/16/17 accesses for null,
below-destination and at/above-destination sources respectively. Positive
owner instruction counts are 43 or 50 plus the scalar child; accesses are
`30 or 31 + 2*q + 2*r`, for q DWORDs and r bytes. Independent tests cover
counts, alignments, previous lengths, pointer order, all ordinary flags,
broad geometry, strict types, pre-write/pre-child ledgers, complete child
forgeries, detachment, source preservation and padding.

Executable probes cover 192 standard cases and eighteen null, unmapped or
inline-padding zero-pointer cases, comparing complete pages, GPRs, XMMs,
accesses, traces, flags, DF and endpoint. Sparse memcpy provenance is pinned.
No broader native corpus seal, allocation ownership or gameplay claim follows;
whole-program accounting is unchanged.
