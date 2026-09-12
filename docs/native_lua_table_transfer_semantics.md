# Conditional two-value Lua transfer request model

The independent model describes the requested Lua API operations of the
180-byte helper at `0x002ec050`. Entry Lua state contains a destination and a
source value above an unchanged prefix. A supplied finite iterator sequence
categorizes each key by its normal equality result against `__init` and
`__finalize`; all other keys are eligible for an assignment request.

The helper seeds iteration with nil and calls lua_next at -2. A matching
filtered key discards the temporary literal and current value, retaining the
iterator key. A nonmatching key discards each comparison literal, duplicates
the key at -2, moves that copy before the value, and requests lua_settable at
-5. Immediately before assignment, the relative stack is destination, source,
iterator-key, copied-key, value. The assignment consumes the copied pair,
leaving the original key for the next iteration.

Normal exhaustion restores the exact entry prefix and both entry values.
The model checks assignments independently as the positions of unfiltered
keys. It returns API requests and stack snapshots, not a changed Lua heap.
Actual settable or metamethod effects, source-table mutation and imported VM
execution are not modeled. Supplied iteration order, valid values and normal
API responses are premises.

The finite interface accepts up to eight entries and eight prefix values.
Request counts are two setup/exhaustion calls plus four calls for an init key,
seven for a finalize key, or ten for another key. Independent review: **GO**.
**14 tests passed**, including all key-category sequences of length zero through
four across three prefix lengths (363 model cases), exact request orders,
assignment indices, cleanup paths, bounds and detached snapshots.

- [Model](../src/observatory/native_lua_table_transfer_semantics.py)
- [Tests](../tests/test_itb_native_lua_table_transfer_semantics.py)

The model is separate from native instruction replay. It adds no whole-program
accounting promotion or claim about errors, nonlocal exits, actual Lua storage,
metamethod behavior or enclosing callers.
