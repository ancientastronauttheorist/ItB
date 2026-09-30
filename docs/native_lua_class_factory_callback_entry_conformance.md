# Produced factory userdata through callback class entry

This conditional proof joins actual native factory output to a fresh callback
invocation and stops at class-helper entry RVA `0x002eb140`. The factory,
initializer and allocation machinery execute in one machine. Their actual
final data pages are captured, then retained in a second machine that executes
the returned callback and both marker helpers continuously. The intervening
Lua closure invocation is an explicit supplied host boundary. This does not
execute the Lua VM or prove a live invocation.

The executable SHA is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Eleven sources are pinned: the eight complete-factory sources plus complete
factory, callback and marker conformance receipts. The factory's complete
native body identities and its physical/Lua oracles retain their earlier
checks. The callback's complete 269-byte body is checked before selecting
173 bytes through its actual class CALL. The marker's 84 bytes are checked
against its sealed instruction witnesses. No class-helper instruction runs.

The finite corpus contains 48 producer cases: name lengths 0, 1, 16 and 255,
high-byte names crossing their page boundary, distinct first and second name
pointers, two caller profiles, two record geometries and three registry
profiles. All factory instructions execute under 34 normal Lua responses and
one successful heap response per case. The runtime factory token controller
records closure target `0x006ec110` and its single actual userdata upvalue.
The captured pages come from the machine; they are not regenerated oracle
pages or callback tree fixtures.

The host boundary writes eight bytes for a fresh callback frame in a separate
region of the existing stack pages and sets incoming ESP to that region.
Other incoming GPRs are the returned factory GPRs. Because the older proofs
use different synthetic import bindings, the adapter explicitly patches only
the named shared Lua slot bytes and three named literal byte sequences.
It records each before/after byte; it never replaces a whole existing page.
All unrelated bytes remain retained, including the producer's frames, FS
head, names, context, references, 72-byte userdata and 24-byte record.
New literal pages, when needed, have a declared synthetic fill.

The callback's supplied upvalue conversion returns the captured U. Both native
marker helpers execute with compatible supplied metatables and truthy values
(zero for the upvalue, table for the argument). The second conversion returns
the supplied argument identity A. A is not dereferenced before this endpoint.
Factory metatable-setting requests and retained references do not themselves
establish marker lookup success; that remains a compatible Lua contract.

The independent
[`native_lua_class_factory_callback_entry_semantics.apply`](../src/observatory/native_lua_class_factory_callback_entry_semantics.py)
checks the exact closure target and single U identity, strict uint32 words,
reached U/P/frame extents, two true metatable contracts and truthy marker
kinds. It describes twelve requests and identity-bound before/after token
stacks. It accepts all nine combinations of zero, empty string and table,
including aliasing A=U. Native cases use the narrower supplied combination.
The runtime observer consumes actual physical arguments and typed responses
and joins its trace to this detached model. Full high-EAX marker returns
remain visible while the parent guards inspect AL.

For callback entry ESP T and frame F=T-4, class entry C=T-48 has
`[C]=0x006ec1bd` and `[C+4]=T-20`. The latter points to the original local
pair `[0,A]`. EAX=T-20, EBX=L, ECX=U, EDX=`0xb1000002`, ESI=U, EDI=A,
EBP=F and ESP=C. The final defined flags come from ADD ESP,8 after the
argument conversion, independently calculated from F-44 plus eight under
mask `0xcd5`; they do not come from the marker TEST. All incoming API GPRs,
physical frames, actual child continuations, ordered native data events and
every mapped data page are checked against separate frame/child oracles.
Factory U/P bytes and registry-reference fields remain unchanged throughout.

The selected callback/marker union has 88 static and 67 executed sites in
257 bytes. Sixteen parent assertion/error sites and five false-marker sites
remain unexecuted. Each callback case executes 94 instructions. Totals are
27,552 factory instructions, 4,512 callback/marker instructions, 1,632 factory
Lua responses, 576 callback Lua responses, 48 heap responses and 96 actual
native marker calls. The required normal coverage partition is enforced,
and class entry itself is absent from the instruction trace.

All eleven exact controls reject: U, record marker, local pair, continuation,
ancestor and reference corruption; receiver GPR and defined flag corruption;
wrong converted upvalue identity; and both parent AL guard mutations. The
guard mutations reject before assertion/error instructions execute. The pure
model separately rejects wrong closure targets/upvalues and malformed reached
contracts.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_callback_entry_conformance.json`.
Canonical SHA:
`cca405ff5c16dfebb85f23c07e5333c14b300c209ad24dfab42033d17c89b94e`.
File SHA:
`b7485db988408f110547fe5475ebbf55dabbea908c9b86699393549fbcbf1a0b`.
The deterministic UTF-8 LF receipt is 32,578 bytes. The CLI supports build,
exact verify and PE-free verify-structure. Native tests run in isolated
subprocesses. The shared callback oracle's prefix mode is optional and its
existing complete-callback behavior retains its original sealed boundary.

Class-helper execution, tree transfer, vector growth, callback return, real
Lua VM/metatable/registry behavior, heap ownership, arbitrary receiver/source
domains, assertion delivery and whole-program accounting promotion remain
excluded. A later class continuation must consume these actual U/P pages;
existing fixed-address tree fixtures cannot overwrite the produced state.
