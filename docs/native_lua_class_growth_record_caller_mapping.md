# Callback local record through first allocation and small growth

The [first-null vector return](../src/observatory/native_lua_class_empty_vector_return_conformance.py)
and [small old-vector return](../src/observatory/native_lua_class_old_vector_return_conformance.py)
now accept the same checked optional caller mapping as the class prefix and
external-spare helper. Defaults retain the original fixed record and fixtures.

For class entry S, the returned callback supplies its two-word record at S+28,
with `[0, SOURCE_OBJECT]`, actual incoming general registers and continuation
`BASE+0x002ec1bd`. The mapping forwards to the prefix's centralized validation:
strict uint32 registers, exact receiver/ESP, permitted record and continuation,
immutable mapped pages, original return word and nonnull source pointer. The
record pointer is derived from the original argument slot S+4. No separate
argument metadata can disagree with that slot.

All external-argument range checks and both post-growth record reads use this
checked original pointer. The independent models append its original eight
bytes, preserve its caller-stack storage at and above S+8, copy old live vector
bytes from the original fixture and retain the old buffer contents. Forging
both the final caller record and appended copy cannot satisfy those models.

First allocation runs the existing native growth/allocation/zero-copy path.
The bounded old-vector family runs allocation, native old-record copy and
HeapFree, including old sizes zero through three. The allocation request is
eight bytes for the first-null vector or `8*(old_size+1)` for the selected
full old vector. HeapAlloc and HeapFree retain their supplied successful
stdcall contracts; all selected native helpers still execute. Both return
with RET4, original nonvolatile registers, EAX SOURCE_OBJECT and the normal
cookie check. Actual heap ownership and exceptional returns remain premises
or separate work.

[Focused tests](../tests/test_itb_native_lua_class_growth_record_caller_mapping.py)
cover largest finite empty/new/existing/mixed tree recipes, selected node and
frame layouts, allocation alignment, old sizes, actual callback registers,
original-pair append, preserved ancestors and dynamic heap/free requests.
Endpoint argument corruption must reach the exact ancestor-memory rejection.
Tests also forge original-record and appended copies together, forge old/copy
bytes, and reject malformed supplied fixture/caller fields. Native execution
runs only in isolated subprocesses.

Validation passed **147 tests, zero skips, in 71.85 seconds**, including 48
mapped native successes, four exact-reason ancestor/record controls and both
original CLI rebuilds. The original **576-case first-null** and **1,536-case
old-growth** receipts rebuilt byte for byte with unchanged seals and file
hashes. Their original pure suites also passed **43 tests with two gated
skips in 74.94 seconds**; those two native tests ran in the separate complete
validation above. Independent semantic review: **GO**.

This extends helper mappings; the enclosing callback's
[continuous external-spare receipt](native_lua_class_callback_conformance.md)
still covers spare capacity only. Joining first allocation and small growth
into that enclosing callback needs an extended logical vector contract,
shared HeapFree binding, current child state and a new continuous receipt.
Other internal-record families, allocation failure, Lua errors and broader
object/tree domains remain open. No accounting promotion occurs.
