# October 1 decompilation checkpoints

Continue on the human-authorized `codex/full-decompile` branch. The active
deadline is **October 1, 2026, 5 pm America/Chicago = 22:00 UTC**. Stop new
work then, safely finish current validation, push the final checkpoint, verify
protected files and remote HEAD, and pause `decompile-until-5-pm`.
The full game remains unfinished. Subagents inherit the primary model with
no explicit override; do not reactivate the older Astra agents.

The [September 30 handoff](decompile_handoff_2026_09_30.md) is the baseline.
Its final pushed HEAD was `a2e3595d`. The branch was pulled with `--ff-only`
before October 1 work; all thirteen protected baseline hashes matched.

Pushed checkpoint `0ce43627` closes actual produced receiver through class
first-null return. The subsequent full callback return is documented below.

## Actual produced receiver through empty-class return

[Documentation](native_lua_class_factory_callback_empty_class_conformance.md):
54 exact native cases join complete aligned factory output across a supplied
closure-invocation boundary to the returned callback, both native marker
helpers, and first-null class allocation through class RET4 at VA `0x006ec1bd`.
The callback/class phase is continuous in one machine. Current producer and
prefix pages are retained; no generated child pages replace them.

Canonical SHA:
`09117544ab5c8c4366aec36ee3bd295263157cdbd22455b1a1597d6eaf73851a`.
File SHA:
`4352b1a18d11b76a4ec99ba46103886a647d1af48dfa6789001d5350ff215fc2`.
Receipt size 195,298 bytes; 955 selected sites, 261 normal executed sites,
2,470 selected bytes; 35,820 factory and 15,552 callback/class instructions.
All 22 exact controls reject. Focused gate: **171 passed, no skips**;
new build/exact verify/structure modes and unchanged prior-entry rebuild pass.
Independent semantic review: **GO**. All thirteen protected hashes matched.

Source A/head reuse bytes are explicit, and the new host frame reuses historical
factory scratch. U=`0x0fffffcc`, embedded field U+52=`0x10000000`, actual
allocated P=`0x10000100`. Class C=`0x30001000`/`0x3000100f`, callback T=C+48,
original local pair at C+28. Cookie comes from retained producer bytes at
`0x00893f28`. V=`0x06002000` plus 0/7/31. Class updates only U+4/8/12;
the other fifteen DWORDs and all P24 remain preserved. ESP at class return
is T-40, while callback EBP remains T-4. Registry/table transfers and callback
normal return remain next boundaries.

## Next useful continuation

The actual produced receiver's full normal callback return is now sealed in
[the next composition](native_lua_class_factory_callback_return_conformance.md).
Its 324 cases cover both table transfers and the source-word copy, preserve
actual factory references/sentinel bytes, and retain five modeled Lua values
before zero-result return. Canonical SHA
`6b0f0ced057240a366ccd5c9545d482feb2d7fbcd3af70aaa5186779c3ad885e`;
file SHA `80c3c514d6ebe07d5dec4a25a900ffa30f6dc064a4822d6910c59a2ddd8035c7`;
293,817 bytes; 1,062 selected/368 executed sites in 2,746 unique bytes.
All 26 controls pass, including the actual callback-cookie failure boundary.
The complete gate passes **274 tests, no skips** (156 model, 41 new
conformance, 77 old spare/growth callbacks), including new build/exact verify
and byte-identical old receipt rebuilds. Independent semantic review: **GO**.
All thirteen protected user hashes remain unchanged.

## Actual produced receiver with bounded nonempty source

[Documentation](native_lua_class_factory_callback_tree_conformance.md):
1,296 exact native cases retain actual initially empty receiver/sentinel pages,
supply zero/one/three/seven reversed source keys in disjoint storage, then run
insertion, balancing, successor traversal, first-null vector growth and full
callback return continuously. No generated fixture replaces current pages.

Canonical SHA `a924cb10e338afa823ced7bf0fb3de20e8b8bb4b1e962fdcc299fec2f2b77614`;
file SHA `0d73e76a3be7e1a3b51d4be8662936a1e310d65f5c7924e0fb7eaac0cc5f0555`;
692,724 bytes, 26 pins. The 1,062 selected sites contain 713 executed sites:
76 callback, 539 class-operation, 27 marker and 71 table sites; 349 are excluded.
Empty/one/three/seven-node families reach 368/572/701/713 sites. Totals:
859,680 factory and 1,866,564 callback/helper instructions, 44,064 factory and
53,136 callback Lua requests, 1,296 factory allocations, 3,564 tree allocations
(85,536 bytes) and 1,296 eight-byte vector allocations. All 29 controls pass.

The gate passes **366 tests, no skips** (262 model, 63 new conformance,
41 predecessor full return). New build/exact verify and predecessor rebuild
are byte-identical. Independent review: **GO**; thirteen protected hashes match.
Key storage at `0x1c000fff + 32*i + (node_alignment % 4)` avoids actual names;
previous SEH and cookie come from retained producer pages. Copies preserve
source insertion IDs while routing to sorted destination IDs. Native destination
insertion is monotonically ascending, so other balancing orders remain open.
Final mutable U offsets are 0/4/8/12/56; thirteen other DWORDs and P12..23
remain preserved. Source construction, registry/VM effects and ownership are
still explicit premises; no accounting promotion.

## Two callbacks on verified actual return state

[Documentation](native_lua_class_factory_callback_repeat_conformance.md):
432 native cases retain verified first-return pages and all eight GPRs before
explicit second host invocation. The same source topology receives updated
payloads; existing destination IDs and sentinel bytes survive. Native vector
growth copies the actual old eight-byte record, requests free of its allocation,
appends the second record and completes the callback return.

Canonical SHA `b4b28a9a2f8675705257af3a100f50b72082d1c543a12aff2a5d76e17950966e`;
file SHA `b2999b07fe273580a4c49a93ec87a008db9decf2e1e67449ab4ed86665094355`;
389,842 bytes and 31 pins. The 1,115 selected sites contain 797 executed sites:
76 callback, 623 class-operation, 27 marker and 71 table sites; 318 excluded.
First calls retain the predecessor's 713-site union; second calls execute 546.
Totals: 286,560 factory, 622,188 first-callback and 520,560 second-callback
instructions, 432 frees, 1,188 existing payload updates and zero second tree
allocations. All 33 controls reject, including identity checks before host
patching, free handoff/response boundaries and native cookie failure.

The focused gate passes **260 tests, no skips** (205 model, 55 conformance),
including new native build and exact verification. The shared regression passes
**107 tests, no skips**, rebuilding the preceding tree and growth receipts
unchanged. Independent review: **GO**; thirteen protected hashes match.

New vector span uses two DATA pages, allocation `0x06001000+a`; retained old
vector page is `0x06002000`. Free entry checks all eight GPRs and defined flags,
including parity determined by the aligned pointer's low byte. Host source-word,
references, transfers, successful free response and retained freed bytes remain
explicit premises. No VM ownership or accounting promotion.

## Mixed existing and new second-source keys

[Documentation](native_lua_class_factory_callback_extend_conformance.md):
864 native cases start with three actual inserted destination nodes, then
supply a second source with minimum/interior/end insertions and existing
updates. First keys are 0/1/16 or 1/16/255; native final unions contain at most
eight nodes. Existing pointers and omitted key16 payloads survive; second
query strings use disjoint 1d storage while retained nodes keep 1c pointers.
New node requests use DATA+0x41f with 32-byte spacing; the shared prefix's
existing fixture base now controls its allocation schedule, default unchanged.
Unused candidates may overlap existing nodes when no allocation occurs.

Canonical SHA `c0cc89b3af1cecb03d752cf7e17fde6c621631bcbb43046475124609bd589797`;
file SHA `c1997e061f2f161538ec5dc953a185a251585b6affff078115e3c1a701c447e8`;
590,914 bytes, 32 pins. Selected/executed sites: 1,115/881, 2,905 unique bytes.
First calls retain the predecessor's three-node 701-site family; second calls
execute 864 sites. Partition: 76 callback, 707 class, 27 marker, 71 table,
234 excluded. Totals include 2,052 new second nodes, 756 existing updates,
2,808 second source copies, 4,644 final nodes, and 864 old-vector frees.
All 40 controls reject, including coordinated capture digest/node mutations.
The guard independently rechecks actual first GPRs, U/P/vector/tree/key bytes
before host binding, in addition to native full-return capture identity.

The complete gate passes **453 tests, no skips** (317 model, 81 new
conformance, 55 predecessor repeat conformance), including byte-identical new
build/exact verify and predecessor repeat rebuild/verify. Independent review:
**GO**; all thirteen protected hashes match. Logical model supports a union
of fourteen, separately from the native eight-node bound. Source/VM/allocator
premises remain explicit; no ownership or accounting promotion.

## Third callback on retained actual receiver

[Documentation](native_lua_class_factory_callback_third_conformance.md):
216 native cases retain actual first and mixed second return pages and GPRs,
then invoke a third callback with unchanged second-source topology and changed
payloads. All existing tree IDs, links and key pointers survive; omitted key16
is untouched. The full two-record vector grows to capacity three: allocate24,
copy16, free the old16 allocation, append the third record and return normally.

Canonical SHA `2e12f3b7af5475178f0660fbdab0aae7a7478fc684d1ad8f68e8bec7a96a7832`;
file SHA `f3da47c838db5835c969359dda92143c02bf79179117d98f26330911070e3cbf`;
348,679 bytes, 33 pins. Site unions first/second/third: 701/864/546;
combined 881 of 1,115 selected sites and 2,905 unique bytes. There are
648 callback invocations, 1,512 third payload updates, zero third tree
allocations, 432 frees, and 37 rejecting controls. Refreshed capture hashes
cannot bypass independent retained GPR, U/P/vector/tree/key checks.

The third allocation is DATA+0x800+a with new_page_count=1 and old_base
DATA+0x1000. Original freed first8 and second16 remain explicit retained-byte
premises. Heap ABI checks now derive capacity k=max(n+1,n+n//2), request8k,
EDI=n, EBX=0x1fffffff-n//2 and TEST(request,request) parity flags; free
entry/response EBX=n. Other free GPR/frame/flag laws retain their sealed form.
The complete gate passes **380 tests, no skips**: model208, new conformance91
and predecessor mixed-key81. New native build/exact verification and unchanged
predecessor rebuild/verification pass. Independent reviews: **GO**; all thirteen
protected hashes match. No ownership or accounting promotion.

## Fourth callback on retained actual receiver

[Documentation](native_lua_class_factory_callback_fourth_conformance.md):
216 native cases retain all three preceding verified returns, preserve the
eight destination nodes and original key pointers, then allocate32/copy24/
freeold24 and append the fourth [0,A] record. All P24 and thirteen preserved
U words survive. The capture guard independently checks GPRs, U/P/tree
including padding14/15, key bytes, all three prior vectors, FS/cookie,
untouched captured page3 and the exact prior free packet before host binding.
Fourth V=DATA+0x3800+a, new_base DATA+0x3000/new_page_count1, old_base DATA.
The fixed free error-page snapshot comes from retained old page0, after the
named existing-key payload updates. Optional mapping bases preserve defaults.

Canonical SHA `3b0727908ddef36b171733a0c686e0ad2dbe1a08ac3e7937834cd9158feced5a`;
file SHA `0261f2a79114245ef8b96cc7d8597d0ebacd6c5cf6eee9adc5c4212ff4b6432e`;
359,299 bytes, 34 pins. Site sets first/second/third/fourth: 701/864/546/548;
combined 881/1,115 sites and 2,905 bytes, partition76/707/27/71/234.
There are 864 callbacks, 537,840 fourth instructions, 35,424 callback Lua
requests, 1,512 fourth payload updates, zero fourth tree allocations,
648 frees and 37 rejecting controls. Independent final receipt review: GO.
The complete gate passes **523 tests, no skips**: model214, new conformance116,
third-call predecessor91 and default allocation/resize/growth102. New native
build/exact verification and unchanged predecessor/default rebuilds pass.
Independent reviews are GO; all thirteen protected hashes match.

## SIMD frontier after the fourth call

Fifth growth is full4/cap4 to cap6: allocate48/copy32/freeold32, append to
size5/cap6. Sixth append would use the spare slot without allocation/free.
Those factory compositions remain unproved. Retained feature DWORD
0x00893f30=0x93939393 selects the already sealed short MOVDQU copy path;
feature-zero scalar resize/growth receipts do not establish that case.
Use existing short SIMD semantics/replay pins, carry all eight XMM registers
and clear DF, and check the pinned emulator's ordered two8-byte halves per
16-byte architectural access. Widening a size bound alone is insufficient.

A reusable installed-storage SIMD copy oracle/runner and focused tests are
integrated with independent GO. The relocation suite passes208 tests, including
the unchanged sealed4992-case forward receipt build/exact verification; the
original SIMD suite passes70 including four exact CLI rebuilds. Native tests
use isolated subprocesses. The standalone full4/request6 SIMD resize ingredient
is now sealed: see [documentation](native_simd_vector_resize_conformance.md).
It passes105 focused tests and102 default predecessor regressions, no skips,
including native24-case rebuild/exact verification, all five intended controls
and all three CLI commands. Independent draft/final reviews are GO.
Canonical SHA553ca197fff9214a2dba573c44174d3407acc804dcda6b9cf73352a0964f05c7;
file SHA15a234c49c848d613e398f73b7c401e9706f8d1b7c871f8338169a77811f93ce;
53,994 bytes,9pins,274 loaded/165 executed sites,730 loaded bytes.
Neither is an actual fifth factory callback or an accounting
promotion. Candidate fifth vector placement is DATA+0x2800+a in captured
page2, preserving the original first8 at DATA+0x2000+a and old fourth32
at DATA+0x3800+a. Subsequent source/VM/heap/ownership premises stay explicit.

## Environment and protected work

Exact PE: `B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe`.
SHA: `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Python 3.13, private Capstone 5.0.7 and Unicorn 2.1.4:

```powershell
$env:PYTHONPATH='.local_decompile/fill_runtime;.'
$env:ITB_EXACT_EXE='B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe'
```

Native tools/tests run serially in isolated subprocesses. Publish only normalized
RVA/size/hash witnesses, synthetic facts and digests. Exact executable and raw
analysis remain private. Sealed publication uses exclusive create and UTF-8 LF.

Protected work remains the thirteen hashes in
`.local_decompile/sep30/protected_work.json`: achievements, weapon penalties,
default log, resist/failure recordings, active session, loop commands,
lightning-war test, four board/solve/threat JSON files and smoke-run notes.
Never stage/reset/revert them. No live game actions were taken.
