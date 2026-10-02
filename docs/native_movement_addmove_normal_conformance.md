# Continuous selected normal AddMove proof

The native proof in `src/observatory/native_movement_addmove_normal_conformance.py`
executes the selected count-two `0x257340` AddMove arm through record
construction, path assignment, record copy, append, both temporary destructors,
caller path release and cookie checking. Three successful sixteen-byte
allocation responses and three successful free responses are supplied.
Independent source, CLI and receipt review is GO. All 162 independent checks
pass without skips: fourteen expensive execution and CLI checks in 565.64
seconds, then 148 fixture, schema and rejection checks in 129.77 seconds after
correcting a test adapter's unrelated unused-page assumption. The correction
preserves complete typed equality with the handwritten packet oracle.
Both direct-code and forged-model workers additionally assert empty machine
construction ledgers after every rejection; the four changed normal-movement
workers pass their focused gate in 24.40 seconds.

The canonical receipt seal is
`1f7f77d9ef362f2b9157cc444b43b1981fd5a1173c35e3788f275c2f73d89f88`.
The deterministic UTF-8 LF receipt is 1,235,636 bytes with raw SHA-256
`afaf03d30cd132040f9afedb92338002fc45d16e508e3a42de8432b50faa4c0f`.
Its 48 recipes combine sixteen alignments with three profiles of parameter
bits, initial flags, cookie and SEH values. Each executes 2,089 instructions,
1,293 ordered accesses and 24 complete states, including six imports and the
outer entry/return. Totals are 100,272 instructions, 62,064 accesses, 1,152
states, 144 supplied allocations requesting 2,304 bytes and 144 supplied frees.
All 120 controls have distinct state-role and corruption-kind reasons.

Twenty full selected bodies total 3,727 bytes and 1,206 loaded instruction
sites; 804 sites execute. The normalized point anchor is
`1a4b2521a802a2dd8c42414f5481c92c820d42708b40f217dd3bbb3a124f54b6`.
Nine input evidence identities, common build identity, complete body hashes,
sizes and ranges are checked before executable loading. Code packets must
exactly partition the selected bytes before a machine is created.

One x86-32 Haswell machine executes each case in seven emulation starts around
the six supplied responses. Actual helper calls run their selected bodies.
Every observed state checks all eight GPRs and eight XMMs, full mapped pages,
ordered access prefixes, defined flags, DF and installed endpoint. Each import
also checks the four physical caller words and response preservation. SAR uses
mask `0xc5`, TEST uses `0x8c5` and ordinary arithmetic uses `0x8d5`.

Before execution, the complete fourteen-field pure packet, fixture geometry,
typed child envelopes, event replay and all state prefixes are checked. The
caller free's full eight-field packet and join are closed before transporting
its checked final RET continuation. Reviewed nested child semantics remain
trusted; this proof does not independently reject every coordinated child
forgery. The independent observers use handwritten predecessor laws and attach
after CPU selection. Capture receives detached expected, fixture and register
identity data after constructing the actual observation.

The record's raw parameter is loaded into XMM0 with zero upper bits, its type
is four and mode is zero. Receiver end advances by 308 bytes. The three path
copies request sixteen bytes each. Free order is the second temporary path,
first temporary path, then original caller path. Final EAX is one, ECX is the
cookie, EDX is the supplied volatile free-response value, ESP advances twenty
bytes, nonvolatile registers preserve and other XMMs preserve. Full page
checks include record padding and original source preservation.

The receipt covers eight empty strings, a two-entry path, existing receiver
capacity and ordinary successful API responses. Other counts, nonempty strings,
capacity growth, failures, exception unwind, ownership, Lua callers and gameplay
remain separate gates. No whole-program body-accounting promotion follows.
