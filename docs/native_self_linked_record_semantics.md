# Conditional self-linked-record helper model

`src/observatory/native_self_linked_record_semantics.py` is a standalone pure
Python model of the normal-return stores in the 41-byte helper at RVA
`0x0007c600`. The preexisting self-linked-record helper-chain artifact seals
that body (SHA-256 `bf6d8eea868843a089fcc2b74af1426c5f71328fc018f028310cc48259f0dda1`)
and all 16 instructions. This model does not execute those instructions or
prove conformance by itself.

The interface is `apply(*, pointer)`. `pointer` supplies the allocation call's
normal return: an exact Python int, positive uint32 word, with a writable
24-byte extent as an external premise. The entire extent must fit without
address wrap (`pointer+23 <= 0xffffffff`). Bools and int subclasses are
rejected. This deliberately excludes zero or wrapping pointer families where
the exact EAX, EAX-plus-four, and EAX-plus-eight guards could skip stores.

The output requests 24 bytes, records the supplied `returned_pointer`, and
contains these `ordered_writes`:

| Byte offset | Width | Value |
| --- | --- | --- |
| 0 | 4 | `pointer` |
| 4 | 4 | `pointer` |
| 8 | 4 | `pointer` |
| 12 | 2 | `0x0101` |

The actual highest written byte is offset 13. Byte offsets 14 through 23 are
reported as `untouched_offsets`, without asserting their existing contents.
The word stores are little-endian in the x86 comparison domain.

`final_ecx` is `pointer+8`; the returned EAX word is `pointer`.
`instruction_count=16` counts the helper only, including its call and return,
and excludes every instruction in the allocation callee. The recorded
`native_allocation_call` requests argument `[24]` at target RVA `0x003574db`,
with return RVA `0x0007c607`. The callee's normal return is supplied here,
without implementing allocation retry, a heap API, exceptions, or failure.

The last flag-setting instruction is TEST of `pointer+8`. Defined CF and OF
are zero; ZF tests that word for zero, SF is its bit 31, and PF is even parity
of its low byte. `flags_mask=0x8c5` selects only CF, PF, ZF, SF, and OF;
`flags_value` packs those bits and `flags` exposes their named values. AF is
undefined and omitted. Later stores and RET preserve these selected flags.

Tests compare independent little-endian byte arenas, every untouched byte,
finite pointer families, exhaustive low-byte parity and sign transitions,
strict word rejection, the inclusive 24-byte extent boundary, and detached
outputs. They are conditional model laws. The helper name, self-address stores,
and size immediate do not establish a source-level record/container identity,
ownership, lifetime, allocation success, valid live memory, or a whole native
allocation/runtime proof.
