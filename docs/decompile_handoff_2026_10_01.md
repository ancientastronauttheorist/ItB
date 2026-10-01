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

## Next useful frontier

Mix existing and new second-source keys on the captured actual receiver. Keep
original key strings at `0x1c000fff` intact for retained destination pointers;
relocate second query strings to `0x1d000fff`. Start with three first-source
nodes using canonical or positive keys; exercise interior, minimum, end and
existing searches with second sources of at most seven nodes. The planned native
union bound is eight; the independent pure extension model supports fourteen.

Use the fixture's existing node-allocation base rather than a global address
constant. First nodes occupy DATA+0x100; proposed new nodes start DATA+0x400,
with 32-byte spacing, disjoint from retained nodes and vector DATA+0x1000.
Validate stable existing IDs, omitted payloads and original key pointers,
updated sentinel links/count, separate tree/vector heap boundaries and free.
The extension model and 317 tests are working files awaiting runtime validation
and independent review; no mixed-source native claim is sealed yet.

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
