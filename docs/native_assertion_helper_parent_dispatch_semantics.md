# Logical assertion parent dispatch

The standalone model describes RVA379cc2 from its entry through the actual
CALL entry of one selected opaque child. It always supplies mode3 to the first
native getter at RVA38e392. This selects the read of DWORD VA008b7534 without
executing its setter or invalid-mode descendants. Only a zero first result
calls the two-instruction getter at RVA38c89f, reading VA008b7318. The alternate
child is selected iff first==1 or first==0/second==1; every other value selects
the normal child. Getter inputs are strict uint32, including high-bit values.

With original ESP=Q, the parent saves EBP at Q-4 and ESI at Q-8, then loads
the original caller return into ESI. Mode3 is pushed at Q-12; first CALL return
at Q-16 is VA00779cd2. The getter saves parent EBP at Q-20, reads mode, reads
its global, restores EBP and returns. Parent POP restores ECX=3 and ESP=Q-8.
The optional second CALL uses return VA00779ce1 at Q-12 and returns to Q-8.
No selected instruction writes either global.

Normal child RVA379550 receives four arguments in order: condition, filename,
line, original caller return. Its frame is Q-28 with return VA00779cf5.
Alternate child RVA379b31 receives the first three arguments only; its frame
is Q-24 with return VA00779d09. Both stop after the parent CALL pushes that
return word, before any opaque child instruction. Cleanup, parent RET and
alternate INT3 remain outside this model.

Final EAX is first unless first==0, then second. ECX=3, ESI is the original
caller return, EBP=Q-4 and ESP is the selected child frame. EBX, EDX and EDI
survive. Final CMP(value,1) defines CF/PF/AF/ZF/SF/OF under maskCD5 including
preserved DF0. For first nonzero other than1, final TEST(first,first) uses
maskCC5, leaving AF unclaimed. Independent equations include signed-overflow,
nibble-borrow and parity edges. The model accepts strict uint32 incoming flags
with clear DF; these instructions preserve DF rather than clearing it. No
full EFLAGS output is inferred from the default incoming246.

`apply` validates explicit caller/getter DWORDs against typed immutable pages.
`apply_to_pages` derives them directly from an arbitrary actual unaligned Q
without constructing a fixture or patching pages. Its premise reads are not
execution events. Outputs detach all eight GPRs, pages, exact ordered
four-byte accesses with source RVAs, selected instruction path and child/getter
packets. The complete stack span is [Q-24,Q+16) for alternate or [Q-28,Q+16)
for normal, disjoint from fixed globals and selected code extents. Byte
adjacency and an exclusive32-bit upper boundary are admitted; overlap and wrap
are rejected. All untouched page bytes and original caller words survive.

The254 tests pass without skips. They independently replay event/page writes,
check full getter frames and literal paths, cover the seven-by-seven getter
matrix, high-bit flag cases, argument order, typed schemas, detached outputs,
stack adjacency/wrap, actual-Q adaptation and incoming AF variation. The test
fixture avoids trying to write beyond32-bit memory before the model can reject
an invalid stack. Independent source review is GO.

This logical evidence derives from three pinned static boundaries. The
[native dispatcher](native_assertion_helper_parent_dispatch_conformance.md)
now passes its full2,352-case build; the continuous enclosing callback join
is next. Runtime global
values, opaque child behavior, CRT identity, dialog/abort/trap, unwind, hardware,
ownership and whole-program accounting remain unproved.
