# Integrated growth for small vectors

The growth helper at `0x002eb620` now executes its native resize, allocation,
short-copy and deallocation descendants. The bounded full-vector cases have
zero through three live elements, including null and nonnull empty storage.
Spare-capacity cases have zero through three live elements in capacity four.
Only successful HeapAlloc and HeapFree responses remain supplied.

Full vectors request max(size+1, capacity+floor(capacity/2)). Spare vectors
return without changing storage. For growth entry G, resize enters at G-20,
the deepest allocation CALL reaches G-96 and free reaches G-88. Both outcomes
finish at ESP=G+8: the helper consumes its unused argument with RET 4.

Before resize, EAX is capacity plus its half, EBX is the maximum-element
constant minus that half, EDI is old capacity, ESI/ECX name the vector and
EDX is requested capacity. After native resize, growth's POP/RET suffix
restores its original nonvolatile registers and preserves the child's final
flags. Spare return instead leaves EAX=spare element count, EDX=old end,
ECX=vector and flags from CMP(spare,1).

The independent integrated-resize oracle is rebased at G-20 with explicit
replacement of its caller-return event by the native growth continuation.
Fresh growth prefix and suffix events connect that child state. Complete
ancestor stack, object, payload, metadata, globals and import slots are checked,
as are ordered native accesses, general registers, defined flags and clear DF.
Old live bytes survive into new storage under the declared successful API
memory-preservation premises.

## Evidence and reproduction

Unicorn 2.1.4 checks 1,152 cases and 198 executed sites from 756 loaded bytes
and 295 static sites. The cases split into 640 native resizes and 512 spare
returns; 640 allocation and 512 free responses are supplied. No opaque callee
instruction executes. Paired block alignments cover every alignment, across
four stack alignments. Ancestor and payload mutation controls are rejected.
Independent review passed, and all 21 focused tests passed, including the
exact-executable CLI rebuild.

Larger live vectors, failures/retries, actual API effects and append integration
remain outside this checkpoint. No whole-program accounting promotion occurs.

`scripts/itb_native_small_vector_growth_conformance.py` accepts the six source
flags from the integrated small-resize CLI, plus `--resize-conformance` and
`--growth`. It provides `build`, `verify` and `verify-structure`; exact commands
require `--executable`, verification requires `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_small_vector_growth_conformance.json`.
Canonical SHA-256:
`b3f0dff73c7b9eeabc82fb9044782e2bf9829c3798c91d0868ae69c967706b92`.
Raw SHA-256:
`4741638fe6ba63f417a7497b404abbed02cb2e05c0f2903d17de29b9b65cf6af`.
