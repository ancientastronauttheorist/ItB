# Continuous factory record construction

This finite exact-build proof extends the
[factory and initializer prefix](native_lua_class_factory_initializer_prefix_conformance.md)
through native helper `0x0007c600`, allocation retry `0x003574db`, thunk
`0x00379f52` and heap wrapper `0x0038942b`. Only one successful stdcall
HeapAlloc response and the seven existing cdecl Lua responses are supplied.
The native record helper and all three allocation bodies execute continuously
in the same x86 machine.

The exact executable SHA is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Seven source receipts are pinned: program facts, factory chain, initializer
chain, factory prefix, joined initializer prefix, self-linked record helper
chain and the native vector-allocation receipt. The latter contributes the
exact retry, thunk and heap-wrapper code; its vector allocation body is not
selected or substituted. The 41-byte helper SHA is
`bf6d8eea868843a089fcc2b74af1426c5f71328fc018f028310cc48259f0dda1`.

The corpus has 1,728 cases: every one of 216 factory vectors combined with
two record address biases `{0x100,0xfff}` and four offsets `{0,7,15,31}`.
The bias `0xfff` with offset zero crosses a page boundary in the first DWORD
store. All geometries have a disjoint writable 24-byte supplied record.

Let initializer frame be `G`. Helper entry is `H=G-36`; retry entry is
`N=H-8`. At the HeapAlloc import, ESP is `N-36=G-80`, with stack words
`[0x00789463,heap_handle,0,24]`. Every entry GPR and stdcall continuation is
checked. The API returns the supplied record pointer `P`, preserves mapped
memory and nonvolatile registers, and consumes its three arguments plus the
return word. Native wrapper, retry and helper returns restore their frames.

The independent [record model](native_self_linked_record_semantics.md) specifies
DWORD stores of P at offsets 0, 4 and 8, then WORD `0x0101` at offset 12.
Bytes 14 through 23 retain their original values. After the actual helper RET,
initializer instructions push zero and store P through ESI into userdata
offset 52. The machine stops at `0x002ead94`, before the next initializer
instruction. These field facts assign no source-level ownership or type.

At that endpoint, EAX=P, ECX=P+8, EDX is the supplied heap volatile word,
ESI=userdata+52, EDI=userdata, EBP=G and ESP=G-36. The active nested FS chain
and original ancestors are preserved. The last flag-setting instruction is
the helper TEST of P+8, checked under mask `0x8c5`; AF is undefined. The oracle
reconstructs every ordered native memory event and all mapped data pages,
including heap globals, IAT slots, original padding and stack scratch cells.

The selected union has 195 sites, 160 executed normal sites and 576 bytes.
Across the corpus, 609,408 native instructions execute: 67,392 initializer
instructions, 27,648 record-helper instructions and 58,752 allocator
instructions, plus factory instructions. Supplied API counts are 12,096 Lua
calls and 1,728 HeapAlloc calls. All 30 controls reject with specified reasons.
New controls cover record links, marker, padding, tail, heap global, stored
record, heap request and heap response. The inherited `helper_return` control
now mutates the former helper-return scratch cell at G-36, overwritten with
zero by the native initializer push. It does not check a live return address.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_record_conformance.json`.
Canonical SHA:
`94fb1682f5d89c131e6fe2eab62e926f0f4b71494d0fa12a5e89762dd8253a79`.
File SHA:
`bc514c41fd8c2779e4e8c97aee406d4c05b4cbada41aa5daaf9e474e57372c23`.
The CLI supports build, exact verify and PE-free verify-structure, with all
seven source receipts required. Native execution runs in isolated processes.

The original factory and initializer-prefix receipts remain separately
byte-identical after adding the private fixture and heap hooks. This proof
excludes actual imported DLL behavior, allocation failure, retry handlers,
heap ownership, later initializer Lua calls, both function returns, remaining
factory instructions, real VM behavior, exception handling, cookie checking,
arbitrary memory domains and program-wide accounting promotion.
