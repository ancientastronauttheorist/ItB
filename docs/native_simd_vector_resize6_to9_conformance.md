# Ordinary six-record resize to capacity nine

This separate proof targets the native resize owner at RVA `0x002eb680`
with six live eight-byte records, capacity six, and requested capacity nine.
The successful path requests 72 bytes, copies the original 48 bytes through
the installed SIMD/scalar-tail helper, supplies successful free of the old
pointer, and writes the header as capacity, end, then begin. Six records remain
live and 24 bytes remain spare. Heap responses are supplied premises.

The old fixed four-to-six resize and its receipt remain unchanged. This
tranche does not establish the growth decision, class append, a seventh
callback, heap ownership, metadata allocation, failure behavior, or whole-game
accounting.

## Installed boundaries

Let `R` be resize entry ESP, `O` the old begin, `D` the supplied allocation
result, and `H` the header address. Initial words are `[O,O+48,O+48]` at `H`
and `[caller_return,9]` at `R`. The protected stack is `[R-76,R+8)`.

| Boundary | ESP | Installed words or resulting state |
|---|---|---|
| Allocation helper entry | `R-28` | `[0x006eb695,9]`; EAX9, ESIH, EBPR-4 |
| HeapAlloc entry | `R-76` | `[0x00789463,heap,0,72]` |
| Copy entry | `R-36` | `[0x006eb6a6,D,O,48]`; EAX/EDID, ECX48, EDXO |
| Copy return | `R-32` | EAXD, ECX0, EDXoriginalDWORD(O+44) |
| Free guard entry | `R-36` | `[0x006eb6c8,O,6,8]`; EAX/EBX6, ECXO |
| HeapFree entry | `R-68` | `[0x00789172,heap,0,O]`; EDX7 after guard division |
| Resize return | `R+8` | EAXD+48; header `[D,D+48,D+72]` |

HeapFree receives the old pointer. Its actual frame contains no byte-count
argument. The old 48-byte extent is a logical buffer bound, not an API size
word. The proof retains mapped old bytes for comparison and claims no real
heap release or unmapping.

The copy executes one 32-byte SIMD block followed by four scalar DWORD pairs.
All eight GPRs and XMM registers, exact ordered accesses, full pages, caller
ancestors, and installed continuations are compared at the actual boundaries
in one Unicorn machine. Boundary observations are machine reads taken after
validation. There is no intermediate native helper replay or fixture reseed.
The only stop/resume boundaries supply the two external heap responses.

The scalar tail leaves EDX equal to the original last DWORD at copy return and
free-guard entry. The guard subsequently divides `0xffffffff` by stride eight,
leaving remainder seven before HeapFree. Copy flags are `0x44` under mask
`0x8c5`, with AF unclaimed. At free entry, the three-bit SAR defines only
CF/PF/ZF/SF under mask `0xc5`; AF and OF are unclaimed. DF is checked separately
throughout. The owner return defines six arithmetic flags through its final
stack ADD under mask `0x8d5`.

## Ordinary allocation relocation

The predecessor allocation oracle admits synthetic pointers only in its old
four-page domain. The new destination is outside that domain. For count nine,
the ordinary result packet contains no metadata writes or pointer-bearing
memory events. The adapter calls the unchanged oracle at canonical
`0x06000800+a`, checks its complete seven-field packet against independent
ordinary equations, then transports only relation.result and returned EAX/ECX
to actual `D=0x06004800+a`. It binds the installed caller RET separately.
Stack, payload, events, request72, flags and preserved registers cannot change
through this transport. The actual native machine must independently produce
and validate D before the copy starts. The old receipt's domain is not widened.

## Evidence and reproduction

The separate finite corpus couples alignments zero through fifteen for stack,
source and destination with three distinct payload/GPR/XMM profiles. All 48
native cases and 30 intended rejecting controls pass. The receipt pins nine
predecessors and checks 249 loaded sites/660 bytes, 179 executed sites, 9,456
instruction occurrences and 4,992 ordered memory events. It records 48
allocation and 48 free summaries, 2,304 copied/retained-old bytes, 3,456
allocated bytes, and 1,152 spare bytes. Wide and scalar-tail reads/writes each
total 192. Accounting promotions remain zero.

The direct runner independently anchors the sorted unique instruction packets
to canonical SHA
`3cdbf66fbd4a4624d94cfba3f07d625732512a97e8689b0e15ee30c410bc4660`.
Every named body must have contiguous exact RVA coverage and matching byte
hashes. Overlapping code ranges must agree. Controls cover actual boundaries,
request words, preserved pages, registers, flags/DF, and injected event/path
records. Injected records do not establish native execution of their
represented writes or sites.

Receipt prefix: `windows_build_13725832_31fe35265598_`.
`native_simd_vector_resize6_to9_conformance.json` is 54,344 bytes, UTF-8 LF:

- Canonical SHA: `009f36e1b254058ec21f7af157f6e86ebfa18039abe24fce1690f9df97bc2949`.
- File SHA: `4c879a5946aae052b6644fd310be248aaa3caeb8e8eca39a656c423f7a533982`.

`scripts/itb_native_simd_vector_resize6_to9_conformance.py` supports `build`,
`verify`, and `verify-structure`. All commands require the nine dynamic source
flags; native commands also require `--executable`, and verification requires
`--evidence`. Set `ITB_EXACT_EXE` and the reviewed private runtime `PYTHONPATH`
for isolated native tests. All 115 focused tests pass without skips, including
the handwritten 48-vector page/event/ABI law, 16 isolated actual machine
captures, all rejection controls, source and receipt mutations, direct code
packet tampering, exact receipt rebuild, and CLI build/verify/structure.
Independent production-source/CLI and published-receipt reviews are GO.

The next join needs an actual-page resize adapter at the growth caller's
installed frame and `0x006eb66e` continuation. The standalone finite fixture
is not transplanted into that machine. Growth and class append remain separate
validation gates.
