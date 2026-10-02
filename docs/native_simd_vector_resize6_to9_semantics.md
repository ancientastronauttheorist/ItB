# Actual-page ordinary resize6-to9 law

The pure adapter consumes the caller's complete installed pages, eight GPRs,
eight XMM registers, actual ESP and header address, source/destination,
installed return address, and incoming flags. It constructs no fixture and
repairs no caller words or header. Its independent tests pass 117 checks without
skips; independent production-source review is GO. This is logical evidence.
The [finite native resize](native_simd_vector_resize6_to9_conformance.md) retains
its original 48-case domain and receipt unchanged.

## Inputs and preserved state

`apply(*, pages, registers, xmm, source, destination, object_address,
return_address, entry_flags)` requires exact typed register/page schemas,
immutable complete pages, ordinary incoming flags, header `[O,O+48,O+48]`, ECX equal to the
header address, and installed caller words `[return,9]`. Source O is positive,
destination D is greater than O+48, and the complete destination capacity72,
source48 and header12 extents are mapped and disjoint. Their exclusive ends
are representable uint32 values. Addresses and alignment may vary independently.

The selected runtime support remains fixed: two stack pages at `0x30000000`,
error storage at `0x06000000`, and the complete feature, heap-global and IAT
pages. Those regions and selected code exclude the data/header extents.
All supplied data pages exclude selected code/import pages; the positive
return address excludes supplied data, imports and selected bodies. The
feature DWORD is `0x93939393`, heap handle `0x12345678`, and both heap IAT
entries bind the supplied import endpoint. Remaining page contents are actual
input bytes. Frames may be unaligned within the two mapped stack pages.

The output has the same exact 18-field schema as the finite resize packet.
Independent owner equations reconstruct all 104 accesses and 197 instruction
occurrences around strictly compared seven-field allocation, ten-field copy,
and eight-field free packets. The selected allocation relocation remains
narrow and fully checked. Every supplied page survives except documented
stack writes, D48 and ordered header writes: capacity D+72, end D+48, begin D.
Old48, spare24, ancestors, error storage, feature/cookie padding and all other
bytes remain unchanged. Returned containers are detached from input containers.

Return EAX is D+48, ECX `0xa0000001`, EDX `0xb0000001`, and ESP advances by
eight. Nonvolatile GPRs restore; XMM0/1 contain the original first32 bytes and
XMM2..7 preserve input values. Defined final flags follow ADD(R-32,12) under
mask `0x8d5`, with DF checked separately. Supplied successful heap responses
remain premises; ownership, unmapping, reuse, metadata/error paths and
whole-program accounting are outside this law.

## Actual flags and growth continuation

Incoming flags must be a typed uint32 containing only mask `0xad7`: six
arithmetic status bits, IF and fixed bit one, which must be set. DF and every
other execution-control/system/reserved bit are excluded. Abstract words zero
and four are not actual incoming EFLAGS; masked arithmetic boundary values may
still be zero or four. Within this selected ordinary domain, the owner prologue
preserves incoming flags into allocation entry. The fixed native words `0x246`
and growth's `0x202` remain admitted; their receipts are unchanged.
The domain excludes resume/single-step/alignment and other system modes whose
behavior this adapter does not model. Intel documents resume-flag clearing
during instruction execution ([Intel instruction/system manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)).
Copy-entry flags derive from SUB(O+48,O). When O=`0x7ffffff0`, the end crosses
the signed boundary and the subtraction defines `0x804` under mask `0x8d5`.
The adapter computes this overflow; it does not hardcode the ordinary low-address
value four. The copy's final AND defines `0x44/0x8c5`; AF is unclaimed.
Free-entry SAR3 defines four under mask `0xc5`, with AF/OF unclaimed.

The tests independently reconstruct complete pages, events, traces, registers,
flags and child packets for all 48 predecessor profiles at actual growth
R=G-20, an arbitrary header at `0x10000104`, and installed return `0x006eb66e`.
They also cover source/destination/header page crossings, stack endpoints,
the uint32 extent boundary, malformed schemas/aliases/premises, source pins,
coordinated child corruption and attempted fixture creation. They use handwritten
equations rather than production `apply` or `_expected` as expected results.

The [native growth proof](native_simd_vector_growth6_to9_conformance.md) validates
and captures the growth machine's actual resize entry/return, then continues in
that same machine. This adapter alone
does not execute the growth owner, class append, or another callback.
