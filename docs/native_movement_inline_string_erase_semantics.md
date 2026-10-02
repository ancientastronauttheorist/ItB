# Inline string erasure semantics

`src/observatory/native_movement_inline_string_erase_semantics.py` predicts
RVA8410 on mapped inline strings of length0..15 and capacity15. Offset and
requested removal are actual unsigned caller words. Offset must not exceed
length. The five-input API returns a complete fourteen-field packet including
the original24-byte object snapshot, final object, optional complete memmove
packet and two complete checkpoints for a positive interior shift.

If remaining length is no greater than requested removal, erasure truncates
at offset and writes NUL. If removal is zero while bytes remain, the object
receives no writes. Positive interior erasure shifts the trailing bytes left
through the actual memmove entry36E580, updates length and appends NUL.
Counted bytes can contain NUL; source terminators are not a premise. Every
untouched object/caller/page byte preserves.

Truncation executes23 instructions/13 accesses and returns ECX=offset,
EDX=requested, flags 0x85/mask 0x8D5. No-op executes21/10 and returns ECX=offset,
EDX=0, flags 0x44/mask 0x8C5. Positive shift executes42 owner instructions plus the
selected memmove trace; accesses are `29+2*q+2*r`. Its child entry flags come
from actual subtraction `(old_length-requested)-offset`, with complete mask 0x8D5.
Final ECX is zero, EDX is last copied DWORD or trailing count if no DWORD,
flags 0x85/mask 0x8D5. All paths return the object in EAX, advance ESP twelve,
preserve nonvolatile GPRs/eight XMM values and preserve DF0.

The full child eleven-field schema, actual-input geometry, complete ordered
accesses, terminal ABI, snapshot and page replay are closed before adoption.
Child instruction labels remain trusted at fixed expected trace length, stated
explicitly and tested with a valid transported label change. Upfront domain
rejections instrument both writes and child attempts. Selected code pages,
stack/object disjointness, mapped immutable pages and strict types are checked.

Independent source review is GO. All2,326 independent checks pass without
skips in16.57seconds. Handwritten owner expectations compose an independent
memmove test oracle and a separate final object/stack equation. All1,272
complete native cases agree across every length/offset, zero/short/exact/MAX
removal requests and two alignments, including both child checkpoints.

Heap storage, growth, invalid offsets, failures, ownership, gameplay and
broader native receipts remain separate work. Whole-program accounting is
unchanged.
