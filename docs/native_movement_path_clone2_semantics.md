# Actual-page two-entry movement path clone

The clean-room law in `src/observatory/native_movement_path_clone2_semantics.py`
describes the selected normal `0x9a8e0` owner, reserve, allocator and scalar
copy for two eight-byte entries. Independent source review is GO and all
**359 independent pure tests pass**, without skips. The earlier finite native
receipt is unchanged; broader actual-page input coverage is a pure claim.

`apply` accepts complete immutable pages, all eight GPRs and XMMs, an installed
logical return word, ordinary DF-clear flags and a supplied allocation result.
It derives the source header from the actual caller word and the destination
header from ECX. The source capacity word is arbitrary, unread and preserved.
Headers, payloads and the touched frame must be disjoint. The actual two-page
stack window is derived from ESP; allocation stays in the existing four-page
synthetic data domain. Exact types, conservative nonwrapping extents, complete
mappings and separation from selected code and heap/IAT pages are checked.

The fifteen-field result predicts full pages, registers, XMMs, 136 instructions,
83 ordered accesses, seven complete boundary states, the imported allocation
boundary and both complete child packets. The supplied HeapAlloc success
returns sixteen bytes with explicit volatile-register and flag premises.
The full seven-field allocator packet is compared before rebinding only its
installed return event; the full ten-field scalar packet is compared on the
actual pages. No actual operating-system allocator executes in this law.

Final EAX is the destination header, ECX the source's last DWORD, EDX the
source end and ESP the entry frame plus eight. Nonvolatile registers and
all XMMs preserve. Final defined flags come from the parent's stack ADD,
under mask `0x8d5`; DF is zero. The new header and sixteen copied bytes change,
with exact stack writes and preservation of all unrelated supplied bytes.
Outputs are detached from the inputs and from each other.

Tests use handwritten whole-packet, boundary, access, trace and byte equations.
They cover the 48 prior finite geometries, all 128 ordinary flag combinations,
broader low, signed and top-address frames, record-local adjacent headers,
page crossings, arbitrary unread capacity, strict domains and coordinated
child corruption. The actual record-copy continuation `0x0055bbca` is admitted;
other accepted outside-body words are logical endpoints without a claim that
the caller executes. Private native probes corroborate four broader geometries,
but do not extend the published finite native corpus.

This specification does not establish arbitrary path lengths, allocation
failure, old destination ownership, freeing, overlapping copies, SIMD copying,
record append or destruction, normal AddMove, AddCharge or gameplay. Seven
complete selected bodies total 440 bytes; their source pins are in the module.
