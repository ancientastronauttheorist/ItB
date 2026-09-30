# Native callback upvalue assertion prefixes

This finite proof executes callback validation through either native
assertion-helper entry: a null userdata upvalue, or a nonzero userdata whose
marker is absent, nil or false. The actual marker helper executes continuously
with the callback for the nonzero families. Execution stops before the first
instruction at target RVA `0x00379cc2`; no helper response is supplied.

The executable SHA is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Five receipts are pinned: program facts, factory chain, marker semantics,
marker native conformance and the prior callback argument-error proof.
The complete 269-byte callback body is checked. Selected code is its 101-byte
prefix through exclusive RVA `0x002ec175`, plus the 84-byte marker body.
The 185-byte union has 65 static sites and 59 executed sites. Six selected
sites do not execute: the first assertion continuation's cleanup and the five
instructions in the marker's truthy tail.

The corpus has 192 cases: 16 frame alignments, three caller/volatile profiles,
and four families, with 48 cases each. Null upvalue needs one normal Lua
response and 23 native instructions. An absent upvalue metatable needs two
responses and 39 instructions. Nil and false marker values with metatables
each need six responses and 55 instructions. These paths reach the actual
native helper, rather than returning from the callback or invoking error DLL
code. Native marker returns retain supplied high EAX bits while the parent
TEST observes AL alone.

The independent [boundary model](native_lua_class_callback_assertion_prefix_semantics.md)
short-circuits unused contracts in the null family. For other families it
tracks the marker lookup and restored original argument prefix. A separate
runtime observer consumes actual physical Lua arguments and compares the
token trace and final stack against that model. Every physical API entry GPR,
frame, supplied response and real child continuation is checked. Child
oracles receive current parent state; their independently specified stack
corollaries verify frame writes, while native helper instructions execute in
the same machine.

With entry ESP S, frame F=S-4 and idle ESP F-36, both assertion-call entries
have ESP F-52. Null upvalue produces stack words
`[0x006ec151,0x0083ca00,0x0083c9c8,69]`; false upvalue marker produces
`[0x006ec175,0x0083c908,0x0083c9c8,70]`. These pointer and scalar words are
exact native requests. Their expression and filename contents are neither
read nor validated; their synthetic mapped pages are protected.

At the endpoint EBP=F, EBX=L, ESI is the supplied userdata word, and EDI is the
staged touserdata target. EAX is zero for null and absent families; present
false markers retain the supplied final void word's high 24 bits with AL
cleared. ECX and EDX are the last supplied API volatile words. The final TEST
defines flags `0x44` under mask `0xcc5`, including clear DF and excluding
undefined AF. Cookie XOR F remains stored at F-8, userdata at F-20, and
original EBX/ESI/EDI at F-28/F-32/F-36. No FS registration or epilogue occurs.
Ordered native data events and all mapped pages are checked against an
independent parent-frame and child-stack oracle.

The sweep executes 8,256 native instructions and supplies 720 normal Lua
responses, including 144 native marker calls, reaching 192 assertion
boundaries. All 16 exact controls reject for their specified reasons. They
cover memory and call words, cookie setup, saved state, API arguments and
response, final registers/flags, Lua identity and a changed AL guard that
leaves the declared prefix.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_callback_assertion_prefix_conformance.json`.
Canonical SHA:
`b6486105640001ae644f9ea2023c98ca62626df5f1ab2c2041ba2dea2879484e`.
File SHA:
`566da6057527a877f2441b7b29075a4742cc32c1bb65e6952f3e50c1ae0eb861`.
The CLI supports build, exact verify and PE-free verify-structure with strict
deterministic UTF-8 LF bytes. Native rebuilding runs in isolated processes.

Assertion-helper execution, behavior or response, imported DLL behavior,
assertion delivery, recovery, unwind, callback return, expression/filename
contents, argument-marker checks, class operations, table transfers,
cookie verification and program-wide accounting promotion remain excluded.
Earlier helper structural proofs do not turn this entry boundary into a
runtime assertion or exception-handling proof.
