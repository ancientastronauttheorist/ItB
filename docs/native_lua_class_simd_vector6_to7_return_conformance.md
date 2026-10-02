# Native existing-key class append from six records to seven

The class helper at RVA `0x002eb140` now has a finite continuous replay through
existing-key tree transfer, growth from capacity six to nine, an eight-byte
record append and normal caller return. All288 cases execute the native
allocation72/copy48/free-old48 path in one machine, then leave seven live
records and16 unchanged spare bytes. This closes this class-helper join;
the seventh factory callback, arbitrary tree/string inputs and whole-game
semantics remain open.

## Domain and continuous joins

The corpus reuses48 independently sealed existing-key tree fixtures, vector
alignments0/7/31 and two nonzero eight-register XMM profiles. Source and
destination have matching key sets of zero through seven nodes. All1,008
transfers update existing nodes, with no tree allocation. Successful supplied
HeapAlloc and HeapFree responses preserve all eight XMM registers.

With class entry stack `L` and userdata `U`, growth enters at `L-44` with
header `U+4` and the installed return `0x006eb205`. Its unused caller word
retains the actual preceding ECX. Resize enters at `L-64`; copy and free
guards enter at `L-100`. HeapAlloc and HeapFree imports enter at `L-140` and
`L-132`. The actual-page growth law checks its entire21-field packet and
complete18-field resize and7/10/8-field primitive joins before any class
append expectation is admitted.

Ten native checkpoints capture complete GPR/XMM/flags/DF, endpoint, full-page
and ordered-event hashes. Both imported boundaries capture the actual full
ABI before supplied responses. No child emulator or fixture transplant is
used. Only the four selected MOVDQU sites admit the emulator's two eight-byte
halves; the remaining16 copied bytes use scalar accesses. Copy return EDX is
the old DWORD at offset44. XMM0/XMM1 become the first32 source bytes, while
XMM2 through XMM7 retain their input values.

The final header is `[D,D+56,D+72]`. Old48, copied48, appended8, spare16, all
tree/key/argument pages, padding, stack, runtime globals and every mapped byte
are checked. The normal cookie return restores nonvolatile registers and
returns at `L+8` with clear DF. The independently handwritten new tail has
264 instructions and137 ordered accesses after the reused tree prefix.

## Receipt and validation

The normalized receipt is
`windows_build_13725832_31fe35265598_native_lua_class_simd_vector6_to7_return_conformance.json`:

- Canonical SHA256: `9103e9dd655eaeb9530b0c09f2ea2d050e6e5462c2f796ce3136e63264ff37e6`.
- File SHA256: `e0e0593001657ac09f32fd342c0ed30b21291db6ddf191a6780ef5993061bc60`.
- 298,913 bytes,20 source pins,939 loaded sites/2,440 bytes,398 executed sites.
- 376,956 executed instructions and171,252 ordered memory events.
- 288 allocation requests and288 free requests;13,824 copied bytes;16,128 live vector bytes;
  4,608 preserved spare bytes; zero accounting promotions.

All60 controls pass:55 rejected machine mutations, the exact cookie
first-failure frontier and four injected-record checks. Failure-handler
execution, allocation failure, new-key ownership, Lua behavior and arbitrary
runtime contexts are excluded.

The97-test focused suite passes without skips:96 passed in the full gate and
the remaining receipt-schema test passed after its range comparison was
normalized between the legacy `end_rva` and new `exclusive_end_rva` schema.
No production or receipt change was needed for that correction. Tests include
16 isolated actual captures, independently counted machine traces, complete
child/page/boundary laws, controls, source/receipt/code mutations and exact
rebuild plus build/verify/verify-structure CLI commands. Independent source,
CLI and published-receipt reviews are GO.

Use `scripts/itb_native_lua_class_simd_vector6_to7_return_conformance.py` with
every required source path. Native commands require the privately supplied
exact `--executable`; verification requires `--evidence`. Run isolated workers
serially with `ITB_EXACT_EXE` and the reviewed runtime `PYTHONPATH`, removing
`PYTHONFAULTHANDLER` and using pytest `-p no:faulthandler`.
Published evidence contains normalized facts and hashes, never executable
bytes or raw disassembly. The next distinct frontier is the AddMove/AddCharge
binding and selected movement-parent paths.
