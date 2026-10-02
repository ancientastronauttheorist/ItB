# Continuous native two-entry movement path clone

The selected two-entry path clone now has a finite continuous native proof.
All **123 independent focused tests pass** without skips, including nine
independently hooked actual-machine captures, the full 48-case observation
digest, all 59 intended controls, exact rebuild and all three CLI commands.
Independent native source, CLI and scalar-law reviews are GO.

One CPU19 Haswell Unicorn state executes the path owner at RVA `0x9a8e0`,
reserve at `0x9ac40`, the ordinary allocator chain and
[the scalar copy](native_movement_path_scalar_clone2_semantics.md). It stops
and resumes only for one supplied successful HeapAlloc response. No helper
native execution is delegated and the state is not reseeded between children.
The 48 recipes combine sixteen alignments and three complete page/register
profiles. Two sixteen-byte source and destination extents are disjoint.

Each case executes 136 instructions and 83 ordered DWORD accesses, including
four scalar read/write pairs. Totals are **6,528 instructions, 3,984 accesses,
48 allocation requests and 768 copied bytes**. All sixteen source bytes per
case, nonvolatile GPRs, eight XMMs and every unrelated byte of ten full mapped
pages are preserved. There are no frees or wide memory accesses.

The complete unchanged seven-field ordinary allocation packet is checked
against a handwritten count-two law before its fixed RET event sentinel alone
is rebound to the installed continuation. The supplied destination lies in
the existing allocator pointer domain; no pointer relocation is needed.
The prior allocator corpus omitted count two, so its native evidence comes
from this new continuous machine. The complete ten-field actual-page scalar
packet is separately checked before joining.

Seven checkpoints capture actual GPRs, XMMs, raw flags, defined flags, DF, PC,
full-page hashes and ordered event-prefix hashes. The imported HeapAlloc frame
also checks the installed return, heap handle, flags zero and request size
sixteen. Its supplied response explicitly preserves all pages, nonvolatile
GPRs, every XMM and DF. Reserve sets AL to one while retaining pointer-derived
high EAX bits; replacing full EAX with one is rejected. The final vector
header is `[destination,destination+16,destination+16]`, EAX is the destination
header, ECX is the source's final DWORD and EDX is its end. Final flags come
from the parent's stack ADD, after the scalar child's final CMP.

The 59 controls cover state at all seven checkpoints, full reserve EAX,
allocation request and response, final pages and ABI, plus three access-record
mutations and one trace-record mutation. Record mutations do not establish
execution of their represented accesses. Body substitutions and refreshed
point metadata cannot authorize new code. Independent test oracles handwrite
the owner, allocator and scalar joins and full pages; production expectations
and native observations do not supply their expected semantics.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_movement_path_clone2_conformance.json`.

- Canonical SHA-256: `1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b`.
- File SHA-256: `372f888f88a580e159997382de7241f7281fa5ac2cb42904639f550da769ca53`.
- 44,965 bytes, four source pins, seven ranges, 440 loaded bytes, 174 loaded sites and 126 executed sites.

CLI `scripts/itb_native_movement_path_clone2_conformance.py` supports build,
verify and verify-structure with program-facts, movement-binding,
allocation-composition and allocation-conformance sources. Native commands
require the exact executable; evidence is deterministic UTF-8 LF.

The imported allocation success is a premise. This proof does not establish
operating-system allocation, allocator ownership, unmapping, failure or unwind,
arbitrary path lengths, overlapping copies, effect-record construction/copy/
append/destruction, AddMove's ordinary path, AddCharge, runtime binding,
gameplay or whole-game accounting. Accounting promotions remain zero.
