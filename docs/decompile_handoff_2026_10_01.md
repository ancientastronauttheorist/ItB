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

The next useful frontier is a nonempty source under the actual initially empty
produced receiver. First design disjoint key storage: legacy source keys at
`0x15000000` overlap the factory's second-name page. Keep named source-node/key
patches explicit and preserve all other captured bytes. Consume the actual
allocated sentinel, retain native insertion/balancing/successor machinery and
first-null vector growth, and update preservation claims for count/sentinel
links actually changed by insertion. Source object, class word and two registry
references remain supplied host premises unless separately joined to a producer.
Existing tree/spare/growth/table proofs are independent sources; their generated
fixture pages cannot replace actual producer state.

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
