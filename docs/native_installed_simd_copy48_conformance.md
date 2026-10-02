# Installed 48-byte SIMD copy

The new standalone contract closes the exact forward copy48 path. The old
4,992-case native copy matrix omits length48; its receipt and default vectors
remain unchanged. This proof supplies the missing installed copy ingredient
for a later full6/cap6 resize to capacity9.

The pure model consumes actual immutable pages, eight uint32 GPRs, eight
uint128 XMM values, source/destination addresses, caller return and incoming
flags. ESP=C identifies four existing caller words [return,D,O,48]; the
adapter constructs no fixture. Its chosen domain has D>O+48, disjoint source48,
destination48, stack[C-8,C+16), feature page and selected code. Extent ends
must remain representable uint32. The complete feature page is retained and
DWORD VA00893f30 must be93939393. Supplied DF is clear; final AF is unclaimed.
Boundary tests reject exact adjacency because it is outside this chosen domain.

One32-byte MOVDQU block loads both source vectors before storing either,
followed by four scalar DWORD read/write pairs at offsets32,36,40,44. All
copied values derive from the original48-byte snapshot. The69-instruction
path visits51 sites, with no byte tail or alignment NOP. Unicorn2.1.4 reports
each architectural16-byte MOVDQU transfer as two ordered8-byte halves. Only
RVA36ea60/64/69/6d admit these exact halves; the26-event contract explicitly
describes normalized hook witnesses rather than architectural widths.

Return EAX=D, ECX=0 and EDX=DWORD(original O+44); ESP=C+4. EBX, ESI, EDI
and EBP survive. XMM0/1 contain original source bytes0..32, while XMM2..7
survive. Defined flags are44 under mask8C5, with DF0 checked separately.
Complete pages change only at D48 and the two saved ESI/EDI DWORDs. All old
source, ancestor stack, destination padding/spare24 and feature/cookie bytes
are independently preserved.

The48 cases couple16 source/destination/stack alignments with three payload,
GPR and XMM profiles. O=DATA2800+a, D=DATA4800+a and C=STACK1000+a; six
complete data pages are retained. Distinct nonzero final DWORD sentinels
1122AA48/EEDDCB48/D15C0048 prevent the stale copy32 EDX=0 law from agreeing
accidentally. The third profile otherwise resembles six retained records.
Native execution runs in one machine with no imported API response or helper
delegation. Exact code bytes and all59 point records bind to three pinned
predecessor sources, across169 loaded bytes and two ranges.

Native totals are3,312 instruction occurrences,2,304 copied bytes,1,248
accesses,192 wide reads/writes and192 scalar-tail reads/writes each. All31
controls reject at their intended boundary:25 machine mutations and six
event/path-record mutations. Reordered/missing halves, scalar corruption,
restored-write records and a byte-tail trace injection are record mutations;
they do not establish execution of their represented instructions or stores.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_installed_simd_copy48_conformance.json`.
Canonical SHA256
`cc7ba0512777a3d8ed06c5c720857d364296935fcaeb703ca9221938c7ca7cf7`;
file SHA256
`fcd21af5a4e69983dc9d3c91763e4ccd2c7f3c283705c8f46aa692e41f5db94b`;
21,299 deterministic UTF-8 LF bytes. CLI commands are `build`, executable
`verify` and source-pinned `verify-structure`.

All80 checks pass without skips, including48 pure checks,16 isolated actual
captures, all31 controls and exact CLI rebuild/verify/structure. Independent
tests reconstruct all events,
registers, XMMs, snapshots and complete pages; test a source crossing pages and
an arbitrary unaligned caller frame; reject typed aliases, overlap/wrap and
fixture relabeling; and compare actual native captures against those laws.
Independent source/CLI/test and published
receipt reviews are GO; protected user files remain unchanged.

Resize, growth, allocation/free, class append and actual callback7 remain
separate future joins. No heap ownership, unmapping, hardware/SSE environment,
failure/unwind or whole-program accounting is inferred. Independent alignment
combinations outside the coupled corpus and other copy paths remain excluded.
