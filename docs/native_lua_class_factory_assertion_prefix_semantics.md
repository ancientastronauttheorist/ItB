# Factory context assertion boundary model

`native_lua_class_factory_assertion_prefix_semantics.apply` independently
describes the normal factory requests and initializer requests up to the
context guard's minus-two assertion arm. The first name pointer is measured
through its first NUL; the second pointer remains independent and is stored
at userdata offset 16. Reached pointers must cover their actual accessed
extents without uint32 wrap. The supplied context guard must be exactly
`0xfffffffe`, and the two registry references must be distinct positive int32
words.

The model records seven factory Lua requests followed by eleven initializer
requests: two create-table, duplicate and reference sequences, removal of
both temporary tables, then the classes registry lookup and stack restoration.
The original argument and new userdata remain on the boundary stack. Two
independent table identities remain associated with their supplied references.
Calls record detached arguments, results and before/after token stacks.
Imported Lua behavior remains an explicit conditional contract.

Fourteen userdata words are modeled: offset 0 is `0x0089d1d4`; offsets
4, 8, 12 and 20 are zero; offset 16 is the second name pointer; offset 24
is minus two; offsets 28 and 36 contain L; offsets 32 and 40 contain the
two reference identities; offset 44 is one; offsets 56 and 60 are zero.
Offsets 48, 52, 64 and 68 are outside this logical field model. The separate
native proof checks the actual allocated record at offset 52 and preserves
the other three words. Only context offset 12 is read before this boundary.

The native request targets RVA `0x00379cc2` from CALL RVA `0x002eae76`,
with continuation VA `0x006eae7b` and argument words
`[0x0083c6b0,0x0083c680,96]`. Expression and filename contents are opaque.
With initializer EBP G, the assertion boundary ESP is G-48 and its four words
are `[0x006eae7b,0x0083c6b0,0x0083c680,96]`. The post-record resume stack
is G-36 with the first trailing zero argument already present. The first
three Lua calls and their 28-byte cleanup restore G-32; the second group does
the same. The following five two-argument calls and 40-byte cleanup restore
G-32 before three assertion pushes and CALL produce G-48.

No assertion response, helper instruction, unwind, initializer return or
factory return is modeled. Later metatable, third reference, graph, ID-map,
closure and global requests remain outside this prefix. Independent tests
check the request sequence and token identities, strict reached domains,
first-NUL routing, exact frame words, field ownership and output detachment.
