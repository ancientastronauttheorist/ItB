# Continuous complete normal class factory

This finite exact-build proof extends the
[native record composition](native_lua_class_factory_record_conformance.md)
through the remaining initializer instructions and the factory return. The
factory, initializer, self-linked record helper, allocation retry, thunk and
heap wrapper execute continuously in one x86 machine. Only 34 normal cdecl
Lua responses and one successful stdcall HeapAlloc response per case are
supplied. No native helper is replaced by a process-local implementation.

The executable SHA is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Eight source receipts are pinned, adding the sealed record composition to its
seven sources. The complete factory body is 296 bytes and the initializer
body is 612 bytes. The selected union contains 365 sites and 1,089 bytes;
302 normal sites execute. Error, assertion and prior-reference unref arms
remain excluded, including four skipped unref guard instructions.

The corpus combines all 1,728 record vectors with three independent supplied
registry profiles, for 5,184 cases. Profiles vary the context word, compatible
context guard, metatable reference, three distinct positive registry
references, and graph and ID-map pointers. Record page crossings, first-name
lengths and byte patterns, independent first and second name pointers, and
caller register profiles retain their earlier coverage.

The independent [request model](native_lua_class_factory_semantics.md)
describes seven prefix calls, 23 initializer calls and four factory-tail
calls. A separate runtime controller consumes the actual physical arguments
and supplies identity tokens. Every call is checked against the independent
model for arguments, result and Lua stack transitions. The initializer creates
two tables, obtains their references, looks up a compatible context, requests
a metatable and a third reference for userdata, and obtains graph and ID-map
pointers. The tail requests a global assignment using the opaque second name
pointer, then creates a closure with userdata as its one upvalue.

Final userdata DWORDs are checked at all 18 offsets: the fixed word at 0;
zeros at 4, 8 and 12; second name pointer at 16; state and third reference at
20 and 24; state and first reference at 28 and 32; state and second reference
at 36 and 40; one at 44; context word at 48; actual allocated record at 52;
zeros at 56 and 60; graph pointer at 64; ID-map pointer at 68. Record links,
marker and padding retain the earlier proof. Context and all other mapped
data pages are preserved except independently specified native writes.

The oracle independently reconstructs all physical API frames, ordered native
memory events, deferred stack cleanup, final mapped pages and caller state.
Both nested FS registrations are restored in order, followed by the original
FS head. Original EBX, ESI, EDI and EBP return intact. With original entry
stack pointer S and factory frame F=S-4, the final ESP is S+4, EAX is one,
ECX is the supplied cookie XOR F, and EDX is the final supplied Lua volatile
word. Defined final ADD flags, including AF, are checked under mask `0xcd5`,
which also requires DF clear. Neither epilogue invokes a security-cookie
checking function; preparing the cookie value does not verify it.

The final logical stack retains the argument and the newly created closure.
The native return count selects that closure. Its target is VA `0x006ec110`
and its single upvalue is the actual userdata identity. The closure is not
invoked. Metatable, registry and global assignment observations are supplied
requests and token identities, with no claim about real VM storage or effects.

The sweep executes 2,564,352 native instructions, including 813,888 initializer
instructions, 82,944 record-helper instructions, 176,256 allocation
instructions and 124,416 factory-tail instructions. Supplied calls total
176,256 Lua calls and 5,184 heap calls. All 38 exact negative controls reject
for their specified reasons, including final references, context reads,
returned closure identity, return count, restored return cells and a guard
mutation that branches into the excluded assertion arm.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_conformance.json`.
Canonical SHA:
`d8b36d30d732467edb54396ba22a3cd2a167dca15780f3020df18256c617dbcf`.
File SHA:
`29dc4376f28a537d0052c2dbd39c90328e8213fc029932fe3c16ee9ec1df291a`.
The CLI provides build, exact verify and PE-free verify-structure. Native
execution belongs in isolated subprocesses. Earlier factory, initializer
prefix and record receipts remain independent sealed boundaries.

This conditional proof excludes actual imported DLL behavior, Lua VM and
metamethod or host effects, allocation failure, prior-reference unref arms,
assertions, exceptions, cookie verification, validation of second-name bytes,
returned-closure invocation, arbitrary memory domains and program-wide
accounting promotion. It establishes the supplied normal path, rather than
unrestricted class-factory success or ownership semantics.
