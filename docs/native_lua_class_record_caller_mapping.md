# Class argument record on the enclosing callback stack

The native class tree-copy prefix and external spare-vector return now accept
the actual returned callback's record and incoming register layout. For class
entry S, callback frame F=S+44, the local record is S+28 and its two words are
zero and SOURCE_OBJECT. The native class argument slot S+4 contains that record
address, and its full return continuation is `BASE+0x002ec1bd`.

The optional `caller` mapping on both fixtures has exactly four fields:
argument_address, argument_record, return_address and registers. Addresses are
restricted to the legacy record or S+28; the second record word must remain
SOURCE_OBJECT. The first word can be any uint32, with zero used by the actual
callback cases. Complete incoming GPRs must be uint32 values with ESP=S and
ECX=RECEIVER. Native stack geometry, return word and immutable mapped pages are
checked centrally, including for directly supplied fixtures. The entry remains
on the existing finite stack base; arbitrary stack/object relocation is open.

The prefix's independent memory model now restores original caller bytes at
and above S+8 after taking modeled callee scratch pages. It also preserves the
original eight record bytes. S+8 is the callback's saved EDI slot. The spare
append model reads its source pair from the original fixture, so forging both
the final argument and appended record cannot make the independent check pass.
Native corruption controls change the record at the helper endpoint and require
the exact ancestor-memory rejection, without causing an earlier event mismatch.

The [focused tests](../tests/test_itb_native_lua_class_record_caller_mapping.py),
original prefix suite and original spare-return suite passed **140 tests in
94.74 seconds**. A final strengthened native-test rerun passed in 4.50 seconds:
exact executable identity and source pins, **48 native successes**, and **four
exact-reason corruption controls**. The native cases cover the largest finite
empty/new/existing/mixed tree profiles across all selected node/frame layouts,
both class runners, zero record word, real continuation and callback registers.
The original **192-case prefix** and **1,152-case spare return** receipts rebuilt
byte for byte without changing their seals. Independent review: **GO**.
The broader ten-suite class regression passed **326 tests with eight gated
skips in 139.43 seconds**, covering all existing class return families, key
mapping and the logical class model. Its exact subprocess tests were gated;
the two original receipts and new caller cases ran separately as described above.

- [Prefix implementation](../src/observatory/native_lua_class_tree_conformance.py)
- [Spare-return implementation](../src/observatory/native_lua_class_spare_return_conformance.py)
- [Existing prefix receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_tree_conformance.json)
- [Existing spare receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_spare_return_conformance.json)
- [Callback integration dossier](native_lua_class_callback_integration.md)

This tranche proves finite helper mappings and their native executions. It does
not yet execute the enclosing callback continuously. Shared Lua/heap import
targets, literal pages, current stack/register state and one abstract Lua stack
must be joined before that claim. Other class return families retain their
existing fixed record fixtures. Allocation failure, assertion/error paths,
actual Lua VM/heap instructions and broader object domains remain open. No
whole-program accounting promotion occurs.
