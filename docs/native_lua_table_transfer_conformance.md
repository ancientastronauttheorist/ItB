# Native conditional Lua table-transfer return

The 180-byte helper at `0x002ec050` executes all 71 native instruction sites
through its normal caller return. Fourteen call sites use eight Lua imports;
their implementations are supplied normal API response contracts. This proof
executes the helper's actual instructions, not the imported Lua DLL or VM.

The independent [request model](native_lua_table_transfer_semantics.md) checks
the abstract Lua stack, retained iterator keys, and assignment requests. Keys
matching `__init` or `__finalize` are filtered. Other keys produce a duplicate
key/value pair consumed by `lua_settable(-5)`. Iterator exhaustion restores the
entry prefix and both source/destination values. Assignment requests do not
establish actual destination-table mutation or metamethod behavior.

The corpus contains every category sequence of length zero through three,
four native alignments and two Lua prefix lengths: **320 cases**, **816
iterations**, **272 assignment requests** and **6,352 supplied API returns**.
All 71 instructions and all 14 direct or staged call sites execute. The
independent model contract seals 80 category/prefix cases separately from the
native alignment dimension.

For native entry S, the first pushnil and next API frames are S-12 and S-20.
Nonempty iteration additionally saves EBX/EDI, which retain the pushstring
and settop dispatch targets. Later argument groups are cleaned by the native
caller, including the 32-byte group on the assignment path. Every API argument,
return word, dispatch target, saved register and complete mapped native page
is checked. Pinned literal and IAT pages are protected by the response contract.
The final EAX is zero from exhausted lua_next, ESP is S+4, nonvolatile registers
are restored, and defined arithmetic flags and DF are checked.

Ten mutation controls reject corrupted ancestor storage, saved registers,
arguments, return/result values, literal/IAT padding and staged dispatch state.
Independent review: **GO**. **16 tests passed in 12.19 seconds**, including an
exact 320-case subprocess CLI rebuild matching the published receipt byte for
byte.

- [Implementation](../src/observatory/native_lua_table_transfer_conformance.py)
- [CLI](../scripts/itb_native_lua_table_transfer_conformance.py)
- [Tests](../tests/test_itb_native_lua_table_transfer_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_table_transfer_conformance.json)

Canonical SHA-256:
`c592340aaef40157af3330b0bdf096441ff7a3f25fa12902ce7f023e81772063`.
Encoded SHA-256:
`747ba7fda8b4ebf813f5af3f8aba7d1ae20c17e4d05cb0cb356a03280896d2fe`.

The CLI supports build, verify and verify-structure with --program-facts and
--class-chain. Exact operations require --executable; verification requires
--evidence. Evidence is specific to Windows build 13725832 and its pinned
executable SHA. Errors, nonlocal exits, arbitrary iterator lengths, actual Lua
heap effects and enclosing callback composition remain open. Accounting
promotions are zero.

## Actual callback mappings

An optional caller mapping provides entry, return_address, all native registers
and immutable stack_pages. The guard validates the full 48-byte live scratch
interval, original return word, nonwrapping RET result and disjoint data pages.
The callback return may share the helper's native code page while remaining
outside its executed body; the runner maps that page once. Prefix length one
is now available to the fixture, while the sealed corpus and model-contract
digest retain their original prefixes zero and three.

The original suite and [caller-mapping tests](../tests/test_itb_native_lua_table_transfer_caller_mapping.py)
passed **46 tests in 15.15 seconds**, including a byte-identical rebuild of the
original 320-case receipt and 16 isolated native caller cases. They exercise
both callback frames, prefixes one/three, empty and each filtering path, retained
rawgeti argument words and the local record above the callee frame. Complete
mapped pages are checked. Independent review: **GO**. Lua-state continuity
between the two calls and complete enclosing callback execution remain open.
