# Native normal factory prefix

This finite exact-build proof executes the factory at RVA `0x002ec220`
continuously until native initializer entry `0x002eacf0`, before its first
instruction executes. It uses the independent
[request model](native_lua_class_factory_prefix_semantics.md).

The exact executable SHA is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Program facts, the factory chain and initializer chain are canonical-pinned.
The 296-byte factory owner has SHA
`8a9c01de90919d67efa728e4ed9e41e9f9d68fa7f0faf0e8abbdd809cce91f9e`.
The selected 231-byte prefix has SHA
`e2c23a81fc721e20d333ada784b7e7c7dd7660782794b8e510ba824c311b299f`.

The corpus has 216 cases: six measured lengths `{0,1,2,15,16,255}`, three
byte patterns, three address alignments `{0,7,4095}`, equal or distinct string
pointers and two caller profiles. Names at alignment 4095 cross the page
boundary when the terminating NUL lies in the next page. Bytes following the
first NUL remain opaque protected data. The supplied object-length response
equals the first NUL offset; those trailing fixture bytes are not additional
Lua string contents.

Each case supplies seven normal cdecl Lua responses. Exact native API entry
registers, stack arguments, return addresses and continuations are checked.
The runtime substitutes imported APIs only. All selected native instructions
execute in one x86 Unicorn machine, including the inline byte loop, prologue,
cookie setup, active FS registration and initializer call instruction.

The first `lua_tolstring` result is measured. The second result is handed to
the initializer. Distinct results are deliberately supported and checked;
their pointer equality or byte equality is not implied. A separate unchanged
Lua argument and storage premise would be needed to call the handed-off bytes
validated bytes.

For entry ESP `S`, the frame pointer is `F=S-4`; idle ESP is `F-36`.
Initializer entry ESP is `F-48`, with words `[0x006ec307,L,P2]`,
EAX=ECX=userdata, ESI=L, EDI=P2 and EBX equal to the staged pushstring binding.
The independent oracle reconstructs every native memory event, all mapped
data pages, saved caller cells, local userdata cells, FS:[0] and the final
registers. Final TEST flags use mask `0x8c5`; AF is undefined and excluded.

All 71 normal instruction sites execute; 12 error-arm sites are excluded.
The corpus executes 56,952 native instructions and supplies 1,512 API calls.
Each case checks the independent `71+4n` instruction count. Fifteen controls
check ancestor, name suffix, second buffer, userdata, IAT padding, cookie,
FS chain, saved register, local userdata, handoff pointer, result register,
defined flag, API argument, second response and unequal length detection.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_prefix_conformance.json`.
Canonical SHA:
`cebf742aac9945f22829e2d3b1b387ff618840217b3c9a2330a8335ca3a0d0ed`.
File SHA:
`dc56cc73bf36a0f1e642638f5d5f1b7ad80f7121f45dde197f0256f642bd9955`.
The CLI supports build, exact verify and PE-free verify-structure, with all
three source arguments required. Native tests execute only in subprocesses.

This boundary establishes conditional native handoff behavior for the declared
fixtures. It does not execute the initializer, return the factory closure,
run a real Lua VM, establish allocator ownership, handle errors or null
userdata, dispatch exceptions, verify the cookie, or promote program-wide
accounting. Larger or arbitrary memory domains remain unproved.
