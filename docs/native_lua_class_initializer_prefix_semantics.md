# Conditional initializer-prefix model

`src/observatory/native_lua_class_initializer_prefix_semantics.py` is a standalone
pure Python fixed-offset model of the 37 instructions from RVA `0x002eacf0`
through the call at `0x002ead8b`. Its endpoint is helper entry `0x0007c600`,
before that helper's first instruction. The preexisting initializer-chain
artifact seals the containing body and call; this model alone proves no native
execution or conformance.

The interface is `apply(*, userdata, name_pointer)`. Both inputs must be exact
Python ints and nonzero uint32 words; bools and subclasses are rejected. A
writable userdata region through offset 59 is an external premise. The actual
highest written byte, `userdata+59`, must not wrap uint32. The name pointer is
never dereferenced here, so values including `0xfffffffe` and `0xffffffff` are
accepted as opaque words without a string or readable-memory premise.

The output includes `ordered_offset_writes` (offset, four-byte size, and value),
`final_fields` containing only the written words, and `untouched_offsets`.
The exact write partition is:

| Offset | Written value |
| --- | --- |
| 0 | Literal `0x0089d1d4` |
| 4, 8, 12 | 0 |
| 16 | `name_pointer` |
| 20 | 0 |
| 24 | `0xfffffffe` |
| 28 | 0 |
| 32 | `0xfffffffe` |
| 36 | 0 |
| 40 | `0xfffffffe` |
| 44 | 1 |
| 52, 56 | 0 |

Offsets 48, 60, 64, and 68 are untouched at this endpoint. Their previous
contents are unspecified; the output does not replace them with zero. The
literal at offset zero and other fixed offsets receive no source-level type,
vtable identity, ownership, registry, or lifetime interpretation.

`instruction_count` is 37. `native_handoff` records target RVA `0x0007c600`,
return RVA `0x002ead90`, no newly pushed stack arguments, and constrained
registers EAX=`name_pointer`, ECX=EDI=`userdata`, ESI=`userdata+52`. Neither
the helper nor later initializer Lua calls execute in the model.

For initializer entry ESP `N`, let EBP `G=N-4`. The stack pointer before the
helper call is `G-32`, and at helper entry it is `G-36`, containing return VA
`0x006ead90`. The nested prologue saves the incoming FS:[0] at `G-12`, then
sets FS:[0] to `G-12`; in factory composition, the saved value is the parent's
active chain. The handler immediate is VA `0x007d107c`. The word read at VA
`0x00893f28` is XORed with G and pushed at `G-32`. The model records frame
offsets, without predicting actual FS contents, cookie values, or exception
handling behavior.

The second argument is read from `[G+12]` into EAX, then that same argument
slot is overwritten with `userdata+52`. The local word `[G-16]` holds userdata.
The scope word `[G-4]` starts at -1, becomes zero, and receives a byte store of
3, leaving final word 3. `frame` exposes the argument-slot and final local facts.

Tests exercise a bounded cross product of userdata/name words, the exact write
partition and order, preservation of every unspecified arena byte, frame and
argument-slot laws, strict invalid-word checks, the inclusive last-byte boundary,
and independent output containers. These are pure model laws; readable names,
valid memory, helper success, allocation, Lua behavior, exception behavior,
source-level classes, and complete initializer behavior remain unproved.
