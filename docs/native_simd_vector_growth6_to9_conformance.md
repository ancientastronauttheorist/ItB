# Continuous ordinary growth from capacity six to nine

This finite native proof executes the growth owner at RVA `0x002eb620`
and its installed resize child continuously in one machine. With six live
eight-byte records and capacity six, the owner selects capacity nine: spare
zero, half three, proposal nine, minimum seven and room `0x1ffffffc`.
The child requests 72 bytes, copies the old 48 bytes, supplies successful
ordinary pointer free and writes the header `[D,D+48,D+72]`. Six records remain
live and 24 bytes remain spare. Heap responses are supplied premises.

## Actual caller and child join

Let G be growth entry ESP, H the header, O the old begin and D the supplied
allocation result. Initial header words are `[O,O+48,O+48]`. The finite corpus
uses caller words `[0x04000000,1]`; the second word is consumed by RET4 but
never read on this selected path. It remains protected input memory.

Eight prefix events save ESI, EDI and EBX, read capacity/end/begin, and install
the resize request and continuation. Resize enters at R=G-20 with caller
words `[0x006eb66e,9]` and GPRs EAX9, EBX`0x1ffffffc`, ECX/ESIH, EDX9,
EDI6, original EBP and ESPR. CMP9 versus7 defines zero under mask `0x8d5`;
the fixed DF-clear incoming `0x246` leaves actual raw EFLAGS `0x202`.
The machine validates this complete entry before executing the child.

The [actual-page resize law](native_simd_vector_resize6_to9_semantics.md)
consumes those installed pages and registers. Independent owner equations
compare its complete 18-field packet, including full seven-field allocation,
ten-field copy and eight-field free packets. No standalone fixture is
transplanted and no intermediate native helper is replayed. The only machine
stops supply successful HeapAlloc and HeapFree responses.

| Boundary | ESP | Installed words or state |
|---|---|---|
| Resize entry | G-20 | `[0x006eb66e,9]` |
| Allocation helper | G-48 | `[0x006eb695,9]` |
| HeapAlloc | G-96 | `[0x00789463,heap,0,72]` |
| Copy entry | G-56 | `[0x006eb6a6,D,O,48]` |
| Free guard | G-56 | `[0x006eb6c8,O,6,8]` |
| HeapFree | G-88 | `[0x00789172,heap,0,O]` |
| Resize return | G-12 | EAXD+48; endpoint `0x006eb66e` |
| Growth return | G+8 | Restored nonvolatile GPRs |

The protected stack is `[G-96,G+8)`. Copy-return EDX equals the original DWORD
at O+44; free entry retains that value. Guard division subsequently leaves
EDX7 before HeapFree. The API frame has no byte-count argument. Copy flags
define `0x44/0x8c5`, with AF unclaimed; free-entry SAR3 defines four under
mask `0xc5`, with AF/OF unclaimed. DF is checked separately. Final defined
flags follow ADD(G-52,12) under mask `0x8d5`.

The outer packet has exactly 21 fields: the resize schema plus resize entry,
resize return and the detached local resize packet. Child events remain local
104; outer events are prefix8 + child104 + suffix4 =116. Seven actual boundary
captures bind all GPRs, XMMs, raw/defined flags, DF, endpoint and full-page/event
hashes. Both imported request observations are complete machine reads before
the supplied response. Full pages preserve old48, spare24, ancestors, unused
argument, error storage and runtime padding outside documented writes.

## Evidence and reproduction

The corpus contains 48 cases: coupled alignments zero through fifteen and
three distinct payload/GPR/XMM profiles. All cases and 43 intended controls
pass. Controls comprise 39 machine mutations and four injected event/path
records; record injection does not prove execution of represented stores.
The receipt pins eleven sources and exact contiguous code packets:
289 loaded sites/754 bytes, 217 executed sites, 11,280 instruction occurrences
and 5,568 ordered memory events. Totals are 48 resize/allocation/free calls,
2,304 copied and retained-old bytes, 3,456 allocated bytes and 1,152 spare
bytes; each wide/scalar read/write total is192. Accounting promotions are zero.

Direct point-packet canonical SHA:
`a2288f29ad9c57968d54196062f106d9111f45f28c75c80cf31db1964aa42b44`.
The separate receipt, prefix `windows_build_13725832_31fe35265598_`, is
`native_simd_vector_growth6_to9_conformance.json`, 63,203 bytes, UTF-8 LF:

- Canonical SHA: `23eeb7708d498a7f0187b6031835c07d62e6ec99e27326734460808edaceaf25`.
- File SHA: `777279d377fb0cfe9447076aac11bbe230f85d4e5fcc8e0cb11595e11fe155e3`.

The corresponding script supports `build`, `verify` and `verify-structure`.
Every command requires its eleven dynamic source flags; native commands also
require `--executable`, and verification requires `--evidence`. With the exact
executable and private runtime configured, all107 focused tests pass without
skips: handwritten full-state laws, 16 isolated actual captures, all controls,
source/code/receipt mutations, exact rebuild and all three CLI commands.
Independent source/CLI and published-receipt reviews are GO. Old resize,
installed48, generic copy and fixed4-to6 receipts remain unchanged.

This proves the finite supplied-success ordinary growth path. No class append,
seventh callback, allocator ownership, failure/error behavior or full-game
accounting is inferred. The next class join requires a broader actual-page
growth law that preserves its arbitrary unused caller word and installed
`0x006eb205` continuation; it then needs its own native proof.
