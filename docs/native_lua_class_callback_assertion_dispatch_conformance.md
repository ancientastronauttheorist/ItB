# Continuous callback assertion dispatch

The selected callback validation failures now execute continuously from
RVA2ec110 through the actual assertion-parent entry RVA379cc2, its fixed
mode3 first getter and conditional second getter, to the selected opaque
child CALL entry. The same Unicorn machine carries the callback frame into
the dispatcher. At the join there is no stop/resume, register rewrite,
replacement page, host patch or delegated native helper run.

Before fall-through, the runner checks the complete original callback prefix:
all mapped pages, ordered data accesses, exact instruction path, supplied Lua
requests/responses, abstract Lua calls/stack, eight GPRs and defined flags
under maskCC5. It then captures actual full GPRs, EFLAGS, EIP and page bytes,
checks these against the independent prefix contract and recomputes the pure
dispatcher law from the actual ESP and caller words. Refreshed page hashes
cannot substitute for page-byte equality. The actual unclaimed AF survives
capture; no complete boundary flags value is imposed.

The old prefix observation projection uses exactly its original pages,
events and three-key vector. Its 192-case aggregate SHA256 remains
`49e83a1601e72244d5cfab28d2e059ee2bdeb135dbce5687acb01183fd6fccc8`,
identical across all four dispatcher recipes and to the pinned predecessor.
The new getter page is mapped before callback execution and checked separately
at the join; it is excluded from that old projection. The full new join digest
is `ba552080eb7253ea40e8518ba7af6d21a46590110f8a3c3316b846a5f346b5ca`.

The 768 vectors combine all 192 original null/absent/nil/false producers with
four supplied getter recipes: (1,FFFFFFFF), (0,1), (0,2), (2,FFFFFFFF).
Both alternate and normal paths have 384 cases. Together they make 768
first-getter calls and 384 conditional second-getter calls. The normal child
receives condition, file, line and the original callback assertion continuation
as its fourth argument; alternate receives the first three words only.
All final GPRs, defined CMP/TEST flags, getter entry/return frames, arguments,
ordered instruction-tagged accesses and complete retained pages are checked.
Execution stops before the first opcode of RVA379550 or RVA379b31.

Nine source pins bind five ranges with 326 instruction bytes and 119 loaded
sites. The 98 executed sites partition into 59 original prefix and 39
dispatcher sites. Native instruction totals are 33,024 prefix plus 24,192
dispatcher, 57,216 combined. There are 2,880 supplied Lua requests, 576 marker
calls and 768 actual assertion joins. Global stores, opaque child instructions
and whole-program accounting promotions remain zero in this corpus.

The 40 rejecting controls retain all 16 prefix controls, namespace the 19
standalone dispatcher controls, add three machine join corruptions with
refreshed page hashes and add two prefix event/path-record corruptions.
Missing/extra/restored-global-write dispatcher records and mutated traces
are injected observations, not executed native global stores or opaque
instructions. Lua identity controls concern the supplied abstract controller.
Every control rejects at its declared boundary.

The published receipt is
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_callback_assertion_dispatch_conformance.json`.
Canonical SHA256 is
`f6693e3b32ec3776e6b1193e582af68f4df77d6178a864e5cffb545eeaff11ce`;
file SHA256 is
`efea61a5c1bf67e737c2e31ecc2a49bba01bb667f90f5cfbff4c5414e34c693f`.
Its deterministic UTF-8 LF encoding has 117,006 bytes. The CLI builds,
executes verification or verifies source-pinned receipt structure.

Independent tests reuse the handwritten predecessor frame/event/page equations
and standalone dispatcher flag/path equations. They compare actual captures
against those expectations, cover all 16 alignments, three profiles, four
failure families and four dispatch recipes, and reject coordinated register,
page/hash and projection forgeries. Strict schemas reject Boolean words and
fixture relabeling. Receipt and all nine source dependencies are mutation
tested separately.
All 114 checks pass without skips, including 74 pure join checks, 16 isolated
actual capture specimens, all 40 controls and exact CLI rebuild, verification
and structure verification. Independent source/CLI/test and published-receipt
reviews are GO. All 13 protected user hashes remain unchanged.

Lua return values and runtime getter DWORDs are supplied synthetic premises.
This does not observe actual bootstrap global defaults or imported DLL
behavior. Opaque child bodies, assertion cleanup, callback return, trap,
dialog/abort/unwind, CRT identity, hardware execution and heap ownership remain
excluded. Existing standalone and prefix receipts remain unchanged. The full
game remains unfinished.
