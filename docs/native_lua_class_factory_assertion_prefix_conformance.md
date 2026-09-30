# Native factory context assertion prefix

This finite proof executes the factory, initializer, actual record helper and
native allocator chain continuously through the context guard's minus-two
assertion arm. Execution stops before the first instruction at native helper
RVA `0x00379cc2`. No helper response is supplied.

The executable SHA is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Nine sealed sources are pinned: program facts, factory chain, initializer
chain, record chain, allocation conformance, factory prefix conformance,
initializer prefix conformance, record conformance and complete normal
factory conformance. Full factory and initializer body identities are checked
before selecting their 231-byte and 395-byte prefixes. The selected record,
retry, thunk and heap-wrapper bodies add 41, 51, 11 and 78 bytes.

The 807-byte union has 270 static sites and 221 executed sites. The normal
path executes 71 factory sites plus four loop instructions per name byte,
100 initializer instructions, 16 record instructions and 34 allocation
instructions. Unexecuted selected sites comprise twelve factory error sites,
fourteen prior-reference removal sites and twenty-three allocation alternate
sites. The corpus contains 5,184 cases, retaining all 1,728 record geometries,
name and independent-pointer configurations across three registry profiles.
Every case supplies eighteen normal Lua responses and one successful heap
response. Only the context guard is changed to `0xfffffffe`.

The independent [logical model](native_lua_class_factory_assertion_prefix_semantics.md)
checks the eighteen requests, original argument plus userdata stack, two table
identities and two registry bindings. The separate physical oracle derives
native API frames, incoming registers, supplied volatile responses, ordered
data events and final pages. The runtime Lua observer consumes the actual
physical arguments. All fourteen logical userdata fields, the real allocated
self-linked record at offset 52 and untouched offsets 48, 64 and 68 are
checked. The only context read is offset 12; later offsets 8 and 16 are not
read. Registry, graph and ID-map contracts from the normal-return proof do
not execute beyond this boundary.

Let entry ESP be S, factory EBP F=S-4 and initializer EBP G=F-52. At assertion
entry ESP=G-48 and its words are
`[0x006eae7b,0x0083c6b0,0x0083c680,96]`. The independent cdecl derivation
accounts for the trailing zero already present at record resume G-36; two
28-byte cleanups and the later 40-byte cleanup leave G-32 before the
three-argument assertion CALL. Pointer contents are neither read nor
validated; this proves the native pointer and scalar request words.

At the endpoint EAX is the context pointer, EBX is the settop binding, ESI=L,
EDI is the userdata pointer and EBP=G. ECX and EDX are the last supplied Lua
volatile words. CMP of minus two against minus two defines flags `0x44`
under mask `0xcd5`. The active FS head is G-12, chained through the outer
factory record at F-12 to the original head. Both cookies and saved frames
remain intact. Neither epilogue has executed.

The sweep executes 2,144,448 native instructions, supplies 93,312 Lua responses
and 5,184 heap responses, and reaches 5,184 assertion boundaries. All 41
controls reject for their specified reasons. They cover protected data and
call words, saved frames and cookies, API requests and responses, actual
record construction, Lua identity, final registers and defined flags, plus
the guard mutation that leaves the declared prefix. Inherited control names
for later fields check that those fields remain untouched here.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_assertion_prefix_conformance.json`.
Canonical SHA:
`c164d95f08507d66c26fae898a1f00dff84ce1db64a14b380122f66ed00ae59f`.
File SHA:
`a0dcaf08f40f8aa82baa07524765c88eaebefc69103682ed8ed01b44af2e06db`.
The deterministic UTF-8 LF receipt is 1,197,155 bytes. The CLI supports build,
exact verify and PE-free verify-structure. Native execution runs in isolated
subprocesses. The optional shared physical oracle leaves the normal-return
path unchanged; its earlier exact receipt was rebuilt byte-identically.

Assertion-helper execution or response, assertion delivery, recovery, unwind,
both function returns, later registry and metatable requests, closure creation,
live VM behavior, cookie verification and program-wide accounting promotion
remain excluded. Earlier helper structural proofs do not supply these runtime
contracts.
