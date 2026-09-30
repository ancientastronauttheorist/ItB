# Returned callback argument-marker rejection

This finite exact-build proof executes the returned callback and both actual
native marker helpers continuously in one x86 machine. A compatible truthy
closure-upvalue marker passes; an absent, nil or false argument marker selects
the callback's error message and reaches `lua_error` import entry. The import
instruction does not execute, and no error response or unwind is supplied.

The executable SHA is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Four source receipts are pinned: program facts, factory chain, marker semantics
and marker native conformance. The complete 269-byte callback owner is checked;
selected code is its 139-byte prefix from RVA `0x002ec110` through exclusive
`0x002ec19b`, plus the complete 84-byte marker body. The 223-byte union has
76 static sites and 66 executed sites. The ten selected assertion-arm sites
do not execute. No class operation, allocation, table transfer or epilogue is
selected as a continuation.

The 432 cases combine all 16 frame alignments, three caller/volatile profiles,
three truthy upvalue marker kinds (zero, empty string and table), and three
argument modes (no metatable, metatable with nil marker, metatable with false
marker). Lua zero and empty strings remain truthy. The independently authored
[request model](native_lua_class_callback_error_semantics.md) tracks the original
argument, compatible closure upvalue, both marker lookups, restored stack
prefixes and selected error-message token. A separate runtime controller
consumes actual API argument words and compares every reached identity
transition against that model.

The parent obtains nonzero userdata with `lua_touserdata(L,-10003)`. It calls
the native marker at `0x002eb560` first with ECX=L and EDX=-10003, then with
ECX=L and EDX=1. The first marker has a metatable and a truthy lookup; the
second has no metatable or a false lookup. Native helper returns preserve
their frames and restore the Lua argument prefix. The parent tests AL alone:
one for its upvalue marker and zero for the argument marker. Supplied high
24-bit words remain independently checked through actual returns and following
API-entry GPRs, without treating whole-EAX nonzero as Lua truth.

Each native child oracle receives the current parent pages, registers and real
CALL continuation. No separately generated child fixture replaces that state.
The marker's independently specified final-stack corollary also checks its
frame writes. Actual child instructions execute in the same machine as the
parent; neither helper is substituted or delegated to a separate native run.
Exact traces contain 34 parent instructions and 27 first-marker instructions,
then 11 or 27 second-marker instructions: totals of 72 or 88 per case.

With callback entry S and frame F=S-4, idle ESP is F-36. Both marker calls enter
at F-40 and return to F-36. The final pushstring import enters at F-48 with
`[0x006ec194,L,0x0083c99c]`. Its normal cdecl return pops only the return word;
the parent retains its argument words, pushes L and calls the error import.
At error entry ESP=F-52 with `[0x006ec19b,L,L,0x0083c99c]`. Every physical API
frame, continuation, incoming GPR and supplied response is checked.

At the endpoint EBP=F, EBX=L, ESI is actual supplied userdata, and EDI remains
the staged touserdata target. EAX is the supplied parent pushstring result
zero; ECX and EDX are its supplied volatile words. Its flags are checked under
mask `0xcd5`, including clear DF. Cookie XOR F is stored at F-8, userdata at
F-20, and original EBX/ESI/EDI at F-28/F-32/F-36. The callback establishes no
FS registration. No epilogue, security-cookie verification or caller return
occurs. Ordered native memory events and all mapped pages preserve the opaque
userdata, original caller ancestors, literal bytes, IAT padding and scratch
cells except independently specified native writes.

The sweep executes 35,712 native instructions and supplies 4,608 normal Lua
responses. Its 864 native marker calls lead to 432 error boundaries. All 18
controls reject for specified reasons, covering protected memory and frames,
cookie setup, supplied result/flags, API and error arguments, message identity,
and mutations of each native AL guard that enter excluded paths.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_callback_error_conformance.json`.
Canonical SHA:
`1c720f1a11c848aa2e5c9ef31dbb4aea6eb9e24bcb1867b30f463cb2d35ff988`.
File SHA:
`970e677a0ea99e2ae9eabf27fb825fd70f0efdd2845e991b7d7f6ce89d2b9a6e`.
The CLI supports build, exact verify and PE-free verify-structure, checking
deterministic UTF-8 LF bytes. Native rebuilding belongs in isolated processes.

This proof excludes actual Lua VM, imported DLL and metamethod behavior,
assertion arms, `lua_error` execution or response, unwinding, callback return,
class operations, table transfer, cookie verification, arbitrary pointer
domains, source-level ownership and program-wide accounting promotion. The
factory return and successful callback have separate conditional proofs;
their receipt existence does not prove invocation by a live Lua VM.
