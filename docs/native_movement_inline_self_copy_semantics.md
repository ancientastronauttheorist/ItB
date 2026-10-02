# Inline self-substring copy semantics

`src/observatory/native_movement_inline_self_copy_semantics.py` predicts the
self-source branch at RVA80D0. Receiver and source object are identical,
inline capacity is15, length is0..15 and unsigned offset does not exceed
length. Requested count is clamped to the available suffix. The five-input
API returns a complete fourteen-field packet with the original24-byte object
snapshot, final object, full erase packet and chronological full checkpoints.

The owner first writes length `offset+count` and its NUL, then calls erase8410
at frameG-28 with erase offset zero and requested removal equal to the original
offset. Positive offset/count uses actual memmove36E580 at frameG-60. The
complete conservative stack extends toG-68. Final counted bytes equal the
original `object[offset:offset+count]`; every other byte preserves except the
two terminators, length and explicit stack saves. Original snapshot remains
original even though the same source object is legitimately changed.

The entire fourteen-field erase child and nested eleven-field memmove packet
are predicted and compared before adoption, including actual pages, ordered
accesses, every GPR/XMM, geometry, snapshots and all checkpoints. Canonical
trace contents remain explicitly trusted at fixed expected lengths. The
independent suite tests that boundary without claiming universal forgery
rejection. Inputs are strictly typed and reject invalid/code/stack/return
geometry before writes or child attempts.

Zero count executes58 instructions/33 accesses/two checkpoints; positive count
at offset zero uses56/30/two. Positive offset and count use
`101+6*q+6*r+2*(r!=0)` instructions, `49+2*q+2*r` accesses and four checkpoints.
All paths return the object in EAX, advance ESP sixteen and preserve all
nonvolatile GPRs/eight XMM values/DF0. Actual erase ECX/EDX/defined flags carry
through, including the no-op erase distinction at zero offset.

Independent source review is GO. All2,342 checks pass without skips in
25.32seconds. The expected owner is handwritten and composes an independent
erase test oracle, plus a separate equation from original object bytes.
Coverage includes every length/offset/request arm,128 ordinary flags, complete
packets and checkpoint joins, strict validation ledgers, forgeries, trust and
detachment. All1,272 complete native cases agree, including every checkpoint,
page, GPR, XMM, ordered access, trace, defined flag, DF and endpoint.

Heap strings, growth, invalid offsets, ownership, gameplay and broader native
receipt sealing remain separate work. Whole-program accounting is unchanged.
