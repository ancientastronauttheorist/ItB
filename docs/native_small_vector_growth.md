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

## Actual caller storage for an initially null vector

The allocation, small-resize and small-growth ordered oracles accept an explicit
stack base. Resize/growth also accept an object-buffer base, and geometry accepts
an explicit fresh pointer within the existing allocation buffer. Defaults retain
the original sealed fixture addresses. These mappings let the enclosing class
call use its real stack, receiver fields and a new vector block separate from
its earlier tree-node allocations.

Validation checks nonwrapping actual buffers, complete frame/object containment,
separate storage and actual allocation-request containment. Relocated old-storage
cases were initially rejected until the deallocation join supported that mapping.
The first native caller proof covers an initially null/empty vector.

Independent review: **GO**. Mapping tests: **43 passed**, covering actual base
addresses, alignments, preserved storage, default equivalence and invalid/short
mappings. All three original exact CLI receipts rebuilt byte-for-byte unchanged,
including the final allocation-buffer guard. These tests are oracle checks; the
new native caller execution is established separately by the class composition.
See [caller-mapping tests](../tests/test_itb_native_vector_caller_mapping.py).

## Actual caller storage with a successful old-buffer free

The HeapFree protocol and joined vector-deallocation oracles now also accept an
explicit stack base. They validate actual frame bounds, nonwrapping buffers,
error-page separation and metadata aliases. Relocated free contracts require a
completed successful HeapFree response (or the null-pointer return); failure
protocols retain their original fixture domain.

Resize forwards the real stack base into deallocation. Relocated old buffers
are admitted only for capacities/requests at most four records, with all live
bytes, capacity and any metadata inside the actual old buffer. Old, new, object
and stack buffers must remain disjoint. Successful free responses supply the
known volatile register contract; this is not a claim about actual heap effects.

Independent review: **GO**. The expanded mapping suite passed **77 tests**.
The original HeapFree, joined deallocation, resize and growth exact CLI receipts
all rebuilt byte-for-byte unchanged. Whole-class native old-buffer execution is
a separate integration proof; these mapping tests check the ordered oracles.

## Actual old-buffer addresses for internal argument relocation

Resize geometry accepts an explicit non-null `old_pointer` for the small
capacity domain. Resize/growth oracles accept `old_base`, defaulting to the
original old-buffer base, and use it for all live-copy indices, bounds and final
snapshot checks. Explicit pointer plus capacity must fit DWORD pointer fields;
wrapping endpoints and malformed/null explicit pointers are rejected. The
whole old buffer remains disjoint from new storage, object storage and stack.

This lets a class argument live inside old vector storage on its existing
source metadata page, with the actual live vector interval kept separate from
the source object and head. The native deallocation oracle still consumes the
absolute old begin pointer. Old-page preservation is part of the supplied
successful HeapFree contract; real heap behavior remains outside this model.

Independent review: **GO**. The new old-buffer mapping tests plus existing
caller tests passed **130 tests**. Both original resize and growth exact CLI
receipts rebuilt byte-for-byte unchanged. Internal class reallocation is
verified separately by its native composition.
