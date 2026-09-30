# September 30 decompilation checkpoints

The authorized working branch is `codex/full-decompile`, explicitly selected
by the user despite the general main-only policy. The time-bound request is
to continue useful validated work until **September 30, 2026, 5 pm
America/Chicago = 22:00 UTC**. Stop new work then, finish current validation
safely, push the final checkpoint, verify protected files and pause the
`decompile-until-5-pm` continuation heartbeat. The full game remains unfinished.

## Pushed checkpoints

| Commit | Completed tranche |
|---|---|
| `07d24a0c` | AGENTS.md now tells subagents to inherit the primary model, with no explicit model override. |
| `2ca21ff3` | Actual callback local record and incoming registers mapped to class prefix/external-spare return. |
| `de119fa2` | Shared 13 Lua import targets, heap allocation target and three literal pages for marker/table composition. |
| `60ebc3fb` | Independent callback logical class operation and continuous Lua registry/table request model. |
| `30ec0e1e` | Sealed one-machine external-spare callback, markers, class operation and both table transfers. |
| `5344217e` | Actual callback record mapped through first-null vector allocation and small old-vector growth/copy/free. |
| `c4c934b4` | Sealed continuous callback through first-null and small old-full vector growth. |
| `f5b5186e` | Sealed normal factory prefix through its actual initializer handoff. |

The earlier [September 11 handoff](decompile_handoff_2026_09_11.md) records the
existing standalone tree, balancing, insertion, vector, marker and table proofs.
Do not repeat those tranches or promote whole-program accounting from these
finite proofs.

## Continuous external-spare callback

[Documentation](native_lua_class_callback_conformance.md) and
[receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_callback_conformance.json):

- Canonical SHA: `e4bc62a4677e0bf190d861cc1749fc0346ee048c8cb39d112ed2c4a36f151cfa`.
- File SHA: `3ed08f6a7a82749ff1e87b01893849e320844f0a207dc4d0862d8be4609c9218`.
- 1,152 cases; 874 selected sites; 778 executed sites; 2,280 unique selected bytes.
- 1,611,648 native instructions; 43,008 supplied API calls; 1,584 tree allocations.
- Ten exact controls; independent GO; 198 focused tests passed, no skips,
  including byte-identical exact CLI rebuild.

All native helpers execute continuously in one Unicorn machine, receiving the
actual current memory/register state. The runtime API interpreter carries one
Lua token stack and retains four registry identities before returning zero
results. The independent model checks class transfer, original record append,
copied source word, filtered assignments, parent-owned cells and ancestors.
Imported Lua and heap APIs remain explicit supplied normal contracts. This
does not establish real VM/table/metamethod behavior or arbitrary domains.

The stack-local class record is above both finite vector ranges. Exactly three
sites from the legacy-record class receipt cannot execute here:
`0x002eb1c5`, `0x002eb1c8`, `0x002eb1ca`. Every other inherited class site,
every table site and every normal callback site is required. The record
argument is derived from current child initial pages at S+4; no separate
argument metadata should be invented.

## Completed growth caller mapping

[Documentation](native_lua_class_growth_record_caller_mapping.md):
first-null and old-full helpers accept the checked local `[0,SOURCE_OBJECT]`
at S+28, callback GPRs and real `2ec1bd` continuation. Models preserve original
caller bytes and record words through growth, native copy and supplied free.
Validation: 147 passing tests, no skips, 48 native caller successes and four
exact controls. Original 576-case first-null and 1,536-case old-growth receipts
rebuilt byte for byte. Original pure suites also passed 43 tests with two skips;
those native tests ran separately as part of the complete validation.

## Completed continuous growth callback

[Documentation](native_lua_class_callback_growth_conformance.md) and
[receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_callback_growth_conformance.json):

- Canonical SHA: `59a2123f649633045e35102d2900cf936048f7252095152a27cee6774d60d443`.
- File SHA: `b0fb268b5e364c807fd3b62ae5f6716aa137665ba0c24cfd99a01d8d4cd7c723`.
- 2,304 cases, split equally between first-null and old-full vector families.
- 945 executed sites; 1,115 selected sites; 2,905 unique selected bytes.
- 3,636,288 native instructions; 86,016 supplied API calls; 5,472 allocations;
  1,152 frees; 2,304 logical assignment requests.
- All 26 exact controls passed; independent GO; 428 focused tests passed with
  no skips, including the byte-identical exact CLI rebuild.
- Original external-spare receipt remained byte-identical across its 33-test
  suite after the common runtime machinery changed.

The opt-in logical model accepts external full live sizes zero through three.
Each family executes its actual native class helper continuously with the
callback and table transfers. Supplied heap calls are distinguished by exact
native continuations and checked requests. Larger vectors, internal storage,
error paths and real VM behavior remain outside this finite proof.

## Completed normal factory prefix

[Documentation](native_lua_class_factory_prefix_conformance.md): 216 cases,
83 selected sites, 71 executed sites and 231 selected bytes. Exact execution
covered 56,952 native instructions and 1,512 supplied API calls. All 15 controls
were rejected for their specified reasons. Model and conformance validation
passed 102 tests with no skips, including the byte-identical exact CLI rebuild.
Canonical SHA: `cebf742aac9945f22829e2d3b1b387ff618840217b3c9a2330a8335ca3a0d0ed`.
File SHA: `dc56cc73bf36a0f1e642638f5d5f1b7ad80f7121f45dde197f0256f642bd9955`.

## Completed initializer prefix composition

[Documentation](native_lua_class_factory_initializer_prefix_conformance.md):
216 continuous factory/initializer cases, 120 selected sites, 108 executed
sites and 391 selected bytes. Native execution covered 64,944 instructions,
including 7,992 initializer instructions, and 1,512 supplied Lua API calls.
All 22 controls passed; independent GO; 67 new focused tests passed with no
skips, including the byte-identical exact CLI rebuild. A preceding 124-test
gate also proved the original factory receipt remains byte-identical.
Canonical SHA: `abd888a364076edd037f460a0515b9586610218f9e5437aa4f67ab0cd972c47e`.
File SHA: `9f64ec4a0124e1ad7f52cda34c7faaa949e924484df55e9a8f40c24ab23e827f`.
The 14 fixed word writes, four untouched words, second pointer at userdata
offset 16, nested FS chain and overwritten argument cell are checked. The
machine stops at `0x0007c600` before the helper's first instruction.

## Active continuation

The normal factory prefix now reaches initializer entry `0x002eacf0`.
Its seven Lua API calls remain supplied contracts. The first
`lua_tolstring` pointer is measured by the inline NUL loop; the second pointer
is passed to the initializer. Preserve independent pointer routing rather
than assuming the pointers or bytes are equal. Error arms and null-userdata
bypass are separate boundaries. No initializer, ownership or exception-handling
claim follows from that first handoff alone. Its following 37 initializer
instructions are now checked by the separate composition above. Next useful
continuation: execute the self-linked record helper `0x0007c600`, native retry
wrapper, thunk and heap wrapper continuously, supplying only one successful
HeapAlloc response. Check all record bytes and its actual store at userdata
offset 52 before tackling later initializer Lua calls.

## Environment and preservation

Exact PE: `B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe`.
SHA-256: `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Native runtime uses Python 3.13, private Capstone 5.0.7 and Unicorn 2.1.4:

```powershell
$env:PYTHONPATH='.local_decompile/fill_runtime;.'
$env:ITB_EXACT_EXE='B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe'
```

Native execution belongs in isolated subprocesses and tests run serially.
Publish only safe normalized instruction witnesses, synthetic vectors, facts
and digests. The executable and raw inspection files remain private. Sealed
receipts use deterministic UTF-8 LF and exclusive publication after checking
canonical and file identity.

Protected original dirty work: achievements, weapon penalties, default log,
resist/failure recordings, active session, loop commands, lightning-war test,
four default board/solve/threat JSONs and smoke-run notes. Thirteen baseline
file hashes live privately at `.local_decompile/sep30/protected_work.json`.
They were verified unchanged after callback sealing. Never stage, reset or
revert this work. No live game actions were taken for these decompilation
tranches. The user asked to stop using expensive Astra agents; the remaining
older reviewer was stopped and subsequent subagents were freshly spawned
with inherited model settings and no Astra override.
